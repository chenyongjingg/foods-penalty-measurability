"""Freeze the corpus and build the final release bundle (D-71).

This is the last step of the pipeline, and it is deliberately one command:
re-derive every product from the frozen corpus, verify the products, build the
bundle, and verify the bundle. Nothing here decides a number; it only refuses
to publish when the preconditions for a reproducible snapshot do not hold, and
it records the evidence in a receipt either way.

Preconditions, each checked and written into `data/reports/finalize_<stamp>.json`:

1. every stage returns rc=0 -- `retier extract analyze report`, run through
   `scripts/chain_locked.py` so it cannot overlap the daemon's own cycle;
2. `data/silver/silver.jsonl` has the same sha256 before and after the run.
   A changed sha means documents arrived mid-run and the bundle would mix two
   snapshots under one name;
3. `scripts/verify_products.py` exits 0 with **0 failed and 0 stale** checks.
   `stale_vs_silver` is exactly the case "this metric describes an older
   corpus" (D-68), which is the failure this step exists to prevent;
4. the bundle's own `MANIFEST.sha256` verifies with `sha256sum -c` -- every
   listed file, not a sample.

Usage:
    python scripts/finalize_release.py --stamp 20261105 [--dry-run] [--out DIR]

`--dry-run` stops before `export_release.py`: it still runs the stages, the
metric rebuilds and `verify_products`, so the whole path is exercised without
creating a bundle. Exit 0 means "the bundle exists and verifies" (or, for
--dry-run, "every precondition short of the export holds").
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
SILVER = ROOT / "data" / "silver" / "silver.jsonl"


def utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def run(cmd: list[str], timeout: int = 6 * 3600) -> dict:
    t0 = datetime.now(timezone.utc)
    proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True,
                          timeout=timeout)
    return {"cmd": " ".join(cmd), "rc": proc.returncode,
            "seconds": round((datetime.now(timezone.utc) - t0).total_seconds(), 1),
            "stdout_tail": (proc.stdout or "")[-4000:],
            "stderr_tail": (proc.stderr or "")[-2000:]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stamp", default=datetime.now(timezone.utc).strftime("%Y%m%d"))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    receipt: dict = {"at_utc": utc(), "stamp": args.stamp,
                     "dry_run": args.dry_run, "steps": [], "checks": {},
                     "status": "unknown"}
    rec_dir = ROOT / "data" / "reports"
    rec_dir.mkdir(parents=True, exist_ok=True)
    rec_path = rec_dir / f"finalize_{args.stamp}.json"

    def finish(status: str, code: int) -> int:
        receipt["status"] = status
        receipt["finished_utc"] = utc()
        rec_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=1),
                            encoding="utf-8")
        print(json.dumps({k: receipt[k] for k in
                          ("status", "stamp", "dry_run", "checks", "finished_utc")},
                         ensure_ascii=False))
        return code

    if not SILVER.exists():
        receipt["checks"]["silver_present"] = False
        return finish("no_silver", 3)

    sha_before = sha256(SILVER)
    receipt["checks"]["silver_sha_before"] = sha_before

    # 1. stages, under the same lock the daemon uses
    stage = run([PY, "scripts/chain_locked.py", "retier", "extract",
                 "analyze", "report"])
    receipt["steps"].append(stage)
    if stage["rc"] != 0:
        return finish("stage_failed", 4)

    sha_after = sha256(SILVER)
    receipt["checks"]["silver_sha_after"] = sha_after
    if sha_after != sha_before:
        receipt["checks"]["corpus_drift"] = True
        return finish("corpus_drift", 5)

    # 2. products that are not produced by the stages. Order matters: E8 reads
    # E6's distribution, and E6's negative control needs the LLM server up.
    # E6-E8 are v7 plan Results 1-3 (D-72/D-74/D-75); a failure here stops the
    # bundle rather than shipping a release whose paper tables have no product.
    for script in ("scripts/e1_preladder.py", "scripts/tier_shrunk.py",
                   "scripts/query_family_agreement.py",
                   "scripts/e6_descriptive.py", "scripts/e7_typology.py",
                   "scripts/e8_us_cn.py"):
        step = run([PY, script], timeout=1800)
        receipt["steps"].append(step)
        if step["rc"] != 0:
            return finish(f"failed:{Path(script).name}", 6)

    # 3. product verification -- 0 failed AND 0 stale
    ver = run([PY, "scripts/verify_products.py"], timeout=1800)
    receipt["steps"].append(ver)
    vjson = json.loads((ROOT / "data" / "metrics" / "verify_products.json")
                       .read_text(encoding="utf-8"))
    receipt["checks"]["verify_products"] = {
        "n_checks": vjson.get("n_checks"), "n_failed": vjson.get("n_failed"),
        "n_stale": vjson.get("n_stale"), "status": vjson.get("status"),
        "silver": (vjson.get("silver") or {}).get("sha256")}
    if ver["rc"] != 0 or vjson.get("n_failed") or vjson.get("n_stale"):
        return finish("verify_failed", 7)

    if args.dry_run:
        receipt["checks"]["would_build"] = args.out or \
            f"release/foods_silver_{args.stamp}"
        return finish("dry_run_ok", 0)

    # 4. the bundle, then verify the bundle
    cmd = [PY, "scripts/export_release.py"]
    if args.out:
        cmd += ["--out", args.out]
    exp = run(cmd, timeout=3600)
    receipt["steps"].append(exp)
    if exp["rc"] != 0:
        return finish("export_failed", 8)
    bundle = None
    for line in reversed((exp["stdout_tail"] or "").splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                bundle = json.loads(line).get("out")
            except Exception:  # noqa: BLE001
                pass
            break
    if not bundle:
        return finish("export_unparsed", 9)

    bdir = Path(bundle)
    manifest = bdir / "MANIFEST.sha256"
    if not manifest.exists():
        return finish("manifest_missing", 10)
    chk = subprocess.run(["sha256sum", "-c", "MANIFEST.sha256"], cwd=str(bdir),
                         capture_output=True, text=True)
    ok = len(re.findall(r": OK$", chk.stdout, re.M))
    bad = len(re.findall(r"FAILED", chk.stdout))
    receipt["checks"]["bundle"] = {"path": str(bdir), "sha_ok": ok,
                                   "sha_failed": bad,
                                   "n_listed": len(manifest.read_text().splitlines()),
                                   "silver_in_bundle": sha256(bdir / "data" / "silver.jsonl")}
    # the bundle must carry the very corpus we froze, not a copy taken earlier
    if bad or ok != receipt["checks"]["bundle"]["n_listed"] \
            or receipt["checks"]["bundle"]["silver_in_bundle"] != sha_before:
        return finish("bundle_verify_failed", 11)

    receipt["checks"]["corpus_frozen_at"] = sha_before
    return finish("released", 0)


if __name__ == "__main__":
    raise SystemExit(main())

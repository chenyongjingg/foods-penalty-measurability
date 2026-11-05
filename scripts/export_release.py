"""Build the open-data release bundle (Plan P115: "代码与银标准数据集开放").

What ships and what does not:

* ships  — `data/silver/silver.jsonl` (labels, anchors, per-document metrics,
  tier), `data/extracted/dataset.jsonl` (entity rows over PII-masked text),
  `metrics/` (the gate and estimate JSONs the paper quotes, so each number is
  checkable without re-running the pipeline), the config directory, the code
  tree, and a MANIFEST with a sha256 per file;
* does not ship — raw HTML/PDF, the clean text files, the SQLite manifest, and
  anything under `state/` or `logs/`. Raw documents are third-party government
  publications; the release points at their URLs (stored in the manifest, not
  in silver) instead of redistributing them.

Every file in the bundle is listed in `MANIFEST.tsv` with its byte size and
sha256, and the bundle's own `MANIFEST.sha256` is written last, so a reader can
verify the whole thing with one command:

    sha256sum -c MANIFEST.sha256

Usage: python scripts/export_release.py [--out DIR]
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from foods_pipeline.common import path_of  # noqa: E402

CODE_DIRS = ["foods_pipeline", "scripts", "config", "tests"]
CODE_FILES = ["README.md", "DEVIATIONS.md", "DECISIONS.md", "Makefile", "requirements.txt"]


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _counts(p: Path) -> dict:
    n = 0
    tiers: dict[str, int] = {}
    with open(p, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            n += 1
            try:
                t = json.loads(line).get("tier")
            except Exception:
                continue
            if t:
                tiers[t] = tiers.get(t, 0) + 1
    return {"rows": n, "tiers": tiers}


def main() -> int:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    out = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv else \
        path_of("reports").parent / "release" / f"foods_silver_{stamp}"
    if out.exists():
        raise SystemExit(f"REFUSED: {out} exists; remove it or pass --out")
    out.mkdir(parents=True)

    # 1. data
    (out / "data").mkdir()
    silver = path_of("data") / "silver" / "silver.jsonl"
    dataset = path_of("data") / "extracted" / "dataset.jsonl"
    copied = []
    for src, name in ((silver, "silver.jsonl"), (dataset, "dataset.jsonl")):
        if not src.exists():
            print(f"skip missing {src}")
            continue
        shutil.copy2(src, out / "data" / name)
        copied.append(out / "data" / name)

    # 2. derived metrics: every number the paper quotes has to be checkable from
    # the bundle without re-running the pipeline. They are products of this same
    # snapshot -- scripts/verify_products.py must pass (0 stale) before the build,
    # because `stale_vs_silver` is exactly the case where a metric is older than
    # the corpus it claims to describe (D-68).
    metrics = out / "metrics"
    metrics.mkdir()
    METRIC_SRC = [path_of("data") / "metrics" / n for n in (
        "e1.json", "e1_preladder.json", "tier_shrunk.json",
        "query_family_agreement.json", "ladder.json", "ladder_entity_rule.json",
        "stability_v2.json", "verify_products.json")] + [
        path_of("data") / "analysis" / n for n in (
        "gates.json", "network_metrics.json", "compare.json", "displacement.json",
        "attack_tolerance.json", "survival.json", "hawkes.json", "shocks.json",
        "sensitivity.json", "keywords.json", "keyword_sensitivity.json",
        # v7 plan E6-E8: every Results table's source product, so the reader can
        # check Results 1-3 from the bundle without re-running the pipeline.
        "e6_descriptive.json", "e7_typology.json", "e8_us_cn.json")]
    shipped = []
    for src in METRIC_SRC:
        if not src.exists():
            continue
        # `_module_status.json` is a per-cycle receipt, not a result: it stays out.
        shutil.copy2(src, metrics / src.name)
        shipped.append(src.name)

    # 3. code + config as a tarball (keeps the tree reproducible)
    code_tar = out / "foods_code.tar.gz"
    with tarfile.open(code_tar, "w:gz") as tf:
        for d in CODE_DIRS:
            p = ROOT / d
            if p.exists():
                tf.add(p, arcname=d, filter=lambda ti: None if "__pycache__" in
                       ti.name else ti)
        for f in CODE_FILES:
            p = ROOT / f
            if p.exists():
                tf.add(p, arcname=f)

    # 4. release note (written before the manifest so the manifest covers it)
    meta = {
        "built_utc": datetime.now(timezone.utc).strftime("%FT%TZ"),
        "corpus": {p.name: _counts(p) for p in copied},
        "metrics_shipped": sorted(shipped),
        "e1_reported_twice": {
            "pre_registered_single_shot": "metrics/e1_preladder.json",
            "post_ladder_mixture": "metrics/e1.json",
            "note": ("Two estimates, never interchangeable: the pre-registered "
                     "single-shot E1 is the paper's figure; the e1.json headline "
                     "pools voted and single-shot documents (D-63/D-68)."),
        },
        # v7 plan Results 1-3. Their population differs from E1's on purpose:
        # E6/E7 use the Chinese frame (high tier for E7), E8 compares that frame
        # with openFDA recalls. The population of each table is written inside
        # the product, not inferred here.
        "paper_results": {
            "Results 1": "metrics/e6_descriptive.json",
            "Results 2": "metrics/e7_typology.json",
            "Results 3": "metrics/e8_us_cn.json",
        },
        "excludes": ["raw documents (third-party government publications)",
                     "clean text (reconstructible from raw)", "state/ (manifest sqlite)",
                     "logs/", "model weights"],
        "verify": "sha256sum -c MANIFEST.sha256",
    }
    (out / "RELEASE.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1),
                                      encoding="utf-8")

    # 4. manifest
    rows = []
    for p in sorted(out.rglob("*")):
        if p.is_file() and p.name not in ("MANIFEST.tsv", "MANIFEST.sha256"):
            rows.append(f"{p.relative_to(out)}\t{p.stat().st_size}\t{sha256(p)}")
    (out / "MANIFEST.tsv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    (out / "MANIFEST.sha256").write_text(
        "\n".join(f"{r.split(chr(9))[2]}  {r.split(chr(9))[0]}" for r in rows) + "\n",
        encoding="utf-8")

    print(json.dumps({"out": str(out), "files": len(rows),
                      "corpus": meta["corpus"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

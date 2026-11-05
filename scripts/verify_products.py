"""Check that the audit's acceptance keys are actually present in the products.

Every check names the file, the key path, and why it matters. A missing key is
a FAIL with the file's mtime and sha, because the failure mode this guards
against is not "the file is absent" but "the file is present and the key was
never written" (D-52: network_metrics.json existed, graphml key did not).

Also reports staleness: a product older than silver.jsonl cannot be a statement
about the current corpus, however complete its keys are.

Usage: ./venv/bin/python scripts/verify_products.py [--json]
Exit code 0 = all checks pass, 1 = at least one FAIL.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
AN = DATA / "analysis"
MET = DATA / "metrics"


def _load(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _get(obj, path: str):
    cur = obj
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def _info(p: Path) -> dict:
    if not p.exists():
        return {"exists": False}
    raw = p.read_bytes()
    return {"exists": True, "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "mtime_utc": datetime.fromtimestamp(p.stat().st_mtime, timezone.utc)
                                  .strftime("%Y-%m-%dT%H:%M:%SZ")}


def _latest(pattern: str) -> Path | None:
    files = sorted(MET.glob(pattern))
    return files[-1] if files else None


def main() -> int:
    silver = DATA / "silver" / "silver.jsonl"
    silver_info = _info(silver)
    silver_mtime = silver.stat().st_mtime if silver.exists() else 0

    checks = []

    def check(name: str, path: Path | None, key: str | None, why: str,
              required: bool = True, extra=None):
        info = _info(path) if path else {"exists": False}
        value = None
        if info["exists"] and key:
            value = _get(_load(path), key)
        ok = info["exists"] and (key is None or value is not None)
        if extra is not None and ok:
            ok = bool(extra(value))
        stale = bool(info.get("exists") and info.get("mtime_utc")
                     and silver_mtime and path.stat().st_mtime < silver_mtime - 5)
        checks.append({"check": name, "file": str(path) if path else None,
                       "key": key, "ok": ok, "required": required,
                       "value": value if not isinstance(value, (dict, list)) else
                                (list(value)[:8] if isinstance(value, dict) else f"{len(value)} items"),
                       "stale_vs_silver": stale, "why": why, **info})

    e1 = MET / "e1.json"
    check("e1 scored denominator", e1, "n_scored_agreement", "D-43: agreement denominator")
    check("e1 zero-entity count", e1, "n_zero_entities", "D-43: documents with no entity")
    check("e1 malformed count", e1, "align_ground_malformed", "D-45: dropped model output")
    check("e1 ladder decision", e1, "ladder.triggered", "P095: ladder is recorded, not folded into status")
    check("e1 shrunk agreement", e1, "mean_agreement_shrunk", "P095: type-shrunk figure")
    check("e1 status full-type", e1, "status", "D-53: E1 stays graded on the full type set")
    check("e1 decoding mix", e1, "decoding_mix", "D-63: headline E1 pools two regimes")
    pre = MET / "e1_preladder.json"
    check("pre-registered E1", pre, "e1.mean_agreement",
          "D-68: single-shot estimate reconstructed from the archives")

    anchor = _latest("anchor_*.json")
    check("anchor basis counts", anchor, "basis_counts", "D-43: anchor basis before/after")
    check("anchor F1 stale guard", anchor, "f1_exact_stale_docs", "D-55: exact-F1 cache vs channels")

    cmpj = AN / "compare.json"
    check("compare estimability", cmpj, "main_corpus_estimable", "D-51: degenerate main corpus")
    check("compare selection diagnostic", cmpj, "selection_diagnostic", "D-49: tier is genre-selected")
    check("compare profile", cmpj, "main_corpus_profile", "D-51: modal-category profile")
    cmp_obj = _load(cmpj) or {}
    has_test = _get(cmp_obj, "primary_test") is not None or \
        _get(cmp_obj, "test_on_degenerate_table.primary_test") is not None
    checks.append({"check": "compare test of record", "file": str(cmpj),
                   "key": "primary_test | test_on_degenerate_table.primary_test",
                   "ok": has_test, "required": True, "value": None,
                   "stale_vs_silver": False,
                   "why": "D-43: a test must exist even when the table is degenerate"})

    nm = AN / "network_metrics.json"
    check("network graphml receipt", nm, "graphml.written", "D-52: export must be recorded")
    check("network actor coverage", nm, "actor_coverage.docs_with_two_or_more_actor_nodes",
          "D-54: edges bounded by documents naming two distinct actors")
    check("network provider coverage", nm, "actor_coverage.docs_with_provider_and_end_user",
          "D-49/D-54: the edge-enabling count")
    check("network dataset staleness", nm, "stale_dataset", "a stale dataset cannot support §6")

    disp = AN / "displacement.json"
    check("displacement denominator", disp, "denominator", "D-40: events per scanned document")

    gates = AN / "gates.json"
    for g in ("E1", "E2", "E3", "E4", "E5"):
        check(f"gate {g}", gates, f"gates.{g}", "Plan §6.1: every gate must be reported")

    ms = AN / "_module_status.json"
    ms_obj = _load(ms) or {}
    no_fail = isinstance(ms_obj.get("failed_modules"), dict) and not ms_obj["failed_modules"]
    checks.append({"check": "analyze modules all ran", "file": str(ms),
                   "key": "failed_modules == {}",
                   "ok": ms.exists() and no_fail, "required": True,
                   "value": ms_obj.get("failed_modules"), "stale_vs_silver": False,
                   "why": "D-61: a crashed module leaves a stale product that the gate read"})

    ts = MET / "tier_shrunk.json"
    check("shrunk corpus variant", ts, "tier_counts.shrunk", "D-53: P095 corpus variant")
    check("shrunk corpus e1 untouched", ts, "e1_status_unchanged", "D-53: no gate gaming")
    qf = MET / "query_family_agreement.json"
    check("query-family balance", qf, "high_tier_balance", "D-48: main corpus is not query-balanced")

    # v7 plan Results 1-3 (E6-E8). The three products are checked for the key
    # that makes each table readable, and E8 is cross-checked against the very
    # corpus sha E6 used: two tables built on two different corpora under one
    # release name is the failure this guards against (D-68's pattern).
    e6 = AN / "e6_descriptive.json"
    check("E6 category distribution", e6, "category_distribution", "v7 E6: Results 1")
    check("E6 negative control", e6, "negative_control.status", "D-73: rule-vs-LLM check")
    check("E6 statute map version", e6, "map_version", "D-72: which table made the table")
    e7 = AN / "e7_typology.json"
    check("E7 dual-channel agreement", e7, "dual_channel_agreement", "v7 E7: Results 2 gate")
    check("E7 typology entries", e7, "entries", "v7 E7: the typology itself")
    check("E7 corpus size", e7, "corpus.n", "v7 E7: main corpus denominator")
    e8 = AN / "e8_us_cn.json"
    check("E8 estimability", e8, "estimability", "v7 E8: instrument-mismatch verdict")
    check("E8 test of record", e8, "test.primary_test", "v7 E8: a test must exist")
    e8_obj = _load(e8) or {}
    same_corpus = (_get(e8_obj, "cn.silver_sha256") is not None and
                   _get(e8_obj, "cn.silver_sha256") == silver_info.get("sha256"))
    checks.append({"check": "E8 built on the same corpus as E6", "file": str(e8),
                   "key": "cn.silver_sha256 == silver.sha256", "ok": same_corpus,
                   "required": True, "value": _get(e8_obj, "cn.silver_sha256"),
                   "stale_vs_silver": False,
                   "why": "two Results tables over one release must share one corpus sha"})

    failed = [c for c in checks if not c["ok"]]
    stale = [c for c in checks if c["stale_vs_silver"]]
    out = {"at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "silver": silver_info, "n_checks": len(checks),
           "n_failed": len(failed), "n_stale": len(stale),
           "status": "pass" if not failed else "fail", "checks": checks}

    if "--json" in sys.argv:
        print(json.dumps(out, ensure_ascii=False, indent=1))
    else:
        print(f"silver {silver_info.get('sha256', '?')[:16]} {silver_info.get('mtime_utc')}")
        for c in checks:
            mark = "PASS" if c["ok"] else "FAIL"
            extra = "  [stale vs silver]" if c["stale_vs_silver"] else ""
            val = f" = {c['value']}" if c["value"] is not None else ""
            print(f"  {mark} {c['check']}{val}{extra}")
        print(f"\n{len(checks) - len(failed)}/{len(checks)} pass, {len(stale)} stale")

    dst = MET / "verify_products.json"
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())

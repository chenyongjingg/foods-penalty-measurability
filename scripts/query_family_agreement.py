"""Agreement F1 and tier rate by crawl query family (D-48).

The 2026-11-04 label wave looked like it had an instrument discontinuity at
04:00Z: documents labelled before it had mean F1 0.60, after it 0.65. It was a
composition effect -- the label pool drains `iter_stage("clean")` in insertion
order, and every document from the base-crawl query families was labelled
before any document from the later families. The two sets of queries are
disjoint, so "before/after" was never comparing like with like. Ten of the
early documents re-labelled at 04:53-05:16Z under the identical protocol
reproduced their own low level (0.5558 -> 0.5234, delta -0.032, SE 0.029),
which rules out instrument drift of the observed size.

What remains is a measurement property that the paper has to carry: agreement
F1 differs systematically by query family, so the high tier -- the main
corpus -- is not query-balanced. This script writes that table to
data/metrics/query_family_agreement.json, with the input file's sha256 and the
reporting timestamp, so the claim can be re-read from the product layer rather
than from a terminal scrollback.

Usage: python scripts/query_family_agreement.py
"""
from __future__ import annotations

import hashlib
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from foods_pipeline.common import path_of, utc_iso  # noqa: E402


def f1(r: dict) -> float:
    mt = r.get("metrics") or {}
    v = mt.get("agreement_f1_exact")
    if isinstance(v, (int, float)):
        return float(v)
    return float(mt.get("agreement_f1") or 0.0)


def family(r: dict) -> str:
    q = (r.get("meta") or {}).get("query")
    if isinstance(q, list):
        return " + ".join(str(x) for x in q)
    return str(q) if q else "<none>"


def main() -> int:
    silver = path_of("data") / "silver" / "silver.jsonl"
    raw = silver.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    recs = [json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip()]

    groups: dict[str, list[dict]] = defaultdict(list)
    for r in recs:
        groups[family(r)].append(r)

    rows = []
    for fam, rs in groups.items():
        n = len(rs)
        dens = statistics.mean(
            len((r.get("channels") or {}).get("a") or []) for r in rs)
        docn = statistics.mean(
            sum(1 for e in ((r.get("channels") or {}).get("a") or [])
                if e.get("type") == "DOCUMENT") for r in rs)
        tiers = Counter(r.get("tier") for r in rs)
        rows.append({
            "query_family": fam, "n": n,
            "mean_f1": round(statistics.mean(f1(r) for r in rs), 4),
            "median_f1": round(statistics.median(f1(r) for r in rs), 4),
            "sd_f1": round(statistics.pstdev([f1(r) for r in rs]), 4),
            "mean_entities_channel_a": round(dens, 3),
            "mean_document_entities": round(docn, 3),
            "tier_counts": {k: tiers.get(k, 0) for k in ("high", "medium", "low")},
            "high_rate": round(tiers.get("high", 0) / n, 4),
            "langs": dict(Counter(r.get("lang") for r in rs)),
        })
    rows.sort(key=lambda x: (-x["n"], x["query_family"]))

    # Is the high tier query-balanced? Compare the family mix inside the high
    # tier against the family mix of the whole corpus.
    high = [r for r in recs if r.get("tier") == "high"]
    corpus_mix = Counter(family(r) for r in recs)
    high_mix = Counter(family(r) for r in high)
    balance = []
    for fam, c in corpus_mix.most_common():
        share_all = c / len(recs)
        share_high = high_mix.get(fam, 0) / len(high) if high else 0.0
        balance.append({"query_family": fam, "share_corpus": round(share_all, 4),
                        "share_high": round(share_high, 4),
                        "ratio": round(share_high / share_all, 3) if share_all else None})

    out = {
        "at_utc": utc_iso(),
        "input": str(silver),
        "input_sha256": sha,
        "n_records": len(recs),
        "n_high": len(high),
        "f1_spread_across_families": round(
            max(r["mean_f1"] for r in rows) - min(r["mean_f1"] for r in rows), 4),
        "families": rows,
        "high_tier_balance": balance,
        "note": ("High tier = main corpus. A ratio above 1 means the family is "
                 "over-represented in the main corpus relative to the full "
                 "labelled set; this is agreement-driven, not a sampling "
                 "design. Report in the paper's limitations (D-48)."),
    }
    dst = path_of("data") / "metrics" / "query_family_agreement.json"
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {dst}  families={len(rows)}  n={len(recs)}  high={len(high)}")
    for r in rows[:12]:
        print(f"  {r['query_family'][:30]:30s} n={r['n']:4d} f1={r['mean_f1']:.4f} "
              f"DOC={r['mean_document_entities']:.2f} high={r['tier_counts']['high']:3d} "
              f"({100*r['high_rate']:.0f}%)")
    print("high-tier representativeness (share_high / share_corpus):")
    for b in balance[:12]:
        print(f"  {b['query_family'][:30]:30s} corpus={100*b['share_corpus']:4.1f}% "
              f"high={100*b['share_high']:4.1f}% ratio={b['ratio']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Offline evaluation of an anchor-engine variant (read-only).

Variant B: when the penalty clause (`依据《X法》第Y条`) maps to no category,
fall back to the mapped categories of *all* cited articles, with the same
ambiguity policy. The current engine falls back to all cited articles only when
no penalty clause was found at all, so a decision whose penalty sentence cites
only an unmapped article (e.g. 行政处罚法第七十二条, the late-payment surcharge)
loses its anchor entirely.

Reported per variant: anchor coverage, basis distribution, and the resulting
high-tier count on the same records (stored agreement F1 + stored LLM category).
"""
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

ROOT = Path("/opt/foods")
sys.path.insert(0, str(ROOT))
from foods_pipeline.label import anchors  # noqa: E402

SILVER = Path(sys.argv[1] if len(sys.argv) > 1 else
              "/opt/foods/data/archive/v1_20261104T0235Z/silver.jsonl")
TARGET = 0.85


def label_variant_b(text: str) -> dict:
    cited = anchors.extract_statutes(text)
    pen = anchors.penalty_statutes(text)
    cand_pen = anchors._map_statutes(pen)
    cand_all = anchors._map_statutes(cited)
    facts = anchors.fact_categories(text)
    cand = cand_pen or cand_all
    cat, basis = None, None
    if len(cand) == 1:
        cat, basis = next(iter(cand)), ("penalty_statute" if cand_pen else "cited_statute")
    elif cand:
        chosen = [c for c in facts if c in cand]
        if len(chosen) == 1:
            cat, basis = chosen[0], "statute+fact"
        elif len(chosen) > 1:
            cat, basis = None, "ambiguous_facts"
        else:
            cat, basis = None, "ambiguous_statute"
    else:
        chosen = facts
        if len(chosen) == 1:
            cat, basis = chosen[0], "fact_only"
        elif len(chosen) > 1:
            cat, basis = None, "ambiguous_facts"
    return {"category": cat, "basis": basis}


recs = [json.loads(l) for l in open(SILVER, encoding="utf-8") if l.strip()]
zh = [r for r in recs if r.get("lang") == "zh"]
conn = sqlite3.connect(str(ROOT / "state" / "foods.sqlite"))
conn.row_factory = sqlite3.Row
texts = {}
for r in zh:
    row = conn.execute("SELECT text_path FROM docs WHERE doc_id=?", (r["doc_id"],)).fetchone()
    if row and row["text_path"] and Path(row["text_path"]).exists():
        texts[r["doc_id"]] = Path(row["text_path"]).read_text(encoding="utf-8")

out = {"silver": str(SILVER), "n_zh": len(zh), "n_with_text": len(texts), "variants": {}}
for name in ("current", "fallback_cited"):
    basis = Counter()
    high = mismatch = cover = 0
    for r in zh:
        if name == "current":
            a = r.get("anchor") or {}
            cat, b = a.get("category"), a.get("basis")
        else:
            text = texts.get(r["doc_id"])
            v = label_variant_b(text) if text else {"category": None, "basis": None}
            cat, b = v["category"], v["basis"]
        basis[b] += 1
        if cat:
            cover += 1
        f1 = (r.get("metrics") or {}).get("agreement_f1", 0) or 0
        ap = bool(cat and r["violation_category"] == cat)
        if f1 >= TARGET:
            if ap:
                high += 1
            else:
                mismatch += 1
    out["variants"][name] = {"coverage": cover,
                             "coverage_rate": round(cover / max(1, len(zh)), 4),
                             "basis": dict(basis), "high_if_retiered": high,
                             "anchor_mismatch_at_085": mismatch}
print(json.dumps(out, ensure_ascii=False, indent=1))

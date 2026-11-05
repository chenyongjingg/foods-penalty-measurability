#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read-only: summarize anchor vs LLM category mismatches in silver.jsonl.

Prints (a) confusion counts, (b) basis mix among mismatches, (c) up to N
example documents with the matched fact phrase and the statute list, so a
human can judge whether the anchor mapping or the LLM is wrong.
"""
import json, sys
from collections import Counter

P = "/opt/foods/data/silver/silver.jsonl"
N = int(sys.argv[1]) if len(sys.argv) > 1 else 8

rows = []
for line in open(P, encoding="utf-8"):
    line = line.strip()
    if not line:
        continue
    try:
        rows.append(json.loads(line))
    except Exception:
        continue

pairs = Counter()
basis_mis = Counter()
basis_all = Counter()
examples = []
for r in rows:
    a = r.get("anchor") or {}
    cat = a.get("category")
    b = a.get("basis") or "none"
    basis_all[b] += 1
    if not cat:
        continue
    llm = r.get("violation_category")
    ok = llm == cat
    pairs[(cat, llm, ok)] += 1
    if not ok:
        basis_mis[b] += 1
        if len(examples) < N:
            examples.append({"doc": r.get("doc_id"), "llm": llm, "anchor": cat,
                             "basis": b, "facts": a.get("facts"),
                             "statutes": (a.get("statutes") or [])[:6],
                             "pen": (a.get("penalty_statutes") or [])[:4],
                             "tier": r.get("tier")})

print("docs with anchor:", sum(v for (c, l, ok), v in pairs.items()))
print("agree:", sum(v for (c, l, ok), v in pairs.items() if ok),
      "disagree:", sum(v for (c, l, ok), v in pairs.items() if not ok))
print("basis all:", dict(basis_all))
print("basis among mismatches:", dict(basis_mis))
print("top confusions (anchor -> llm, n):")
for (c, l, ok), v in pairs.most_common(12):
    print(f"  {c:26s} -> {str(l):26s} {'OK ' if ok else 'BAD'} {v}")
print("examples:")
for e in examples:
    print(json.dumps(e, ensure_ascii=False))

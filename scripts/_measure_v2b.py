#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Second read-only measurement: where does the anchor go missing?"""
import json
import re
import sqlite3
import sys
from collections import Counter
from pathlib import Path

ROOT = Path("/opt/foods")
sys.path.insert(0, str(ROOT))
from foods_pipeline.label import anchors  # noqa: E402

conn = sqlite3.connect(str(ROOT / "state" / "foods.sqlite"))
conn.row_factory = sqlite3.Row
sil = []
with open(ROOT / "data" / "silver" / "silver.jsonl", encoding="utf-8") as f:
    for line in f:
        if line.strip():
            sil.append(json.loads(line))

CIT = re.compile(r"第[一二三四五六七八九十百零〇\d]+条")
PEN = re.compile(r"(?:依据|根据)")
res = {"n_silver": len(sil)}
# where do citations live?
pos_pen, pos_cit, lens, after6000, no_cit, no_pen_anywhere = [], [], [], 0, 0, 0
for r in sil:
    d = conn.execute("SELECT text_path FROM docs WHERE doc_id=?", (r["doc_id"],)).fetchone()
    if not d or not d["text_path"]:
        continue
    text = Path(d["text_path"]).read_text(encoding="utf-8")
    lens.append(len(text))
    m = PEN.search(text)
    if m:
        pos_pen.append(m.start())
    else:
        no_pen_anywhere += 1
    c = list(CIT.finditer(text))
    if c:
        pos_cit.append(c[-1].start())
        if c[-1].start() >= 6000:
            after6000 += 1
    else:
        no_cit += 1

def hist(xs):
    return {k: sum(1 for x in xs if lo <= x < hi) for k, (lo, hi) in {
        "0-2k": (0, 2000), "2k-4k": (2000, 4000), "4k-6k": (4000, 6000),
        "6k-10k": (6000, 10000), "10k+": (10000, 10 ** 9)}.items()}

res["first_依据/根据_position"] = hist(pos_pen)
res["last_citation_position"] = hist(pos_cit)
res["docs_whose_last_citation_is_after_6000"] = after6000
res["docs_without_any_citation"] = no_cit
res["docs_without_依据/根据_anywhere"] = no_pen_anywhere

# among docs with a citation after 6000, what tier/anchor do they get?
tier_after = Counter()
for r in sil:
    d = conn.execute("SELECT text_path FROM docs WHERE doc_id=?", (r["doc_id"],)).fetchone()
    if not d or not d["text_path"]:
        continue
    text = Path(d["text_path"]).read_text(encoding="utf-8")
    c = list(CIT.finditer(text))
    if c and c[-1].start() >= 6000:
        tier_after[(r["tier"], (r.get("anchor") or {}).get("basis"))] += 1
res["tier_of_docs_with_late_citation"] = {f"{k[0]}|{k[1]}": v for k, v in tier_after.items()}

# sample 3 texts where no 依据/根据 exists, to see the phrasing
samples = []
for r in sil:
    if len(samples) >= 3:
        break
    d = conn.execute("SELECT text_path FROM docs WHERE doc_id=?", (r["doc_id"],)).fetchone()
    if not d or not d["text_path"]:
        continue
    text = Path(d["text_path"]).read_text(encoding="utf-8")
    if not PEN.search(text):
        i = text.find("第一百二十四条")
        samples.append({"doc": r["doc_id"], "len": len(text),
                        "around": text[max(0, i - 120):i + 80] if i >= 0 else None,
                        "tail": text[-400:]})
res["no_penalty_clause_samples"] = samples

print(json.dumps(res, ensure_ascii=False, indent=1))

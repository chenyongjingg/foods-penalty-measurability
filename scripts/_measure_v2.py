#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read-only measurements for protocol revision v2 (no writes to state/data).

Run on the pod:  cd /opt/foods && ./venv/bin/python scripts/_measure_v2.py
"""
import json
import os
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path("/opt/foods")
sys.path.insert(0, str(ROOT))

from foods_pipeline.label import anchors  # noqa: E402

out = {}
conn = sqlite3.connect(str(ROOT / "state" / "foods.sqlite"))
conn.row_factory = sqlite3.Row


def q(sql, *a):
    return conn.execute(sql, a).fetchall()


# 1. text length distribution among clean/labeled/extracted
rows = q("SELECT stage, n_chars, lang, source, error FROM docs WHERE n_chars IS NOT NULL")
lens = sorted(r["n_chars"] for r in rows if r["stage"] in ("clean", "labeled", "extracted"))
def pct(xs, p):
    if not xs:
        return None
    k = max(0, min(len(xs) - 1, int(round(p / 100 * (len(xs) - 1)))))
    return xs[k]
out["clean_len"] = {"n": len(lens), "p50": pct(lens, 50), "p90": pct(lens, 90),
                    "p95": pct(lens, 95), "p99": pct(lens, 99), "max": max(lens) if lens else None,
                    "gt6000": sum(1 for x in lens if x > 6000),
                    "gt8000": sum(1 for x in lens if x > 8000),
                    "gt12000": sum(1 for x in lens if x > 12000),
                    "gt16000": sum(1 for x in lens if x > 16000)}

# 2. parse failures vs labelled lengths
fail = [r["n_chars"] for r in rows if r["stage"] == "clean"
        and (r["error"] or "") == ""]
fl = [r["n_chars"] for r in q("SELECT n_chars FROM docs WHERE error LIKE 'label_parse_failed%' AND n_chars IS NOT NULL")]
out["pending_clean_len"] = {"n": len(fail), "p50": pct(sorted(fail), 50),
                            "p90": pct(sorted(fail), 90)}
out["parse_failed_len"] = {"n": len(fl), "p50": pct(sorted(fl), 50), "p90": pct(sorted(fl), 90)}

# 3. silver: tiers, anchor basis and coverage
sil = []
with open(ROOT / "data" / "silver" / "silver.jsonl", encoding="utf-8") as f:
    for line in f:
        if line.strip():
            sil.append(json.loads(line))
basis = Counter()
basis_by_lang = Counter()
anchor_cat = Counter()
tiers = Counter()
hi_wrong = 0
for r in sil:
    a = r.get("anchor") or {}
    tiers[(r["lang"], r["tier"])] += 1
    basis[(r["lang"], a.get("basis"))] += 1
    anchor_cat[(a.get("basis"), bool(a.get("category")))] += 1
out["tiers"] = {f"{k[0]}|{k[1]}": v for k, v in tiers.items()}
out["anchor_basis"] = {f"{k[0]}|{k[1]}": v for k, v in basis.items()}
out["anchor_has_cat"] = {f"{k[0]}|{str(k[1])}": v for k, v in anchor_cat.items()}

# 4. unmapped penalty statutes (frequency over silver docs, recomputed from text)
mp = anchors.load_map()
mapped = {tuple(p) for cat, spec in mp["categories"].items() for p in spec.get("statutes", [])}
unmapped_pen = Counter()
unmapped_all = Counter()
n_no_statute = 0
n_text_missing = 0
for r in sil:
    d = conn.execute("SELECT text_path FROM docs WHERE doc_id=?", (r["doc_id"],)).fetchone()
    if not d or not d["text_path"] or not Path(d["text_path"]).exists():
        n_text_missing += 1
        continue
    text = Path(d["text_path"]).read_text(encoding="utf-8")
    pen = anchors.penalty_statutes(text)
    if not pen:
        n_no_statute += 1
    for s in pen:
        if s not in mapped:
            unmapped_pen[s] += 1
    for s in anchors.extract_statutes(text):
        if s not in mapped:
            unmapped_all[s] += 1
out["unmapped_penalty_statutes"] = [{"law": k[0], "article": k[1], "docs": v}
                                    for k, v in unmapped_pen.most_common(40)]
out["unmapped_all_statutes"] = [{"law": k[0], "article": k[1], "docs": v}
                                for k, v in unmapped_all.most_common(30)]
out["silver_docs_without_penalty_clause"] = n_no_statute
out["silver_docs_text_missing"] = n_text_missing

# 5. zh docs with f1 >= 0.85: what stops them from reaching high
hi = [r for r in sil if r.get("lang") == "zh" and (r.get("metrics") or {}).get("agreement_f1", 0) >= 0.85]
out["zh_f1_ge_085"] = {
    "n": len(hi),
    "anchor_none_basis": dict(Counter((r.get("anchor") or {}).get("basis") for r in hi if not (r.get("anchor") or {}).get("category"))),
    "anchor_mismatch": sum(1 for r in hi if (r.get("anchor") or {}).get("category")
                           and not r.get("anchor_pass")),
    "already_high": sum(1 for r in hi if r["tier"] == "high"),
}

# 6. runtime facts
out["llm_max_model_len"] = None
try:
    for ln in (ROOT / "logs" / "vllm.log").read_text(errors="replace").splitlines()[-400:]:
        if "max_model_len" in ln:
            out["llm_max_model_len"] = ln.strip()[:300]
except Exception as e:
    out["llm_max_model_len"] = f"unreadable: {e}"
try:
    out["start_llm_sh"] = (ROOT / "scripts" / "start_llm.sh").read_text()[:1200]
except Exception:
    pass

print(json.dumps(out, ensure_ascii=False, indent=1))

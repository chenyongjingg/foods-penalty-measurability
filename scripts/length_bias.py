#!/usr/bin/env python3
"""Length-bias product (D-86): is the excluded set longer than the labelled set?

Two exclusions can bias length:
  * stage='clean'  -- documents that have full text but failed the annotation protocol;
  * stage='failed' -- documents with metadata but no retrievable full text (no n_chars).

All quantiles are over the database's own n_chars column, i.e. the same instrument
for every group. Read-only; counts and quantiles only.
"""
import datetime, json, sqlite3, statistics as st
from pathlib import Path

ROOT = Path("/opt/foods")
con = sqlite3.connect(f"file:{ROOT/'state/foods.sqlite'}?mode=ro", uri=True)


def q(vals, p):
    v = sorted(vals)
    return v[int(p * (len(v) - 1))] if v else None


def group(where):
    rows = con.execute(f"SELECT n_chars FROM docs WHERE {where}").fetchall()
    vals = [r[0] for r in rows if r[0]]
    return {"n_rows": len(rows), "n_with_len": len(vals),
            "p50": q(vals, 0.5), "p90": q(vals, 0.9), "max": max(vals) if vals else None}


out = {"product": "length_bias", "at_utc": None,
       "labelled_zh": group("stage='extracted' AND lang='zh'"),
       "labelled_en": group("stage='extracted' AND lang='en'"),
       "clean_unlabelled": group("stage='clean'"),
       "failed_no_text": group("stage='failed'")}
a = out["clean_unlabelled"]["p50"]
b = out["labelled_zh"]["p50"]
if a and b:
    out["ratio_clean_over_labelled_zh"] = round(a / b, 2)
out["per_error"] = {}
for err, in con.execute("SELECT DISTINCT error FROM docs WHERE stage='clean'"):
    rows = [r[0] for r in con.execute(
        "SELECT n_chars FROM docs WHERE stage='clean' AND error IS ?", (err,)).fetchall() if r[0]]
    out["per_error"][err or "none"] = {"n": len(rows), "p50": q(rows, 0.5)}
out["note"] = ("All quantiles use the same column (docs.n_chars). stage='failed' rows have no "
               "n_chars at all -- they never received text -- so they cannot enter a length "
               "comparison and are reported as n_with_len=0 rather than imputed.")
con.close()
out["at_utc"] = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
(ROOT / "data/reports/length_bias.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(out, ensure_ascii=False))

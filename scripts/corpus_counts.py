#!/usr/bin/env python3
"""Corpus accounting product: every count the manuscript quotes about *size*.

The manuscript may only quote numbers a product records, and corpus size is
quoted in several places (silver rows, per language, per tier, what was
excluded and why). `finalize_*.json` records the sha and the verify result but
not the exclusion classes; `e1.json`/`e6_descriptive.json` each record a subset
under their own frame. This product puts all of them in one place, with the SQL
that produces each number, so a reader can re-run it.

Read-only: it never writes to the database. Output:
`data/reports/corpus_counts.json`.
"""
from __future__ import annotations

import collections
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from foods_pipeline.common import utc_iso          # noqa: E402
from foods_pipeline.manifest import Manifest       # noqa: E402

SILVER = ROOT / "data" / "silver" / "silver.jsonl"
DATASET = ROOT / "data" / "extracted" / "dataset.jsonl"
OUT = ROOT / "data" / "reports" / "corpus_counts.json"


def _sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _lines(p: Path) -> int:
    n = 0
    with open(p, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            n += block.count(b"\n")
    return n


def main() -> int:
    recs = [json.loads(line) for line in open(SILVER, encoding="utf-8") if line.strip()]
    by_lang = collections.Counter(r.get("lang") for r in recs)
    by_tier = collections.Counter(r.get("tier") for r in recs)
    tier_lang = collections.Counter((r.get("tier"), r.get("lang")) for r in recs)

    m = Manifest()
    stage_src, err = collections.Counter(), collections.Counter()
    stage_lang = collections.Counter()
    with m.conn() as c:
        for row in c.execute("SELECT source, stage, error, count(*) AS n FROM docs "
                             "GROUP BY source, stage, error"):
            stage_src[(row["source"], row["stage"])] += row["n"]
            if row["stage"] == "failed":
                err[row["error"] or "NULL"] += row["n"]
        for row in c.execute("SELECT stage, lang, count(*) AS n FROM docs GROUP BY stage, lang"):
            stage_lang[(row["stage"], row["lang"])] += row["n"]

    out = {
        "at_utc": utc_iso(),
        "product": "corpus_counts",
        "silver": {"path": str(SILVER), "sha256": _sha(SILVER), "n": len(recs),
                   "by_lang": dict(sorted(by_lang.items())),
                   "by_tier": dict(sorted(by_tier.items())),
                   "tier_x_lang": {f"{t}/{l}": n for (t, l), n in
                                   sorted(tier_lang.items(), key=lambda kv: (str(kv[0][0]),
                                                                             str(kv[0][1])))}},
        "dataset": {"path": str(DATASET), "sha256": _sha(DATASET), "lines": _lines(DATASET)}
        if DATASET.exists() else None,
        "docs_by_source_stage": {f"{s}/{st}": n for (s, st), n in
                                 sorted(stage_src.items(), key=lambda kv: (-kv[1], kv[0]))},
        "docs_by_stage_lang": {f"{st}/{l}": n for (st, l), n in sorted(stage_lang.items())},
        "failed_by_error": dict(sorted(err.items(), key=lambda kv: -kv[1])),
        "queries": {
            "silver_rows": "wc -l data/silver/silver.jsonl",
            "docs_by_source_stage": "SELECT source, stage, count(*) FROM docs GROUP BY 1,2",
            "failed_by_error": "SELECT error, count(*) FROM docs WHERE stage='failed' GROUP BY 1",
        },
        "note": ("Counts only; no labels, no thresholds. `failed` is not one class -- "
                 "group by error before calling it a failure (D-84)."),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(OUT)
    print(json.dumps({"ok": True, "silver_n": len(recs),
                      "by_lang": out["silver"]["by_lang"],
                      "by_tier": out["silver"]["by_tier"],
                      "dataset_lines": (out["dataset"] or {}).get("lines"),
                      "failed_by_error": out["failed_by_error"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

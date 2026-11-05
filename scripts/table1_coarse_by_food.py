#!/usr/bin/env python3
"""Table 1 addendum: coarse category x primary food category on the frozen corpus.

Read-only re-derivation for the manuscript. It imports the *same* functions and
constants as `scripts/e6_descriptive.py` (COARSE, label_v2, fact_segment,
food_hits) and the same inputs (frozen silver + the docs table), so every cell
can be reproduced from the frozen silver sha. It writes
`data/analysis/table1_coarse_by_food.json`; it changes no released number and
is not part of the release bundle.

Why this file exists: `e6_descriptive.json` reports the coarse distribution and
the food-category distribution separately. A reader of Table 1 needs the joint
table, and the manuscript may only quote numbers that a product records
(the "no hand-typed numbers" rule), so the joint table has to be its own
product with its own at_utc and sha.
"""
from __future__ import annotations

import collections
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SILVER = ROOT / "data" / "silver" / "silver.jsonl"
OUT = ROOT / "data" / "analysis" / "table1_coarse_by_food.json"

_spec = importlib.util.spec_from_file_location(
    "e6_descriptive", str(Path(__file__).resolve().parent / "e6_descriptive.py"))
e6 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(e6)

from foods_pipeline.common import utc_iso          # noqa: E402
from foods_pipeline.manifest import Manifest       # noqa: E402

COARSE_ORDER = ["DATA_FALSIFICATION", "MARKET_ORDER", "UNLICENSED",
                "PROCEDURAL", "UNDETERMINED"]


def _sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    mp = e6.load_v2()
    fd = e6.load_food()
    all_recs = [json.loads(line) for line in open(SILVER, encoding="utf-8") if line.strip()]
    recs = [r for r in all_recs if r.get("lang") == "zh"]
    if not recs:
        print("no Chinese silver records", file=sys.stderr)
        return 1

    m = Manifest()
    texts, metas = {}, {}
    with m.conn() as c:
        for row in c.execute("SELECT doc_id, text_path, meta FROM docs"):
            if row["text_path"]:
                try:
                    texts[row["doc_id"]] = Path(row["text_path"]).read_text(encoding="utf-8")
                except OSError:
                    pass
            metas[row["doc_id"]] = json.loads(row["meta"] or "{}")

    missing = [r["doc_id"] for r in recs if r["doc_id"] not in texts]
    if missing:
        print(f"{len(missing)} silver docs have no text on disk, e.g. {missing[:3]}",
              file=sys.stderr)
        return 1

    joint: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    coarse_n = collections.Counter()
    for r in recs:
        did = r["doc_id"]
        text = texts[did]
        lab = e6.label_v2(text, mp)
        coarse = e6.COARSE.get(lab["category"] or "UNRESOLVED", "UNDETERMINED")
        meta = metas.get(did, {})
        fh = e6.food_hits({"penalty_content": meta.get("penalty_content") or "",
                           "fact_segment": e6.fact_segment(text)}, fd)
        food = fh["primary"] or "UNMATCHED"
        joint[food][coarse] += 1
        joint[food]["TOTAL"] += 1
        coarse_n[coarse] += 1

    rows = []
    for food, cnt in sorted(joint.items(), key=lambda kv: (-kv[1]["TOTAL"], kv[0])):
        row = {"food": food, "n": cnt["TOTAL"]}
        for c in COARSE_ORDER:
            row[c] = cnt[c]
        rows.append(row)

    n = len(recs)
    out = {
        "at_utc": utc_iso(),
        "product": "table1_coarse_by_food",
        "silver": {"path": str(SILVER), "sha256": _sha(SILVER), "n": n},
        "frame": "Chinese penalty decisions (silver lang=zh, frozen corpus)",
        "coarse_order": COARSE_ORDER,
        "coarse_map": e6.COARSE,
        "food_dict_version": int(fd.get("version", 1)),
        "map_version": int(mp.get("version", 0)),
        "rows": rows,
        "column_totals": {c: coarse_n[c] for c in COARSE_ORDER},
        "n_total": n,
        "matchable_n": sum(r["n"] for r in rows if r["food"] != "UNMATCHED"),
        "matchable_rate": round(sum(r["n"] for r in rows if r["food"] != "UNMATCHED") / n, 4),
        "note": ("Joint distribution of the deterministic coarse category and the primary "
                 "food category, re-derived from the frozen silver with the same functions "
                 "e6_descriptive.py uses. UNMATCHED is a food-category miss, not a "
                 "misclassification: the statutes still decide the coarse category. "
                 "Cell counts are descriptive; no test is run on them."),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(OUT)
    print(json.dumps({"ok": True, "n": n, "rows": len(rows),
                      "matchable_rate": out["matchable_rate"],
                      "column_totals": out["column_totals"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

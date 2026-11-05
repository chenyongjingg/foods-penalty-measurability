#!/usr/bin/env python
"""Decompose the three pairwise agreements (D-107): how much of each agreement
is joint abstention (OTHER vs OTHER) rather than agreement on a substantive class.

Descriptive only. It cannot change any verdict: the D-102 verdict was computed by
scripts/e11c_three_coder.py from the same three files and is unaffected by this
decomposition. Written because D-106 must report "64 agreements, of which 42 are
OTHER-vs-OTHER" from a product file and not from a hand tally.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path("/opt/foods")
SAMPLE = ROOT / "data/analysis/human_sample.json"
CODED = {c: ROOT / f"human/coded_{c}.json" for c in "ABC"}
OUT = ROOT / "data/analysis/e11c_decomposition.json"

PAIRS = [("A", "B"), ("A", "C"), ("B", "C")]


def load(path: Path) -> dict[str, str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("items", data.get("coded", []))
    return {d["doc_id"]: d["label"] for d in data if d.get("label")}


def r4(x):
    return round(x, 4)


def main() -> None:
    ids = [d["doc_id"] for d in json.loads(SAMPLE.read_text(encoding="utf-8"))["items"]]
    lab = {c: load(p) for c, p in CODED.items()}
    ids = [i for i in ids if all(i in lab[c] for c in "ABC")]

    out = {
        "at_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "criterion_register": "D-107",
        "role": "descriptive_decomposition_only",
        "n_docs": len(ids),
        "inputs": {"sample_sha256": hashlib.sha256(SAMPLE.read_bytes()).hexdigest()},
        "pairs": {},
        "other_share": {},
    }
    for c, p in CODED.items():
        out["inputs"][f"coded_{c}_sha256"] = hashlib.sha256(p.read_bytes()).hexdigest()

    for c in "ABC":
        out["other_share"][c] = r4(sum(1 for i in ids if lab[c][i] == "OTHER") / len(ids))

    for a, b in PAIRS:
        agree = [i for i in ids if lab[a][i] == lab[b][i]]
        both_other = [i for i in agree if lab[a][i] == "OTHER"]
        rest = [i for i in ids if i not in set(both_other)]
        sub_agree = [i for i in rest if lab[a][i] == lab[b][i]]
        out["pairs"][f"{a}_{b}"] = {
            "n_docs": len(ids),
            "n_agree": len(agree),
            "n_agree_other_other": len(both_other),
            "agreement": r4(len(agree) / len(ids)),
            "n_scored_substantive": len(rest),
            "n_agree_substantive": len(sub_agree),
            "substantive_agreement": r4(len(sub_agree) / len(rest)) if rest else None,
            "other_share": {a: out["other_share"][a], b: out["other_share"][b]},
        }

    outs = {
        "at_utc": out["at_utc"],
        "criterion_register": out["criterion_register"],
        "role": out["role"],
        "n_docs": out["n_docs"],
        "inputs": out["inputs"],
        "other_share": out["other_share"],
        "pairs": out["pairs"],
        "label_counts": {c: dict(Counter(lab[c][i] for i in ids)) for c in "ABC"},
    }
    tmp = OUT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(outs, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(OUT)
    print(json.dumps(outs, ensure_ascii=False, indent=1))
    print("sha", hashlib.sha256(OUT.read_bytes()).hexdigest())


if __name__ == "__main__":
    main()

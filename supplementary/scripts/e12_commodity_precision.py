#!/usr/bin/env python
"""D-115: measured precision of the D-111 commodity keyword presence index.

Reads the frozen adjudication sample (data/analysis/e12_precision_sample.json,
270 items = 15 per category, selected in sha256(doc_id) order as registered in
D-111) and joins it with the adjudication below. Every verdict was decided by
reading the registered +-120-character window; where the window was not
decisive the full cleaned text was read (flagged in NOTES).

Verdict vocabulary, fixed in D-113 before adjudication finished:
  S = subject   the term names the commodity the case is about
  I = mention   the term appears but not as the case subject (ingredient list,
                menu component, business scope, neighbouring product, ...)
  T = statute   the term appears only inside quoted law/standard text
                (a strict subset of I, recorded separately)
  F = false     the term does not refer to that food category at all: place or
                company name, homograph, or a cross-word-boundary substring
                (金桂花+生产 -> "金花生"; 面包车; 土豆干; 拷贝; 苹果酸; 葡萄糖酸)

The registered pass test (D-111) counts S, I and T as passes and only F as a
failure. Both figures below are reported and neither may be called "the
precision" alone (D-113):
  precision_any_mention = (S+I+T)/n        precision_subject = S/n
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
from pathlib import Path

ROOT = Path("/opt/foods")
SAMPLE = ROOT / "data/analysis/e12_precision_sample.json"
INDEX = ROOT / "data/analysis/e12_commodity_index.json"
OUT = ROOT / "data/analysis/e12_commodity_precision.json"
CRITERION = "D-115"

# category -> (n_sampled, {verdict: [1-based positions within the category]})
# Unlisted positions default to I; later entries override earlier ones
# (S, then T, then F), so a false match inside an otherwise-subject category
# wins over the category default.
RULES: dict[int, tuple[int, dict[str, list[int]]]] = {
    1: (15, {"S": [6, 11, 13, 14]}),
    2: (15, {"S": [10, 12, 14]}),
    3: (15, {"S": [2, 3, 10, 13]}),
    4: (15, {"S": [1, 2, 6, 7, 10, 11, 13, 14, 15]}),
    5: (15, {"S": [1, 2, 4, 7, 13], "F": [10, 11, 15]}),
    6: (15, {"S": [4, 7, 8, 10, 14, 15]}),
    7: (15, {"S": [1, 5, 10, 11, 14], "T": [2, 8], "F": [6, 9, 12, 13]}),
    8: (15, {"S": [1, 5, 11, 15], "T": [9], "F": [2, 10, 13]}),
    9: (15, {"S": [6, 9, 12], "T": [15], "F": [3, 7, 11, 13]}),
    10: (15, {"S": list(range(1, 16)), "F": [8]}),
    11: (15, {"S": [1, 4, 5, 7, 8, 9, 11, 13, 15], "F": [14]}),
    12: (15, {"S": [1, 2, 3, 4, 5, 6, 7, 8, 10, 11, 12, 13, 15]}),
    13: (15, {"S": [2, 3, 4, 7, 9, 12, 13, 14], "T": [6, 10, 15]}),
    14: (15, {"S": [1, 7, 10, 11, 15], "T": [6], "F": [2, 8]}),
    15: (15, {"S": [1, 10], "T": [14]}),
    16: (15, {"S": [13], "T": [2, 6, 10, 12]}),
    17: (15, {"S": [1, 6, 7, 9, 10, 13, 14, 15], "F": [3]}),
    18: (15, {"S": [12], "I": [11], "T": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 13, 14, 15]}),
}

NOTES: dict[tuple[int, int], str] = {
    (5, 4): "substring of 鲍鱼 (abalone); still an aquatic food commodity",
    (5, 10): "company name 鱼爪网",
    (5, 11): "place name 呼伦贝尔",
    (5, 15): "cross-word-boundary: 拷贝 (video copy disc)",
    (7, 6): "flavour word 草莓牛奶味 in a candy",
    (7, 9): "flavour words 蓝莓酸奶味 / 高级牛奶味",
    (7, 12): "flavour word 牛奶味 in a cake name",
    (7, 13): "flavour/product-name fragment in a candy",
    (8, 2): "company name 南京太二酸菜有限公司",
    (8, 10): "place name 石笋镇",
    (8, 13): "place name 蔬菜物流园",
    (9, 3): "chemical name 苹果酸 (malic acid)",
    (9, 7): "flavour word 葡萄牛奶味",
    (9, 10): "fruit shapes printed on packaging, not commodities",
    (9, 11): "flavour word 葡萄牛奶味",
    (9, 13): "chemical name 葡萄糖酸-δ内酯",
    (10, 8): "cross-word-boundary: 土豆干 is potato, not 豆干",
    (11, 10): "substring of 芝麻饼 (sesame cake variety)",
    (11, 14): "cross-word-boundary: 面包车 (van)",
    (14, 2): "place/company name 普洱糯扎渡发展有限公司",
    (14, 8): "place/company name 普洱牛哄哄食品有限责任公司",
    (17, 3): "cross-word-boundary: 金桂花 + 生产日期 -> 金花生",
    (18, 11): "case-specific finding that the product is NOT a supplementary food",
}


def build(n: int, spec: dict[str, list[int]]) -> list[str]:
    out = ["I"] * n
    for lab in ("I", "S", "T", "F"):
        for pos in spec.get(lab, []):
            if not 1 <= pos <= n:
                raise SystemExit(f"position {pos} outside 1..{n}")
            out[pos - 1] = lab
    return out


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (round((c - h) / d, 4), round((c + h) / d, 4))


def main() -> None:
    sample = json.loads(SAMPLE.read_text(encoding="utf-8"))
    index = json.loads(INDEX.read_text(encoding="utf-8"))

    by_cat: dict[int, list[dict]] = {}
    for it in sample["items"]:
        by_cat.setdefault(it["category"], []).append(it)

    if set(by_cat) != set(RULES):
        raise SystemExit(f"category mismatch: sample {sorted(by_cat)} vs rules {sorted(RULES)}")
    for cid, (n, _spec) in RULES.items():
        if len(by_cat[cid]) != n:
            raise SystemExit(f"cat {cid}: {len(by_cat[cid])} sample items vs {n} declared")

    per_cat, out_items = {}, []
    for cid in sorted(by_cat):
        n, spec = RULES[cid]
        seq = build(n, spec)
        n_k = index["categories"][str(cid)]["n_docs"]
        c = {"n_docs_in_corpus": n_k, "n_sampled": n}
        for lab in "SITF":
            c[lab] = seq.count(lab)
        c["precision_any_mention"] = round((c["S"] + c["I"] + c["T"]) / n, 4)
        c["precision_subject"] = round(c["S"] / n, 4)
        c["wilson_any_mention"] = wilson(c["S"] + c["I"] + c["T"], n)
        c["wilson_subject"] = wilson(c["S"], n)
        per_cat[cid] = c
        for pos, (it, v) in enumerate(zip(by_cat[cid], seq), start=1):
            out_items.append({
                "doc_id": it["doc_id"], "category": cid, "category_name": it["category_name"],
                "terms": [w["term"] for w in it["windows"]],
                "verdict": v, "note": NOTES.get((cid, pos), ""),
            })

    n = len(out_items)
    k_any = sum(1 for i in out_items if i["verdict"] != "F")
    k_sub = sum(1 for i in out_items if i["verdict"] == "S")
    w_all = sum(c["n_docs_in_corpus"] for c in per_cat.values())
    w_any = sum(c["n_docs_in_corpus"] * c["precision_any_mention"] for c in per_cat.values())
    w_sub = sum(c["n_docs_in_corpus"] * c["precision_subject"] for c in per_cat.values())

    out = {
        "at_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "criterion_register": CRITERION,
        "role": "human_adjudicated_precision_of_keyword_presence",
        "verdict_vocabulary": {"S": "subject", "I": "mention, not the case subject",
                               "T": "statute/standard text only (subset of I)",
                               "F": "false: not a reference to that food category"},
        "inputs": {
            "sample_sha256": hashlib.sha256(SAMPLE.read_bytes()).hexdigest(),
            "index_sha256": hashlib.sha256(INDEX.read_bytes()).hexdigest(),
        },
        "n_items": n,
        "counts": {lab: sum(1 for i in out_items if i["verdict"] == lab) for lab in "SITF"},
        "overall": {
            "design": "equal allocation, 15 per category, not proportional; per-category figures are primary",
            "equal_allocation_any_mention": round(k_any / n, 4),
            "equal_allocation_subject": round(k_sub / n, 4),
            "equal_allocation_wilson_any_mention": wilson(k_any, n),
            "equal_allocation_wilson_subject": wilson(k_sub, n),
            "poststratified_any_mention": round(w_any / w_all, 4),
            "poststratified_subject": round(w_sub / w_all, 4),
            "poststratified_note": "weights = corpus documents per category; no interval reported for this column",
        },
        "per_category": {str(k): v for k, v in per_cat.items()},
        "items": out_items,
    }

    tmp = OUT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(OUT)

    print("counts", out["counts"], "n", n)
    print("overall", json.dumps(out["overall"], ensure_ascii=False, indent=1))
    for cid in sorted(per_cat):
        c = per_cat[cid]
        print(f"{cid:>2} N={c['n_docs_in_corpus']:>4} S={c['S']:>2} I={c['I']:>2} T={c['T']:>2} F={c['F']:>2} "
              f"any={c['precision_any_mention']:.4f} {c['wilson_any_mention']} "
              f"subj={c['precision_subject']:.4f} {c['wilson_subject']}")
    print("sha", hashlib.sha256(OUT.read_bytes()).hexdigest())


if __name__ == "__main__":
    main()

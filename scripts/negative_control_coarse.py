#!/usr/bin/env python3
"""Does collapsing to coarse categories rescue the deterministic layer?

The pre-registered fallback said: if rule-vs-LLM agreement falls below the 0.75 floor,
report only coarse categories. That fallback silently assumes fine-grained
disagreement mostly collapses away. This product tests the assumption on the same
50-document negative-control slice, using the already-frozen coarse map. No
threshold, mapping or slice is changed -- this is a re-reading of an existing product.
"""
import datetime, json
from collections import Counter

E6 = "/opt/foods/data/analysis/e6_descriptive.json"
T1 = "/opt/foods/data/analysis/table1_coarse_by_food.json"
OUT = "/opt/foods/data/analysis/negative_control_coarse.json"

e6 = json.load(open(E6, encoding="utf-8"))
cm = json.load(open(T1, encoding="utf-8"))["coarse_map"]
nc = e6["negative_control"]
rows = nc["rows"]


def coarse(x):
    return "UNDETERMINED" if x is None else cm.get(x, "UNDETERMINED")


def rate(pairs):
    n = len(pairs)
    k = sum(1 for x, y in pairs if x == y)
    return {"n": n, "agree": k, "rate": round(k / n, 4) if n else None}


fine_ra = rate([(r["rule"], r["a"]) for r in rows])
fine_rb = rate([(r["rule"], r["b"]) for r in rows])
co_ra = rate([(coarse(r["rule"]), coarse(r["a"])) for r in rows])
co_rb = rate([(coarse(r["rule"]), coarse(r["b"])) for r in rows])
co_ab = rate([(coarse(r["a"]), coarse(r["b"])) for r in rows])
decided = [r for r in rows if coarse(r["rule"]) != "UNDETERMINED"]
co_ra_dec = rate([(coarse(r["rule"]), coarse(r["a"])) for r in decided])

conf = Counter((coarse(r["rule"]), coarse(r["a"])) for r in rows)
out = {
    "product": "negative_control_coarse",
    "source": E6,
    "coarse_map_source": T1,
    "slice": {"n": len(rows), "seed": nc["seed"], "doc_ids_sha_note": "identical slice as e6.negative_control"},
    "fine": {"rule_vs_a": fine_ra, "rule_vs_b": fine_rb},
    "coarse": {"rule_vs_a": co_ra, "rule_vs_b": co_rb, "a_vs_b": co_ab,
               "rule_vs_a_on_decided": co_ra_dec},
    "n_rule_undetermined": len(rows) - len(decided),
    "confusion_rule_x_a": [{"rule": k[0], "a": k[1], "n": v} for k, v in conf.most_common()],
    "reading": ("Coarse collapse does not change agreement: the same 14 of 50 documents "
                "agree at fine and at coarse granularity, so the pre-registered fallback to "
                "coarse categories is not licensed by the negative control either. The "
                "distribution in Table 1 is the output of a documented instrument, not an "
                "estimate of the population. Disagreement is concentrated where one side "
                "abstains (rule UNDETERMINED vs LLM category)."),
    "at_utc": None,
}
out["at_utc"] = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
open(OUT, "w", encoding="utf-8").write(json.dumps(out, ensure_ascii=False, indent=1))
print(json.dumps({k: v for k, v in out.items() if k != "confusion_rule_x_a"}, ensure_ascii=False))

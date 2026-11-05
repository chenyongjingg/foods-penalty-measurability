#!/usr/bin/env python3
"""Frame sensitivity for the E8 comparison, plus the macro-F1 with and without the
class the instrument never emits.

Why this exists: the paper reports one odds ratio (9.57) for one definition of the
comparison frame — the "fraud framework", which excludes market-order and procedural
documents. A reader cannot tell from that number how much of it is the frame choice.
This script computes the same contrast under every frame the product data supports, so
the manuscript can print the sensitivity instead of leaving it to a reviewer to
reconstruct. It also reports the anchor macro-F1 with the never-emitted class excluded,
because that class contributes a structural zero to the "honest" figure as well.

No model calls, no threshold changes, no new data: every input is an existing product.
Writes data/analysis/metric_sensitivity.json.
"""
from __future__ import annotations

import hashlib
import json
import math
import time
from pathlib import Path

from scipy.stats import fisher_exact

ROOT = Path("/opt/foods")
E8 = ROOT / "data/analysis/e8_us_cn.json"
E6 = ROOT / "data/analysis/e6_descriptive.json"
E1 = ROOT / "data/metrics/e1.json"
OUT = ROOT / "data/analysis/metric_sensitivity.json"


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def contrast(a: int, b: int, c: int, d: int) -> dict:
    """Odds ratio, Fisher p and a Woolf 95% CI for [[a,b],[c,d]]."""
    orr, p = fisher_exact([[a, b], [c, d]])
    se = math.sqrt(1 / a + 1 / b + 1 / c + 1 / d)
    return {
        "table": [[a, b], [c, d]],
        "odds_ratio": round(float(orr), 4),
        "fisher_p": float(f"{p:.6g}"),
        "ci95_woolf": [round(math.exp(math.log(orr) - 1.96 * se), 2),
                       round(math.exp(math.log(orr) + 1.96 * se), 2)],
    }


def main() -> int:
    e8 = json.loads(E8.read_text(encoding="utf-8"))
    e6 = json.loads(E6.read_text(encoding="utf-8"))
    e1 = json.loads(E1.read_text(encoding="utf-8"))

    cn = e8["cn"]["counts"]
    us = e8["us"]["counts"]
    fl_cn, fl_us = cn["FALSE_LABELING"], us["FALSE_LABELING"]
    other_us = sum(v for k, v in us.items() if k != "FALSE_LABELING")
    other_fraud = sum(v for k, v in cn.items() if k != "FALSE_LABELING")

    # the two coarse categories that the fraud framework leaves out, from E6 itself
    fine = e6["category_distribution"]
    market_order = (fine.get("TRADEMARK_INFRINGEMENT", 0)
                    + fine.get("FALSE_ADVERTISING", 0)
                    + fine.get("PRODUCT_QUALITY", 0))
    procedural = fine.get("PROCEDURAL_NONCOMPLIANCE", 0)
    unlicensed = fine.get("UNLICENSED_OPERATION", 0)

    frames = {
        "fraud_framework_as_published": contrast(fl_cn, other_fraud, fl_us, other_us),
        "plus_framework_excluded": contrast(
            fl_cn, other_fraud + market_order + procedural, fl_us, other_us),
        "fraud_framework_without_unlicensed": contrast(
            fl_cn, other_fraud - unlicensed, fl_us, other_us),
    }

    # anchor macro-F1: with every class, and with the never-emitted class dropped
    a = e1["anchor_f1"]
    per_class = a["per_class_f1"]
    pc = a["support"]["per_class"]          # {class: {f1, support, predicted}}
    ge20 = {k: v for k, v in per_class.items() if pc.get(k, {}).get("support", 0) >= 20}
    never_emitted = [k for k, v in pc.items()
                     if v.get("support", 0) > 0 and v.get("predicted", 0) == 0]
    excl = {k: v for k, v in ge20.items() if k not in never_emitted}

    out = {
        "at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "product": "E8 frame sensitivity + anchor macro sensitivity",
        "inputs": {str(p.relative_to(ROOT)): sha(p) for p in (E8, E6, E1)},
        "silver_sha256": e8["cn"]["silver_sha256"],
        "e8_frames": {
            "cn_false_labelling": fl_cn,
            "cn_other_in_fraud_framework": other_fraud,
            "cn_market_order": market_order,
            "cn_procedural": procedural,
            "cn_unlicensed": unlicensed,
            "us_false_labelling": fl_us,
            "us_other": other_us,
            "contrasts": frames,
            "reading": "The direction and significance of the contrast survive every "
                       "frame; the magnitude does not. Report the frame with the odds "
                       "ratio, never the odds ratio alone.",
        },
        "anchor_macro": {
            "all_classes": a["macro_f1"],
            "ge20_classes": sorted(ge20),
            "macro_ge20": round(sum(ge20.values()) / len(ge20), 4),
            "never_emitted_classes": never_emitted,
            "macro_ge20_excluding_never_emitted": round(sum(excl.values()) / len(excl), 4),
            "classes_excluded": sorted(set(ge20) - set(excl)),
            "per_class_used": excl,
        },
        "coarse_data_falsification_composition": {
            "total": fine.get("FALSE_LABELING", 0) + fine.get("FORGED_INSPECTION_REPORT", 0)
                     + fine.get("FAKE_CERTIFICATION", 0),
            "false_labelling": fine.get("FALSE_LABELING", 0),
            "forged_inspection_report": fine.get("FORGED_INSPECTION_REPORT", 0),
            "fake_certification": fine.get("FAKE_CERTIFICATION", 0),
            "false_labelling_share": round(
                fine.get("FALSE_LABELING", 0)
                / max(1, fine.get("FALSE_LABELING", 0) + fine.get("FORGED_INSPECTION_REPORT", 0)
                      + fine.get("FAKE_CERTIFICATION", 0)), 4),
        },
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"ok": True, "frames": {k: v["odds_ratio"] for k, v in frames.items()},
                      "macro_ge20_excl": out["anchor_macro"]["macro_ge20_excluding_never_emitted"],
                      "never_emitted": never_emitted}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

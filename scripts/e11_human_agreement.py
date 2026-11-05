#!/usr/bin/env python
"""H1-H4 of PREREG_20261105_rescue.md.

Reads the human coding sheet (`human/coded.json`, a list of
{doc_id, label}) plus human_sample.json and silver.jsonl, and writes
data/analysis/e11_agreement.json.

Everything here is fixed by the pre-registration; this script only computes.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import os
from collections import Counter
from pathlib import Path

ROOT = Path("/opt/foods")
SILVER = ROOT / "data/silver/silver.jsonl"
SAMPLE = ROOT / "data/analysis/human_sample.json"
CODED = ROOT / "human/coded.json"
OUT = ROOT / "data/analysis/e11_agreement.json"

FRAUD_FINE = {"FORGED_INSPECTION_REPORT", "TAMPERED_TRACEABILITY", "FAKE_CERTIFICATION"}


def wilson(k: int, n: int, z: float = 1.959963985) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def newcombe_diff(k1: int, n1: int, k2: int, n2: int) -> dict:
    """Newcombe (1998) method 10: square-and-add score interval for p1 - p2."""
    p1, p2 = k1 / n1, k2 / n2
    l1, u1 = wilson(k1, n1)
    l2, u2 = wilson(k2, n2)
    d = p1 - p2
    lo = d - math.sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2)
    hi = d + math.sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2)
    return {"diff": d, "lo": lo, "hi": hi, "p1": p1, "p2": p2, "n1": n1, "n2": n2}


def kappa(pairs: list[tuple[str, str]]) -> dict:
    n = len(pairs)
    if n == 0:
        return {"po": float("nan"), "pe": float("nan"), "kappa": float("nan")}
    po = sum(1 for a, b in pairs if a == b) / n
    ca, cb = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    keys = set(ca) | set(cb)
    pe = sum((ca[k] / n) * (cb[k] / n) for k in keys)
    kp = (po - pe) / (1 - pe) if pe < 1 else float("nan")
    # Gwet's AC1
    q = len(keys)
    pi = {k: (ca[k] + cb[k]) / (2 * n) for k in keys}
    pe_ac1 = sum(pi[k] * (1 - pi[k]) for k in keys) / (q - 1) if q > 1 else float("nan")
    ac1 = (po - pe_ac1) / (1 - pe_ac1) if q > 1 and pe_ac1 < 1 else float("nan")
    pabak = (q * po - 1) / (q - 1) if q > 1 else float("nan")
    return {"po": po, "pe": pe, "kappa": kp, "ac1": ac1, "pabak": pabak,
            "n_classes_observed": q,
            "prevalence": {k: round(ca[k] / n, 4) for k in sorted(keys)}}


def analyse(rows: list[dict], tag: str) -> dict:
    """rows: [{doc_id, I, H}]"""
    keep = [r for r in rows if r["H"] != "UNRESOLVED"]
    n_all, n_unres = len(rows), len(rows) - len(keep)
    pairs = [(r["I"], r["H"]) for r in keep]
    k = sum(1 for a, b in pairs if a == b)
    n = len(pairs)
    lo, hi = wilson(k, n)
    out = {
        "n_coded": n_all, "n_unresolved": n_unres, "n_scored": n,
        "n_agree": k,
        "agreement": round(k / n, 4) if n else None,
        "wilson95": [round(lo, 4), round(hi, 4)],
        **{f"_{x}": (round(v, 4) if isinstance(v, float) else v)
           for x, v in kappa(pairs).items()},
    }
    # sensitivity: UNRESOLVED -> OTHER
    pairs2 = [(r["I"], "OTHER" if r["H"] == "UNRESOLVED" else r["H"]) for r in rows]
    k2 = sum(1 for a, b in pairs2 if a == b)
    out["sensitivity_unresolved_as_other"] = {
        "n": len(pairs2), "n_agree": k2,
        "agreement": round(k2 / len(pairs2), 4),
        "wilson95": [round(x, 4) for x in wilson(k2, len(pairs2))],
        "kappa": round(kappa(pairs2)["kappa"], 4),
    }
    # confusion
    conf: dict[str, Counter] = {}
    for a, b in pairs2:
        conf.setdefault(a, Counter())[b] += 1
    out["confusion_I_rows"] = {a: dict(c) for a, c in sorted(conf.items())}
    out["_tag"] = tag
    return out


def main() -> None:
    coded = json.loads(CODED.read_text(encoding="utf-8"))
    if isinstance(coded, dict):
        coded = coded.get("items", coded.get("coded", []))
    sample = json.loads(SAMPLE.read_text(encoding="utf-8"))
    stratum = {x["doc_id"]: x["stratum"] for x in sample["items"]}

    silver = {r["doc_id"]: r for r in
              (json.loads(l) for l in SILVER.open(encoding="utf-8"))}

    rows = []
    for c in coded:
        d = c["doc_id"]
        if d not in silver:
            continue
        rows.append({"doc_id": d, "I": silver[d]["violation_category"],
                     "H": c.get("label"), "stratum": stratum.get(d)})

    s1 = [r for r in rows if r["stratum"] == "srs" and r["H"]]
    s2 = [r for r in rows if r["stratum"] == "disagreement" and r["H"]]
    res = {"at_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "inputs": {"silver_sha256": hashlib.sha256(SILVER.read_bytes()).hexdigest(),
                      "sample_sha256": hashlib.sha256(SAMPLE.read_bytes()).hexdigest()},
           "H1_S1": analyse(s1, "H1"),
           "H2_S2": analyse(s2, "H2")}
    if len(s1) and len(s2):
        a = res["H1_S1"]["n_agree"], res["H1_S1"]["n_scored"]
        b = res["H2_S2"]["n_agree"], res["H2_S2"]["n_scored"]
        res["H2_contrast_S2_minus_S1"] = newcombe_diff(b[0], b[1], a[0], a[1])

    # H3: subset where I is one of the three fine fraud classes
    h3 = [r for r in s1 if r["I"] in FRAUD_FINE and r["H"]]
    res["H3_fraud_subset"] = analyse(h3, "H3")

    # H4 verdicts
    h1 = res["H1_S1"]
    v = {}
    v["H1_supported"] = bool(h1["n_scored"] and h1["agreement"] >= 0.85
                             and h1["wilson95"][0] >= 0.74)
    v["H4_1_agreement_below_0.70"] = bool(h1["n_scored"] and h1["agreement"] < 0.70)
    v["H4_2_unresolved_gt_12"] = h1["n_unresolved"] > 12
    v["H4_3_human_classes_lt_3"] = len(set(r["H"] for r in s1)) < 3
    v["H3_estimable"] = len(h3) >= 10
    v["rescue_failed"] = v["H4_1_agreement_below_0.70"] or v["H4_2_unresolved_gt_12"] \
        or v["H4_3_human_classes_lt_3"]
    res["verdict"] = v

    tmp = OUT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, OUT)
    print(json.dumps(res, ensure_ascii=False, indent=1)[:2400])
    print("sha", hashlib.sha256(OUT.read_bytes()).hexdigest())


if __name__ == "__main__":
    main()

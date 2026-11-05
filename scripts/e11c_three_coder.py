#!/usr/bin/env python
"""Three-coder layer (D-102): A, B, C on the same 80 documents.

Criteria are fixed by D-102, written before coder C produced any answer.
This script only computes; it must not be edited after C's data lands.

Primary statistic: Fleiss' kappa over the 80 x 3 table, 6 categories.
Secondary: the three pairwise agreements with Wilson intervals and Cohen's kappa.
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
SAMPLE = ROOT / "data/analysis/human_sample.json"
CODED = {c: ROOT / f"human/coded_{c}.json" for c in "ABC"}
OUT = ROOT / "data/analysis/e11c_three_coder.json"

CATS = ["FORGED_INSPECTION_REPORT", "TAMPERED_TRACEABILITY", "FAKE_CERTIFICATION",
        "FALSE_LABELING", "UNLICENSED_OPERATION", "OTHER"]


def wilson(k: int, n: int, z: float = 1.959963985) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def cohen(pairs: list[tuple[str, str]]) -> dict:
    n = len(pairs)
    if n == 0:
        return {"n": 0}
    po = sum(1 for a, b in pairs if a == b) / n
    ca, cb = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    keys = set(ca) | set(cb)
    pe = sum((ca[k] / n) * (cb[k] / n) for k in keys)
    kp = (po - pe) / (1 - pe) if pe < 1 else float("nan")
    q = len(keys)
    pi = {k: (ca[k] + cb[k]) / (2 * n) for k in keys}
    pe_ac1 = sum(pi[k] * (1 - pi[k]) for k in keys) / (q - 1) if q > 1 else float("nan")
    ac1 = (po - pe_ac1) / (1 - pe_ac1) if q > 1 and pe_ac1 < 1 else float("nan")
    pabak = (q * po - 1) / (q - 1) if q > 1 else float("nan")
    return {"n": n, "n_agree": sum(1 for a, b in pairs if a == b), "po": po, "pe": pe,
            "kappa": kp, "ac1": ac1, "pabak": pabak, "n_classes": q,
            "prevalence": {k: round(ca[k] / n, 4) for k in sorted(keys)}}


def fleiss(rows: list[list[str]]) -> dict:
    """rows: one list of m labels per subject."""
    N = len(rows)
    if N == 0:
        return {"n": 0}
    m = len(rows[0])
    p_i = []
    tot = Counter()
    for r in rows:
        c = Counter(r)
        tot.update(c)
        p_i.append((sum(v * v for v in c.values()) - m) / (m * (m - 1)))
    p_bar = sum(p_i) / N
    p_e = sum((tot[k] / (N * m)) ** 2 for k in tot)
    kf = (p_bar - p_e) / (1 - p_e) if p_e < 1 else float("nan")
    # per-category agreement (Fleiss 1971, table form)
    per_cat = {}
    for k in sorted(tot):
        num = sum(Counter(r)[k] ** 2 for r in rows)
        per_cat[k] = round((num - N * m * (tot[k] / (N * m)) ** 2) / (N * m * (m - 1)), 4)
    return {"n_subjects": N, "m_raters": m, "p_bar": p_bar, "p_e": p_e,
            "fleiss_kappa": kf, "per_category_agreement": per_cat}


def load(path: Path) -> dict[str, str] | None:
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("items", data.get("coded", []))
    return {d["doc_id"]: d.get("label") for d in data if d.get("label")}


def r4(x):
    return round(x, 4) if isinstance(x, float) and not math.isnan(x) else x


def main() -> None:
    sample = json.loads(SAMPLE.read_text(encoding="utf-8"))
    docs = [d["doc_id"] for d in sample["items"]]
    C = {c: load(p) for c, p in CODED.items()}

    res = {"at_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "criterion_register": "D-102",
           "inputs": {"sample_sha256": hashlib.sha256(SAMPLE.read_bytes()).hexdigest()}}
    for c, p in CODED.items():
        res["inputs"][f"coded_{c}_sha256"] = (hashlib.sha256(p.read_bytes()).hexdigest()
                                              if p.exists() else None)

    missing = [p.name for p in CODED.values() if not p.exists()]
    if missing:
        res["status"] = "pending"
        res["missing"] = missing
        OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
        print(json.dumps(res, ensure_ascii=False, indent=1))
        return

    res["status"] = "complete"
    ids = [d for d in docs if all(d in C[c] for c in "ABC")]
    res["n_docs"] = len(ids)

    # pairwise
    pw = {}
    for a, b in [("A", "B"), ("A", "C"), ("B", "C")]:
        pairs = [(C[a][d], C[b][d]) for d in ids]
        keep = [(x, y) for x, y in pairs if x != "UNRESOLVED" and y != "UNRESOLVED"]
        k = sum(1 for x, y in keep if x == y)
        lo, hi = wilson(k, len(keep))
        st = cohen(keep)
        pw[f"{a}_{b}"] = {"n_scored": len(keep), "n_agree": k,
                          "agreement": r4(k / len(keep)) if keep else None,
                          "wilson95": [r4(lo), r4(hi)],
                          "kappa": r4(st["kappa"]), "ac1": r4(st["ac1"]),
                          "pabak": r4(st["pabak"]), "n_classes": st["n_classes"]}
    res["pairwise"] = pw

    # Fleiss over complete records (no UNRESOLVED in the 3-way table)
    full = [d for d in ids if all(C[c][d] != "UNRESOLVED" for c in "ABC")]
    rows = [[C["A"][d], C["B"][d], C["C"][d]] for d in full]
    fl = fleiss(rows)
    res["fleiss"] = {"n_subjects": fl.get("n_subjects"), "m_raters": 3,
                     "p_bar": r4(fl.get("p_bar")), "p_e": r4(fl.get("p_e")),
                     "fleiss_kappa": r4(fl.get("fleiss_kappa")),
                     "per_category_agreement": fl.get("per_category_agreement")}
    res["n_excluded_unresolved"] = len(ids) - len(full)

    # distributions
    res["distribution"] = {c: {k: r4(v / len(C[c])) for k, v in
                               sorted(Counter(C[c].values()).items(), key=lambda t: -t[1])}
                           for c in "ABC"}

    # verdict — exactly as written in D-102
    p_ab = pw["A_B"]["agreement"] or 0.0
    p_ac = pw["A_C"]["agreement"] or 0.0
    p_bc = pw["B_C"]["agreement"] or 0.0
    min_p = min(p_ab, p_ac, p_bc)
    min_lo = min(pw["A_B"]["wilson95"][0] or 0, pw["A_C"]["wilson95"][0] or 0,
                 pw["B_C"]["wilson95"][0] or 0)
    kf = res["fleiss"]["fleiss_kappa"] or 0.0
    v = {"fleiss_kappa": kf, "min_pairwise_agreement": min_p,
         "min_pairwise_wilson_lo": min_lo,
         "typology_shared_reading": bool(min_p >= 0.80 and min_lo >= 0.70 and kf >= 0.60),
         "typology_no_shared_reading": bool(kf < 0.40 or min_p < 0.60)}
    if v["typology_shared_reading"]:
        v["verdict"] = "shared_reading"
    elif v["typology_no_shared_reading"]:
        v["verdict"] = "no_shared_reading"
    else:
        v["verdict"] = "intermediate"
    res["verdict"] = v

    tmp = OUT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, OUT)
    print(json.dumps({"pairwise": {k: {kk: vv[kk] for kk in
                                       ("n_agree", "n_scored", "agreement", "wilson95", "kappa")}
                                   for k, vv in pw.items()},
                      "fleiss": res["fleiss"], "verdict": v},
                     ensure_ascii=False, indent=1))
    print("sha", hashlib.sha256(OUT.read_bytes()).hexdigest())


if __name__ == "__main__":
    main()

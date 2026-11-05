#!/usr/bin/env python
"""H5 / H6 of D-98: inter-coder agreement between coder A and coder B.

Reads human/coded_A.json and human/coded_B.json (lists of {doc_id, label}),
plus human_sample.json and silver.jsonl, and writes
data/analysis/e11_ab_agreement.json.

The criteria are fixed by D-98, which was written before coder B produced any
answer. This script only computes; it must not be edited after B's data lands.
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
CODED_A = ROOT / "human/coded_A.json"
CODED_B = ROOT / "human/coded_B.json"
OUT = ROOT / "data/analysis/e11_ab_agreement.json"


def wilson(k: int, n: int, z: float = 1.959963985) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def kappa(pairs: list[tuple[str, str]]) -> dict:
    n = len(pairs)
    if n == 0:
        return {"po": float("nan"), "pe": float("nan"), "kappa": float("nan"),
                "ac1": float("nan"), "pabak": float("nan"),
                "n_classes_observed": 0, "prevalence": {}}
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
    # Bennett-free prevalence index: |CA - CB| style index on the modal class
    modal = max(keys, key=lambda k: ca[k] + cb[k])
    prevalence_index = abs(ca[modal] - cb[modal]) / n
    return {"po": po, "pe": pe, "kappa": kp, "ac1": ac1, "pabak": pabak,
            "n_classes_observed": q,
            "prevalence_index": prevalence_index,
            "prevalence": {k: round(ca[k] / n, 4) for k in sorted(keys)}}


def r4(x):
    return round(x, 4) if isinstance(x, float) and not math.isnan(x) else x


def analyse(pairs_all: list[tuple[str, str]], tag: str) -> dict:
    keep = [(a, b) for a, b in pairs_all if a != "UNRESOLVED" and b != "UNRESOLVED"]
    n_all, n_unres = len(pairs_all), len(pairs_all) - len(keep)
    k = sum(1 for a, b in keep if a == b)
    n = len(keep)
    lo, hi = wilson(k, n)
    km = kappa(keep)
    out = {
        "_tag": tag,
        "n_pairs": n_all,
        "n_excluded_unresolved": n_unres,
        "n_scored": n,
        "n_agree": k,
        "agreement": r4(k / n) if n else None,
        "wilson95": [r4(lo), r4(hi)],
        "po": r4(km["po"]), "pe": r4(km["pe"]),
        "kappa": r4(km["kappa"]), "ac1": r4(km["ac1"]), "pabak": r4(km["pabak"]),
        "n_classes_observed": km["n_classes_observed"],
        "prevalence_index": r4(km["prevalence_index"]),
        "prevalence": km["prevalence"],
    }
    # sensitivity: any UNRESOLVED -> OTHER
    p2 = [("OTHER" if a == "UNRESOLVED" else a, "OTHER" if b == "UNRESOLVED" else b)
          for a, b in pairs_all]
    k2 = sum(1 for a, b in p2 if a == b)
    out["sensitivity_unresolved_as_other"] = {
        "n": len(p2), "n_agree": k2,
        "agreement": r4(k2 / len(p2)) if p2 else None,
        "wilson95": [r4(x) for x in wilson(k2, len(p2))],
        "kappa": r4(kappa(p2)["kappa"]),
    }
    return out


def confusion(pairs: list[tuple[str, str]]) -> dict:
    c: dict[str, Counter] = {}
    for a, b in pairs:
        c.setdefault(a, Counter())[b] += 1
    return {a: dict(v) for a, v in sorted(c.items())}


def load(path: Path) -> dict[str, str] | None:
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("items", data.get("coded", []))
    return {d["doc_id"]: d.get("label") for d in data if d.get("label")}


def main() -> None:
    A = load(CODED_A)
    B = load(CODED_B)
    sample = json.loads(SAMPLE.read_text(encoding="utf-8"))
    stratum = {x["doc_id"]: x["stratum"] for x in sample["items"]}
    silver = {r["doc_id"]: r for r in
              (json.loads(l) for l in SILVER.open(encoding="utf-8"))}

    res = {"at_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "criterion_register": "D-98",
           "inputs": {"sample_sha256": hashlib.sha256(SAMPLE.read_bytes()).hexdigest(),
                      "silver_sha256": hashlib.sha256(SILVER.read_bytes()).hexdigest(),
                      "coded_A_sha256": hashlib.sha256(CODED_A.read_bytes()).hexdigest()
                      if CODED_A.exists() else None}}

    if A is None or B is None:
        res["status"] = "pending"
        res["missing"] = [p.name for p in (CODED_A, CODED_B) if not p.exists()]
        OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
        print(json.dumps(res, ensure_ascii=False, indent=1))
        return

    res["status"] = "complete"
    res["inputs"]["coded_B_sha256"] = hashlib.sha256(CODED_B.read_bytes()).hexdigest()

    docs = [d for d in sample["items"] if d["doc_id"] in A and d["doc_id"] in B]
    pairs_ab = [(A[d["doc_id"]], B[d["doc_id"]]) for d in docs]
    s1 = [(A[d["doc_id"]], B[d["doc_id"]]) for d in docs if d["stratum"] == "srs"]
    s2 = [(A[d["doc_id"]], B[d["doc_id"]]) for d in docs if d["stratum"] == "disagreement"]

    res["H5_A_vs_B_all80"] = analyse(pairs_ab, "H5")
    res["H5_A_vs_B_s1"] = analyse(s1, "H5-S1")
    res["H5_A_vs_B_s2"] = analyse(s2, "H5-S2")
    res["confusion_A_rows_B_cols"] = confusion(pairs_ab)

    # H6: instrument vs each coder
    pa = [(silver[d["doc_id"]]["violation_category"], A[d["doc_id"]])
          for d in docs if d["doc_id"] in silver]
    pb = [(silver[d["doc_id"]]["violation_category"], B[d["doc_id"]])
          for d in docs if d["doc_id"] in silver]
    ia, ib = analyse(pa, "H6-IA"), analyse(pb, "H6-IB")
    res["H6_I_vs_A"] = ia
    res["H6_I_vs_B"] = ib
    res["confusion_I_rows_A_cols"] = confusion(pa)
    res["confusion_I_rows_B_cols"] = confusion(pb)

    # S1-only variants of the instrument agreement, so that the H6 attribution
    # can be read against the preregistered H1 figure (0.4833, S1, n=60).
    s1ids = {d["doc_id"] for d in docs if d["stratum"] == "srs"}
    res["H6_I_vs_A_s1"] = analyse(
        [(silver[d2]["violation_category"], A[d2]) for d2 in s1ids if d2 in silver],
        "H6-IA-S1")
    res["H6_I_vs_B_s1"] = analyse(
        [(silver[d2]["violation_category"], B[d2]) for d2 in s1ids if d2 in silver],
        "H6-IB-S1")

    def other_share(m: dict[str, str]) -> float:
        n = len(m)
        return r4(sum(1 for v in m.values() if v == "OTHER") / n) if n else None

    res["H6_other_share"] = {"A": other_share(A), "B": other_share(B)}
    res["H6_p_IA_minus_p_IB"] = r4((ia["agreement"] or 0) - (ib["agreement"] or 0))

    # H5 verdict — exactly as written in D-98
    h5 = res["H5_A_vs_B_all80"]
    p_ab = h5["agreement"] or 0.0
    lo = h5["wilson95"][0]
    kp = h5["kappa"] if isinstance(h5["kappa"], float) else 0.0
    v = {
        "p_AB": p_ab, "wilson_lo": lo, "kappa": kp,
        "human_recoverable": bool(p_ab >= 0.80 and lo >= 0.70 and kp >= 0.60),
        "human_not_recoverable": bool(p_ab < 0.60 or kp < 0.40),
    }
    if v["human_recoverable"]:
        v["verdict"] = "human_recoverable"
    elif v["human_not_recoverable"]:
        v["verdict"] = "human_not_recoverable"
    else:
        v["verdict"] = "intermediate"

    # H6 attribution, only when p_AB is high and the two instrument agreements concur
    diff = abs(res["H6_p_IA_minus_p_IB"] or 0)
    v["instrument_systematic_deviation"] = bool(
        v["human_recoverable"] and ia["agreement"] is not None
        and ib["agreement"] is not None and diff <= 0.10)
    res["verdict"] = v

    tmp = OUT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, OUT)
    print(json.dumps({"H5": res["H5_A_vs_B_all80"], "verdict": v,
                      "other_share": res["H6_other_share"],
                      "p_IA": ia["agreement"], "p_IB": ib["agreement"]},
                     ensure_ascii=False, indent=1))
    print("sha", hashlib.sha256(OUT.read_bytes()).hexdigest())


if __name__ == "__main__":
    main()

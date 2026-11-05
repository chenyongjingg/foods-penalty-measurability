"""Cross-jurisdiction typology comparison (Plan §4.3, E5).

CN (cfws + municipal) vs US (openFDA): category distribution, chi-square with
an expected-count check; Fisher's exact is used for the collapsed 2x2
(table-vs-fraud) when any expected cell < 5. Descriptive report only — no
claim about EU unless RASFF data are available (D3b degrades non-blocking).
"""
from __future__ import annotations

import json
from collections import Counter

from scipy import stats

from ..common import cfg, get_logger, path_of, utc_iso, write_json
from ..manifest import Manifest

CATS = ["FORGED_INSPECTION_REPORT", "TAMPERED_TRACEABILITY", "FAKE_CERTIFICATION",
        "FALSE_LABELING", "UNLICENSED_OPERATION", "OTHER"]


def run() -> dict:
    # E5 is a category-distribution comparison, not a separate corpus
    # definition: it uses the same high-confidence main corpus as every other
    # experiment (Plan §5.2). The floor band is reported alongside as a
    # sensitivity so that a reader can see how much the comparison depends on
    # the tier rule, but it is never the headline figure.
    tier_sets = {"high": ("high",), "high_medium": ("high", "medium"),
                 "all": ("high", "medium", "low")}
    counts_by_tier = {k: {"cn": Counter(), "us": Counter()} for k in tier_sets}
    # D-49: the high tier is an agreement-selected subset whose selection rate
    # differs by document genre, and the English and Chinese corpora are
    # selected at different intensities (37.1% vs 10.6% on the 2026-11-04
    # corpus). An estimate on the high tier therefore compares two samples that
    # were filtered differently. The rates are emitted with the estimate so the
    # asymmetry travels with the number instead of living in a log line.
    pool = {"cn": Counter(), "us": Counter()}
    # Categories live in the silver file; read it directly.
    silver = path_of("data") / "silver" / "silver.jsonl"
    if silver.exists():
        with open(silver, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                r = json.loads(line)
                grp = "cn" if r["source"] in ("cfws", "municipal") else "us"
                pool[grp][r.get("tier")] += 1
                for name, tset in tier_sets.items():
                    if r["tier"] in tset:
                        counts_by_tier[name][grp][r["violation_category"]] += 1
    counts = counts_by_tier["high"]
    outdir = path_of("data") / "analysis"
    selection = {}
    for grp in ("cn", "us"):
        n_total = sum(pool[grp].values())
        n_high = pool[grp].get("high", 0)
        selection[grp] = {"n_labelled": n_total, "n_high": n_high,
                          "high_rate": round(n_high / n_total, 4) if n_total else None}
    rates = [selection[g]["high_rate"] for g in ("cn", "us")]

    # How far does the high-tier filter move the category distribution?
    # Total variation distance between the high-tier distribution and the
    # all-tier distribution, per jurisdiction. 0 = the filter changes nothing;
    # 1 = the two distributions share no mass. This separates "we compared the
    # main corpus" from "we compared whatever survived the agreement filter".
    def _tvd(a: Counter, b: Counter) -> float | None:
        na, nb = sum(a.values()), sum(b.values())
        if not na or not nb:
            return None
        keys = set(a) | set(b)
        return round(0.5 * sum(abs(a.get(k, 0) / na - b.get(k, 0) / nb)
                               for k in keys), 4)

    diagnostic = {g: {"high_vs_all_tvd": _tvd(counts_by_tier["high"][g],
                                              counts_by_tier["all"][g]),
                      "high_counts": dict(counts_by_tier["high"][g]),
                      "all_counts": dict(counts_by_tier["all"][g])}
                  for g in ("cn", "us")}
    res = {"counts": {k: dict(v) for k, v in counts.items()},
           "tier": "high",
           "selection": selection,
           "selection_diagnostic": diagnostic,
           "selection_asymmetry": (round(max(rates) / min(rates), 3)
                                   if all(rates) else None),
           "selection_note": (
               "The two jurisdictions are filtered into the main corpus at "
               "different rates (D-49); the category comparison is conditional "
               "on agreement-selected document genre on each side. Report these "
               "rates beside the test, not instead of it."),
           "sensitivity_tiers": {name: {grp: dict(c) for grp, c in d.items()}
                                 for name, d in counts_by_tier.items()},
           "at_utc": utc_iso()}
    if sum(counts["cn"].values()) < 5 or sum(counts["us"].values()) < 5:
        res["status"] = "insufficient_data"
        write_json(outdir / "compare.json", res)
        return res
    table_all = [[counts["cn"].get(c, 0) for c in CATS],
                 [counts["us"].get(c, 0) for c in CATS]]
    # D-60: a category absent from both jurisdictions is a zero column. scipy
    # raises ValueError ("table of expected frequencies has a zero element")
    # for such a table, which killed the whole compare step before it could
    # write anything — leaving a stale compare.json for the E5 gate. A zero
    # column contributes nothing to chi-square, so drop it and run the same
    # test on the categories that occur. No threshold or test choice changes.
    keep = [i for i in range(len(CATS)) if table_all[0][i] + table_all[1][i] > 0]
    if len(keep) < 2:
        res["status"] = "insufficient_data"
        res["note"] = "fewer than two categories observed in the corpus"
        write_json(outdir / "compare.json", res)
        return res
    table = [[row[i] for i in keep] for row in table_all]

    # D-51: on the 2026-11-04 corpus the Chinese main corpus is 95% a single
    # category while the full Chinese set carries five, so the tier filter
    # removes the variation the comparison is meant to test (TVD 0.3335 on the
    # Chinese side, 0.0113 on the English side). A distribution with one modal
    # category at >=90%, or fewer than two categories with >=5 documents, cannot
    # support a typology comparison: the resulting test would rest on a handful
    # of documents. The criterion is pre-registered in DEVIATIONS.md D-51.
    def _profile(counter: Counter) -> dict:
        n = sum(counter.values())
        if not n:
            return {"n": 0}
        modal, mcount = counter.most_common(1)[0]
        return {"n": n, "modal_category": modal,
                "modal_share": round(mcount / n, 4),
                "n_categories_ge5": sum(1 for v in counter.values() if v >= 5)}

    profile = {g: _profile(counts[g]) for g in ("cn", "us")}
    degenerate = [g for g, pr in profile.items()
                  if not pr.get("n") or pr["modal_share"] >= 0.90
                  or pr["n_categories_ge5"] < 2]
    res["main_corpus_profile"] = profile
    res["main_corpus_estimable"] = not degenerate

    chi2, p, dof, exp = stats.chi2_contingency(table)
    min_exp = float(exp.min())
    res.update({"chi2": float(chi2), "p": float(p), "dof": int(dof),
                "min_expected": round(min_exp, 3)})
    if min_exp < float(cfg("analysis.chi2_min_expected", 5)):
        # The chi-square approximation is invalid when a cell's expected count
        # is below 5. The number is still computed (it is what a reader would
        # get), but it must not be the inferential statistic: it is moved under
        # `chi2_unreliable` and the test of record becomes Fisher's exact on a
        # collapsed 2x2 (forged-report vs all other categories).
        a = [counts["cn"].get("FORGED_INSPECTION_REPORT", 0),
             counts["us"].get("FORGED_INSPECTION_REPORT", 0)]
        rest_cn = sum(counts["cn"].values()) - a[0]
        rest_us = sum(counts["us"].values()) - a[1]
        odds, fp = stats.fisher_exact([[a[0], rest_cn], [a[1], rest_us]])
        res["chi2_unreliable"] = {"chi2": res.pop("chi2"), "p": res.pop("p"),
                                  "dof": res.pop("dof"),
                                  "note": "min expected count < 5; not the test of record"}
        res.update({"collapsed_fisher": {"odds_ratio": float(odds), "p": float(fp),
                                         "table": [[a[0], rest_cn], [a[1], rest_us]]},
                    "status": "ok_fisher_collapsed", "primary_test": "fisher_collapsed"})
    else:
        res.update({"status": "ok_chi2", "primary_test": "chi2_full"})
    if degenerate:
        # The test is kept for audit, but it is no longer the test of record.
        res["status_on_main_corpus"] = res.get("status")
        res["test_on_degenerate_table"] = {
            "primary_test": res.pop("primary_test", None),
            "collapsed_fisher": res.pop("collapsed_fisher", None),
            "chi2_unreliable": res.pop("chi2_unreliable", None),
            "note": "computed but not the test of record (D-51)"}
        res["status"] = "not_estimable_degenerate_main_corpus"
        res["not_estimable"] = {
            "reason": "main-corpus category distribution is degenerate",
            "degenerate_jurisdictions": degenerate,
            "criterion": ("modal category >= 90% of documents, or fewer than two "
                          "categories with >= 5 documents"),
            "exploratory_alternative": ("all-tier distributions in "
                                        "sensitivity_tiers.all are descriptive "
                                        "only; they are not selected for "
                                        "annotation confidence")}
    write_json(outdir / "compare.json", res)
    get_logger("analyze.compare").info("compare: %s", res["status"])
    return res

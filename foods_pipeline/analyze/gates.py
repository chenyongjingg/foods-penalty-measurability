"""Experiment gate evaluation (Plan §6.1) and degradation ladder (Plan §6.2)."""
from __future__ import annotations

import json

from ..common import cfg, get_logger, path_of, read_json, utc_iso, write_json


def run() -> dict:
    A = path_of("data") / "analysis"
    e1 = read_json(path_of("data") / "metrics" / "e1.json", {}) or {}
    net = read_json(A / "network_metrics.json", {}) or {}
    atk = read_json(A / "attack_tolerance.json", {}) or {}
    surv = read_json(A / "survival.json", {}) or {}
    haw = read_json(A / "hawkes.json", {}) or {}
    disp = read_json(A / "displacement.json", {}) or {}
    comp = read_json(A / "compare.json", {}) or {}
    shk = read_json(A / "shocks.json", {}) or {}
    sens = read_json(A / "sensitivity.json", {}) or {}

    gates, actions = {}, []

    # E1 is pooled, but the pooled figure can hide a failing side: report the
    # per-language agreement and the P095 type-shrink decision next to it.
    gates["E1"] = {"status": e1.get("status", "no_data"),
                   "mean_agreement": e1.get("mean_agreement"),
                   "by_lang": {k: v.get("mean_agreement")
                               for k, v in (e1.get("by_lang") or {}).items()},
                   "tau_sensitivity": {k: v.get("mean_agreement")
                                       for k, v in (e1.get("tau_sensitivity") or {}).items()},
                   "ladder": e1.get("ladder"),
                   "anchor_f1": (e1.get("anchor_f1") or {}).get("f1"),
                   "thresholds": e1.get("thresholds")}
    if str(e1.get("status", "")).startswith("failed"):
        actions.append("E1 fallback: self-consistency -> self-training / entity shrinkage "
                       "(see state kv actions:ladder)")
    if (e1.get("ladder") or {}).get("triggered"):
        actions.append(f"P095 type shrinkage: stable types "
                       f"{(e1['ladder'].get('stable_types') or [])}, "
                       f"agreement on them {e1['ladder'].get('agreement_shrunk')}")

    # Anchor macro-F1 divides by the number of labels on either side, so a
    # class with one document moves the mean by 1/k (D-18). On the v2 corpus
    # that is decisive: macro 0.25 against micro 0.81. The gate keeps the
    # pre-registered statistic, but the support travels with it so the number
    # cannot be read as an extraction-quality verdict on its own (D-58).
    try:
        from ..label.anchors import anchor_pairs, anchor_support
        _silver = path_of("data") / "silver" / "silver.jsonl"
        _recs = []
        if _silver.exists():
            with open(_silver, "r", encoding="utf-8") as fh:
                for line in fh:
                    if line.strip():
                        _recs.append(json.loads(line))
        if _recs:
            _pairs, _fact_only = anchor_pairs(_recs)
            sup = anchor_support(_pairs)
            sup["fact_only_docs"] = _fact_only
            gates["E1"]["anchor_support"] = sup
            if (sup.get("n_classes_support_lt3") or 0) >= 2:
                actions.append(
                    f"E1 anchor macro is decided by {sup['n_classes_support_lt3']} "
                    f"classes with <3 documents (macro "
                    f"{sup['macro_all_classes']} vs micro {sup['micro']}, n={sup['n']}). "
                    "Report per-class F1 and support; do not quote macro alone (D-58).")
    except Exception as exc:  # never let diagnostics hide the gate itself
        gates["E1"]["anchor_support"] = {"error": str(exc)}

    # D-63/D-68: the headline agreement in e1.json is the post-ladder mixture
    # whenever the corpus has voted documents. The pre-registered estimate is
    # the single-shot one, reconstructed from the archives and written by
    # scripts/e1_preladder.py. Both travel with the gate; neither replaces the
    # other, and the status is never taken from the reconstructed value.
    pre = read_json(path_of("data") / "metrics" / "e1_preladder.json", {}) or {}
    if (pre.get("e1") or {}).get("mean_agreement") is not None:
        pe, pv = pre["e1"], pre.get("provenance") or {}
        gates["E1"]["pre_registered"] = {
            "mean_agreement": pe.get("mean_agreement"), "status": pe.get("status"),
            "by_lang": {k: v.get("mean_agreement")
                        for k, v in (pe.get("by_lang") or {}).items()},
            "n_scored": pe.get("n"),
            "n_substituted_from_archive": pv.get("n_substituted_from_archive"),
            "n_voted_without_archive": pv.get("n_voted_without_archive"),
            "as_of": pre.get("at_utc"),
            "note": ("single-shot channels for every document; voted documents "
                     "scored on their archived pre-ladder channels. This is the "
                     "pre-registered E1; the headline figure above is the "
                     "post-ladder mixture (D-63).")}
        lost = pv.get("n_voted_without_archive") or 0
        if lost:
            actions.append(
                f"pre-registered E1 excludes {lost} voted documents whose "
                "single-shot channels were overwritten before any archive was "
                "taken; the ladder now snapshots the corpus first (D-68).")

    n = net.get("n_nodes", 0)
    tgt, floor = int(cfg("analysis.e2_nodes_target", 800)), int(cfg("analysis.e2_nodes_floor", 400))
    # D-50: E2 counts nodes, but an edge needs two actor mentions in the same
    # document. Expansion raises n_nodes without raising that count, so the
    # floor can be met by adding isolated nodes. The gate carries the binding
    # constraint (multi-actor documents) and the saturation ratio so "target
    # met" cannot be read as "network estimated".
    cov = net.get("actor_coverage") or {}
    max_edges = cov.get("max_edges_possible_by_structure")
    # Distinct nodes, not mentions: build() drops repeated names, so a document
    # that names the same operator twice can still only contribute one node.
    if "docs_with_two_or_more_actor_nodes" in cov:
        multi = cov.get("docs_with_two_or_more_actor_nodes")
        multi_key = "docs_with_two_or_more_actor_nodes"
    else:
        multi = cov.get("docs_with_two_or_more_actor_mentions")
        multi_key = "docs_with_two_or_more_actor_mentions"
    docs = cov.get("main_corpus_docs")
    gates["E2"] = {"n_nodes": n, "status": "target_met" if n >= tgt
                   else ("floor_met" if n >= floor else "downgraded"),
                   "note": "" if n >= floor else "case-chain typology replaces network metrics",
                   "n_edges": net.get("n_edges"),
                   "binding_constraint": {
                       "main_corpus_docs": docs,
                       multi_key: multi,
                       "docs_with_provider": cov.get("docs_with_provider"),
                       "docs_with_provider_and_end_user": cov.get(
                           "docs_with_provider_and_end_user"),
                       "max_edges_possible_by_structure": max_edges,
                       "multi_actor_doc_share": (round(multi / docs, 4)
                                                 if docs and multi is not None else None),
                       "edge_saturation": (round(net.get("n_edges", 0) / max_edges, 4)
                                           if max_edges else None),
                       "note": ("Edges are bounded by documents that name two "
                                "actors. Saturation 1.0 means the graph already "
                                "contains every edge the corpus permits (D-49).")},
                   "dataset_lag_s": net.get("dataset_lag_s"),
                   "stale_dataset": net.get("stale_dataset")}
    if max_edges is not None and docs and multi is not None and multi < 0.1 * docs:
        actions.append(
            f"E2 network is structurally bounded: only {multi} of {docs} main-corpus "
            f"documents name two actors, allowing at most {max_edges} edges. "
            "Expansion raises n_nodes but not this count — report Plan §6 as "
            "not_estimable rather than expanding further for the network (D-50).")
    if n < floor:
        # Plan §6.2 assigns expansion to the pipeline. The ladder is automatic
        # but pre-registered: analyze/expansion.py takes the next batch from
        # config/expansion_queries.yaml at the head of the next cycle.
        try:
            from .expansion import plan as expansion_plan
            pl = expansion_plan()
            gates["E2"]["expansion"] = {"action": pl.get("action"),
                                        "batch": (pl.get("batch") or {}).get("id"),
                                        "reason": pl.get("reason"),
                                        "batches_done": pl.get("batches_done")}
            actions.append(f"E2 below floor ({n}/{floor}): automatic expansion -> "
                           f"{pl.get('action')} {(pl.get('batch') or {}).get('id', '')} "
                           f"({pl.get('reason', '')})")
        except Exception as exc:  # noqa: BLE001
            gates["E2"]["expansion"] = {"action": "error", "reason": str(exc)}
            actions.append(f"E2 below floor ({n}/{floor}): expansion planner failed: {exc}")
    if net.get("stale_dataset"):
        actions.append("network built from a dataset older than silver.jsonl — "
                       "re-run extract before quoting these numbers")

    gates["E3"] = {"attack": atk.get("status"), "h1_supported": atk.get("h1_supported"),
                   "h3_supported": atk.get("h3_supported"),
                   "survival": surv.get("status"), "hawkes": haw.get("status"),
                   "hawkes_p": haw.get("lr_p"), "branching_ratio": haw.get("branching_ratio"),
                   "hawkes_nonparametric": haw.get("nonparametric"),
                   "note": "negative or inconclusive results are reported, not hidden"}

    # H2 (governance shocks): the D4 event calendar plus per-shock before/after
    # rate contrasts.  `insufficient` here means the corpus cannot test H2 yet;
    # it is not a null result and must not be written as one.
    gates["H2"] = {"n_gov_events": shk.get("n_gov_events"),
                   "n_gov_events_raw": shk.get("n_gov_events_raw"),
                   "n_evaluable": shk.get("n_evaluable"),
                   "status": shk.get("status"), "note": shk.get("note")}
    gates["sensitivity"] = {k: (v.get("n_nodes") if isinstance(v, dict) else None)
                            for k, v in (sens.get("variants") or {}).items()}
    kw = read_json(A / "keyword_sensitivity.json", {}) or {}
    if kw:
        gates["keywords"] = {"frame": kw.get("frame"),
                             "admitted_share": kw.get("plan_rule_admitted_share"),
                             "variants": {k: {"admitted": v.get("admitted"),
                                              "jaccard": (v.get("vs_baseline") or {}).get("jaccard"),
                                              "high_tier_retained": v.get("high_tier_retained")}
                                          for k, v in (kw.get("variants") or {}).items()}}

    ne = disp.get("n_events", 0)
    gates["E4"] = {"n_events": ne, "status": disp.get("status"),
                   "note": "" if ne >= int(cfg("analysis.e4_events_floor", 8))
                   else "merged into qualitative discussion (Plan §6.2 E4)"}

    # D-51: when the main corpus is degenerate the comparison is not the test
    # of record, so the primary_test/chi2/fisher keys are read from wherever
    # compare.py left them and the profile travels with them.
    _moved = comp.get("test_on_degenerate_table") or {}
    gates["E5"] = {"status": comp.get("status"),
                   "primary_test": comp.get("primary_test") or _moved.get("primary_test"),
                   "chi2": comp.get("chi2"),
                   "p": comp.get("p"),
                   "fisher": comp.get("collapsed_fisher") or _moved.get("collapsed_fisher"),
                   "chi2_unreliable": comp.get("chi2_unreliable") or _moved.get("chi2_unreliable"),
                   "estimable": comp.get("main_corpus_estimable"),
                   "profile": comp.get("main_corpus_profile"),
                   "selection_asymmetry": comp.get("selection_asymmetry")}
    if comp.get("main_corpus_estimable") is False:
        actions.append(
            "E5 main-corpus comparison is degenerate (D-51): "
            + ", ".join(f"{g} modal {p.get('modal_category')} "
                        f"{100*p.get('modal_share', 0):.0f}%"
                        for g, p in (comp.get("main_corpus_profile") or {}).items())
            + ". Report E5 as not_estimable on the main corpus; all-tier "
              "distributions are descriptive only.")

    # D-61: an analyze submodule that raises leaves last cycle's JSON in place,
    # so a gate can read a stale product as if it were fresh. cmd_analyze now
    # records which modules failed; carry that into gates.json and the action
    # list so a stale read can never be silent.
    ms = read_json(A / "_module_status.json", {}) or {}
    failed = ms.get("failed_modules") or {}
    gates["module_status"] = {"failed_modules": failed,
                              "receipt_present": bool(ms),
                              "as_of": ms.get("at_utc"),
                              "note": ("A module listed here did not run this cycle; "
                                       "the gate numbers below it are from an older "
                                       "file and must not be quoted as current.")}
    for mod, err in failed.items():
        actions.append(f"analyze module '{mod}' failed this cycle ({err}); its "
                       "product on disk is stale (D-61).")

    all_cn = (e1.get("tier_counts") or {})
    if gates["E1"]["status"] == "failed" and gates["E2"]["status"] == "downgraded" and ne < 8:
        actions.append("GLOBAL FALLBACK: dataset + baseline + method-evaluation Communication "
                       "(Plan §6.2 全局兜底)")
    out = {"gates": gates, "actions": actions, "at_utc": utc_iso()}
    write_json(A / "gates.json", out)
    get_logger("analyze.gates").info("gates: %s", {k: v.get("status") for k, v in gates.items()})
    return out

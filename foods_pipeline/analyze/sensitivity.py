"""Corpus-definition sensitivity for the network estimates (Plan §5.2 / §6.2).

The main estimate uses the high-confidence tier only.  The pre-registered
sensitivity question is whether the network conclusions survive when the
0.75-0.85 floor band (medium) is added, and — reported separately as
exploratory — when low-tier documents are added too.  If the three variants
disagree in sign or in order of magnitude, the tier rule is doing substantive
work and the paper must say so rather than quoting the main estimate alone.

A second axis is the node taxonomy (D-26): the main graph is actors only; the
five-type graph adds TACTIC/DOCUMENT/JURISDICTION nodes.  Both are reported on
the same high-tier corpus so the effect of the taxonomy is separable from the
effect of the tier rule.

This module deliberately reports *descriptive* network statistics.  It does
not re-run the attack or Hawkes analyses on the looser corpora, because those
have their own tier assumptions and pooling them here would double-count.
"""
from __future__ import annotations

from ..common import cfg, get_logger, path_of, utc_iso, write_json
from .network import ALL_NODE_TYPES, build, load_edges, metrics, node_types

VARIANTS = [
    ("high", ("high",), "main estimate (Plan §5.2 high-confidence tier)"),
    ("high_medium", ("high", "medium"), "pre-registered sensitivity (+ floor band)"),
    ("all_tiers", ("high", "medium", "low"), "exploratory only (adds low tier)"),
]


def run() -> dict:
    out = {"variants": {}, "at_utc": utc_iso()}
    base = None
    for name, tiers, note in VARIANTS:
        docs, _ = load_edges(tiers=tiers)
        if not docs:
            out["variants"][name] = {"status": "no_documents", "tiers": list(tiers)}
            continue
        g = build(docs)
        m = metrics(g)
        m.update({"tiers": list(tiers), "note": note, "n_docs": len(docs)})
        out["variants"][name] = m
        if name == "high":
            base = m

    # Deltas are computed against the main estimate so the table reads as a
    # robustness check, not as three competing results.
    if base and base.get("n_nodes"):
        for name, v in out["variants"].items():
            if name == "high" or "n_nodes" not in v:
                continue
            v["delta_vs_main"] = {
                k: (round(v[k] - base[k], 6) if isinstance(v.get(k), (int, float))
                    and isinstance(base.get(k), (int, float)) else None)
                for k in ("n_nodes", "n_edges", "density", "gcc_frac", "modularity")}

    # Node-taxonomy sensitivity (D-26). The main graph is actor-only; this
    # shows what the type-level document/tactic phrases and the administrative
    # units do to the same statistics on the same corpus.
    docs_high, _ = load_edges(tiers=("high",))
    out["taxonomy"] = {}
    for name, types in (("actors", node_types()), ("all_entity_types", ALL_NODE_TYPES)):
        g = build(docs_high, types=types)
        m = metrics(g)
        m["node_types_allowed"] = list(types)
        m["n_docs"] = len(docs_high)
        out["taxonomy"][name] = m

    out["main_variant"] = "high"
    out["status"] = "ok" if base and base.get("n_nodes") else "no_main_corpus"
    write_json(path_of("data") / "analysis" / "sensitivity.json", out)
    get_logger("analyze.sensitivity").info(
        "sensitivity: %s", {k: v.get("n_nodes") for k, v in out["variants"].items()})
    return out

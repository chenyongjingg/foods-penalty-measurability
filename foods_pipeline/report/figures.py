"""L6 figures (Plan §5.1: "Foods 风格图表模板").

Every figure is generated from an artefact that a gate already reads, so a
figure cannot say more than the gate does. Two rules:

* a panel whose statistic was not estimated (gate downgraded) is drawn as a
  status card, never as an empty or fabricated curve — a reviewer must be able
  to tell "we did not estimate this" from "the estimate was zero";
* the corpus size and the tier the panel rests on are printed inside the panel,
  so a figure copied into the manuscript carries its own denominator.

Output: reports/figures/figN_*.png (300 dpi) + figures.json with the reading
behind each panel.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from ..common import cfg, iter_jsonl, path_of, read_json, utc_iso, write_json  # noqa: E402

DPI = 300
UI = "#2b2b2b"
ACCENT = "#1f4e79"
ACCENT2 = "#c0504d"
MUTED = "#8c8c8c"
CATS = ["FORGED_INSPECTION_REPORT", "TAMPERED_TRACEABILITY", "FAKE_CERTIFICATION",
        "FALSE_LABELING", "UNLICENSED_OPERATION", "OTHER"]
# English labels: the manuscript is English and the pod's default font has no
# CJK glyphs (Chinese labels would render as tofu boxes in the PNG).
CAT_EN = {"FORGED_INSPECTION_REPORT": "forged report", "TAMPERED_TRACEABILITY": "traceability",
          "FAKE_CERTIFICATION": "fake certification", "FALSE_LABELING": "false labelling",
          "UNLICENSED_OPERATION": "unlicensed", "OTHER": "other"}


def _style() -> None:
    plt.rcParams.update({
        "figure.dpi": DPI, "savefig.dpi": DPI, "font.size": 8,
        "axes.edgecolor": UI, "axes.labelcolor": UI, "text.color": UI,
        "xtick.color": UI, "ytick.color": UI, "axes.spines.top": False,
        "axes.spines.right": False, "font.family": "DejaVu Sans",
        "savefig.bbox": "tight", "figure.facecolor": "white",
    })


def _outdir() -> Path:
    d = path_of("reports") / "figures"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _status_card(ax, title: str, status: str, note: str) -> None:
    ax.axis("off")
    ax.text(0.5, 0.62, status.upper(), ha="center", va="center", fontsize=11,
            color=ACCENT2, transform=ax.transAxes)
    ax.text(0.5, 0.34, note, ha="center", va="center", fontsize=7.5, color=MUTED,
            wrap=True, transform=ax.transAxes)
    ax.set_title(title, fontsize=9, loc="left")


def _load_silver() -> list[dict]:
    p = path_of("data") / "silver" / "silver.jsonl"
    if not p.exists():
        return []
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]


# --- fig 1: corpus flow ---------------------------------------------------
def fig_flow(out: Path) -> dict:
    from ..manifest import Manifest
    m = Manifest()
    counts = m.counts()
    stages = ["raw", "clean", "labeled", "extracted"]
    srcs = sorted(counts)
    fig, ax = plt.subplots(figsize=(6.4, 2.6))
    width = 0.8 / max(1, len(srcs))
    for i, s in enumerate(srcs):
        vals = [counts[s].get(k, 0) for k in stages]
        xs = [j + i * width for j in range(len(stages))]
        bars = ax.bar(xs, vals, width=width * 0.92, label=s)
        for x, v in zip(xs, vals):
            ax.text(x, v, str(v), ha="center", va="bottom", fontsize=6)
    ax.set_xticks(range(len(stages)))
    ax.set_xticklabels(["raw", "clean (D1' admitted)", "labelled", "extracted"])
    ax.set_ylabel("documents")
    ax.set_title("Corpus flow by source", loc="left", fontsize=9)
    ax.legend(frameon=False, fontsize=7)
    fig.savefig(out)
    plt.close(fig)
    return {"panel": "corpus flow", "counts": {s: counts[s] for s in srcs}}


# --- fig 2: E1 agreement --------------------------------------------------
def fig_e1(out: Path) -> dict:
    recs = _load_silver()
    if not recs:
        fig, ax = plt.subplots(figsize=(6.4, 2.4))
        _status_card(ax, "E1 dual-channel agreement", "no data", "silver.jsonl is empty")
        fig.savefig(out)
        plt.close(fig)
        return {"panel": "E1 agreement", "status": "no_data"}
    target = float(cfg("label.agreement_target", 0.85))
    floor = float(cfg("label.agreement_floor", 0.75))
    fig, ax = plt.subplots(figsize=(6.4, 2.8))
    bins = [i / 20 for i in range(21)]
    for lang, color in (("zh", ACCENT), ("en", ACCENT2)):
        vals = [r["metrics"]["agreement_f1"] for r in recs if r.get("lang") == lang]
        if vals:
            ax.hist(vals, bins=bins, alpha=0.55, label=f"{lang} (n={len(vals)})",
                    color=color, edgecolor="white", linewidth=0.4)
    ax.axvline(target, color=UI, lw=0.8, ls="--")
    ax.axvline(floor, color=MUTED, lw=0.8, ls=":")
    ax.text(target, ax.get_ylim()[1] * 0.96, " target 0.85", fontsize=6.5, va="top")
    ax.text(floor, ax.get_ylim()[1] * 0.88, " floor 0.75", fontsize=6.5, va="top",
            color=MUTED)
    ax.set_xlabel("per-document dual-channel agreement (micro-F1, IoU τ=0.5)")
    ax.set_ylabel("documents")
    tiers = {t: sum(1 for r in recs if r["tier"] == t) for t in ("high", "medium", "low")}
    ax.set_title(f"Dual-channel agreement — n={len(recs)} "
                 f"(high {tiers['high']} / medium {tiers['medium']} / low {tiers['low']})",
                 loc="left", fontsize=9)
    ax.legend(frameon=False, fontsize=7)
    fig.savefig(out)
    plt.close(fig)
    return {"panel": "E1 agreement", "n": len(recs), "tiers": tiers}


# --- fig 3: actor network -------------------------------------------------
def fig_network(out: Path) -> dict:
    nm = read_json(path_of("data") / "analysis" / "network_metrics.json", {}) or {}
    nodes = list(iter_jsonl(path_of("data") / "analysis" / "network_nodes.jsonl"))
    edges = list(iter_jsonl(path_of("data") / "analysis" / "network_edges.jsonl"))
    fig, ax = plt.subplots(figsize=(4.6, 4.0))
    if not nodes:
        _status_card(ax, "FS-DBI actor network", "not built", "network_nodes.jsonl missing")
        fig.savefig(out)
        plt.close(fig)
        return {"panel": "network", "status": "not_built"}
    import networkx as nx
    g = nx.Graph()
    for n in nodes:
        g.add_node(n.get("id") or n.get("node_id"), t=n.get("type") or n.get("node_type"))
    for e in edges:
        g.add_edge(e["source"], e["target"])
    pos = nx.spring_layout(g, seed=20261104, k=0.6) if g.number_of_nodes() > 1 else \
        {n: (0, 0) for n in g.nodes()}
    colors = {"SERVICE_PROVIDER": ACCENT2, "END_USER": ACCENT}
    sizes = [120 + 60 * g.degree(n) for n in g.nodes()]
    nx.draw_networkx_edges(g, pos, ax=ax, alpha=0.35, width=0.7)
    nx.draw_networkx_nodes(g, pos, ax=ax, node_size=sizes,
                           node_color=[colors.get(g.nodes[n]["t"], MUTED)
                                       for n in g.nodes()], linewidths=0)
    ax.axis("off")
    # D-49/D-50: an edge needs two actor mentions in one document, so the
    # node/edge counts measure document structure, not market structure. The
    # caption carries the bound; a bare "N nodes, M edges" would be read as a
    # finding about the ecosystem.
    cov = nm.get("actor_coverage") or {}
    max_edges = cov.get("max_edges_possible_by_structure")
    # Distinct nodes, not mentions (D-54): build() drops a repeated name, so a
    # document naming one actor twice cannot produce an edge.
    multi = cov.get("docs_with_two_or_more_actor_nodes",
                    cov.get("docs_with_two_or_more_actor_mentions"))
    ndocs = cov.get("main_corpus_docs")
    title = (f"Actor network (main corpus) — {nm.get('n_nodes', g.number_of_nodes())} nodes, "
             f"{nm.get('n_edges', g.number_of_edges())} edges")
    if max_edges is not None and ndocs:
        title += (f"\nstructural maximum {max_edges} edges; "
                  f"{multi} of {ndocs} documents name two distinct actors")
    ax.set_title(title, loc="left", fontsize=8.5)
    from matplotlib.lines import Line2D
    ax.legend(handles=[Line2D([], [], marker="o", ls="", color=colors["SERVICE_PROVIDER"],
                              label="service provider", markersize=6),
                       Line2D([], [], marker="o", ls="", color=colors["END_USER"],
                              label="end user", markersize=6)],
              frameon=False, fontsize=7, loc="lower left")
    fig.savefig(out)
    plt.close(fig)
    return {"panel": "network", "n_nodes": nm.get("n_nodes"),
            "n_edges": nm.get("n_edges"),
            "structural_max_edges": max_edges,
            "docs_with_two_or_more_actor_nodes": multi,
            "main_corpus_docs": ndocs,
            "note": "node/edge counts are bounded by document structure (D-49)"}


# --- fig 4: attack tolerance ---------------------------------------------
def fig_attack(out: Path) -> dict:
    a = read_json(path_of("data") / "analysis" / "attack_tolerance.json", {}) or {}
    fig, ax = plt.subplots(figsize=(4.6, 3.0))
    if a.get("status") != "ok" or not a.get("curves"):
        _status_card(ax, "Attack tolerance", a.get("status") or "no data",
                     a.get("note") or "E2 not estimable at this corpus size")
        fig.savefig(out)
        plt.close(fig)
        return {"panel": "attack", "status": a.get("status")}
    for name, color, ls in (("targeted", ACCENT2, "-"), ("random", ACCENT, "--")):
        c = a["curves"].get(name) or []
        if c:
            ax.plot([p["frac_removed"] for p in c], [p["gcc_frac"] for p in c],
                    color=color, ls=ls, lw=1.2, label=name)
    ax.set_xlabel("fraction of nodes removed")
    ax.set_ylabel("largest component fraction")
    ax.set_title("Attack tolerance (H1/H3)", loc="left", fontsize=9)
    ax.legend(frameon=False, fontsize=7)
    fig.savefig(out)
    plt.close(fig)
    return {"panel": "attack", "status": a.get("status")}


# --- fig 5: displacement --------------------------------------------------
def fig_displacement(out: Path) -> dict:
    d = read_json(path_of("data") / "analysis" / "displacement.json", {}) or {}
    fig, ax = plt.subplots(figsize=(4.6, 2.8))
    by = d.get("by_type") or {}
    if not by:
        _status_card(ax, "Displacement (six types)", d.get("status") or "no events",
                     f"n_events={d.get('n_events', 0)} — Plan §6.2 E4: merged into "
                     "qualitative discussion")
        fig.savefig(out)
        plt.close(fig)
        return {"panel": "displacement", "n_events": d.get("n_events", 0)}
    types = ["spatial", "temporal", "target", "tactical", "functional", "perpetrator"]
    vals = [by.get(t, 0) for t in types]
    ax.barh(types, vals, color=ACCENT, height=0.6)
    for i, v in enumerate(vals):
        ax.text(v, i, f" {v}", va="center", fontsize=7)
    ax.set_xlabel("coded events")
    ax.set_title(f"Displacement by type — n={d.get('n_events', 0)}", loc="left", fontsize=9)
    fig.savefig(out)
    plt.close(fig)
    return {"panel": "displacement", "by_type": by}


# --- fig 6: cross-jurisdiction comparison --------------------------------
def fig_compare(out: Path) -> dict:
    c = read_json(path_of("data") / "analysis" / "compare.json", {}) or {}
    fig, ax = plt.subplots(figsize=(6.0, 2.8))
    counts = c.get("counts") or {}
    if not counts or c.get("status") == "insufficient_data":
        _status_card(ax, "CN vs US category distribution", c.get("status") or "no data",
                     "chi-square/Fisher is not read below the expected-count floor")
        fig.savefig(out)
        plt.close(fig)
        return {"panel": "compare", "status": c.get("status")}
    import numpy as np
    xs = np.arange(len(CATS))
    w = 0.38
    for i, (j, color) in enumerate((("cn", ACCENT), ("us", ACCENT2))):
        d = counts.get(j) or {}
        tot = sum(d.values()) or 1
        vals = [d.get(k, 0) / tot for k in CATS]
        ax.bar(xs + i * w, vals, w * 0.95, color=color, label=j.upper())
    ax.set_xticks(xs + w / 2)
    ax.set_xticklabels([CAT_EN[k] for k in CATS], rotation=20, ha="right", fontsize=7)
    ax.set_ylabel("share of labelled documents")
    stat = (c.get("collapsed_fisher") or {}).get("p") if c.get("primary_test") == \
        "fisher_collapsed" else c.get("p")
    test = "Fisher (collapsed)" if c.get("primary_test") == "fisher_collapsed" else "chi2"
    ax.set_title(f"CN vs US fraud typology — {test} p={stat}", loc="left", fontsize=9)
    ax.legend(frameon=False, fontsize=7)
    fig.savefig(out)
    plt.close(fig)
    return {"panel": "compare", "status": c.get("status")}


def run() -> dict:
    _style()
    d = _outdir()
    panels, figs = {}, {
        "fig1_corpus_flow": fig_flow,
        "fig2_e1_agreement": fig_e1,
        "fig3_actor_network": fig_network,
        "fig4_attack_tolerance": fig_attack,
        "fig5_displacement": fig_displacement,
        "fig6_cn_us_compare": fig_compare,
    }
    for name, fn in figs.items():
        p = d / f"{name}.png"
        try:
            panels[name] = {"file": str(p), **fn(p)}
        except Exception as exc:  # noqa: BLE001
            panels[name] = {"file": None, "error": f"{type(exc).__name__}: {exc}"}
    out = {"at_utc": utc_iso(), "dir": str(d), "panels": panels}
    write_json(path_of("reports") / "figures" / "figures.json", out)
    return out

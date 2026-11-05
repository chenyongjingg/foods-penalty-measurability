"""Attack tolerance: targeted vs random node removal (Plan §6.1 E3, H1/H3).

Tolerance = area under the largest-connected-component (GCC) fraction curve as
a function of the removed fraction (higher = more tolerant). We compare:
  - highest-degree removal
  - highest-betweenness removal
  - SERVICE_PROVIDER (intermediary) removal  [H3]
  - END_USER removal                         [H3]
  - random removal (100 repetitions, seed fixed)
H1 is supported when targeted AUC is significantly below random AUC;
H3 when intermediary AUC is significantly below terminal-user AUC.
"""
from __future__ import annotations

import json
import random
from collections import defaultdict

import networkx as nx

from ..common import cfg, get_logger, path_of, utc_iso, write_json
from .network import build, load_edges

STEPS = 20


def gcc_frac(g: nx.Graph) -> float:
    n = g.number_of_nodes()
    if n == 0:
        return 0.0
    comps = nx.connected_components(g)
    return len(max(comps, key=len)) / n


def curve(g: nx.Graph, order: list[str]) -> list[float]:
    h = g.copy()
    vals = [gcc_frac(h)]
    n = len(order)
    for k in range(1, STEPS + 1):
        cut = int(round(n * k / STEPS))
        for node in order[:cut]:
            if h.has_node(node):
                h.remove_node(node)
        vals.append(gcc_frac(h))
    return vals


def auc(vals: list[float]) -> float:
    # trapezoid over uniform x in [0,1]
    return sum((vals[i] + vals[i + 1]) / 2 for i in range(len(vals) - 1)) / (len(vals) - 1)


def _aucs_for(g: nx.Graph) -> dict:
    """Degree / provider / end-user AUCs on one graph (no random baseline)."""
    ntypes = nx.get_node_attributes(g, "ntype")
    deg = sorted(g.nodes, key=lambda x: g.degree(x), reverse=True)

    def type_first(t: str) -> list[str] | None:
        group = [x for x in deg if ntypes.get(x) == t]
        if not group:
            return None
        seen = set(group)
        return group + [x for x in deg if x not in seen]

    out = {"degree": auc(curve(g, deg))}
    for name, t in (("service_provider", "SERVICE_PROVIDER"), ("end_user", "END_USER")):
        order = type_first(t)
        if order:
            out[name] = auc(curve(g, order))
    return out


def bootstrap(docs: list[dict], reps: int, seed: int) -> dict:
    """Document-level bootstrap over the attack AUCs.

    The sampling unit is the penalty case, not the node: resampling nodes
    would hold the case structure fixed and understate the uncertainty that
    matters for H1/H3, which are statements about the corpus, not about one
    realised graph.  Returns percentile CIs and, for H3, the share of
    resamples in which intermediary tolerance is below terminal tolerance —
    a sign-stability measure, not a p-value.
    """
    rng = random.Random(seed)
    deg, diffs, prov, user = [], [], [], []
    for _ in range(reps):
        sample = [docs[rng.randrange(len(docs))] for _ in range(len(docs))]
        a = _aucs_for(build(sample))
        deg.append(a["degree"])
        if "service_provider" in a and "end_user" in a:
            prov.append(a["service_provider"])
            user.append(a["end_user"])
            diffs.append(a["service_provider"] - a["end_user"])

    def ci(v: list[float]) -> list[float] | None:
        if not v:
            return None
        v = sorted(v)
        return [round(v[int(0.025 * len(v))], 4), round(v[int(0.975 * len(v)) - 1], 4)]

    return {"reps": reps,
            "degree_auc_ci95": ci(deg),
            "service_provider_auc_ci95": ci(prov),
            "end_user_auc_ci95": ci(user),
            "h3_diff_ci95": ci(diffs),
            "h3_sign_stability": (round(sum(1 for d in diffs if d < 0) / len(diffs), 3)
                                  if diffs else None)}


def run() -> dict:
    docs, _ = load_edges()
    g = build(docs)
    n = g.number_of_nodes()
    outdir = path_of("data") / "analysis"
    res = {"n_nodes": n, "steps": STEPS, "at_utc": utc_iso()}
    if n < int(cfg("analysis.e2_nodes_floor", 400)):
        res["status"] = "insufficient_nodes"
        res["note"] = "E2 below floor -> case-chain typology replaces network metrics (Plan §6.2)"
        write_json(outdir / "attack_tolerance.json", res)
        return res

    deg = sorted(g.nodes, key=lambda x: g.degree(x), reverse=True)
    btw = nx.betweenness_centrality(g, weight="weight", seed=int(cfg("analysis.seed", 20261104)))
    btw_order = sorted(g.nodes, key=lambda x: btw[x], reverse=True)
    ntypes = nx.get_node_attributes(g, "ntype")
    providers = sorted([x for x in g.nodes if ntypes.get(x) == "SERVICE_PROVIDER"],
                       key=lambda x: g.degree(x), reverse=True)
    users = sorted([x for x in g.nodes if ntypes.get(x) == "END_USER"],
                   key=lambda x: g.degree(x), reverse=True)

    def type_first(group: list[str]) -> list[str]:
        head = list(group)
        seen = set(head)
        return head + [x for x in deg if x not in seen]

    curves = {
        "degree": curve(g, deg),
        "betweenness": curve(g, btw_order),
        "service_provider": curve(g, type_first(providers)) if providers else None,
        "end_user": curve(g, type_first(users)) if users else None,
    }
    aucs = {k: round(auc(v), 4) for k, v in curves.items() if v}

    rng = random.Random(int(cfg("analysis.seed", 20261104)))
    reps = int(cfg("analysis.random_reps", 100))
    random_aucs = []
    nodes = list(g.nodes)
    for _ in range(reps):
        rng.shuffle(nodes)
        random_aucs.append(auc(curve(g, list(nodes))))
    random_aucs.sort()
    rand_mean = sum(random_aucs) / len(random_aucs)

    def p_less(target: float) -> float:
        return sum(1 for x in random_aucs if x <= target) / len(random_aucs)

    boot = bootstrap(docs, int(cfg("analysis.bootstrap", 200)),
                     int(cfg("analysis.seed", 20261104)))
    h3_ci = boot.get("h3_diff_ci95")
    res.update({
        "status": "ok",
        "auc": aucs,
        "bootstrap": boot,
        "random_auc_mean": round(rand_mean, 4),
        "random_auc_ci95": [round(random_aucs[int(0.025 * reps)], 4),
                            round(random_aucs[int(0.975 * reps) - 1], 4)],
        "p_targeted_less_than_random": {
            "degree": p_less(aucs["degree"]),
            "betweenness": p_less(aucs["betweenness"]),
        },
        "n_providers": len(providers), "n_end_users": len(users),
        "h1_supported": aucs["degree"] < random_aucs[int(0.05 * reps)],
        # H3 is a comparative claim between two node classes: require the
        # bootstrap CI of the difference to exclude zero and at least 20 nodes
        # per class, so a single hub cannot decide the sign.
        "h3_supported": bool(h3_ci and h3_ci[1] < 0
                             and len(providers) >= 20 and len(users) >= 20),
        "curves": {k: [round(x, 4) for x in v] for k, v in curves.items() if v},
    })
    write_json(outdir / "attack_tolerance.json", res)
    get_logger("analyze.attack").info("attack: %s", json.dumps(aucs))
    return res

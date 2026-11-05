"""L5a FS-DBI ecosystem network construction (Plan §6.1 E2).

Nodes are grounded entities; an edge connects two entities co-mentioned in the
same penalty case. Edge weight = number of cases. Only the main corpus
(high-confidence tier, Plan §5.2) is used; the floor band enters the
pre-registered sensitivity table (analyze/sensitivity.py).

Node taxonomy: the ecosystem under H1/H3 is made of **actors** (the service
provider and the food operator), so the primary graph is actor-only. Document
names and tactic phrases are type-level terms shared by unrelated cases — a
single "检验报告" node joins eight unrelated cases and becomes the highest
degree node in the graph (measured 2026-11-04), which would make every
centrality and attack-tolerance number an artefact of vocabulary. Jurisdiction
names are administrative units, not actors. The five-type graph is kept as a
sensitivity variant (`sensitivity.py`), never as the main estimate.
DEVIATIONS.md D-26.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict

import networkx as nx

from ..common import cfg, get_logger, path_of, utc_iso, write_json
from ..manifest import Manifest

# Primary graph = actors. The five-type graph (adding TACTIC/DOCUMENT/
# JURISDICTION) is a sensitivity variant; see the module docstring and D-26.
NODE_TYPES = ["SERVICE_PROVIDER", "END_USER"]
ALL_NODE_TYPES = ["SERVICE_PROVIDER", "END_USER", "TACTIC", "DOCUMENT", "JURISDICTION"]


def node_types() -> list[str]:
    return list(cfg("analysis.network_node_types", NODE_TYPES))


def normalize_name(s: str) -> str:
    s = (s or "").strip()
    for ch in " \t\r\n（）()【】[]":
        s = s.replace(ch, "")
    return s


def load_edges(path=None, sources: tuple[str, ...] | None = ("cfws", "municipal"),
               tiers: tuple[str, ...] = ("high",)) -> tuple[list[dict], dict]:
    """Main-corpus documents of the Chinese frame.

    The US corpus (D3a) is a typology-comparison sample, not part of the
    FS-DBI ecosystem under study (Plan §4.3): including it would pool the CN
    and US supplier chains into one graph and make every network statistic a
    mixture of two jurisdictions. `sources=None` is available for a deliberate
    sensitivity run, never for the main estimate.
    """
    p = path or (path_of("data") / "extracted" / "dataset.jsonl")
    by_doc: dict[str, list[dict]] = defaultdict(list)
    meta: dict[str, dict] = {}
    with open(p, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            # `main_corpus` is high-tier only (extract/runner.py).  Pass
            # tiers=("high","medium") to run the pre-registered sensitivity
            # variant without relabelling; low is exploratory only.
            if r.get("tier") not in tiers:
                continue
            if sources is not None and r["source"] not in sources:
                continue
            by_doc[r["doc_id"]].append(r)
            meta[r["doc_id"]] = {"source": r["source"], "lang": r["lang"]}
    return [{"doc_id": k, "entities": v, **meta[k]} for k, v in by_doc.items()], meta


def build(docs: list[dict], types: list[str] | None = None) -> nx.Graph:
    g = nx.Graph()
    keep = set(types or node_types())
    for d in docs:
        ents, seen = [], set()
        for e in d["entities"]:
            if e["entity_type"] not in keep:
                continue
            name = normalize_name(e["normalized"])
            if not name or name in seen:
                continue
            seen.add(name)
            ents.append((name, e["entity_type"]))
            if not g.has_node(name):
                g.add_node(name, ntype=e["entity_type"], docs=set())
            g.nodes[name]["docs"].add(d["doc_id"])
        for i in range(len(ents)):
            for j in range(i + 1, len(ents)):
                a, b = ents[i][0], ents[j][0]
                if a == b:
                    continue
                if g.has_edge(a, b):
                    g[a][b]["weight"] += 1
                else:
                    g.add_edge(a, b, weight=1)
    return g


def metrics(g: nx.Graph) -> dict:
    n = g.number_of_nodes()
    if n == 0:
        return {"n_nodes": 0, "status": "empty"}
    comps = sorted(nx.connected_components(g), key=len, reverse=True)
    gcc = g.subgraph(comps[0])
    try:
        communities = nx.community.louvain_communities(g, seed=int(cfg("analysis.seed", 20261104)))
        modularity = nx.community.modularity(g, communities, weight="weight")
    except Exception:
        communities, modularity = [], None
    cores = nx.core_number(g)
    by_type = Counter(nx.get_node_attributes(g, "ntype").values())
    return {
        "n_nodes": n, "n_edges": g.number_of_edges(),
        "density": round(nx.density(g), 6),
        "n_components": len(comps),
        "gcc_size": len(comps[0]), "gcc_frac": round(len(comps[0]) / n, 4),
        "modularity": round(modularity, 4) if modularity is not None else None,
        "max_kcore": max(cores.values()) if cores else 0,
        "mean_degree": round(sum(dict(g.degree()).values()) / n, 3),
        "node_types": dict(by_type),
        "at_utc": utc_iso(),
    }


def _dataset_age() -> dict:
    """Seconds by which dataset.jsonl lags silver.jsonl.

    Every analysis reads the flattened dataset, which is only rewritten by the
    extract stage. Running `analyze` on its own after a label run therefore
    silently reports the *previous* corpus — a stale-artefact trap that already
    produced one wrong node count during the 2026-11-04 audit. The lag is
    recorded with every metric set and surfaced in the gates.
    """
    ds = path_of("data") / "extracted" / "dataset.jsonl"
    sv = path_of("data") / "silver" / "silver.jsonl"
    try:
        lag = int(sv.stat().st_mtime - ds.stat().st_mtime)
    except OSError:
        return {"dataset_lag_s": None, "stale_dataset": None}
    return {"dataset_lag_s": lag, "stale_dataset": lag > 300}


def _actor_coverage(docs: list[dict]) -> dict:
    """How many main-corpus documents can contribute an edge at all (D-49).

    An edge needs two *distinct* actor nodes inside one document. `build()`
    keys nodes on the normalised name and drops repeats, so counting raw
    mentions would overstate the structural ceiling wherever the same actor is
    named twice -- which is common (a document names the operator, then the
    penalty decision names them again). Both counts are reported; the ceiling
    uses distinct nodes, because that is what the graph can actually contain.

    The silver-level measurement behind D-49/D-54: 7 of 79 Chinese high-tier
    documents name both a provider and an end user in the channel the graph is
    built from (3 of 79 if both channels must each contain both types), and 0
    of 91 English documents name a provider under any definition. This function
    measures the dataset the graph is built from, so the two can differ when
    the extract is behind the label wave.
    """
    keep = set(node_types())
    n_docs = len(docs)
    per_doc_mentions, per_doc_nodes = [], []
    provider_docs = both_type_docs = 0
    for d in docs:
        ents = [e for e in d["entities"] if e["entity_type"] in keep]
        names, prov, endu = set(), set(), set()
        for e in ents:
            nm = normalize_name(e.get("normalized") or "")
            if not nm:
                continue
            names.add(nm)
            if e["entity_type"] == "SERVICE_PROVIDER":
                prov.add(nm)
            else:
                endu.add(nm)
        per_doc_mentions.append(len(ents))
        per_doc_nodes.append(len(names))
        provider_docs += bool(prov)
        both_type_docs += bool(prov and endu)
    return {
        "main_corpus_docs": n_docs,
        "docs_with_any_actor": sum(1 for c in per_doc_nodes if c > 0),
        "docs_with_two_or_more_actor_nodes": sum(1 for c in per_doc_nodes if c >= 2),
        "docs_with_two_or_more_actor_mentions": sum(1 for c in per_doc_mentions if c >= 2),
        "docs_with_provider": provider_docs,
        "docs_with_provider_and_end_user": both_type_docs,
        "actor_mentions_total": sum(per_doc_mentions),
        "actor_nodes_total": sum(per_doc_nodes),
        "max_edges_possible_by_structure": sum(max(0, c) * (max(0, c) - 1) // 2
                                               for c in per_doc_nodes),
        "note": ("Documents with fewer than two distinct actor nodes cannot "
                 "produce an edge. Read n_nodes/n_edges against these counts "
                 "before calling the network sparse (D-49); a document that "
                 "repeats one actor contributes one node, not an edge."),
    }


def run() -> dict:
    docs, _ = load_edges()
    g = build(docs)
    m = metrics(g)
    m.update(_dataset_age())
    m["actor_coverage"] = _actor_coverage(docs)
    m["node_types_allowed"] = node_types()
    outdir = path_of("data") / "analysis"
    write_json(outdir / "network_metrics.json", m)
    nodes = [{"id": n, "type": d.get("ntype"), "docs": sorted(d.get("docs", [])),
              "degree": g.degree(n)} for n, d in g.nodes(data=True)]
    edges = [{"source": a, "target": b, "weight": d.get("weight", 1)}
             for a, b, d in g.edges(data=True)]
    (outdir / "network_nodes.jsonl").write_text(
        "\n".join(json.dumps(x, ensure_ascii=False) for x in nodes), encoding="utf-8")
    (outdir / "network_edges.jsonl").write_text(
        "\n".join(json.dumps(x, ensure_ascii=False) for x in edges), encoding="utf-8")
    # GraphML is a convenience export, not an input to any gate. A failed write
    # must not leave a 0-byte file behind: a later reader would take its
    # existence as proof the graph had been exported. On failure the partial
    # file is removed and the reason is recorded in the metrics.
    gp = outdir / "network.graphml"
    try:
        # GraphML cannot carry list-valued attributes. Export a copy whose
        # `docs` attribute is a "|"-joined string; the graph itself is untouched.
        gx = g.copy()
        for _, d in gx.nodes(data=True):
            if isinstance(d.get("docs"), (list, tuple, set)):
                d["docs"] = "|".join(sorted(map(str, d["docs"])))
        nx.write_graphml(gx, gp)
        m["graphml"] = {"written": True, "bytes": gp.stat().st_size}
    except Exception as exc:  # noqa: BLE001
        gp.unlink(missing_ok=True)
        m["graphml"] = {"written": False, "error": f"{type(exc).__name__}: {exc}"}
    # The metrics file was written before the export so that a crash during the
    # export could not lose the counts. That made `graphml.written` unreachable
    # on the success path — the key was set after the only write, so the
    # artefact never recorded that the export had happened, and a checker
    # reading network_metrics.json saw an empty dict while a 10 KB file sat on
    # disk. Write again now that the export outcome is known.
    write_json(outdir / "network_metrics.json", m)
    get_logger("analyze.network").info("network metrics: %s", m)
    return m

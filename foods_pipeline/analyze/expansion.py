"""Automatic corpus expansion (Plan §6.2: "扩年份/扩站点由管线自动执行").

The plan assigns expansion to the pipeline, not to the researcher: when E2
comes in under its floor, more of the same frame should be collected without a
human in the loop. Automatic does not mean unconstrained here:

* the candidate queries are a **pre-registered ordered list**
  (config/expansion_queries.yaml), written before the second labelling wave;
  the pipeline never invents terms;
* the ladder only advances while E2 is below `analysis.expansion.
  trigger_below_nodes`, at most `max_batches_per_day` batches a day, each with
  its own PDF budget;
* every batch that runs is recorded in the manifest kv (`expansion:log`) and
  the documents it produces are tagged with the batch id, so the corpus can be
  split into "first pass" and "expanded" at analysis time.

If the list is exhausted the pipeline says so instead of quietly repeating it:
E2 stays downgraded and the plan's global fallback applies.
"""
from __future__ import annotations

from datetime import datetime, timezone

from ..common import cfg, get_logger, load_yaml, path_of, read_json, utc_iso
from ..manifest import Manifest

KV_LOG = "expansion:log"
KV_DAY = "expansion:day"


def batches() -> list[dict]:
    try:
        data = load_yaml("config/expansion_queries.yaml")
    except FileNotFoundError:
        return []
    return list(data.get("batches") or [])


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def plan(m: Manifest | None = None) -> dict:
    """Decide whether another batch should run, and which one."""
    m = m or Manifest()
    conf = cfg("analysis.expansion", {}) or {}
    if not conf.get("enabled", True):
        return {"action": "skip", "reason": "expansion disabled in config"}
    net = read_json(path_of("data") / "analysis" / "network_metrics.json", {}) or {}
    n_nodes = int(net.get("n_nodes") or 0)
    floor = int(conf.get("trigger_below_nodes", 400))
    if n_nodes >= floor:
        return {"action": "skip", "n_nodes": n_nodes, "floor": floor,
                "reason": "E2 node floor met; no expansion needed"}
    log = m.kv_get(KV_LOG, []) or []
    done = {e.get("batch") for e in log}
    remaining = [b for b in batches() if b.get("id") not in done]
    if not remaining:
        return {"action": "skip", "n_nodes": n_nodes, "floor": floor,
                "batches_done": sorted(x for x in done if x),
                "reason": "pre-registered expansion list exhausted"}
    day = m.kv_get(KV_DAY, {}) or {}
    used_today = int(day.get(_today(), 0))
    cap = int(conf.get("max_batches_per_day", 2))
    if used_today >= cap:
        return {"action": "skip", "n_nodes": n_nodes, "floor": floor,
                "reason": f"daily expansion cap reached ({used_today}/{cap})"}
    batch = dict(remaining[0])
    batch["pdf_budget"] = int(conf.get("pdf_budget_per_batch", 600))
    return {"action": "run", "batch": batch, "n_nodes": n_nodes, "floor": floor,
            "remaining_after": max(0, len(remaining) - 1)}


def run_next(m: Manifest | None = None) -> dict:
    """Execute the next pre-registered batch, if one is due."""
    m = m or Manifest()
    log = get_logger("analyze.expansion")
    p = plan(m)
    if p.get("action") != "run":
        log.info("expansion skipped: %s", p.get("reason"))
        return p
    batch = p["batch"]
    from ..collect.cfws import CfwsCollector
    log.info("expansion batch %s: %d queries", batch["id"], len(batch["queries"]))
    stats = CfwsCollector().run(extra_queries=batch["queries"],
                                expansion_batch=batch["id"],
                                pdf_budget=batch.get("pdf_budget"))
    entry = {"batch": batch["id"], "at_utc": utc_iso(),
             "queries": batch["queries"], "stats": stats}
    hist = m.kv_get(KV_LOG, []) or []
    hist.append(entry)
    m.kv_set(KV_LOG, hist)
    day = m.kv_get(KV_DAY, {}) or {}
    day[_today()] = int(day.get(_today(), 0)) + 1
    m.kv_set(KV_DAY, day)
    log.info("expansion batch %s done: %s", batch["id"],
             {k: stats.get(k) for k in ("queries", "new", "pdfs")})
    return {"action": "ran", "batch": batch["id"], "stats": stats}

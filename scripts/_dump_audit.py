#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read-only dump of every artefact the round-3 audit cites (run on the pod)."""
import glob
import json
import os
import sqlite3

R = "/opt/foods"


def rd(p, default=None):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def main():
    out = {}
    e1 = rd(f"{R}/data/metrics/e1.json", {}) or {}
    out["e1"] = {k: e1.get(k) for k in
                 ("n", "mean_agreement", "mean_agreement_shrunk", "pooled_micro_f1",
                  "stable_types", "status", "tier_counts", "coverage", "protocol",
                  "input_chars", "tau_sensitivity", "n_zero_entities",
                  "n_scored_agreement", "literature_calibration", "ladder")}
    out["e1_by_lang"] = e1.get("by_lang")
    af = e1.get("anchor_f1") or {}
    out["anchor"] = {k: af.get(k) for k in
                     ("n", "f1", "macro_f1", "micro_f1", "fact_only_docs",
                      "basis_counts", "extraction", "per_class_f1")}
    rec = sorted(glob.glob(f"{R}/data/metrics/anchor_*.json"))
    out["retier_receipt"] = rd(rec[-1], {}) if rec else None
    out["retier_receipt_path"] = rec[-1] if rec else None

    g = rd(f"{R}/data/analysis/gates.json", {}) or {}
    out["gates"] = g.get("gates")
    out["actions"] = g.get("actions")

    cp = rd(f"{R}/data/analysis/coverage_probe.json", {}) or {}
    out["coverage_probe"] = {"summary": cp.get("summary"),
                             "ceiling_check": cp.get("ceiling_check"),
                             "probes": [{k: p.get(k) for k in
                                         ("kw1", "kw2", "result_count", "reachable",
                                          "unseen_page1")}
                                        for p in (cp.get("probes") or [])[:12]]}

    kw = rd(f"{R}/data/analysis/keyword_sensitivity.json", {}) or {}
    out["keywords"] = {"frame": kw.get("frame"),
                       "plan_rule_admitted_share": kw.get("plan_rule_admitted_share"),
                       "high_tier_n": kw.get("high_tier_n"),
                       "variants": {k: {"admitted": v.get("admitted"),
                                        "vs_baseline": v.get("vs_baseline"),
                                        "high_tier_retained": v.get("high_tier_retained")}
                                    for k, v in (kw.get("variants") or {}).items()}}

    fig = rd(f"{R}/reports/figures/figures.json", {}) or {}
    out["figures"] = {k: (v or {}).get("panel") for k, v in (fig.get("panels") or {}).items()}

    c = sqlite3.connect(f"{R}/state/foods.sqlite")
    out["stages"] = dict(c.execute("select stage,count(*) from docs group by stage").fetchall())
    out["sources"] = dict(c.execute("select source,count(*) from docs group by source").fetchall())
    kv = dict(c.execute("select k,v from kv").fetchall())
    out["expansion_log"] = json.loads(kv["expansion:log"]) if kv.get("expansion:log") else None
    out["gov_events"] = json.loads(kv["gov_events"]).get("summary") if kv.get("gov_events") else None
    out["source_status"] = {k: json.loads(v) for k, v in kv.items()
                            if k.startswith("source_status:")}
    out["files"] = {p: os.path.getsize(p) for p in
                    [f"{R}/data/silver/silver.jsonl", f"{R}/data/extracted/dataset.jsonl"]
                    if os.path.exists(p)}
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()

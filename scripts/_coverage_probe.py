#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Measure what the cfws portal actually lets this pipeline see (read-only).

The portal reports a `resultCount` far larger than what it will serve: page 5
of a 721-result query returns an empty list. This script bounds the reachable
corpus per query and estimates how many *unseen* decisions the candidate
vocabulary can still yield, which is the evidence base for the E2 ceiling
discussion (DEVIATIONS.md D-35).

No documents are written; only /queryDoc is called, at the collector's own
rate limit.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, "/opt/foods")
from foods_pipeline.collect.cfws import CfwsCollector  # noqa: E402
from foods_pipeline.manifest import Manifest  # noqa: E402

PAGE_CAP = 4  # pages 1..4 at size 50; page 5 returns empty (re-measured 11-04)

FRAUD = ["伪造", "虚假", "篡改", "变造", "冒用", "买卖", "购买", "出售", "套用",
         "出具虚假", "标注虚假"]
DOC = ["检验检测报告", "检验报告", "检测报告", "认证证书", "认证材料", "溯源码",
       "合格证明", "合格证", "检测数据", "检验数据", "检疫证明", "生产日期",
       "食品标签", "厂名", "产地"]


def main() -> int:
    c = CfwsCollector(Manifest())
    seen = set()

    def probe(kw1, kw2=None):
        key = (kw1, kw2)
        if key in seen:
            return None
        seen.add(key)
        try:
            total, rows = c.query(kw1, kw2, 1)
        except Exception as exc:  # noqa: BLE001
            return {"kw1": kw1, "kw2": kw2, "error": f"{type(exc).__name__}: {exc}"}
        new = 0
        for r in rows:
            rk = r.get("rowkey") or r.get("1")
            if rk and not c.m.exists(f"cfws:{rk}"):
                new += 1
        return {"kw1": kw1, "kw2": kw2, "result_count": total,
                "rows_page1": len(rows), "unseen_page1": new,
                "reachable": min(total, PAGE_CAP * 50)}

    out = {"page_cap_rows": PAGE_CAP * 50, "probes": []}
    # 1. Single terms: how large is the reported universe?
    for t in FRAUD:
        out["probes"].append(probe(t))
    for t in DOC:
        out["probes"].append(probe(t))
    # 2. Specific adjacent phrases (small result sets are fully reachable).
    for f_ in ("伪造", "虚假", "篡改", "买卖"):
        for d in ("检验报告", "检测报告", "认证证书", "合格证明", "溯源码", "检测数据"):
            out["probes"].append(probe(f_ + d))
    # 3. Re-test the reachability ceiling on one large query.
    pages = []
    for p in range(1, PAGE_CAP + 2):
        total, rows = c.query("伪造", "食品", p)
        pages.append({"page": p, "result_count": total, "rows": len(rows)})
    out["ceiling_check"] = {"kw": ["伪造", "食品"], "pages": pages}

    probes = [p for p in out["probes"] if p]
    ok = [p for p in probes if not p.get("error")]
    out["summary"] = {
        "n_probes": len(probes),
        "n_zero": sum(1 for p in ok if p["result_count"] == 0),
        "n_fully_reachable": sum(1 for p in ok if p["result_count"] <= PAGE_CAP * 50),
        "n_capped": sum(1 for p in ok if p["result_count"] > PAGE_CAP * 50),
        "reported_universe_sum": sum(p["result_count"] for p in ok),
        "reachable_sum": sum(p["reachable"] for p in ok),
        "unseen_page1_sum": sum(p["unseen_page1"] for p in ok),
    }
    p = Path("/opt/foods/data/analysis/coverage_probe.json")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(out["summary"], ensure_ascii=False))
    print(json.dumps(out["ceiling_check"], ensure_ascii=False))
    top = sorted([x for x in ok if x["unseen_page1"]],
                 key=lambda x: -x["unseen_page1"])[:10]
    for t in top:
        print("unseen", t["kw1"], t["kw2"], t["unseen_page1"], "/", t["result_count"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

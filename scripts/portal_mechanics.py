#!/usr/bin/env python3
"""Record the portal's serving mechanics, so the manuscript's restriction on trend
language rests on a product rather than on a remembered observation.

For each of a few queries: fetch pages 1..6 and record, per page, the number of rows
served and the first/last publication date (column "4" holds the date string; the
collector's own parser is reused). Also record whether page-1 dates are non-increasing.

Polite access: 1 request every 2 s, same as the crawler. Read-only.
"""
import datetime, json, sys, time
sys.path.insert(0, "/opt/foods")

from foods_pipeline.collect.cfws import CfwsCollector
from foods_pipeline.manifest import Manifest

Q = [("检验报告", "食品"), ("伪造", "食品"), ("冒用认证标志", None)]
out = {"product": "portal_mechanics", "at_utc": None, "page_size": None,
       "queries": [], "note": (
           "sortFields is empty, i.e. the portal's default ordering. Row count per page "
           "and the date sequence on page 1 are recorded verbatim so that the sampling "
           "window claim (D-90) has a product behind it.")}

c = CfwsCollector(Manifest())
out["page_size"] = c.page_size

for kw1, kw2 in Q:
    rec = {"query": [kw1, kw2], "pages": []}
    seen_dates = []
    for page in range(1, 7):
        try:
            total, rows = c.query(kw1, kw2, page)
        except Exception as exc:  # noqa: BLE001
            rec["pages"].append({"page": page, "error": f"{type(exc).__name__}: {exc}"})
            time.sleep(2)
            continue
        dates = []
        for r in rows:
            d = CfwsCollector._date(r.get("23") or "")
            if d:
                dates.append(d)
        entry = {"page": page, "result_count": total, "rows": len(rows),
                 "first_date": dates[0] if dates else None,
                 "last_date": dates[-1] if dates else None,
                 "n_dated": len(dates)}
        if page == 1 and dates:
            entry["dates_non_increasing"] = all(dates[i] >= dates[i + 1] for i in range(len(dates) - 1))
            seen_dates = dates
        rec["pages"].append(entry)
        time.sleep(2)
    if seen_dates:
        rec["first_page_date_span"] = [min(seen_dates), max(seen_dates)]
    rec["max_rows_served_in_one_page"] = max(
        (p.get("rows", 0) for p in rec["pages"] if "rows" in p), default=0)
    rec["pages_with_zero_rows"] = [p["page"] for p in rec["pages"] if p.get("rows") == 0]
    out["queries"].append(rec)

out["at_utc"] = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
(open("/opt/foods/data/reports/portal_mechanics.json", "w", encoding="utf-8")
 .write(json.dumps(out, ensure_ascii=False, indent=1)))
print(json.dumps(out, ensure_ascii=False)[:1500])

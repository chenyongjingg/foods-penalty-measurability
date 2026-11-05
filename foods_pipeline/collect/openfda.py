"""openFDA food enforcement API collector (D3a). Public, keyless, JSON."""
from __future__ import annotations

import json

from ..common import RateLimiter, as_date, cfg, http_request, utc_iso
from .base import Collector


class OpenFdaCollector(Collector):
    source = "openfda"

    def __init__(self, manifest=None):
        super().__init__(manifest)
        self.base = cfg("collect.openfda.base")
        self.limit = int(cfg("collect.openfda.limit", 100))
        self.max_records = int(cfg("collect.openfda.max_records", 3000))
        self.rate = RateLimiter(float(cfg("runtime.api_rate_seconds", 0.35)))

    def run(self) -> dict:
        stats = {"queries": 0, "fetched": 0, "new": 0, "errors": 0}
        for q in cfg("collect.openfda.queries", []):
            stats["queries"] += 1
            skip = 0
            while skip < self.max_records:
                params = {"search": q, "limit": self.limit, "skip": skip}
                try:
                    resp = http_request(self.s, "GET", self.base, rate=self.rate, params=params)
                    if resp.status_code == 404:  # openFDA returns 404 for no matches
                        break
                    resp.raise_for_status()
                    payload = resp.json()
                except Exception as exc:  # noqa: BLE001
                    self.log.error("openfda query failed %s skip=%d: %s", q, skip, exc)
                    stats["errors"] += 1
                    break
                results = payload.get("results") or []
                if not results:
                    break
                for rec in results:
                    stats["fetched"] += 1
                    native = (rec.get("recall_number") or
                              f"{rec.get('product_description','')[:40]}|{rec.get('report_date','')}")
                    doc_id = f"{self.source}:{native}"
                    if self.m.exists(doc_id):
                        continue
                    title = (rec.get("product_description") or "")[:200]
                    raw_path = self.save_raw(doc_id, "json", json.dumps(rec, ensure_ascii=False))
                    # report_date is YYYYMMDD; store ISO so every downstream
                    # date reader does not need the source-specific format.
                    rep = as_date(rec.get("report_date"))
                    inserted = self.register(
                        doc_id=doc_id, native_id=native,
                        url="https://api.fda.gov/food/enforcement.json",
                        title=title,
                        published=rep.isoformat() if rep else None,
                        raw_path=raw_path,
                        meta={"query": q, "classification": rec.get("classification"),
                              "status": rec.get("status"), "state": rec.get("state"),
                              "country": rec.get("country"),
                              "reason_for_recall": rec.get("reason_for_recall")})
                    if inserted:
                        stats["new"] += 1
                meta = payload.get("meta", {}).get("results", {})
                total = int(meta.get("total", 0))
                skip += self.limit
                if skip >= total:
                    break
        self.m.kv_set("source_status:openfda", {"ok": True, "at_utc": utc_iso(), **stats})
        return stats

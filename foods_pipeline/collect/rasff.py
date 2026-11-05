"""EU RASFF collector (D3b).

Plan §4.2: RASFF bulk export is treated as OPTIONAL. The EU portal dataset
entry currently exposes only an interactive HTML search window (verified
2026-11-04); no machine-readable CSV/JSON distribution is advertised. The
collector therefore attempts a bounded set of official endpoints, records the
outcome, and never blocks the pipeline. If a bulk file becomes available it is
picked up automatically.
"""
from __future__ import annotations

import json

from ..common import RateLimiter, cfg, http_request, utc_iso
from .base import Collector

CANDIDATE_URLS = [
    # EU health data lake API catalogue (documented by the dataset page)
    "https://developer.datalake.sante.service.ec.europa.eu/api-details",
    # RASFF window application root (JS app; no public export route)
    "https://webgate.ec.europa.eu/rasff-window/screen/search",
]


class RasffCollector(Collector):
    source = "rasff"

    def __init__(self, manifest=None):
        super().__init__(manifest)
        self.rate = RateLimiter(float(cfg("runtime.gov_rate_seconds", 2.0)))

    def run(self) -> dict:
        status = {"ok": False, "attempted": [], "bulk_found": False, "at_utc": utc_iso()}
        for url in CANDIDATE_URLS:
            try:
                resp = http_request(self.s, "GET", url, rate=self.rate)
                ctype = resp.headers.get("content-type", "")
                status["attempted"].append({"url": url, "status": resp.status_code,
                                            "bytes": len(resp.content), "ctype": ctype})
                if "csv" in ctype.lower() or "json" in ctype.lower():
                    status["bulk_found"] = True
                    status["note"] = "machine-readable endpoint detected; adapter needed"
            except Exception as exc:  # noqa: BLE001
                status["attempted"].append({"url": url, "error": type(exc).__name__})
        if not status["bulk_found"]:
            status["note"] = ("no machine-readable bulk distribution advertised; "
                              "D3b degraded per Plan §4.2 (non-blocking)")
        self.m.kv_set("source_status:rasff", status)
        self.log.warning("RASFF status: %s", json.dumps(status, ensure_ascii=False)[:400])
        return status

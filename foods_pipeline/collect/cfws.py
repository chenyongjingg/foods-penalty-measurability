"""National market-regulation penalty-document portal (cfws.samr.gov.cn).

D1' primary intake. The portal exposes a public full-text query endpoint
(POST /queryDoc) and a document endpoint (POST /getDoc) returning the official
PDF as base64. Only lawfully disclosed government information is accessed; the
collector respects a 1 request / 2 s spacing and keeps an append-only raw store.

Scientific note (recorded in DEVIATIONS.md): the plan names ~50 municipal
bulletin columns as D1'. This portal aggregates the same genre (administrative
penalty decisions by municipal/district agencies) nationwide; using it as the
primary frame removes site-by-site sampling heterogeneity and is reported as a
sampling-frame deviation, with the municipal registry retained as a secondary
layer.
"""
from __future__ import annotations

import base64
import json
import re
from datetime import datetime

from ..common import RateLimiter, cfg, http_request, utc_iso
from .base import Collector


class CfwsCollector(Collector):
    source = "cfws"

    def __init__(self, manifest=None):
        super().__init__(manifest)
        self.base = cfg("collect.cfws.base", "https://cfws.samr.gov.cn").rstrip("/")
        self.page_size = int(cfg("collect.cfws.page_size", 50))
        self.max_pages = int(cfg("collect.cfws.max_pages_per_query", 40))
        self.pdf_budget = int(cfg("collect.cfws.pdf_budget_per_run", 400))
        # Because queries overlap, the top pages are all already-seen on a
        # resume run; do not let that look like convergence.
        self.min_pages = int(cfg("collect.cfws.min_pages_before_stop", 5))
        self.rate = RateLimiter(float(cfg("runtime.gov_rate_seconds", 2.0)))
        self._pdf_used = 0

    def _post(self, path: str, data: dict) -> dict:
        url = self.base + path
        # The portal silently returns zero results when the charset is omitted
        # from the form Content-Type (verified 2026-11-04). Keep it explicit.
        resp = http_request(self.s, "POST", url, rate=self.rate, data=data,
                            headers={"X-Requested-With": "XMLHttpRequest",
                                     "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"})
        resp.raise_for_status()
        payload = resp.json()
        if not payload.get("success", True):
            raise RuntimeError(f"portal reported failure: {str(payload)[:200]}")
        return payload

    def query(self, kw1: str, kw2: str | None, page: int) -> tuple[int, list[dict]]:
        cond = [{"key": "quanwen_1", "id": kw1, "name": kw1}]
        if kw2:
            cond.append({"key": "quanwen_2", "id": kw2, "name": kw2})
        data = {
            "pageSize": self.page_size,
            "pageNum": page,
            "queryCondition": json.dumps(cond, ensure_ascii=False),
            "sortFields": "",
            "ciphertext": "",
        }
        payload = self._post("/queryDoc", data)
        qr = (payload.get("result") or {}).get("queryResult") or {}
        return int(qr.get("resultCount") or 0), list(qr.get("resultList") or [])

    def fetch_pdf(self, rowkey: str) -> tuple[str | None, dict]:
        payload = self._post("/getDoc", {"docid": rowkey})
        res = payload.get("result") or {}
        b64 = res.get("i7") or ""
        if not b64:
            return None, {"detail": {k: res.get(k) for k in ("i0", "i1", "i3", "i4", "i5")}}
        try:
            return base64.b64decode(b64), {"detail": {k: res.get(k) for k in ("i0", "i1", "i3", "i4", "i5")}}
        except Exception as exc:  # noqa: BLE001
            self.log.warning("pdf decode failed %s: %s", rowkey, exc)
            return None, {"detail": {}}

    @staticmethod
    def _date(raw: str) -> str | None:
        raw = (raw or "").strip()
        if re.fullmatch(r"\d{8}", raw):
            return f"{raw[:4]}-{raw[4:6]}-{raw[6:]}"
        for fmt in ("%Y-%m-%d", "%Y年%m月%d日", "%Y/%m/%d"):
            try:
                return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
        return None

    def backfill(self) -> dict:
        """Retry documents registered without a PDF in earlier runs.

        A per-run PDF budget must not strand metadata-only rows: they are
        revisited on every run until their PDF is fetched or the source says
        the document has none.
        """
        stats = {"tried": 0, "recovered": 0, "still_missing": 0}
        # Metadata-only rows may already have been through cleaning and parked
        # as `failed` (awaiting_pdf); they must still be revisited, otherwise a
        # per-run PDF budget permanently strands them.
        docs = list(self.m.iter_stage("raw", source=self.source)) + \
            list(self.m.iter_stage("failed", source=self.source))
        for doc in docs:
            if self._pdf_used >= self.pdf_budget:
                break
            meta = json.loads(doc.get("meta") or "{}")
            if not meta.get("pdf_missing"):
                continue
            rowkey = doc.get("native_id")
            stats["tried"] += 1
            try:
                pdf, extra = self.fetch_pdf(rowkey)
                self._pdf_used += 1
            except Exception as exc:  # noqa: BLE001
                self.log.warning("backfill failed %s: %s", rowkey, exc)
                continue
            if pdf:
                raw = self.save_raw(doc["doc_id"], "pdf", pdf)
                meta.pop("pdf_missing", None)
                meta.update(extra)
                self.m.update_raw(doc["doc_id"], raw_path=raw, meta=meta)
                if doc["stage"] != "raw":
                    # Re-enter the normal path; cleaning will pick it up.
                    self.m.set_stage(doc["doc_id"], "raw", note="pdf_backfilled")
                stats["recovered"] += 1
            else:
                stats["still_missing"] += 1
        return stats

    def run(self, extra_queries: list | None = None,
            expansion_batch: str | None = None,
            pdf_budget: int | None = None) -> dict:
        """Collect the configured queries plus any pre-registered expansion batch.

        `expansion_batch` tags every document the batch produces, so the
        corpus can be split into the first pass and the automatic expansion
        (analyze/expansion.py, Plan §6.2). The expansion has its own PDF
        budget: a batch must not starve the backfill of older metadata rows.
        """
        if pdf_budget is not None:
            self.pdf_budget = max(1, int(pdf_budget))
        stats = {"queries": 0, "listed": 0, "new": 0, "pdfs": 0, "no_pdf": 0,
                 "pages": 0, "errors": 0, "zero_result_queries": 0}
        if expansion_batch:
            stats["expansion_batch"] = expansion_batch
        stats["backfill"] = self.backfill()
        seen_q = {tuple(q) for q in cfg("collect.cfws.queries", [])}
        queries = list(cfg("collect.cfws.queries", []))
        for q in (extra_queries or []):
            key = (q[0], q[1] if len(q) > 1 else None)
            if key not in seen_q:
                seen_q.add(key)
                queries.append(list(key))
        for kw1, kw2 in queries:
            stats["queries"] += 1
            empty_pages = 0
            for page in range(1, self.max_pages + 1):
                try:
                    total, rows = self.query(kw1, kw2, page)
                except Exception as exc:  # noqa: BLE001
                    self.log.error("query failed %s/%s p%d: %s", kw1, kw2, page, exc)
                    stats["errors"] += 1
                    break
                stats["pages"] += 1
                if not rows:
                    if page == 1 and total == 0:
                        stats["zero_result_queries"] += 1
                        self.log.error("query %s/%s returned 0 (check request headers)",
                                       kw1, kw2)
                    break
                new_this_page = 0
                for row in rows:
                    stats["listed"] += 1
                    rowkey = row.get("rowkey") or row.get("1")
                    if not rowkey:
                        continue
                    doc_id = f"{self.source}:{rowkey}"
                    if self.m.exists(doc_id):
                        continue
                    pdf, extra = (None, {})
                    if self._pdf_used < self.pdf_budget:
                        try:
                            pdf, extra = self.fetch_pdf(rowkey)
                            self._pdf_used += 1
                        except Exception as exc:  # noqa: BLE001
                            self.log.warning("getDoc failed %s: %s", rowkey, exc)
                            stats["errors"] += 1
                    meta = {
                        "case_no": row.get("2"),
                        "penalty_content": row.get("7"),
                        "agency": row.get("14") or row.get("52"),
                        "party": row.get("30") or row.get("36"),
                        "date": self._date(row.get("23")),
                        "query": [kw1, kw2],
                        **extra,
                    }
                    if expansion_batch:
                        meta["expansion_batch"] = expansion_batch
                    if not pdf:
                        meta["pdf_missing"] = True
                    raw_path = None
                    if pdf:
                        raw_path = self.save_raw(doc_id, "pdf", pdf)
                        stats["pdfs"] += 1
                    else:
                        raw_path = self.save_raw(doc_id, "json",
                                                 json.dumps({"row": row, "extra": extra},
                                                            ensure_ascii=False))
                        stats["no_pdf"] += 1
                    inserted = self.register(
                        doc_id=doc_id, native_id=rowkey,
                        url=f"{self.base}/detail.html?docid={rowkey}",
                        title=row.get("2") or None, published=meta["date"],
                        raw_path=raw_path, meta=meta)
                    if inserted:
                        stats["new"] += 1
                        new_this_page += 1
                # Queries overlap heavily: pages of already-seen rows do not
                # mean the result window is covered, and on a resume run even
                # the first pages are all-seen. Walk to the end of the result
                # list (or the page cap) instead of stopping on duplicates;
                # the page cap bounds the cost at max_pages * n_queries
                # requests per run (≈13 min at 2 s/request for this config).
                if page >= self.max_pages:
                    break
                if page * self.page_size >= total:
                    break
        self.m.kv_set("source_status:cfws", {"ok": True, "at_utc": utc_iso(), **stats})
        return stats

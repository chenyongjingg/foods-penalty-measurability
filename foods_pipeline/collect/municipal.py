"""Municipal market-regulation bulletin adapters (D1' layer, Plan §4.1).

A config-driven generic adapter: for each registered site, find the column that
publishes administrative penalties (双公示 / 行政处罚 / 处罚公示), keep anchors
whose text matches the food/penalty keywords, follow detail pages, and store
the HTML as raw.

Two failure modes are recorded rather than hidden:

* a JavaScript shell (no anchors, small body) is marked `needs_playwright`;
* a page that answers but carries no penalty column is marked
  `no_penalty_column`, with the discovered candidates listed.

Encoding: several provincial sites serve GB18030/GBK with a wrong or missing
charset, which made every keyword match fail on mojibake (measured on Tianjin,
2026-11-04). Pages are decoded from bytes with an explicit utf-8 → gb18030
fallback instead of trusting `resp.text`.

Detail pages must look like a penalty decision (行政处罚决定书 / 处罚决定 /
被处罚 / 违法行为) before they are registered: a news item that merely mentions
食品 would otherwise enter the intake frame as a document.
"""
from __future__ import annotations

import re
from urllib.parse import urljoin

from ..common import (RateLimiter, cfg, get_logger, http_request, load_yaml,
                      normalize_space, utc_iso)
from .base import Collector

# Anchors that name the penalty-publishing column on a provincial homepage.
_COLUMN_HINT = re.compile(r"双公示|行政处罚|处罚公示|处罚信息|行政执法公示|信用公示|"
                          r"处罚结果|行政处罚决定")
_BAD_URL = re.compile(r"javascript:|^#|login|passport|\.(?:jpg|png|pdf|docx?|xlsx?)$", re.I)
_PENALTY_DOC = re.compile(r"行政处罚决定书|处罚决定书|处罚决定|被处罚|违法行为|"
                          r"没收|罚款")
_FOOD = re.compile(r"食品|餐饮|食用农产品|保健食品|预包装|添加剂")


def decode_body(resp) -> str:
    """Decode a response body without trusting a possibly-wrong charset header."""
    raw = resp.content or b""
    for enc in ("utf-8", "gb18030"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode(resp.encoding or "utf-8", errors="replace")


def as_utf8_html(html: str) -> str:
    """Re-declare a decoded page as UTF-8 before it is written to the raw store.

    The raw file must decode back to the same text: `clean.extract_text` hands
    the bytes to lxml, which obeys the in-page charset declaration. Leaving a
    stale `charset=gb2312` on a body that was already decoded to Unicode makes
    the extraction read mojibake — the exact failure this module now avoids.
    """
    body = re.sub(r"<meta[^>]+charset=[^>]*>", "", html, flags=re.I)
    return '<meta charset="utf-8">' + body


def strip_tags(html: str) -> str:
    return normalize_space(re.sub(r"<script.*?</script>|<style.*?</style>|<[^>]+>",
                                  " ", html, flags=re.S | re.I))


class MunicipalCollector(Collector):
    source = "municipal"

    def __init__(self, manifest=None):
        super().__init__(manifest)
        self.reg = load_yaml("config/sources.yaml")
        self.rate = RateLimiter(float(cfg("runtime.gov_rate_seconds", 2.0)))
        self.max_details = int(cfg("collect.municipal.detail_max_per_site", 30))
        self.max_bytes = int(cfg("collect.municipal.detail_max_bytes", 4_000_000))
        # Calibration budget: how many candidate column URLs are tried per site
        # before the site is declared uncalibrated.
        self.max_candidates = int(cfg("collect.municipal.max_column_candidates", 3))

    # -- fetch helpers ----------------------------------------------------
    def _get(self, url: str) -> tuple[str, int]:
        resp = http_request(self.s, "GET", url, rate=self.rate, timeout=25)
        resp.raise_for_status()
        return decode_body(resp), len(resp.content or b"")

    def _anchors(self, html: str, base: str) -> list[tuple[str, str]]:
        out = []
        for m in re.finditer(r"<a[^>]+href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>",
                             html, re.S | re.I):
            href = urljoin(base, m.group(1).strip())
            text = normalize_space(re.sub(r"<[^>]+>", "", m.group(2)))
            if not text or _BAD_URL.search(href):
                continue
            out.append((href, text))
        return out

    def _columns(self, html: str, base: str) -> list[str]:
        """Candidate URLs of the penalty column, in page order, deduplicated."""
        out, seen = [], set()
        for href, text in self._anchors(html, base):
            if not _COLUMN_HINT.search(text):
                continue
            # A column link is a directory/section, not a single decision page.
            if href in seen or href.rstrip("/") == base.rstrip("/"):
                continue
            seen.add(href)
            out.append(href)
        return out

    def _links(self, html: str, base: str, keywords: list[str],
               regex: str) -> list[tuple[str, str]]:
        out, seen = [], set()
        for href, text in self._anchors(html, base):
            if len(text) < 6 or not any(k in text for k in keywords):
                continue
            if href in seen or not href.startswith("http"):
                continue
            if regex and not re.search(regex, href):
                continue
            seen.add(href)
            out.append((href, text))
        return out

    # -- main loop --------------------------------------------------------
    def run(self) -> dict:
        stats = {"sites": 0, "listed": 0, "details": 0, "new": 0,
                 "not_penalty_doc": 0, "discovered_columns": {},
                 "status": {}, "errors": 0}
        defaults = self.reg.get("defaults", {})
        keywords = defaults.get("link_keywords", ["处罚", "食品"])
        regex = defaults.get("detail_link_regex", "")
        limit = int(defaults.get("list_item_limit", 60))
        log = get_logger("collect.municipal")

        for site in self.reg.get("sites", []):
            slug = site["slug"]
            home = site.get("home") or ""
            list_url = site.get("list_url") or ""
            stats["sites"] += 1
            tried, links, html_len = [], [], 0

            # 1. Registered list URL first (it is the cheapest and auditable).
            candidates = [list_url] if list_url else []
            homepage_html = ""
            if not candidates or site.get("status") != "verified":
                # 2. Otherwise discover the penalty column on the homepage.
                try:
                    homepage_html, hlen = self._get(home)
                    discovered = self._columns(homepage_html, home)
                    stats["discovered_columns"][slug] = discovered[:self.max_candidates]
                    for u in discovered[: self.max_candidates]:
                        if u not in candidates:
                            candidates.append(u)
                except Exception as exc:  # noqa: BLE001
                    stats["status"][slug] = f"home_error:{type(exc).__name__}"
                    stats["errors"] += 1
                    continue

            for url in candidates:
                if url in tried:
                    continue
                tried.append(url)
                try:
                    html, html_len = self._get(url)
                except Exception as exc:  # noqa: BLE001
                    continue
                got = self._links(html, url, keywords, regex)[:limit]
                if got:
                    links, list_url = got, url
                    break

            if not links:
                if candidates and html_len and html_len < 20000:
                    stats["status"][slug] = "needs_playwright"
                elif candidates:
                    stats["status"][slug] = "no_penalty_column"
                else:
                    stats["status"][slug] = "pending_calibration"
                continue

            stats["status"][slug] = f"ok_links:{len(links)}"
            stats["listed"] += len(links)

            for href, text in links[: self.max_details]:
                doc_id = self.doc_id(href)
                if self.m.exists(doc_id):
                    continue
                try:
                    body, _ = self._get(href)
                    plain = strip_tags(body)
                    stats["details"] += 1
                    if not (_PENALTY_DOC.search(plain) and _FOOD.search(plain)):
                        stats["not_penalty_doc"] += 1
                        continue
                    if len(body.encode("utf-8")) > self.max_bytes:
                        continue
                    raw_path = self.save_raw(doc_id, "html",
                                             as_utf8_html(body).encode("utf-8"))
                    inserted = self.register(
                        doc_id=doc_id, native_id=href, url=href, title=text,
                        published=None, raw_path=raw_path,
                        meta={"site": slug, "site_name": site.get("name"),
                              "list_url": list_url})
                    if inserted:
                        stats["new"] += 1
                except Exception as exc:  # noqa: BLE001
                    stats["errors"] += 1
                    log.warning("detail failed %s: %s", href, exc)
            log.info("municipal %s: %s new=%d", slug, stats["status"][slug],
                     stats["new"])

        stats["at_utc"] = utc_iso()
        self.m.kv_set("source_status:municipal", stats)
        return stats

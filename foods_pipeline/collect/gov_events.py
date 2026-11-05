"""D4 governance-event timeline (Plan Table 2, D4).

The plan's D4 specification is: D2 + the two supreme-court/procuratorate case
release pages (court.gov.cn / spp.gov.cn, static), auto-extracted, with the
event type and date judged automatically and no manual verification.

This module does the deterministic half — date, title, URL, site — and a
rule-based type judgement.  The rules are stored on every event
(`type_rule`) so the LLM pass (when the GPU is free) can be compared against
them rather than silently replacing them.  Nothing here invents a date: an
item whose date cannot be read is kept with `date: null` and counted in
`undated`, never imputed.

Storage:
  data/events/gov_events.jsonl   append-only, one event per line, keyed by URL
  data/events/gov_events_summary.json   counts by year / type / site
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

from ..common import (RateLimiter, cfg, get_logger, http_request, http_session,
                      load_yaml, path_of, sha256_text, utc_iso)
from ..manifest import Manifest

DATE_RE = re.compile(r"(20\d{2})\s*[-/年.]\s*(\d{1,2})\s*[-/月.]\s*(\d{1,2})")
META_DATE_RE = re.compile(
    r'<meta[^>]+name="(?:PubDate|pubdate|publishdate|ArticleTitle|firstpublishedtime)"'
    r'[^>]+content="([^"]+)"', re.I)
ANCHOR_RE = re.compile(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.S)
TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")

# Keyword families.  `food` is the primary relevance flag; `fraud` and
# `enforcement` describe the governance action.  An item is kept when it is
# food-related, or when it concerns fraud enforcement in general (the 铁拳
# campaign is cross-sector and still a regime-level shock for food).
FAMILIES = {
    "food": ["食品", "食用农产品", "农产品", "餐饮", "保健食品", "食品添加剂", "舌尖"],
    "fraud": ["假冒", "伪劣", "造假", "欺诈", "虚假", "伪造", "篡改", "商标",
              "认证", "检验报告", "检测报告", "溯源", "合格证"],
    "enforcement": ["铁拳", "整治", "专项行动", "打击", "查处", "典型案例",
                    "指导性案例", "通告", "抽检", "执法"],
}

# Order matters: a title is classified by the first family it matches.
# `activity` comes first because 座谈/培训/比武 notices are administrative
# routine, not governance shocks, and must not be read as `inspection`.
TYPE_RULES = [
    ("activity", ["座谈", "培训", "比武", "交流", "党支部", "联学", "调研",
                  "消费提示", "工作会"]),
    ("case_series", ["典型案例", "指导性案例", "案例"]),
    ("policy", ["解释", "意见", "规定", "办法", "决定", "通知", "条例", "公告"]),
    ("crackdown", ["铁拳", "专项行动", "整治", "严打", "打击"]),
    ("judicial", ["判决", "宣判", "审判", "起诉", "批捕", "公诉", "再审"]),
    ("inspection", ["抽检", "通告", "不合格", "通报", "风险预警"]),
]

SKIP_TITLES = {"首页", "上一页", "下一页", "尾页", "更多", "返回", "网站地图"}


def clean_text(s: str) -> str:
    return WS_RE.sub(" ", TAG_RE.sub("", s)).replace("　", " ").strip()


def norm_date(m: re.Match) -> str | None:
    y, mo, d = (int(m.group(i)) for i in (1, 2, 3))
    try:
        return datetime(y, mo, d).strftime("%Y-%m-%d")
    except ValueError:
        return None


def families(title: str) -> dict:
    return {k: sorted({w for w in words if w in title}) for k, words in FAMILIES.items()}


def is_kept(fam: dict, title: str = "") -> bool:
    # A 典型案例/指导性案例 batch is a governance event even when its title
    # does not say 食品: the batch usually mixes sectors.  Those enter with
    # food_specific=False, never as food-specific events, so H2 stays clean.
    if "典型案例" in title or "指导性案例" in title:
        return True
    return bool(fam["food"]) or bool(fam["fraud"] and fam["enforcement"])


def classify(title: str) -> str:
    for name, words in TYPE_RULES:
        if any(w in title for w in words):
            return name
    return "other"


class GovEventsCollector:
    source = "gov_events"

    def __init__(self, manifest: Manifest | None = None):
        self.m = manifest or Manifest()
        self.log = get_logger("collect.gov_events")
        self.cfg = load_yaml("config/gov_sources.yaml")
        self.rate = RateLimiter(float(cfg("runtime.gov_rate_seconds", 2.0)))
        self.s = http_session()
        # GOV_EVENTS_DRY=1 parses and reports without touching data/events;
        # used to test the listing parser before a full crawl is committed.
        self.dry = os.environ.get("GOV_EVENTS_DRY") == "1"
        self.out_dir = path_of("data") / "events"
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.out_dir / "gov_events.jsonl"

    # ---------------- parsing ----------------
    def parse_listing(self, html: str, base_url: str,
                      date_required: bool = True) -> list[dict]:
        items: list[dict] = []
        seen: set[str] = set()

        def add(date: str | None, title: str, href: str, how: str) -> None:
            title = clean_text(title)
            if len(title) < 4 or title in SKIP_TITLES:
                return
            url = urljoin(base_url, href)
            if not url.startswith("http") or url in seen:
                return
            seen.add(url)
            items.append({"date": date, "title": title, "url": url, "parsed_by": how})

        # Pass 1: list blocks (<li>/<tr>) that carry both an anchor and a date.
        for block in re.findall(r"<(?:li|tr)[^>]*>(.*?)</(?:li|tr)>", html, re.S | re.I):
            dm = DATE_RE.search(block)
            if not dm:
                continue
            date = norm_date(dm)
            for am in ANCHOR_RE.finditer(block):
                add(date, am.group(2), am.group(1), "block")
        # Pass 2: anchors with a date in their immediate neighbourhood.  Some
        # columns place the date in a sibling <span> outside the <li>.
        for am in ANCHOR_RE.finditer(html):
            href = am.group(1)
            if not href.startswith(("/", "http")):
                continue
            window = html[max(0, am.start() - 400): am.start()]
            dm = DATE_RE.search(window)
            if dm:
                add(norm_date(dm), am.group(2), href, "window")
        if not date_required:
            # JS-driven columns render article links without dates; the date
            # is read from the article page instead.  Restrict to CMS article
            # URLs so navigation/footer links do not enter the pool.
            for am in ANCHOR_RE.finditer(html):
                href = am.group(1)
                if "art_" not in href and "/art/" not in href:
                    continue
                add(None, am.group(2), href, "article_pending")
        return items

    def parse_article_date(self, html: str) -> str | None:
        mm = META_DATE_RE.search(html)
        if mm:
            dm = DATE_RE.search(mm.group(1))
            if dm:
                return norm_date(dm)
        # Article pages put the publication date before the body; take the
        # first date in the page.
        dm = DATE_RE.search(html)
        return norm_date(dm) if dm else None

    def fetch(self, url: str) -> str | None:
        try:
            resp = http_request(self.s, "GET", url, rate=self.rate)
            if resp.status_code != 200:
                self.log.warning("%s status=%s", url, resp.status_code)
                return None
            resp.encoding = resp.apparent_encoding or resp.encoding
            return resp.text
        except Exception as exc:  # noqa: BLE001
            self.log.warning("%s failed: %s", url, exc)
            return None

    # ---------------- run ----------------
    def run(self) -> dict:
        stats = {"sources": {}, "kept": 0, "new": 0, "undated": 0, "at_utc": utc_iso()}
        known: set[str] = set()
        if self.path.exists():
            with open(self.path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        known.add(json.loads(line)["url"])

        out = None if self.dry else open(self.path, "a", encoding="utf-8")
        try:
            for src in self.cfg.get("sources", []):
                name = src["name"]
                s_stat = {"pages": 0, "items": 0, "kept": 0, "articles": 0, "errors": 0}
                cap = int(os.environ.get("GOV_EVENTS_MAX_PAGES",
                                         src.get("max_pages", 1)))
                for page in range(1, cap + 1):
                    url = src["url"] if page == 1 else src.get("page_url", "").format(n=page)
                    if not url:
                        break
                    html = self.fetch(url)
                    if html is None:
                        s_stat["errors"] += 1
                        break
                    s_stat["pages"] += 1
                    items = self.parse_listing(html, url,
                                               date_required=not src.get("follow_articles"))
                    s_stat["items"] += len(items)
                    if page > 1 and not items:
                        break

                    if src.get("follow_articles"):
                        items = items[: int(os.environ.get("GOV_EVENTS_ARTICLE_MAX",
                                                     src.get("article_max", 25)))]
                        for it in items:
                            s_stat["articles"] += 1
                            art = self.fetch(it["url"])
                            if art:
                                it["date"] = self.parse_article_date(art)

                    for it in items:
                        fam = families(it["title"])
                        if not is_kept(fam, it["title"]):
                            continue
                        s_stat["kept"] += 1
                        if not it["date"]:
                            stats["undated"] += 1
                        rec = {
                            "event_id": "gov:" + sha256_text(it["url"])[:24],
                            "date": it["date"],
                            "title": it["title"],
                            "url": it["url"],
                            "site": src.get("site"),
                            "source": name,
                            "event_type": classify(it["title"]),
                            "type_rule": "keyword",
                            "food_specific": bool(fam["food"]),
                            "keywords": fam,
                            "parsed_by": it["parsed_by"],
                            "first_seen_utc": utc_iso(),
                        }
                        if it["url"] not in known:
                            if not self.dry:
                                out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                            known.add(it["url"])
                            stats["new"] += 1
                        stats["kept"] += 1
                    if page >= cap:
                        break
                stats["sources"][name] = s_stat
                self.log.info("gov_events %s: %s", name, s_stat)
        finally:
            if out is not None:
                out.close()

        summary = self.summarise()
        if self.dry:
            return {**stats, "summary": summary, "dry_run": True}
        self.m.kv_set("gov_events", {"ok": True, **{k: v for k, v in stats.items()
                                                    if k != "sources"},
                                     "summary": summary, "at_utc": utc_iso()})
        return {**stats, "summary": summary}

    def summarise(self) -> dict:
        rows = []
        if self.path.exists():
            with open(self.path, "r", encoding="utf-8") as f:
                rows = [json.loads(line) for line in f if line.strip()]
        by_year: dict[str, int] = {}
        by_type: dict[str, int] = {}
        by_site: dict[str, int] = {}
        for r in rows:
            y = (r.get("date") or "undated")[:4]
            by_year[y] = by_year.get(y, 0) + 1
            by_type[r.get("event_type")] = by_type.get(r.get("event_type"), 0) + 1
            by_site[r.get("site")] = by_site.get(r.get("site"), 0) + 1
        summ = {"n": len(rows), "by_year": dict(sorted(by_year.items())),
                "by_type": dict(sorted(by_type.items())), "by_site": by_site,
                "food_specific": sum(1 for r in rows if r.get("food_specific")),
                "at_utc": utc_iso()}
        (self.out_dir / "gov_events_summary.json").write_text(
            json.dumps(summ, ensure_ascii=False, indent=2), encoding="utf-8")
        return summ

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Diagnose why the municipal (D1') layer returns no links (read-only).

For each probe site: fetch the registered list URL, report status code, body
size, anchor count, how many anchors carry a penalty/food keyword, and a few
sample anchor texts. Nothing is written to the manifest.
"""
import re
import sys
from urllib.parse import urljoin

sys.path.insert(0, "/opt/foods")
from foods_pipeline.common import RateLimiter, cfg, http_request, load_yaml, normalize_space  # noqa: E402

SITES = [
    ("beijing", "https://scjgj.beijing.gov.cn/bsfw/fwdy/xygs/"),
    ("beijing_alt", "https://scjgj.beijing.gov.cn/"),
    ("shanghai", "https://scjgj.sh.gov.cn/"),
    ("tianjin", "https://scjg.tj.gov.cn/"),
    ("zhejiang", "https://zjamr.zj.gov.cn/"),
    ("jiangsu", "https://scjgj.jiangsu.gov.cn/"),
]
KW = ["处罚", "行政处罚", "食品", "公示"]


def main() -> int:
    rate = RateLimiter(float(cfg("runtime.gov_rate_seconds", 2.0)))
    import requests
    s = requests.Session()
    s.headers.update({"User-Agent": cfg("runtime.user_agent")})
    for slug, url in SITES:
        try:
            r = http_request(s, "GET", url, rate=rate, timeout=25)
            html = r.text or ""
            anchors = re.findall(r"<a[^>]+href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", html, re.S | re.I)
            kw = []
            for href, text in anchors:
                t = normalize_space(re.sub(r"<[^>]+>", "", text))
                if t and any(k in t for k in KW):
                    kw.append((urljoin(url, href)[:110], t[:40]))
            print(f"[{slug}] {url} status={r.status_code} bytes={len(r.content)} "
                  f"ctype={(r.headers.get('content-type') or '')[:40]} anchors={len(anchors)} kw={len(kw)}")
            for h, t in kw[:4]:
                print(f"    {t} -> {h}")
            if not kw:
                print("    sample anchors:", [normalize_space(re.sub(r'<[^>]+>', '', x[1]))[:30]
                                             for x in anchors[:6]])
        except Exception as exc:  # noqa: BLE001
            print(f"[{slug}] {url} ERROR {type(exc).__name__}: {str(exc)[:100]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

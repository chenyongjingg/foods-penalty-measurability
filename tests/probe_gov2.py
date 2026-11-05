"""Second probe: listing pages likely to carry dated governance events."""
from __future__ import annotations

import re

import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
URLS = [
    "https://www.court.gov.cn/zixun/gengduo/104.html",
    "https://www.samr.gov.cn/spcjs/sjdt/",
    "https://www.samr.gov.cn/zt/",
    "https://www.samr.gov.cn/xw/zj/",
    "https://www.spp.gov.cn/spp/zdgz/",
    "https://www.spp.gov.cn/spp/xwfbh/",
]
D = re.compile(r"20\d{2}[-/年.]\d{1,2}[-/月.]\d{1,2}")

for url in URLS:
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=25, verify=False)
        txt = r.text
        print(f"== {url} status={r.status_code} bytes={len(txt)} dates={len(D.findall(txt))}")
        blocks = re.findall(r"<li[^>]*>(.*?)</li>", txt, re.S)
        shown = 0
        for b in blocks:
            m = re.search(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', b, re.S)
            if not m:
                continue
            label = re.sub(r"<[^>]+>", "", m.group(2)).strip()
            d = D.search(b)
            if label and d:
                print("   ", d.group(0), label[:40], m.group(1)[:80])
                shown += 1
            if shown >= 4:
                break
    except Exception as exc:
        print(f"== {url} ERROR {type(exc).__name__}: {exc}")

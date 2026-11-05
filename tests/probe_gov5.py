"""Fifth probe: spp typical-case columns + court page 2 content."""
from __future__ import annotations

import re

import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
D = re.compile(r"20\d{2}[-/年.]\d{1,2}[-/月.]\d{1,2}")
URLS = [
    ("https://www.spp.gov.cn/spp/dxal/", "utf-8"),
    ("https://www.spp.gov.cn/spp/jczdal/", "utf-8"),
    ("https://www.spp.gov.cn/spp/zdgz/", "utf-8"),
    ("https://www.spp.gov.cn/spp/xwfbh/", "utf-8"),
    ("https://www.court.gov.cn/zixun/gengduo/104_2.html", "utf-8"),
]
for url, enc in URLS:
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=25, verify=False)
        r.encoding = enc
        txt = r.text
        items = []
        for b in re.findall(r"<li[^>]*>(.*?)</li>", txt, re.S):
            m = re.search(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', b, re.S)
            d = D.search(b)
            if m and d:
                t = re.sub(r"<[^>]+>", "", m.group(2)).strip()
                items.append((d.group(0), t[:48], m.group(1)[:70]))
        food = [i for i in items if re.search(r"食品|食用农产品|假冒|伪劣|认证|检验|溯源", i[1])]
        print(f"== {url} {r.status_code} bytes={len(r.content)} items={len(items)} food={len(food)}")
        for i in (food or items)[:3]:
            print("   ", i)
    except Exception as exc:
        print(f"== {url} ERROR {exc}")

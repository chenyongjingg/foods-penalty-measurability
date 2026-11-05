"""Third probe: samr listing structure + spp charset."""
from __future__ import annotations

import re

import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
URLS = [
    "https://www.samr.gov.cn/spcjs/",
    "https://www.samr.gov.cn/spcjs/sjdt/",
    "https://www.samr.gov.cn/spcjs/spcj/",
    "https://www.samr.gov.cn/zw/zfxxgk/fdzdgknr/spcjs/",
    "https://www.samr.gov.cn/xw/mtjj/",
]
for url in URLS:
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=25, verify=False)
        r.encoding = r.apparent_encoding
        txt = r.text
        links = re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', txt, re.S)
        food = [(re.sub(r"<[^>]+>", "", l).strip()[:44], h)
                for h, l in links
                if re.search(r"食品|抽检|铁拳|整治|通告", re.sub(r"<[^>]+>", "", l))]
        print(f"== {url} status={r.status_code} bytes={len(r.content)} "
              f"enc={r.encoding} links={len(links)} food_links={len(food)}")
        for f in food[:5]:
            print("   ", f)
        if not food:
            print("    sample:", [re.sub(r"<[^>]+>", "", l).strip()[:30] for _, l in links[:8]])
    except Exception as exc:
        print(f"== {url} ERROR {type(exc).__name__}: {exc}")

r = requests.get("https://www.spp.gov.cn/spp/zdgz/",
                 headers={"User-Agent": UA}, timeout=25, verify=False)
print("spp header charset:", r.headers.get("Content-Type"), "apparent:", r.apparent_encoding)

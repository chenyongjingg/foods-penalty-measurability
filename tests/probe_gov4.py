"""Fourth probe: find samr dynamic list endpoint; check court pagination."""
from __future__ import annotations

import re

import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

r = requests.get("https://www.samr.gov.cn/spcjs/sjdt/", headers={"User-Agent": UA},
                 timeout=25, verify=False)
r.encoding = "utf-8"
print("== shell /spcjs/sjdt/ ==")
print(r.text[:3000])

for u in ["https://www.samr.gov.cn/spcjs/sjdt/index.html",
          "https://www.samr.gov.cn/spcjs/sjdt/index_1.html",
          "https://www.samr.gov.cn/spcjs/index.html",
          "https://www.samr.gov.cn/spcjs/gdt/"]:
    try:
        rr = requests.get(u, headers={"User-Agent": UA}, timeout=20, verify=False)
        rr.encoding = "utf-8"
        links = re.findall(r'href="([^"]*art_[^"]+)"[^>]*>([^<]{4,60})', rr.text)
        print(f"== {u} {rr.status_code} bytes={len(rr.content)} artlinks={len(links)}")
        for h, t in links[:4]:
            print("   ", t.strip()[:40], h[:70])
    except Exception as exc:
        print(f"== {u} ERROR {exc}")

for p in (1, 2):
    u = ("https://www.court.gov.cn/zixun/gengduo/104.html" if p == 1
         else f"https://www.court.gov.cn/zixun/gengduo/104_{p}.html")
    rr = requests.get(u, headers={"User-Agent": UA}, timeout=20, verify=False)
    rr.encoding = "utf-8"
    print(f"== court p{p} {rr.status_code} bytes={len(rr.content)}")

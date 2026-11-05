"""Probe government pages for a D4 governance-event timeline (diagnostics)."""
from __future__ import annotations

import re
import sys

import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

URLS = [
    "https://www.samr.gov.cn/",
    "https://www.samr.gov.cn/xw/",
    "https://www.samr.gov.cn/spcjs/",
    "https://www.court.gov.cn/",
    "https://www.spp.gov.cn/",
    "https://www.spp.gov.cn/spp/dxal/",
]

KEY = re.compile(r"食品|铁拳|典型案例|抽检|整治|假冒|伪劣|造假")

for url in URLS:
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=25, verify=False)
        txt = r.text
        hits = []
        for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', txt, re.S):
            href, label = m.group(1), re.sub(r"<[^>]+>", "", m.group(2)).strip()
            if KEY.search(label) and 6 <= len(label) <= 60:
                hits.append((label[:40], href[:110]))
        print(f"== {url} status={r.status_code} bytes={len(txt)} hits={len(hits)}")
        for h in hits[:6]:
            print("   ", h)
    except Exception as exc:
        print(f"== {url} ERROR {type(exc).__name__}: {exc}")
    sys.stdout.flush()

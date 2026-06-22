#!/usr/bin/env python3
import re
import requests
from gaokao_crawl_lib import HEADERS

url = "https://gaokao.eol.cn/zhe_jiang/dongtai/202506/t20250625_2677143.shtml"
h = requests.get(url, headers=HEADERS, timeout=30).text
print("len", len(h))
print("Wjpg", len(re.findall(r"W\d+\.jpg", h, re.I)))
print("rel jpg", re.findall(r'href="(\./W\d+\.jpg)"', h, re.I)[:6])
fname = "W020250625647737442659.jpg"
i = h.find(fname)
open("data/_probe_zj_snippet.txt", "w", encoding="utf-8").write(h[max(0, i - 120) : i + 200] if i >= 0 else "not found")
print("snippet written", i)

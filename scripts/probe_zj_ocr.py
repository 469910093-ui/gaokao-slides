#!/usr/bin/env python3
import requests
from gaokao_crawl_lib import HEADERS, parse_eol_image_table, scrape_eol_entry, CatalogEntry

url = "https://gaokao.eol.cn/zhe_jiang/dongtai/202506/t20250625_2677143.shtml"
s = requests.Session()
html = requests.get(url, headers=HEADERS, timeout=30).text
segs, total = parse_eol_image_table(s, html, url)
print("image_table", len(segs), total)
if segs:
    print("top", segs[0], "bottom", segs[-1])
r = scrape_eol_entry(s, CatalogEntry("浙江", 2025, None, "", url))
print("scrape", bool(r), len(r.segments) if r else 0)

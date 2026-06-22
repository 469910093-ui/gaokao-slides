#!/usr/bin/env python3
import re
import requests
from gaokao_crawl_lib import HEADERS, scrape_eol_entry, CatalogEntry, parse_eol_segments_from_html

urls = [
    ("浙江", "https://gaokao.eol.cn/zhe_jiang/dongtai/202506/t20250625_2677143.shtml"),
    ("广东", "https://gaokao.eol.cn/guang_dong/dongtai/202506/t20250626_2677410.shtml"),
    ("湖北", "https://gaokao.eol.cn/hu_bei/dongtai/202506/t20250627_2677496.shtml"),
]
s = requests.Session()
for prov, url in urls:
    html = requests.get(url, headers=HEADERS, timeout=30).text
    imgs = re.findall(r'(?:href|src)="([^"]+\.(?:jpg|png|jpeg))"', html, re.I)
    print(prov, "imgs", len(imgs), imgs[:3])
    segs, total, kind = parse_eol_segments_from_html(s, html, url)
    print("  parse", kind, len(segs), total)
    r = scrape_eol_entry(s, CatalogEntry(prov, 2025, None, "", url))
    print("  scrape", bool(r), len(r.segments) if r else 0, r.source if r else None)

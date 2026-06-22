#!/usr/bin/env python3
"""Find HTML-table vs image-only EOL segment articles per province/year."""
import json
import re
import requests
from collections import defaultdict

from gaokao_crawl_lib import HEADERS, parse_eol_table, scrape_eol_entry, CatalogEntry

TARGETS = [
    "北京", "上海", "浙江", "广东", "四川", "山东", "云南", "广西",
    "江苏", "湖北", "辽宁", "吉林", "黑龙江",
]

catalog = json.load(open("data/eol_catalog.json", encoding="utf-8"))
by_py: dict[tuple[str, int], list] = defaultdict(list)
for e in catalog:
    if e["province"] in TARGETS:
        by_py[(e["province"], e["year"])].append(e)

s = requests.Session()
report = []
for prov in TARGETS:
    for year in range(2014, 2026):
        entries = by_py.get((prov, year), [])
        if not entries:
            report.append((prov, year, "no_catalog", 0, ""))
            continue
        best = None
        for e in entries[:8]:
            url = e["url"]
            r = scrape_eol_entry(s, CatalogEntry(**e))
            if not r:
                html = requests.get(url, headers=HEADERS, timeout=25).text
                imgs = len(re.findall(r"\.(?:jpg|png|jpeg)", html, re.I))
                trs = html.lower().count("<tr")
                kind = "image" if imgs > 3 and trs < 5 else "fail"
                report.append((prov, year, kind, 0, url[-40:]))
                continue
            report.append((prov, year, "html", len(r.segments), r.title[:40]))

for row in report:
    if row[2] in ("no_catalog", "image", "fail") or row[1] >= 2023:
        print(row)

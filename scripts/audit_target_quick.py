#!/usr/bin/env python3
import json
import re
import requests
from gaokao_crawl_lib import HEADERS, scrape_eol_entry, CatalogEntry

TARGETS = ["北京","上海","浙江","广东","四川","山东","云南","广西","江苏","湖北","辽宁","吉林","黑龙江"]
catalog = json.load(open("data/eol_catalog.json", encoding="utf-8"))
s = requests.Session()

for prov in TARGETS:
    for year in range(2023, 2026):
        entries = [e for e in catalog if e["province"]==prov and e["year"]==year]
        html_best = 0
        has_image = False
        for e in entries:
            r = scrape_eol_entry(s, CatalogEntry(**e))
            if r and len(r.segments) > html_best:
                html_best = len(r.segments)
            elif not r:
                html = requests.get(e["url"], headers=HEADERS, timeout=20).text
                if len(re.findall(r"\.(?:jpg|png)", html, re.I)) > 2:
                    has_image = True
        print(prov, year, "html_max", html_best, "image_only" if has_image and html_best==0 else "")

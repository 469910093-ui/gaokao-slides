#!/usr/bin/env python3
"""Catalog coverage for target provinces 2014-2025."""
import json
from collections import defaultdict

TARGETS = [
    "北京", "上海", "浙江", "广东", "四川", "山东", "云南", "广西",
    "江苏", "湖北", "辽宁", "吉林", "黑龙江",
]
catalog = json.load(open("data/eol_catalog.json", encoding="utf-8"))
by = defaultdict(int)
for e in catalog:
    if e["province"] in TARGETS:
        by[(e["province"], e["year"])] += 1

for prov in TARGETS:
    years = [y for y in range(2014, 2026) if by[(prov, y)]]
    missing = [y for y in range(2014, 2026) if not by[(prov, y)]]
    print(f"{prov}: {len(years)} years, entries={sum(by[(prov,y)] for y in years)}, missing={missing}")

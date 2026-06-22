#!/usr/bin/env python3
import json, re
from collections import Counter
from pathlib import Path

rows = json.loads(Path(__file__).parent.parent.joinpath("data/eol_all_urls.json").read_text(encoding="utf-8"))
for r in rows:
    m = re.search(r"/dongtai/(20\d{2})\d{2}/", r["url"])
    r["year"] = int(m.group(1)) if m else None
years = Counter(r["year"] for r in rows)
print(years)
for r in rows:
    if r["year"] == 2024:
        print(r["slug"], r["url"][-50:])

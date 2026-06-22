#!/usr/bin/env python3
import re, requests, json
from pathlib import Path

url = "https://www.zizzs.com/gk/gaokao/203076.html"
t = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=25).text
# markdown table rows
rows = re.findall(r"\|\s*(\d{3}\+?|\d{3}分|特控线|本科线)\s*\|\s*([\d,]+)名", t)
print("rows", rows[:10])
Path(__file__).parent.parent.joinpath("data/zizzs_probe.json").write_text(
    json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8"
)

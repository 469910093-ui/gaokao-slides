#!/usr/bin/env python3
import re, requests, json
from pathlib import Path

u = "https://gaokao.eol.cn/jiang_su/dongtai/202406/t20240625_2619080.shtml"
t = requests.get(u, headers={"User-Agent": "Mozilla/5.0"}, timeout=25).text
anchors = {
    "undergrad_over": re.findall(r"(\d{2,7})人超本科线", t),
    "special_over": re.findall(r"(\d{2,7})人超特招线|(\d{2,7})人超特殊类型", t),
    "undergrad_line": re.findall(r"物理本科线(\d{3})分|本科线(\d{3})分", t),
    "special_line": re.findall(r"物理特招线(\d{3})分|特招线(\d{3})分", t),
}
Path(__file__).parent.parent.joinpath("data/jiangsu_anchors.json").write_text(
    json.dumps(anchors, ensure_ascii=False, indent=2), encoding="utf-8"
)
# find cumulative at 462 from table
rows = re.findall(r"<tr[^>]*>\s*<td[^>]*>([^<]+)</td>\s*<td[^>]*>(\d+)</td>\s*<td[^>]*>(\d+)</td>", t, re.I)
for score, cnt, cum in rows:
    if score.strip() == "462":
        print("score 462 cum", cum)
print("anchors", anchors)

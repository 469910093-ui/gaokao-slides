#!/usr/bin/env python3
import re
from pathlib import Path

import requests

from gaokao_crawl_lib import HEADERS, parse_eol_table

ROOT = Path(__file__).resolve().parents[1]
url = "https://gaokao.eol.cn/shang_hai/dongtai/202506/t20250623_2676341.shtml"
r = requests.get(url, headers=HEADERS, timeout=30)
r.encoding = "utf-8"
t = r.text
(ROOT / "data" / "tmp_sh.html").write_text(t, encoding="utf-8")

print("len", len(t))
print("iframe", t.lower().count("iframe"))
for m in re.finditer(r"<iframe[^>]*>", t, re.I):
    print("tag", m.group(0)[:200])

# object/embed
for pat in (r"src=['\"]([^'\"]+)['\"]", r"url\(['\"]?([^'\"]+)['\"]?\)"):
    hits = re.findall(pat, t)
    interesting = [h for h in hits if any(k in h.lower() for k in ("xls", "doc", "pdf", "static", "upload", "file"))]
    print(pat, len(interesting), interesting[:8])

# script blocks with data
for m in re.finditer(r"<script[^>]*>([\s\S]{0,5000}?)</script>", t, re.I):
    body = m.group(1)
    if any(k in body for k in ("分数", "累计", "分段", "score", "data")):
        print("script snippet", body[:400].replace("\n", " "))
        break

# vue/react json
for m in re.finditer(r"(\[\s*\{\s*\"(?:score|分数)\"[\s\S]{0,800}?\}\s*\])", t):
    print("json array", m.group(1)[:200])
    break

segs, total = parse_eol_table(t)
print("direct parse", len(segs), total)

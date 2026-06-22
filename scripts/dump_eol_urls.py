#!/usr/bin/env python3
import json, re, requests
from pathlib import Path

HEADERS = {"User-Agent": "Mozilla/5.0"}
text = requests.get("https://gaokao.eol.cn/e_html/gk/gkfsd/", headers=HEADERS, timeout=30).text
text = text  # utf-8 ok in json dump
urls = sorted(set(
    ("https://gaokao.eol.cn" + m if m.startswith("/") else m)
    for m in re.findall(r'href="([^"]+)"', text)
    if "/dongtai/20" in m and m.endswith(".shtml")
))
rows = []
for url in urls:
    if url.startswith("/"):
        url = "https://gaokao.eol.cn" + url
    slug = re.search(r"gaokao\.eol\.cn/([a-z0-9_]+)/", url)
    ym = re.search(r"/20(\d{2})\d{4}/", url)
    year = 2000 + int(ym.group(1)) if ym else None
    idx = text.find(url.replace("https://gaokao.eol.cn", ""))
    snippet = text[max(0, idx-200):idx+100] if idx>=0 else ""
    title_m = re.search(r">([^<>]{4,120})</a>", snippet)
    title = title_m.group(1).strip() if title_m else ""
    rows.append({"url": url, "slug": slug.group(1) if slug else None, "year": year, "title": title})

Path(__file__).parent.parent.joinpath("data/eol_all_urls.json").write_text(
    json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8"
)
print("count", len(rows))
from collections import Counter
print("years", Counter(r["year"] for r in rows))
print("slugs", Counter(r["slug"] for r in rows))

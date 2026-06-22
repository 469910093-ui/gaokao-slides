#!/usr/bin/env python3
import re
import requests
from gaokao_crawl_lib import scrape_eol_entry, CatalogEntry, parse_eol_table, HEADERS

url = "https://gaokao.eol.cn/shang_hai/dongtai/202506/t20250623_2676341.shtml"
r = requests.get(url, headers=HEADERS, timeout=30)
r.encoding = "utf-8"
t = r.text
iframes = re.findall(r'<iframe[^>]+src="([^"]+)"', t, re.I)
print("iframes", len(iframes))
for src in iframes:
    full = src if src.startswith("http") else "https://gaokao.eol.cn" + src
    print(" ->", full[:120])
    try:
        ir = requests.get(full, headers=HEADERS, timeout=30)
        ir.encoding = ir.apparent_encoding or "utf-8"
        segs, total = parse_eol_table(ir.text)
        print("    status", ir.status_code, "len", len(ir.text), "segs", len(segs), "total", total)
        if segs:
            print("    sample", segs[:3])
    except Exception as exc:
        print("    err", exc)

# also check TRS_Editor content
ed = re.search(r'class=["\']?TRS_Editor["\']?[^>]*>(.*?)</div>', t, re.S | re.I)
if ed:
    inner = ed.group(1)
    print("editor inner len", len(inner), "tr", inner.lower().count("<tr"))
    segs, total = parse_eol_table(inner)
    print("editor segs", len(segs))

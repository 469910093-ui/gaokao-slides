#!/usr/bin/env python3
import re
import requests

url = "https://gaokao.eol.cn/e_html/gk/gkfsd/"
r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
r.encoding = r.apparent_encoding or "utf-8"
text = r.text
print("status", r.status_code, "len", len(text))

# province blocks with year links
blocks = re.findall(r"([^<\n]{2,8}20\d{2}年[^<\n]*一分一段[^<\n]*)", text)
print("blocks sample", blocks[:10])

links = re.findall(r'href="([^"]+)"[^>]*>([^<]*一分一段[^<]*)', text)
print("table links", len(links))
for u, t in links[:20]:
    print(repr(t.strip()[:50]), u)

all_eol = sorted(set(re.findall(r'href="(https?://gaokao\.eol\.cn/[^"]+)"', text)))
print("all gaokao links", len(all_eol))
for u in all_eol[:30]:
    print(u)

# search for 2024 article links with tables
for prov_slug in ["jiang_su", "bei_jing", "guang_dong", "he_nan", "si_chuan"]:
    pat = rf"gaokao\.eol\.cn/{prov_slug}/[^\"']+"
    m = re.findall(pat, text)
    print(prov_slug, len(m), m[:3])

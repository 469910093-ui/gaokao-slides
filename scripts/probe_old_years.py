#!/usr/bin/env python3
"""Probe EOL archives for 2014-2020 segment pages."""
import re
import requests

HEADERS = {"User-Agent": "Mozilla/5.0"}
TARGET_SLUGS = [
    "bei_jing", "shang_hai", "zhe_jiang", "guang_dong", "si_chuan", "shan_dong",
    "yun_nan", "guang_xi", "jiang_su", "hu_bei", "liao_ning", "ji_lin", "hei_long_jiang",
]
pages = [
    "https://www.eol.cn/html/gk/gkfsd/index.shtml",
    "https://gaokao.eol.cn/e_html/gk/gkfsd/",
]
for page in pages:
    try:
        r = requests.get(page, headers=HEADERS, timeout=30)
        r.encoding = "utf-8"
        text = r.text
        print(page, r.status_code, "len", len(text))
        for y in range(2014, 2021):
            pat = rf"{y}[^<]{{0,40}}一分一段"
            print(" ", y, len(re.findall(pat, text)))
        for slug in TARGET_SLUGS[:3]:
            links = re.findall(rf'href="([^"]*{slug}/dongtai/20[^"]+\.shtml)"', text)
            print(" ", slug, "links", len(links))
    except Exception as exc:
        print(page, exc)

for y in range(2014, 2021):
    url = f"https://gaokao.eol.cn/e_html/gk/gkfsd/{y}.shtml"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        n = len(re.findall(r"/dongtai/20", r.text)) if r.status_code == 200 else 0
        print("year page", y, r.status_code, n)
    except Exception as exc:
        print("year page", y, exc)

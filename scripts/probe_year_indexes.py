#!/usr/bin/env python3
import re, requests
HEADERS={"User-Agent":"Mozilla/5.0"}
for y in range(2014, 2026):
    url=f"https://gaokao.eol.cn/e_html/gk/gkfsd/{y}.shtml"
    try:
        r=requests.get(url, headers=HEADERS, timeout=15)
        n=len(re.findall(r"/dongtai/20", r.text)) if r.status_code==200 else 0
        print(y, r.status_code, n)
    except Exception as e:
        print(y, e)

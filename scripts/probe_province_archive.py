#!/usr/bin/env python3
import re, requests
HEADERS={"User-Agent":"Mozilla/5.0"}
for slug in ["jiang_su","shan3_xi","shan_xi","shaan_xi","shanxi"]:
    url=f"https://gaokao.eol.cn/{slug}/dongtai/"
    try:
        r=requests.get(url, headers=HEADERS, timeout=20)
        links=len(re.findall(r'/dongtai/20', r.text))
        print(slug, r.status_code, links)
    except Exception as e:
        print(slug, e)

#!/usr/bin/env python3
import re, requests
HEADERS={"User-Agent":"Mozilla/5.0"}
for q in ["江苏 2024 一分一段 物理", "山东 2023 一分一段"]:
    for base in [
        f"https://gaokao.eol.cn/search?keyword={q}",
        f"https://so.eol.cn/s?site=gaokao&q={q}",
    ]:
        try:
            r=requests.get(base, headers=HEADERS, timeout=20)
            links=len(re.findall(r'dongtai/20\d+', r.text))
            print(base[:60], r.status_code, links)
        except Exception as e:
            print(base[:60], e)

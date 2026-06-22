#!/usr/bin/env python3
"""Probe static-data.gaokao.cn / static-gkcx for score segment JSON."""
import time
import requests

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://www.gaokao.cn/",
    "Origin": "https://www.gaokao.cn",
}

PROV = {"北京": 11, "上海": 31, "浙江": 33, "广东": 44, "四川": 51, "山东": 37,
        "云南": 53, "广西": 45, "江苏": 32, "湖北": 42, "辽宁": 21, "吉林": 22, "黑龙江": 23}

patterns = [
    "https://static-data.gaokao.cn/www/2.0/scorerank/{year}/{pid}/lists.json",
    "https://static-data.gaokao.cn/www/2.0/scorerank/{year}/{pid}/1.json",
    "https://static-data.gaokao.cn/www/2.0/rank/score/{year}/{pid}/lists.json",
    "https://static-data.gaokao.cn/www/2.0/province/score/{year}/{pid}/lists.json",
    "https://static-gkcx.eol.cn/www/2.0/json/rank/{year}/{pid}/lists.json",
    "https://static-gkcx.eol.cn/www/2.0/json/score/{year}/{pid}/lists.json",
    "https://static-gkcx.eol.cn/www/2.0/json/fenshu/{year}/{pid}/lists.json",
    "https://static-gkcx.gaokao.cn/www/2.0/json/scorerank/{year}/{pid}/lists.json",
]

for year in [2024, 2025]:
    for name, pid in list(PROV.items())[:3]:
        for pat in patterns:
            url = pat.format(year=year, pid=pid)
            try:
                r = requests.get(url, headers=HEADERS, timeout=12)
            except Exception:
                continue
            if r.status_code == 200 and r.text.strip().startswith("{"):
                txt = r.text[:200]
                if "404" not in txt and "not found" not in txt.lower():
                    print("HIT", name, year, url[:80], txt[:120])
            time.sleep(0.15)

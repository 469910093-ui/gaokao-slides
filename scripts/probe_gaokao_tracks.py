#!/usr/bin/env python3
"""Probe gaokao.cn control line tracks for provinces."""
import json
import time
import requests
from gaokao_crawl_lib import HEADERS

API = "https://api.zjzw.cn/web/api/"
HDR = {**HEADERS, "Referer": "https://www.gaokao.cn/"}
PROVINCE_ID = {
    "北京": 11, "天津": 12, "河北": 13, "山西": 14, "内蒙古": 15,
    "辽宁": 21, "吉林": 22, "黑龙江": 23, "上海": 31, "江苏": 32,
    "浙江": 33, "安徽": 34, "福建": 35, "江西": 36, "山东": 37,
    "河南": 41, "湖北": 42, "湖南": 43, "广东": 44, "广西": 45,
    "海南": 46, "重庆": 50, "四川": 51, "贵州": 52, "云南": 53,
    "西藏": 54, "陕西": 61, "甘肃": 62, "青海": 63, "宁夏": 64,
    "新疆": 65,
}
URIS = [
    "apidata/api/gk/provincecontrol/list",
    "apidata/api/gk/provincecontrol/line",
    "apidata/api/gkv3/province/control",
    "apidata/api/gk/score/province",
    "apidata/api/gk/score/segment",
    "apidata/api/gkv3/score/segment",
    "apidata/api/gk/rank/segment",
]

s = requests.Session()
for prov in ["江西", "北京", "上海", "浙江", "河南", "新疆"]:
    pid = PROVINCE_ID[prov]
    print("===", prov, "===")
    for uri in URIS:
        for extra in [
            {"province_id": pid, "year": 2025},
            {"province_id": pid, "year": 2025, "local_type_name": "物理类"},
            {"province_id": pid, "year": 2025, "local_type_name": "综合"},
        ]:
            try:
                r = s.get(API, params={"uri": uri, **extra}, headers=HDR, timeout=15)
                data = r.json()
                if data.get("code") != "0000":
                    continue
                d = data.get("data")
                if not d:
                    continue
                text = json.dumps(d, ensure_ascii=False)[:400]
                if "分" in text or "line" in text.lower() or "item" in text:
                    print(uri, extra, "->", text[:300])
            except Exception:
                pass
        time.sleep(0.3)

#!/usr/bin/env python3
"""Probe gaokao.cn / zjzw.cn APIs and eol adjacent URLs."""
from __future__ import annotations

import re
import requests
from gaokao_crawl_lib import HEADERS, scrape_eol_entry, CatalogEntry, cumulative_at

BASE = "https://api.zjzw.cn/web/api/"
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
    "apidata/api/gk/score/province",
    "apidata/api/gk/score/batch",
    "apidata/api/gk/province/line",
    "apidata/api/gk/provinceline/list",
    "apidata/api/gk/control/line",
    "apidata/api/gkv3/province/control",
    "apidata/api/gkv3/province/line",
    "apidata/api/gk/score/segment",
    "apidata/api/gk/segment/list",
    "apidata/api/gkv3/score/segment",
    "apidata/api/gk/score/rank",
    "apidata/api/gk/rank/segment",
    "apidata/api/gk/province/batch",
    "apidata/api/gk/province/score",
    "apidata/api/gk/province/segment",
    "apidata/api/gkv3/province/segment",
    "apidata/api/gkv3/score/rank",
    "apidata/api/gk/score/provinceline",
    "apidata/api/gk/provincecontrol/list",
    "apidata/api/gk/provincecontrol/line",
]


def probe_api() -> None:
    s = requests.Session()
    for uri in URIS:
        for extra in [
            {"province_id": 41, "year": 2025, "page": 1, "size": 3},
            {"province_id": 41, "year": 2025, "local_type_name": "物理类", "page": 1, "size": 3},
            {"province": "河南", "year": 2025},
        ]:
            p = {"uri": uri, **extra}
            try:
                r = s.get(BASE, params=p, headers=HDR, timeout=12)
            except Exception as exc:  # noqa: BLE001
                print(uri, extra, "ERR", exc)
                continue
            if r.status_code == 200 and '"1064"' not in r.text[:120] and '"data":""' not in r.text[:120]:
                print("HIT", uri, extra, r.text[:200])


def probe_eol_adjacent() -> None:
    s = requests.Session()
    base = "https://gaokao.eol.cn/he_nan/dongtai/202506/t20250625_267685"
    for suffix in range(6, 12):
        url = f"{base}{suffix}.shtml"
        e = CatalogEntry("河南", 2025, None, "", url)
        r = scrape_eol_entry(s, e)
        if not r:
            print(url, "FAIL")
            continue
        c600 = cumulative_at(r.segments, 600)
        print(url[-20:], "segs", len(r.segments), "total", r.total, "600", c600, "title", r.title[:50])


if __name__ == "__main__":
    print("=== API ===")
    probe_api()
    print("=== EOL adjacent ===")
    probe_eol_adjacent()

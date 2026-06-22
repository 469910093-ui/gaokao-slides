#!/usr/bin/env python3
import json
import re
from collections import Counter
from pathlib import Path

import requests

HEADERS = {"User-Agent": "Mozilla/5.0"}
INDEX = "https://gaokao.eol.cn/e_html/gk/gkfsd/"

PROVINCE_SLUG = {
    "北京": "bei_jing", "天津": "tian_jin", "河北": "he_bei", "山西": "shan_xi",
    "内蒙古": "nei_meng_gu", "辽宁": "liao_ning", "吉林": "ji_lin", "黑龙江": "hei_long_jiang",
    "上海": "shang_hai", "江苏": "jiang_su", "浙江": "zhe_jiang", "安徽": "an_hui",
    "福建": "fu_jian", "江西": "jiang_xi", "山东": "shan_dong", "河南": "he_nan",
    "湖北": "hu_bei", "湖南": "hu_nan", "广东": "guang_dong", "广西": "guang_xi",
    "海南": "hai_nan", "重庆": "chong_qing", "四川": "si_chuan", "贵州": "gui_zhou",
    "云南": "yun_nan", "西藏": "xi_zang", "陕西": "shan3_xi", "甘肃": "gan_su",
    "青海": "qing_hai", "宁夏": "ning_xia", "新疆": "xin_jiang",
}
SLUG_TO_PROVINCE = {v: k for k, v in PROVINCE_SLUG.items()}

TRACK_KEYWORDS = {
    "物理类": ["物理", "理科", "理工", "首选物理"],
    "历史类": ["历史", "文科", "文史", "首选历史"],
}


def detect_track(title: str) -> str | None:
    for track, keys in TRACK_KEYWORDS.items():
        if any(k in title for k in keys):
            return track
    return None


def detect_year(title: str, url: str) -> int | None:
    m = re.search(r"(20\d{2})年", title)
    if m:
        return int(m.group(1))
    m = re.search(r"/20(\d{2})\d{4}/", url)
    if m:
        return 2000 + int(m.group(1))
    return None


def normalize_url(url: str) -> str:
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("/"):
        return "https://gaokao.eol.cn" + url
    return url


def main() -> None:
    r = requests.get(INDEX, headers=HEADERS, timeout=30)
    r.encoding = "utf-8"
    text = r.text

    raw_urls = set()
    for m in re.finditer(r'href="([^"]+)"', text):
        url = normalize_url(m.group(1))
        if "/dongtai/20" in url and url.endswith(".shtml"):
            raw_urls.add(url)

    unknown_slugs = set()
    entries = []
    for url in sorted(raw_urls):
        slug_m = re.search(r"gaokao\.eol\.cn/([a-z0-9_]+)/dongtai/", url)
        if not slug_m:
            continue
        slug = slug_m.group(1)
        prov = SLUG_TO_PROVINCE.get(slug)
        if not prov:
            unknown_slugs.add(slug)
            continue
        idx = text.find(url.split("gaokao.eol.cn")[-1])
        snippet = text[max(0, idx - 250): idx + 120] if idx >= 0 else ""
        title_m = re.search(r">([^<>]{4,140})</a>", snippet)
        title = title_m.group(1).strip() if title_m else ""
        year = detect_year(title, url)
        if not year or year < 2014 or year > 2026:
            continue
        # keep score distribution articles; allow unknown title if June/July gaokao season path
        scoreish = any(k in (title or "") for k in ("一分一段", "逐分段", "分数段", "分段统计", "成绩分布", "成绩分段"))
        if not scoreish and not re.search(r"/20\d{2}0[67]/", url):
            continue
        entries.append({
            "province": prov,
            "year": year,
            "track": detect_track(title or ""),
            "title": title,
            "url": url,
        })

    c = Counter((e["province"], e["year"], e["track"] or "unknown") for e in entries)
    print("raw urls", len(raw_urls))
    print("total entries", len(entries))
    print("unique combos", len(c))
    print("years", sorted(set(e["year"] for e in entries)))
    if unknown_slugs:
        print("unknown slugs", sorted(unknown_slugs))

    out = Path(__file__).parent.parent / "data" / "eol_catalog.json"
    out.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
    print("wrote", out)


if __name__ == "__main__":
    main()

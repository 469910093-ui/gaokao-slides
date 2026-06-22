#!/usr/bin/env python3
"""
掌上高考 gaokao.cn 数据归档：省控线参考 + 分省院校投档最低分。
数据源：https://api.zjzw.cn/web/api/ （与 gaokao.cn 同源）
说明：仅供参考，填报请以省教育考试院官方公布为准。

用法:
  python scripts/scrape_gaokao_cn.py
  python scripts/scrape_gaokao_cn.py --provinces 河南,北京 --years 2025
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from gaokao_crawl_lib import HEADERS
OUT_DIR = ROOT / "data" / "reference" / "gaokao_cn"
API_BASE = "https://api.zjzw.cn/web/api/"

PROVINCE_ID = {
    "北京": 11, "天津": 12, "河北": 13, "山西": 14, "内蒙古": 15,
    "辽宁": 21, "吉林": 22, "黑龙江": 23, "上海": 31, "江苏": 32,
    "浙江": 33, "安徽": 34, "福建": 35, "江西": 36, "山东": 37,
    "河南": 41, "湖北": 42, "湖南": 43, "广东": 44, "广西": 45,
    "海南": 46, "重庆": 50, "四川": 51, "贵州": 52, "云南": 53,
    "西藏": 54, "陕西": 61, "甘肃": 62, "青海": 63, "宁夏": 64,
    "新疆": 65,
}

TRACK_API_NAME = {
    "物理类": "物理类",
    "历史类": "历史类",
    "综合": "综合",
}

YEARS = list(range(2014, 2026))


def api_get(session: requests.Session, uri: str, retries: int = 5, **params: Any) -> dict[str, Any]:
    payload = {"uri": uri, **params}
    hdr = {**HEADERS, "Referer": "https://www.gaokao.cn/"}
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            r = session.get(API_BASE, params=payload, headers=hdr, timeout=30)
            r.raise_for_status()
            data = r.json()
            code = data.get("code")
            msg = str(data.get("message") or "")
            if code == "0000":
                return data.get("data") or {}
            if "频繁" in msg or code in ("1064", "1065"):
                time.sleep(2.5 * (attempt + 1))
                last_err = RuntimeError(f"API {uri} rate limited: {msg}")
                continue
            raise RuntimeError(f"API {uri} failed: {msg}")
        except requests.RequestException as exc:
            last_err = exc
            time.sleep(2.0 * (attempt + 1))
    raise last_err or RuntimeError(f"API {uri} failed after {retries} retries")


def crawl_province_admissions(
    session: requests.Session,
    province: str,
    year: int,
    track: str | None = None,
    page_size: int = 50,
) -> list[dict[str, Any]]:
    """院校专业组/院校投档最低分（掌上高考）。"""
    pid = PROVINCE_ID[province]
    page = 1
    rows: list[dict[str, Any]] = []
    while True:
        params: dict[str, Any] = {
            "province_id": pid,
            "year": year,
            "page": page,
            "size": page_size,
        }
        if track and track != "综合":
            params["local_type_name"] = TRACK_API_NAME.get(track, track)
        data = api_get(session, "apidata/api/gk/score/province", **params)
        items = data.get("item") or []
        if not items:
            break
        for it in items:
            rows.append({
                "province": province,
                "year": year,
                "track": it.get("local_type_name") or track,
                "schoolName": it.get("name"),
                "schoolId": it.get("school_id"),
                "minScore": it.get("min"),
                "minRank": it.get("min_section"),
                "avgScore": it.get("average"),
                "batch": it.get("local_batch_name"),
                "batchId": it.get("local_batch_id"),
                "groupName": it.get("sg_name"),
                "groupInfo": it.get("sg_info"),
                "provinceControlScore": it.get("proscore"),
                "admissions": it.get("admissions"),
                "level": it.get("level_name"),
                "nature": it.get("nature_name"),
                "city": it.get("city_name"),
                "f985": it.get("f985"),
                "f211": it.get("f211"),
                "dualClass": it.get("dual_class_name"),
            })
        num = int(data.get("numFound") or 0)
        if page * page_size >= num or len(items) < page_size:
            break
        page += 1
        time.sleep(1.2)
    return rows


def crawl_control_lines_from_admissions(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """从投档数据中提取省控线（proscore）按批次去重。"""
    seen: set[tuple[Any, ...]] = set()
    lines: list[dict[str, Any]] = []
    for r in rows:
        key = (r["province"], r["year"], r.get("track"), r.get("batch"), r.get("provinceControlScore"))
        if key in seen or r.get("provinceControlScore") in (None, "-", ""):
            continue
        seen.add(key)
        lines.append({
            "province": r["province"],
            "year": r["year"],
            "track": r.get("track"),
            "batch": r.get("batch"),
            "controlScore": r.get("provinceControlScore"),
            "source": "gaokao.cn",
        })
    return lines


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provinces", default=",".join(PROVINCE_ID.keys()))
    parser.add_argument("--years", default="2024,2025")
    parser.add_argument("--tracks", default="物理类,历史类")
    args = parser.parse_args()
    provinces = [p.strip() for p in args.provinces.split(",") if p.strip()]
    years = [int(y.strip()) for y in args.years.split(",") if y.strip()]
    tracks = [t.strip() for t in args.tracks.split(",") if t.strip()]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    summary: dict[str, Any] = {
        "source": "https://www.gaokao.cn/",
        "api": API_BASE,
        "years": years,
        "provinces": provinces,
        "tracks": tracks,
        "note": "院校投档最低分与省控线参考；请以省教育考试院官方公布为准。",
        "files": {},
    }

    for year in years:
        for province in provinces:
            if province not in PROVINCE_ID:
                continue
            for track in tracks:
                try:
                    rows = crawl_province_admissions(session, province, year, track)
                except Exception as exc:  # noqa: BLE001
                    print(f"  [warn] {province} {year} {track}: {exc}")
                    continue
                if not rows:
                    continue
                fname = f"admissions_{province}_{year}_{track}.json"
                path = OUT_DIR / fname
                path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
                summary["files"][fname] = len(rows)
                lines = crawl_control_lines_from_admissions(rows)
                if lines:
                    lname = f"control_lines_{province}_{year}_{track}.json"
                    (OUT_DIR / lname).write_text(
                        json.dumps(lines, ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )
                    summary["files"][lname] = len(lines)
                print(f"  {province} {year} {track}: {len(rows)} rows")
                time.sleep(2.0)

    (OUT_DIR / "manifest.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Wrote archive -> {OUT_DIR}")


if __name__ == "__main__":
    main()

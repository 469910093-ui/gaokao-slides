#!/usr/bin/env python3
"""
投档数据归档：经掌上高考（阳光高考同源）接口拉取，入库前按各省主批次与分数区间校验。
填报请以各省招生考试院、院校招生网公布为准；考试院入口见 admission_filter_lib.PROVINCE_EXAM_PORTALS。

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

from admission_filter_lib import PROVINCE_EXAM_PORTALS, filter_admission_row
from gaokao_crawl_lib import HEADERS
from province_tracks import COMBINED_33_PROVINCES
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

def tracks_for_admission_crawl(province: str, tracks_cli: list[str]) -> list[str | None]:
    """3+3 省用综合科类；其余省按物历爬取。"""
    if province in COMBINED_33_PROVINCES:
        return ["综合"]
    out: list[str] = []
    for t in tracks_cli:
        if t == "理科":
            out.append("物理类")
        elif t == "文科":
            out.append("历史类")
        elif t in ("物理类", "历史类"):
            out.append(t)
    return out or ["物理类", "历史类"]

TRACK_API_NAME = {
    "物理类": "物理类",
    "历史类": "历史类",
    "综合": "综合",
    "综合类": "综合",
}

YEARS = list(range(2014, 2027))


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
                raw = data.get("data")
                if isinstance(raw, list):
                    inner = {"item": raw, "numFound": len(raw)}
                else:
                    inner = raw or {}
                if not inner.get("item") and attempt < retries - 1:
                    time.sleep(2.5 * (attempt + 1))
                    continue
                return inner
            if "频繁" in msg or code in ("1064", "1065"):
                wait = min(90, 12 * (attempt + 1))
                print(f"  [rate-limit] wait {wait}s ({msg})", flush=True)
                time.sleep(wait)
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
    page_size: int = 20,
    page_sleep: float = 3.5,
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
        if track:
            params["local_type_name"] = "综合" if track in ("综合", "综合类") else TRACK_API_NAME.get(track, track)
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
        time.sleep(page_sleep)
    kept = [r for r in rows if filter_admission_row(province, r)]
    if len(kept) < len(rows):
        print(f"  [filter] {province} {year} {track or 'all'}: kept {len(kept)}/{len(rows)} rows", flush=True)
    return kept


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
            "source": "province_exam_portal",
            "sourceUrl": PROVINCE_EXAM_PORTALS.get(r["province"], "https://gaokao.chsi.com.cn/"),
        })
    return lines


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provinces", default=",".join(PROVINCE_ID.keys()))
    parser.add_argument("--years", default="2024,2025")
    parser.add_argument("--tracks", default="物理类,历史类")
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="若对应 JSON 已存在且非空则跳过（断点续爬）",
    )
    parser.add_argument("--pause", type=float, default=8.0, help="每省×年×科类任务间隔秒数")
    parser.add_argument("--page-sleep", type=float, default=3.5, help="分页请求间隔秒数")
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
            crawl_tracks = tracks_for_admission_crawl(province, tracks)
            for track in crawl_tracks:
                track_label = track or "综合"
                fname = f"admissions_{province}_{year}_{track_label}.json"
                path = OUT_DIR / fname
                if args.skip_existing and path.exists():
                    try:
                        existing = json.loads(path.read_text(encoding="utf-8"))
                    except json.JSONDecodeError:
                        existing = None
                    if existing:
                        print(f"  [skip-existing] {province} {year} {track_label}: {len(existing)} rows", flush=True)
                        summary["files"][fname] = len(existing)
                        continue
                try:
                    rows = crawl_province_admissions(
                        session, province, year, track, page_sleep=args.page_sleep
                    )
                except Exception as exc:  # noqa: BLE001
                    print(f"  [warn] {province} {year} {track_label}: {exc}", flush=True)
                    if "rate limited" in str(exc).lower() or "频繁" in str(exc):
                        time.sleep(max(args.pause * 3, 45))
                    continue
                if not rows:
                    print(f"  [skip] {province} {year} {track_label}: 0 rows", flush=True)
                    continue
                path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
                summary["files"][fname] = len(rows)
                lines = crawl_control_lines_from_admissions(rows)
                if lines:
                    lname = f"control_lines_{province}_{year}_{track_label}.json"
                    (OUT_DIR / lname).write_text(
                        json.dumps(lines, ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )
                    summary["files"][lname] = len(lines)
                print(f"  {province} {year} {track_label}: {len(rows)} rows", flush=True)
                time.sleep(args.pause)

    (OUT_DIR / "manifest.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Wrote archive -> {OUT_DIR}")


if __name__ == "__main__":
    main()

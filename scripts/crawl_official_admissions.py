#!/usr/bin/env python3
"""
从各省招生考试院官方公告抓取投档数据，写入 admissions_*_official.json。

用法:
  python scripts/crawl_official_admissions.py --provinces 北京 --years 2023,2024,2025
  python scripts/crawl_official_admissions.py --all
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from admission_filter_lib import filter_admission_row, normalize_track, primary_undergrad_batch
from portals.registry import get_parser, list_provinces

REF_DIR = ROOT / "data" / "reference" / "gaokao_cn"
ALL_PROVINCES = [p["province"] for p in list_provinces()]


def track_file_suffix(track: str) -> str:
    if track == "综合类":
        return "综合"
    return track


def merge_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """同校同年同组保留一条（官方源优先）。"""
    seen: set[tuple[Any, ...]] = set()
    out: list[dict[str, Any]] = []
    for r in rows:
        key = (
            r.get("province"),
            r.get("year"),
            r.get("track"),
            r.get("schoolName"),
            r.get("groupName"),
            r.get("groupInfo"),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def write_official_archive(province: str, year: int, track: str, rows: list[dict[str, Any]]) -> Path:
    suffix = track_file_suffix(track)
    path = REF_DIR / f"admissions_{province}_{year}_{suffix}_official.json"
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provinces", default="北京")
    parser.add_argument("--years", default="2023,2024,2025")
    parser.add_argument("--all", action="store_true", help="全部 registry 省份")
    parser.add_argument("--write-main", action="store_true", help="校验通过后覆盖主 admissions 文件")
    args = parser.parse_args()

    provinces = ALL_PROVINCES if args.all else [p.strip() for p in args.provinces.split(",") if p.strip()]
    years = [int(y.strip()) for y in args.years.split(",") if y.strip()]

    summary: dict[str, Any] = {
        "generatedAt": time.strftime("%Y-%m-%d %H:%M:%S"),
        "results": [],
    }

    for province in provinces:
        p = get_parser(province)
        print(f"\n[{province}] parser={p.implementation} portal={p.portal_url}")
        for year in years:
            rows_raw, errors = p.crawl_admissions(year)
            dicts = [r.to_dict() for r in rows_raw if filter_admission_row(province, r.to_dict())]
            by_track: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for row in dicts:
                tk = normalize_track(row.get("track"), row.get("track") or "综合类")
                row["track"] = tk
                row["batch"] = row.get("batch") or primary_undergrad_batch(province)
                by_track[tk].append(row)

            if not by_track:
                print(f"  {year}: 0 rows" + (f" ({errors[0]})" if errors else ""))
                summary["results"].append({
                    "province": province, "year": year, "rows": 0, "errors": errors,
                })
                continue

            for track, track_rows in by_track.items():
                merged = merge_rows(track_rows)
                out_path = write_official_archive(province, year, track, merged)
                schools = len({r["schoolName"] for r in merged})
                print(f"  {year} {track}: {len(merged)} rows, {schools} schools -> {out_path.name}")
                if args.write_main and p.implementation == "full":
                    main_path = REF_DIR / f"admissions_{province}_{year}_{track_file_suffix(track)}.json"
                    main_path.write_text(json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                summary["results"].append({
                    "province": province,
                    "year": year,
                    "track": track,
                    "rows": len(merged),
                    "schools": schools,
                    "file": out_path.name,
                    "errors": errors,
                })

    out = REF_DIR / "official_crawl_summary.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
官方投档 vs 归档/API 数据交叉校验。

用法:
  python scripts/verify_official_admissions.py --provinces 北京 --years 2024
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

from admission_filter_lib import (
    filter_regular_admission_row,
    normalize_track,
    parse_min_score,
    regular_floor_from_rows,
    select_official_archive_files,
    track_key_from_filename,
)
from portals.registry import get_parser, list_provinces

REF_DIR = ROOT / "data" / "reference" / "gaokao_cn"
TOLERANCE = 0  # 官方 floor 须与归档 floor 完全一致


def floor_by_school(rows: list[dict[str, Any]]) -> dict[str, int]:
    """同年同校普通批专业组 floor（与 build_admission_index 一致）。"""
    by_school: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        school = (r.get("schoolName") or "").strip()
        if school:
            by_school[school].append(r)
    out: dict[str, int] = {}
    for school, school_rows in by_school.items():
        floor = regular_floor_from_rows(school_rows)
        if floor is not None:
            out[school] = floor
    return out


def load_archive_floors(province: str, year: int, track: str) -> dict[str, int]:
    rows: list[dict[str, Any]] = []
    suffix = "综合" if track == "综合类" else track
    pattern = REF_DIR / f"admissions_{province}_{year}_{suffix}_official.json"
    if pattern.exists():
        rows.extend(json.loads(pattern.read_text(encoding="utf-8")))
    filtered = [r for r in rows if filter_regular_admission_row(province, r)]
    track_rows = [r for r in filtered if normalize_track(r.get("track"), track) == track]
    return floor_by_school(track_rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provinces", default="北京")
    parser.add_argument("--years", default="2023,2024,2025")
    parser.add_argument("--tolerance", type=int, default=TOLERANCE)
    args = parser.parse_args()

    provinces = [p.strip() for p in args.provinces.split(",") if p.strip()]
    years = [int(y.strip()) for y in args.years.split(",") if y.strip()]

    report: dict[str, Any] = {
        "generatedAt": time.strftime("%Y-%m-%d %H:%M:%S"),
        "tolerance": args.tolerance,
        "cases": [],
    }
    total_mismatch = 0

    for province in provinces:
        p = get_parser(province)
        for year in years:
            official_rows, errs = p.crawl_admissions(year)
            official_dicts = [r.to_dict() for r in official_rows if filter_regular_admission_row(province, r.to_dict())]
            by_track: dict[str, list[dict]] = defaultdict(list)
            for row in official_dicts:
                tk = normalize_track(row.get("track"), "综合类")
                by_track[tk].append(row)

            for track, o_rows in by_track.items():
                official_floor = floor_by_school(o_rows)
                archive_floor = load_archive_floors(province, year, track)
                if not official_floor:
                    continue
                mismatches = []
                matches = 0
                for school, o_score in sorted(official_floor.items()):
                    a_score = archive_floor.get(school)
                    if a_score is None:
                        mismatches.append({
                            "school": school,
                            "official": o_score,
                            "archive": None,
                            "delta": None,
                            "kind": "MISSING_IN_ARCHIVE",
                        })
                    elif abs(a_score - o_score) > args.tolerance:
                        mismatches.append({
                            "school": school,
                            "official": o_score,
                            "archive": a_score,
                            "delta": a_score - o_score,
                            "kind": "SCORE_MISMATCH",
                        })
                    else:
                        matches += 1

                total_mismatch += len(mismatches)
                case = {
                    "province": province,
                    "year": year,
                    "track": track,
                    "officialSchools": len(official_floor),
                    "archiveSchools": len(archive_floor),
                    "matches": matches,
                    "mismatches": len(mismatches),
                    "pass": len(mismatches) == 0,
                    "samples": mismatches[:20],
                    "errors": errs,
                }
                report["cases"].append(case)
                status = "PASS" if case["pass"] else f"FAIL({len(mismatches)})"
                print(
                    f"{province} {year} {track}: official={len(official_floor)} "
                    f"archive={len(archive_floor)} match={matches} {status}"
                )
                for m in mismatches[:5]:
                    print(f"  {m['kind']} {m['school']}: official={m['official']} archive={m.get('archive')}")

    out_dir = ROOT / "data" / "acceptance"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    out_path = out_dir / f"official_validation_{stamp}.json"
    report["totalMismatches"] = total_mismatch
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\nWrote {out_path} | total mismatches: {total_mismatch}")


if __name__ == "__main__":
    main()

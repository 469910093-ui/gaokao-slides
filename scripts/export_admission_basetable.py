#!/usr/bin/env python3
"""导出 gaokao.cn 投档底表为 CSV（明细 + 校年最低分 + 近三年均分索引）。"""

from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REF_DIR = ROOT / "data" / "reference" / "gaokao_cn"
OUT_DETAIL = REF_DIR / "admission_lines_detail.csv"
OUT_SCHOOL_YEAR = REF_DIR / "admission_lines_school_year.csv"
OUT_INDEX = REF_DIR / "admission_index_flat.csv"
INDEX_JSON = REF_DIR / "admission_index.json"


def parse_min_score(raw: Any) -> int | None:
    if raw in (None, "", "-"):
        return None
    try:
        v = int(float(str(raw).strip()))
        return v if v > 0 else None
    except (TypeError, ValueError):
        return None


def track_key_from_filename(fname: str) -> str:
    m = re.match(r"admissions_.+_\d+_(.+)\.json$", fname)
    key = m.group(1) if m else "综合类"
    if key in ("综合", "综合类"):
        return "综合类"
    return key


def normalize_track(row_track: str | None, file_track: str) -> str:
    t = row_track or file_track
    if file_track == "综合类" or t in ("综合", "综合类"):
        return "综合类"
    if "历史" in str(t) or "文科" in str(t):
        return "历史类"
    if "物理" in str(t) or "理科" in str(t):
        return "物理类"
    return file_track


def export_detail_and_school_year() -> tuple[int, int, set[str], set[str]]:
    detail_rows: list[dict[str, Any]] = []
    # province -> track -> school -> year -> min
    agg: dict[str, dict[str, dict[str, dict[int, int]]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(dict))
    )

    for path in sorted(REF_DIR.glob("admissions_*.json")):
        file_track = track_key_from_filename(path.name)
        rows = json.loads(path.read_text(encoding="utf-8"))
        for row in rows:
            province = (row.get("province") or "").strip()
            school = (row.get("schoolName") or "").strip()
            year = row.get("year")
            score = parse_min_score(row.get("minScore"))
            if not province or not school or not year or score is None:
                continue
            track = normalize_track(row.get("track"), file_track)
            detail_rows.append({
                "province": province,
                "year": int(year),
                "track": track,
                "schoolName": school,
                "schoolId": row.get("schoolId") or "",
                "minScore": score,
                "minRank": row.get("minRank") or "",
                "batch": row.get("batch") or "",
                "groupName": row.get("groupName") or "",
                "groupInfo": row.get("groupInfo") or "",
                "provinceControlScore": row.get("provinceControlScore") or "",
                "city": row.get("city") or "",
                "f985": row.get("f985") or "",
                "f211": row.get("f211") or "",
                "dualClass": row.get("dualClass") or "",
                "sourceFile": path.name,
            })
            y = int(year)
            prev = agg[province][track][school].get(y)
            if prev is None or score < prev:
                agg[province][track][school][y] = score

    detail_fields = [
        "province", "year", "track", "schoolName", "schoolId", "minScore", "minRank",
        "batch", "groupName", "groupInfo", "provinceControlScore",
        "city", "f985", "f211", "dualClass", "sourceFile",
    ]
    with OUT_DETAIL.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=detail_fields)
        w.writeheader()
        w.writerows(detail_rows)

    sy_rows: list[dict[str, Any]] = []
    provinces: set[str] = set()
    tracks: set[str] = set()
    for province in sorted(agg):
        provinces.add(province)
        for track in sorted(agg[province]):
            tracks.add(track)
            for school in sorted(agg[province][track]):
                for year, score in sorted(agg[province][track][school].items()):
                    sy_rows.append({
                        "province": province,
                        "year": year,
                        "track": track,
                        "schoolName": school,
                        "minScore": score,
                    })

    with OUT_SCHOOL_YEAR.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["province", "year", "track", "schoolName", "minScore"])
        w.writeheader()
        w.writerows(sy_rows)

    return len(detail_rows), len(sy_rows), provinces, tracks


def export_index_flat() -> int:
    payload = json.loads(INDEX_JSON.read_text(encoding="utf-8"))
    all_years: set[int] = set()
    for tracks in payload.get("provinces", {}).values():
        for schools in tracks.values():
            for entry in schools.values():
                for y in entry.get("years", {}):
                    all_years.add(int(y))
    years_sorted = sorted(all_years)

    rows: list[dict[str, Any]] = []
    for province in sorted(payload.get("provinces", {})):
        for track in sorted(payload["provinces"][province]):
            for school, entry in sorted(payload["provinces"][province][track].items()):
                row: dict[str, Any] = {
                    "province": province,
                    "track": track,
                    "schoolName": school,
                    "avgMin3y": entry.get("avgMin3y"),
                    "yearCount": entry.get("yearCount"),
                }
                for y in years_sorted:
                    row[str(y)] = entry.get("years", {}).get(str(y), "")
                rows.append(row)

    fields = ["province", "track", "schoolName", "avgMin3y", "yearCount"] + [str(y) for y in years_sorted]
    with OUT_INDEX.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    return len(rows)


def write_coverage_summary(provinces: set[str], tracks: set[str]) -> None:
    payload = json.loads(INDEX_JSON.read_text(encoding="utf-8"))
    cov: dict[str, dict[str, set[int]]] = defaultdict(lambda: defaultdict(set))
    with OUT_SCHOOL_YEAR.open(encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            cov[r["province"]][r["track"]].add(int(r["year"]))

    lines = [
        f"生成时间: {payload['meta'].get('generatedAt', '')}",
        f"来源: {payload['meta'].get('provider', '')}",
        f"原始 JSON 文件数: {payload['meta'].get('files', '')}",
        f"已覆盖省份: {len(provinces)} / 31",
        f"科类: {', '.join(sorted(tracks))}",
        "",
        "=== 各省科类年份覆盖 ===",
    ]
    for p in sorted(cov):
        for t in sorted(cov[p]):
            lines.append(f"{p}\t{t}\t{sorted(cov[p][t])}")
    lines += ["", "=== 索引校数（省×科类）==="]
    for p in sorted(payload.get("provinces", {})):
        parts = [f"{t}:{len(s)}校" for t, s in sorted(payload["provinces"][p].items())]
        lines.append(f"{p}: " + ", ".join(parts))

    summary_path = REF_DIR / "admission_coverage_summary.txt"
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {summary_path.name}")


def main() -> None:
    n_detail, n_sy, provinces, tracks = export_detail_and_school_year()
    n_index = export_index_flat()
    write_coverage_summary(provinces, tracks)
    print(f"Provinces: {len(provinces)} | Tracks: {sorted(tracks)}")
    print(f"Wrote {OUT_DETAIL.name}: {n_detail} rows ({OUT_DETAIL.stat().st_size / 1024:.1f} KB)")
    print(f"Wrote {OUT_SCHOOL_YEAR.name}: {n_sy} rows ({OUT_SCHOOL_YEAR.stat().st_size / 1024:.1f} KB)")
    print(f"Wrote {OUT_INDEX.name}: {n_index} rows ({OUT_INDEX.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    main()

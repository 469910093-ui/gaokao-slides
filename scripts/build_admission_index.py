#!/usr/bin/env python3
"""从官方投档 JSON 构建「省×科类×院校」普通批最低投档索引。"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from admission_filter_lib import (  # noqa: E402
    OFFICIAL_REFERENCES,
    PROVINCE_EXAM_PORTALS,
    filter_regular_admission_row,
    normalize_track,
    official_provinces_in_ref,
    regular_floor_from_rows,
    select_official_archive_files,
    track_key_from_filename,
)

REF_DIR = ROOT / "data" / "reference" / "gaokao_cn"
OUT_JSON = REF_DIR / "admission_index.json"
OUT_META = REF_DIR / "admission_index_meta.json"
SHARD_DIR = REF_DIR / "admission_by_province"
OUT_EMBED = ROOT / "data" / "admission-index-embed.js"

SOURCE_META = {
    "provider": "各省招生考试院官方投档（普通批专业组，已剔除专项计划）",
    "crawlApi": None,
    "crawlPage": None,
    "chsiUrl": OFFICIAL_REFERENCES["chsi"]["url"],
    "method": (
        "仅收录 _official.json；剔除国家/地方专项、定向、预科、中外合作等非普通志愿计划；"
        "同年同校在普通专业组中取最低投档分，并剔除组内极低值；"
        "推荐参考分优先使用最近一年普通批最低分 latestFloor。"
    ),
    "disclaimer": OFFICIAL_REFERENCES["note"],
    "examPortals": PROVINCE_EXAM_PORTALS,
}


def build_index() -> dict[str, Any]:
    # province -> track -> school -> year -> floor
    raw_rows: dict[str, dict[str, dict[str, dict[int, list[dict[str, Any]]]]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    )
    source_urls: dict[str, dict[str, dict[str, str]]] = defaultdict(
        lambda: defaultdict(dict)
    )
    file_count = 0
    row_count = 0
    skipped = 0

    archive_files = select_official_archive_files(REF_DIR)
    for path in archive_files:
        file_count += 1
        rows = json.loads(path.read_text(encoding="utf-8"))
        file_track = track_key_from_filename(path.name)
        for row in rows:
            province = (row.get("province") or "").strip()
            if not province:
                continue
            if not filter_regular_admission_row(province, row):
                skipped += 1
                continue
            school = (row.get("schoolName") or "").strip()
            year = row.get("year")
            if not school or not year:
                skipped += 1
                continue
            t_key = normalize_track(row.get("track"), file_track)
            y = int(year)
            raw_rows[province][t_key][school][y].append(row)
            if row.get("sourceUrl"):
                source_urls[province][t_key][school] = str(row["sourceUrl"])
            row_count += 1

    tier_by_rank = ["985", "211", "双一流", "一本", "二本", "专科"]
    provinces_out: dict[str, Any] = {}
    official_provs = official_provinces_in_ref(REF_DIR)

    for province, tracks in raw_rows.items():
        provinces_out[province] = {}
        portal = PROVINCE_EXAM_PORTALS.get(province, OFFICIAL_REFERENCES["chsi"]["url"])
        for track, schools in tracks.items():
            provinces_out[province][track] = {}
            for school, years_map in schools.items():
                years_regular: dict[int, int] = {}
                for y, y_rows in years_map.items():
                    floor = regular_floor_from_rows(y_rows)
                    if floor is not None:
                        years_regular[y] = floor
                if not years_regular:
                    continue
                years_sorted = dict(sorted(years_regular.items()))
                floor_vals = list(years_sorted.values())
                latest_year = max(years_sorted)
                latest_floor = years_sorted[latest_year]
                sm_levels = set()
                sm_batches = set()
                tr = 9
                for y_rows in years_map.values():
                    for row in y_rows:
                        if row.get("level"):
                            sm_levels.add(str(row["level"]))
                        if row.get("batch"):
                            sm_batches.add(str(row["batch"]))
                        if row.get("f985") == 1:
                            tr = min(tr, 0)
                        elif row.get("f211") == 1:
                            tr = min(tr, 2)
                        elif str(row.get("dualClass") or "") == "双一流":
                            tr = min(tr, 3)
                only_voc = bool(sm_levels) and all("专科" in x for x in sm_levels)
                inferred_tier = tier_by_rank[tr] if tr < len(tier_by_rank) else "二本"
                school_url = source_urls.get(province, {}).get(track, {}).get(school, portal)
                provinces_out[province][track][school] = {
                    "latestFloor": latest_floor,
                    "latestYear": str(latest_year),
                    "yearsRegular": {str(y): v for y, v in years_sorted.items()},
                    "avgMin3y": round(sum(floor_vals) / len(floor_vals)),
                    "avgFloor3y": round(sum(floor_vals) / len(floor_vals)),
                    "years": {str(y): v for y, v in years_sorted.items()},
                    "yearsFloor": {str(y): v for y, v in years_sorted.items()},
                    "yearCount": len(floor_vals),
                    "tier": inferred_tier,
                    "isVocational": only_voc,
                    "source": "province_exam_portal",
                    "sourceUrl": school_url,
                }

    province_status: dict[str, dict[str, Any]] = {}
    for prov in sorted(official_provs):
        tracks = provinces_out.get(prov, {})
        if tracks and any(tracks[t] for t in tracks):
            province_status[prov] = {
                "status": "verified",
                "tracks": sorted(tracks.keys()),
                "schoolCount": sum(len(tracks[t]) for t in tracks),
            }
        else:
            province_status[prov] = {
                "status": "unavailable",
                "reason": "官方归档无有效普通批投档行",
            }

    return {
        "meta": {
            **SOURCE_META,
            "generatedAt": time.strftime("%Y-%m-%d %H:%M:%S"),
            "files": file_count,
            "rowsParsed": row_count,
            "rowsSkipped": skipped,
            "officialProvinces": sorted(official_provs),
            "verifiedProvinces": sorted(
                p for p, s in province_status.items() if s.get("status") == "verified"
            ),
            "provinceStatus": province_status,
            "schoolEntries": sum(
                len(schools) for tracks in provinces_out.values() for schools in tracks.values()
            ),
        },
        "provinces": provinces_out,
    }


def write_embed(payload: dict[str, Any]) -> None:
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    OUT_EMBED.write_text(
        "// Auto-generated — do not edit. Run: python scripts/build_admission_index.py\n"
        f"window.ADMISSION_INDEX={body};\n",
        encoding="utf-8",
    )


def write_province_shards(payload: dict[str, Any]) -> None:
    """按省分片，供 selector 懒加载（避免首屏拉取全量 admission_index）。"""
    meta = payload["meta"]
    OUT_META.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    SHARD_DIR.mkdir(parents=True, exist_ok=True)
    for old in SHARD_DIR.glob("*.json"):
        old.unlink()
    count = 0
    for province, tracks in payload["provinces"].items():
        shard = {
            "meta": meta,
            "province": province,
            "tracks": tracks,
        }
        out = SHARD_DIR / f"{province}.json"
        out.write_text(json.dumps(shard, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
        count += 1
    print(f"Wrote {OUT_META.name} + {count} shards in {SHARD_DIR.name}/")


def run_quality_gate(strict: bool = True) -> int:
    script = ROOT / "scripts" / "admission_quality_gate.py"
    cmd = [sys.executable, str(script)]
    if strict:
        cmd.append("--strict")
    print("\n--- admission quality gate ---")
    return subprocess.call(cmd)


def main() -> None:
    skip_gate = "--skip-gate" in sys.argv
    payload = build_index()
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_embed(payload)
    write_province_shards(payload)
    meta = payload["meta"]
    print(
        f"Wrote {OUT_JSON.name}: {meta['schoolEntries']} school entries "
        f"from {meta['files']} official files ({meta['rowsParsed']} rows kept, "
        f"{meta['rowsSkipped']} skipped)"
    )
    print(f"Verified provinces: {len(meta['verifiedProvinces'])}/{len(meta['officialProvinces'])}")
    print(f"Wrote {OUT_EMBED.name} ({OUT_EMBED.stat().st_size / 1024:.1f} KB)")

    if not skip_gate:
        code = run_quality_gate(strict=True)
        if code != 0:
            sys.exit(code)


if __name__ == "__main__":
    main()

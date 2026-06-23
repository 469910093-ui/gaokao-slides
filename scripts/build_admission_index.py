#!/usr/bin/env python3
"""从投档 JSON 构建「省×科类×院校」近三年最低投档均分索引（经主批次与分数校验）。"""

from __future__ import annotations

import json
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
    filter_admission_row,
    normalize_track,
    parse_min_score,
    track_key_from_filename,
)

REF_DIR = ROOT / "data" / "reference" / "gaokao_cn"
OUT_JSON = REF_DIR / "admission_index.json"
OUT_EMBED = ROOT / "data" / "admission-index-embed.js"

SOURCE_META = {
    "provider": "阳光高考 / 各省招生考试院（经掌上高考接口归档并校验）",
    "crawlApi": "https://api.zjzw.cn/web/api/",
    "crawlPage": "https://www.gaokao.cn/control-line",
    "chsiUrl": OFFICIAL_REFERENCES["chsi"]["url"],
    "method": (
        "仅收录本省普通本科主批次（如北京本科批、浙江平行录取一段）投档行；"
        "剔除外省批次与 min>合理上限的异常分；"
        "每校每年取各专业组投档最低分中的最小值（floor）；"
        "近三年有数据的年份取 floor 算术平均，记为 avgMin3y。"
    ),
    "disclaimer": OFFICIAL_REFERENCES["note"],
    "examPortals": PROVINCE_EXAM_PORTALS,
}


def build_index() -> dict[str, Any]:
    # province -> track -> school -> year -> floor
    raw: dict[str, dict[str, dict[str, dict[int, int]]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(dict))
    )
    meta: dict[str, dict[str, dict[str, dict[str, Any]]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(dict))
    )
    file_count = 0
    row_count = 0
    skipped = 0

    for path in sorted(REF_DIR.glob("admissions_*.json")):
        file_count += 1
        rows = json.loads(path.read_text(encoding="utf-8"))
        file_track = track_key_from_filename(path.name)
        for row in rows:
            province = (row.get("province") or "").strip()
            if not province:
                continue
            if not filter_admission_row(province, row):
                skipped += 1
                continue
            school = (row.get("schoolName") or "").strip()
            year = row.get("year")
            score = parse_min_score(row.get("minScore"))
            if not school or not year or score is None:
                skipped += 1
                continue
            t_key = normalize_track(row.get("track"), file_track)
            y = int(year)
            prev = raw[province][t_key][school].get(y)
            if prev is None or score < prev:
                raw[province][t_key][school][y] = score
            sm = meta[province][t_key][school]
            level = str(row.get("level") or "")
            batch = str(row.get("batch") or "")
            if level:
                sm["levels"] = sm.get("levels", set()) | {level}
            if batch:
                sm["batches"] = sm.get("batches", set()) | {batch}
            if row.get("f985") == 1:
                sm["tierRank"] = min(sm.get("tierRank", 9), 0)
            elif row.get("f211") == 1:
                sm["tierRank"] = min(sm.get("tierRank", 9), 2)
            elif str(row.get("dualClass") or "") == "双一流":
                sm["tierRank"] = min(sm.get("tierRank", 9), 3)
            row_count += 1

    tier_by_rank = ["985", "211", "双一流", "一本", "二本", "专科"]

    provinces_out: dict[str, Any] = {}
    for province, tracks in raw.items():
        provinces_out[province] = {}
        portal = PROVINCE_EXAM_PORTALS.get(province, OFFICIAL_REFERENCES["chsi"]["url"])
        for track, schools in tracks.items():
            provinces_out[province][track] = {}
            for school, years_map in schools.items():
                years_sorted = dict(sorted(years_map.items()))
                floor_vals = list(years_sorted.values())
                if not floor_vals:
                    continue
                sm = meta[province][track].get(school, {})
                levels = sm.get("levels") or set()
                batches = sm.get("batches") or set()
                only_voc = bool(levels) and all("专科" in x for x in levels)
                only_voc = only_voc or (
                    bool(batches) and all("专科" in x for x in batches) and "本科" not in "".join(batches)
                )
                tr = sm.get("tierRank", 9)
                inferred_tier = tier_by_rank[tr] if tr < len(tier_by_rank) else "二本"
                provinces_out[province][track][school] = {
                    "avgMin3y": round(sum(floor_vals) / len(floor_vals)),
                    "avgFloor3y": round(sum(floor_vals) / len(floor_vals)),
                    "years": {str(y): v for y, v in years_sorted.items()},
                    "yearsFloor": {str(y): v for y, v in years_sorted.items()},
                    "yearCount": len(floor_vals),
                    "tier": inferred_tier,
                    "isVocational": only_voc,
                    "source": "province_exam_portal",
                    "sourceUrl": portal,
                }

    return {
        "meta": {
            **SOURCE_META,
            "generatedAt": time.strftime("%Y-%m-%d %H:%M:%S"),
            "files": file_count,
            "rowsParsed": row_count,
            "rowsSkipped": skipped,
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


def main() -> None:
    payload = build_index()
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_embed(payload)
    meta = payload["meta"]
    print(
        f"Wrote {OUT_JSON.name}: {meta['schoolEntries']} school entries "
        f"from {meta['files']} files ({meta['rowsParsed']} rows kept, {meta['rowsSkipped']} skipped)"
    )
    print(f"Wrote {OUT_EMBED.name} ({OUT_EMBED.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    main()

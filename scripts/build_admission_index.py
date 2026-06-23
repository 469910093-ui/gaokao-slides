#!/usr/bin/env python3
"""从 gaokao.cn 投档 JSON 构建「省×科类×院校」近三年最低投档均分索引。"""

from __future__ import annotations

import json
import re
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REF_DIR = ROOT / "data" / "reference" / "gaokao_cn"
OUT_JSON = REF_DIR / "admission_index.json"
OUT_EMBED = ROOT / "data" / "admission-index-embed.js"

SOURCE_META = {
    "provider": "掌上高考 gaokao.cn",
    "api": "https://api.zjzw.cn/web/api/",
    "page": "https://www.gaokao.cn/control-line",
    "method": (
        "对每个院校每年，取所有专业组投档行 min 的最小值记为 floor、最大值记为 line（主流竞争档）；"
        "推荐冲稳保使用 line。近三年有数据的年份取 line 算术平均，记为 avgMin3y。"
        "仅收录 min 为有效数值的记录，不含估算。"
    ),
    "disclaimer": "数据来自掌上高考公开接口归档，请以各省教育考试院官方公布为准。",
}


def parse_min_score(raw: Any) -> int | None:
    if raw in (None, "", "-"):
        return None
    try:
        v = int(float(str(raw).strip()))
        return v if v > 0 else None
    except (TypeError, ValueError):
        return None


def track_key_from_filename(fname: str) -> str:
    # admissions_北京_2024_综合类.json / admissions_北京_2024_综合.json
    m = re.match(r"admissions_.+_\d+_(.+)\.json$", fname)
    key = m.group(1) if m else "综合类"
    if key in ("综合", "综合类"):
        return "综合类"
    return key


def build_index() -> dict[str, Any]:
    # province -> track -> school -> year -> {"floor": int, "line": int}
    raw: dict[str, dict[str, dict[str, dict[int, dict[str, int]]]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(dict))
    )
    meta: dict[str, dict[str, dict[str, dict[str, Any]]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(dict))
    )
    file_count = 0
    row_count = 0

    for path in sorted(REF_DIR.glob("admissions_*.json")):
        file_count += 1
        rows = json.loads(path.read_text(encoding="utf-8"))
        track_key = track_key_from_filename(path.name)
        for row in rows:
            province = row.get("province")
            school = (row.get("schoolName") or "").strip()
            year = row.get("year")
            score = parse_min_score(row.get("minScore"))
            if not province or not school or not year or score is None:
                continue
            t = row.get("track") or track_key
            if track_key == "综合类":
                t_key = "综合类"
            elif "历史" in str(t):
                t_key = "历史类"
            elif "物理" in str(t) or "理科" in str(t):
                t_key = "物理类"
            elif "文科" in str(t):
                t_key = "历史类"
            else:
                t_key = track_key
            y = int(year)
            bucket = raw[province][t_key][school].setdefault(y, {"floor": score, "line": score})
            bucket["floor"] = min(bucket["floor"], score)
            bucket["line"] = max(bucket["line"], score)
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
        for track, schools in tracks.items():
            provinces_out[province][track] = {}
            for school, years_map in schools.items():
                years_sorted = dict(sorted(years_map.items()))
                line_vals = [v["line"] for v in years_sorted.values()]
                floor_vals = [v["floor"] for v in years_sorted.values()]
                if not line_vals:
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
                    "avgMin3y": round(sum(line_vals) / len(line_vals)),
                    "avgFloor3y": round(sum(floor_vals) / len(floor_vals)),
                    "years": {str(y): v["line"] for y, v in years_sorted.items()},
                    "yearsFloor": {str(y): v["floor"] for y, v in years_sorted.items()},
                    "yearCount": len(line_vals),
                    "tier": inferred_tier,
                    "isVocational": only_voc,
                    "source": "gaokao.cn",
                    "sourceUrl": SOURCE_META["page"],
                }

    return {
        "meta": {
            **SOURCE_META,
            "generatedAt": time.strftime("%Y-%m-%d %H:%M:%S"),
            "files": file_count,
            "rowsParsed": row_count,
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
        f"from {meta['files']} files ({meta['rowsParsed']} rows)"
    )
    print(f"Wrote {OUT_EMBED.name} ({OUT_EMBED.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    main()

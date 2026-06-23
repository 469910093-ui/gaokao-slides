#!/usr/bin/env python3
"""多数据源交叉验证：将系统推荐与公开一分一段/投档线基准对比。"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "acceptance"
sys.path.insert(0, str(ROOT / "scripts"))

from province_tracks import pick_track_payload
from acceptance_test_recommendations import (  # noqa: E402
    build_segments,
    cumulative_at,
    percentile_at,
    recommend_majors,
    recommend_schools,
    tier_for_percentile,
)

# 公开数据基准（来源见 ACCEPTANCE_REPORT.md 参考文献）
BENCHMARKS = [
    {
        "id": "BJ619",
        "province": "北京",
        "track": "综合类",
        "score": 619,
        "official_rank": 7983,
        "rank_tolerance": 800,
        "forbidden_schools": ["北京大学", "清华大学", "复旦大学", "上海交通大学"],
        "expected_schools_any": [],
        "sources": ["高三网2025北京一分一段", "高考100北京2025院校专业组"],
    },
    {
        "id": "HN600",
        "province": "河南",
        "track": "物理类",
        "score": 600,
        "official_rank": 45887,
        "rank_tolerance": 3000,
        "forbidden_schools": ["北京大学", "清华大学"],
        "expected_schools_any": [],  # 仅验证位次与禁推校
        "sources": ["高考100河南2025物理类一分一段"],
    },
    {
        "id": "BJ697",
        "province": "北京",
        "track": "综合类",
        "score": 697,
        "official_rank": 136,
        "rank_tolerance": 80,
        "forbidden_schools": [],
        "expected_schools_any": ["北京大学", "清华大学"],
        "sources": ["高考100北京2025院校专业组"],
    },
]


def run_at_score(province: str, track: str, score: int, year: str = "2025") -> dict | None:
    manifest = json.loads((ROOT / "data" / "manifest.json").read_text(encoding="utf-8"))
    catalog = json.loads((ROOT / "data" / "major_catalog.json").read_text(encoding="utf-8"))
    pdata = json.loads((ROOT / "data" / "provinces" / f"{province}.json").read_text(encoding="utf-8"))
    year_obj = pdata.get("years", {}).get(year)
    if not year_obj:
        return None
    track_data = pick_track_payload(year_obj.get("tracks", {}), province, int(year), track)
    if not track_data and track in ("物理类", "历史类"):
        track_data = year_obj.get("tracks", {}).get(track)
    if not track_data:
        return None
    segs = build_segments(track_data.get("segments") or [])
    total = track_data.get("totalCandidates") or 0
    tier_order = manifest.get("tierOrder") or []
    tier_pct = manifest.get("tierPercentile") or {}
    schools = manifest.get("schools") or []
    majors = catalog.get("majors") or []
    p = percentile_at(score, segs)
    rank = cumulative_at(score, segs, total)
    reach = tier_for_percentile(p, tier_order, tier_pct)
    reach_idx = tier_order.index(reach)
    return {
        "province": province,
        "track": track,
        "score": score,
        "percentile": p,
        "rank": rank,
        "reach_tier": reach,
        "segment_source": track_data.get("source") or track_data.get("confidence") or "unknown",
        "schools": recommend_schools(score, p, reach, reach_idx, schools, tier_order, tier_pct),
        "majors": recommend_majors(score, p, reach, reach_idx, majors, track, tier_order, tier_pct),
    }


def main() -> None:
    out = []
    for bm in BENCHMARKS:
        case = run_at_score(bm["province"], bm["track"], bm["score"])
        row = {"benchmark": bm["id"], "status": "NO_CASE", "checks": []}
        if not case:
            out.append(row)
            continue
        rank = case.get("rank")
        schools = case.get("schools") or []
        checks = []

        if rank is not None and bm.get("official_rank"):
            diff = abs(rank - bm["official_rank"])
            ok = diff <= bm.get("rank_tolerance", 500)
            checks.append({
                "item": "位次",
                "pass": ok,
                "system": rank,
                "official": bm["official_rank"],
                "diff": rank - bm["official_rank"],
                "note": f"偏差 {diff} 名",
            })

        for name in bm.get("forbidden_schools") or []:
            hit = name in schools
            checks.append({
                "item": f"禁推校:{name}",
                "pass": not hit,
                "system": hit,
                "note": "不应出现在推荐列表" if hit else "未误推",
            })

        if bm.get("expected_schools_any"):
            hit = [n for n in bm["expected_schools_any"] if n in schools]
            checks.append({
                "item": "命中真实院校",
                "pass": len(hit) >= 1,
                "system": hit,
                "official": bm["expected_schools_any"],
                "note": f"Top10 命中 {len(hit)}/{len(bm['expected_schools_any'])}",
            })

        row = {
            "benchmark": bm["id"],
            "province": bm["province"],
            "track": bm["track"],
            "score": case["score"],
            "percentile": case.get("percentile"),
            "reach_tier": case.get("reach_tier"),
            "segment_source": case.get("segment_source"),
            "schools_top10": schools,
            "majors_top8": (case.get("majors") or [])[:8],
            "status": "PASS" if all(c["pass"] for c in checks) else "FAIL",
            "checks": checks,
            "sources": bm["sources"],
        }
        out.append(row)

    path = DATA / f"cross_validation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(path)
    for r in out:
        print(r["benchmark"], r.get("status"), r.get("checks"))


if __name__ == "__main__":
    main()

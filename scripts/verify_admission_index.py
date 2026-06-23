#!/usr/bin/env python3
"""快速验证 admission_index 各省是否有院校推荐。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from acceptance_test_recommendations import (  # noqa: E402
    DATA,
    admission_track_key,
    build_segments,
    load_json,
    percentile_at,
    reach_idx_for_score,
    recommend_schools,
)

ALL_PROVINCES = [
    "北京", "天津", "河北", "山西", "内蒙古", "辽宁", "吉林", "黑龙江",
    "上海", "江苏", "浙江", "安徽", "福建", "江西", "山东", "河南",
    "湖北", "湖南", "广东", "广西", "海南", "重庆", "四川", "贵州",
    "云南", "西藏", "陕西", "甘肃", "青海", "宁夏", "新疆",
]


def main() -> None:
    manifest = load_json(DATA / "manifest.json")
    tier_order = manifest.get("tierOrder") or []
    tier_pct = manifest.get("tierPercentile") or {}
    admission_index = load_json(DATA / "reference" / "gaokao_cn" / "admission_index.json")
    schools = manifest.get("schools") or []

    in_index = set(admission_index.get("provinces", {}))
    missing = [p for p in ALL_PROVINCES if p not in in_index]
    print(f"Index provinces: {len(in_index)}/31 | entries: {admission_index['meta']['schoolEntries']}")
    if missing:
        print("MISSING:", missing)

    from province_tracks import tracks_for_province

    no_rec = []
    for prov in ALL_PROVINCES:
        pdata = load_json(DATA / "provinces" / f"{prov}.json")
        yo = pdata.get("years", {}).get("2025")
        if not yo:
            continue
        for track in tracks_for_province(prov, 2025):
            td = yo.get("tracks", {}).get(track)
            if not td:
                continue
            score = 600
            segs = build_segments(td.get("segments") or [])
            p = percentile_at(score, segs)
            reach, _ = reach_idx_for_score(score, p, yo.get("batches") or {}, tier_order, tier_pct)
            sch = recommend_schools(score, prov, track, schools, admission_index)
            tk = admission_track_key(prov, track)
            n = len(admission_index.get("provinces", {}).get(prov, {}).get(tk, {}))
            total = len(sch["chong"]) + len(sch["wen"]) + len(sch["bao"])
            if n > 0 and total == 0:
                no_rec.append(f"{prov}/{track} (index {n}校, 600分无推荐)")
            elif n == 0:
                no_rec.append(f"{prov}/{track} (索引空)")

    if no_rec:
        print("\n无推荐或索引空:")
        for line in no_rec:
            print(" ", line)
    else:
        print("\n全部 31 省 600 分抽样均有院校推荐或索引非空")

    for prov, track, score in [
        ("内蒙古", "物理类", 600),
        ("河南", "历史类", 568),
        ("广东", "物理类", 600),
    ]:
        pdata = load_json(DATA / "provinces" / f"{prov}.json")
        yo = pdata["years"]["2025"]
        td = yo["tracks"][track]
        segs = build_segments(td.get("segments") or [])
        p = percentile_at(score, segs)
        reach, _ = reach_idx_for_score(score, p, yo.get("batches") or {}, tier_order, tier_pct)
        sch = recommend_schools(score, prov, track, schools, admission_index)
        print(f"\n{prov} {track} {score} reach={reach}")
        print(f"  冲: {sch['chong']}")
        print(f"  稳: {sch['wen']}")
        print(f"  保: {sch['bao']}")


if __name__ == "__main__":
    main()

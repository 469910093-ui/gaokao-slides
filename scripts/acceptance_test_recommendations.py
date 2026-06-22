#!/usr/bin/env python3
"""
验收测试：复刻 selector.html 院校/专业推荐逻辑，全量扫描并输出报告。
用法: python scripts/acceptance_test_recommendations.py
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT_DIR = DATA / "acceptance"
from province_tracks import COMBINED_33_PROVINCES, major_match_tracks, tracks_for_province

YEAR = "2025"

C9_NAMES = {"清华大学", "北京大学", "复旦大学", "上海交通大学", "浙江大学", "南京大学", "中国科学技术大学"}
TOP985 = C9_NAMES | {
    "哈尔滨工业大学", "西安交通大学", "北京航空航天大学", "同济大学", "华中科技大学",
    "武汉大学", "中山大学", "电子科技大学",
}


@dataclass
class CaseResult:
    province: str
    track: str
    score: int
    percentile: float | None
    rank: int | None
    reach_tier: str
    segment_source: str
    schools: list[str]
    majors: list[str]
    issues: list[dict[str, str]] = field(default_factory=list)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def build_segments(raw_segs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        [
            {
                "score": s["s"],
                "percentile": s.get("p"),
                "cumulative": s.get("c"),
                "count": s.get("n"),
            }
            for s in raw_segs
        ],
        key=lambda x: x["score"],
    )


def cumulative_at(score: int, segs: list[dict[str, Any]], total: int) -> int | None:
    if not segs:
        return None
    exact = next((s for s in segs if s["score"] == score), None)
    if exact and exact.get("cumulative") is not None:
        return int(round(exact["cumulative"]))
    if score <= segs[0]["score"]:
        return int(segs[0].get("cumulative") or 0)
    if score >= segs[-1]["score"]:
        return int(segs[-1].get("cumulative") or total)
    for i in range(len(segs) - 1):
        a, b = segs[i], segs[i + 1]
        if a["score"] <= score <= b["score"]:
            t = (score - a["score"]) / (b["score"] - a["score"] or 1)
            ca = a.get("cumulative") or 0
            cb = b.get("cumulative") or ca
            return int(round(ca + (cb - ca) * t))
    return None


def percentile_at(score: int, segs: list[dict[str, Any]]) -> float | None:
    if not segs:
        return None
    exact = next((s for s in segs if s["score"] == score), None)
    if exact and exact.get("percentile") is not None:
        return float(exact["percentile"])
    if score <= segs[0]["score"]:
        return segs[0].get("percentile")
    if score >= segs[-1]["score"]:
        return segs[-1].get("percentile")
    for i in range(len(segs) - 1):
        a, b = segs[i], segs[i + 1]
        if a["score"] <= score <= b["score"]:
            t = (score - a["score"]) / (b["score"] - a["score"] or 1)
            pa = a.get("percentile") or 0
            pb = b.get("percentile") or pa
            return round(pa + (pb - pa) * t, 2)
    return None


def reach_idx_from_batches(score: int, batches: dict[str, Any], tier_order: list[str]) -> int:
    idx = lambda name: tier_order.index(name) if name in tier_order else len(tier_order) - 1
    special = batches.get("特招线")
    undergrad = batches.get("本科线")
    if special is not None:
        if score >= special + 45:
            return idx("C9")
        if score >= special + 28:
            return idx("985")
        if score >= special + 8:
            return idx("211")
        if score >= special:
            return idx("双一流")
    if undergrad is not None:
        if score >= undergrad + 35:
            return idx("一本")
        if score >= undergrad:
            return idx("二本")
    return idx("专科")


def reach_idx_for_score(
    score: int,
    p: float | None,
    batches: dict[str, Any],
    tier_order: list[str],
    tier_pct: dict[str, float],
) -> tuple[str, int]:
    from_batch = reach_idx_from_batches(score, batches, tier_order)
    from_pct = tier_order.index(tier_for_percentile(p, tier_order, tier_pct)) if p is not None else -1
    candidates = [i for i in (from_batch, from_pct) if i >= 0]
    reach_idx = max(candidates) if candidates else from_batch
    return tier_order[reach_idx], reach_idx


def tier_for_percentile(p: float | None, tier_order: list[str], tier_pct: dict[str, float]) -> str:
    if p is None:
        return "二本"
    for tier in tier_order:
        if tier in tier_pct and p >= tier_pct[tier]:
            return tier
    return "专科"


def school_min_percentile(school: dict[str, Any], tier_pct: dict[str, float]) -> float:
    if school.get("minPercentile") is not None:
        return float(school["minPercentile"])
    return float(tier_pct.get(school["tier"], 50))


def school_reachable(user_p: float, school: dict[str, Any], reach_idx: int, tier_order: list[str], tier_pct: dict[str, float]) -> bool:
    school_p = school_min_percentile(school, tier_pct)
    school_idx = tier_order.index(school["tier"])
    if school_idx < 0:
        return False
    gap = school_p - user_p
    if school_idx < reach_idx:
        delta = reach_idx - school_idx
        if delta == 1:
            return gap <= 8
        if delta == 2:
            return gap <= 6
        return False
    return gap <= 5


def major_matches_subject(major: dict[str, Any], track: str, province: str = "") -> bool:
    subjects = major.get("subjects") or []
    if not subjects:
        disc = major.get("discipline") or major.get("track") or ""
        if disc in ("工科", "理科"):
            subjects = ["物理类"]
        elif disc in ("文科", "艺术"):
            subjects = ["历史类"]
        else:
            subjects = ["物理类", "历史类"]
    allowed = major_match_tracks(track, province) if province else [track]
    return any(t in subjects for t in allowed)


def recommend_schools(
    score: int,
    user_p: float | None,
    reach: str,
    reach_idx: int,
    schools: list[dict[str, Any]],
    tier_order: list[str],
    tier_pct: dict[str, float],
) -> list[str]:
    undergrad = [
        s for s in schools
        if s.get("tier") != "专科" and user_p is not None
        and school_reachable(user_p, s, reach_idx, tier_order, tier_pct)
    ]

    def sort_key(s: dict[str, Any]) -> tuple:
        a_idx = tier_order.index(s["tier"])
        a_chong = a_idx < reach_idx and reach_idx - a_idx <= 2
        da = abs(school_min_percentile(s, tier_pct) - (user_p or 0))
        return (0 if a_chong else 1, da, -school_min_percentile(s, tier_pct))

    undergrad.sort(key=sort_key)
    return [s["name"] for s in undergrad[:10]]


def major_catalog_allowed(major: dict[str, Any], reach_idx: int, tier_order: list[str]) -> bool:
    ct = major.get("catalogType") or "undergraduate"
    voc_idx = tier_order.index("专科")
    ug_only_idx = tier_order.index("二本") if "二本" in tier_order else voc_idx
    if ct in ("vocational", "vocational_undergraduate"):
        return reach_idx >= voc_idx
    if ct != "undergraduate" and reach_idx < ug_only_idx:
        return False
    return True


def recommend_majors(
    score: int,
    user_p: float | None,
    reach: str,
    reach_idx: int,
    majors: list[dict[str, Any]],
    track: str,
    tier_order: list[str],
    tier_pct: dict[str, float],
    province: str = "",
) -> list[str]:
    eligible = [
        m for m in majors
        if major_matches_subject(m, track, province)
        and major_catalog_allowed(m, reach_idx, tier_order)
        and (
            user_p is None
            or school_reachable(
                user_p,
                {"tier": m["tier"], "minPercentile": tier_pct.get(m["tier"])},
                reach_idx,
                tier_order,
                tier_pct,
            )
        )
    ]
    by_name: dict[str, dict[str, Any]] = {}
    for m in eligible:
        prev = by_name.get(m["name"])

        def prefer(a: dict[str, Any] | None, b: dict[str, Any]) -> dict[str, Any]:
            if not a:
                return b
            a_voc = (a.get("catalogType") or "") == "vocational"
            b_voc = (b.get("catalogType") or "") == "vocational"
            if a_voc != b_voc:
                return b if a_voc else a
            a_dist = abs(tier_order.index(a["tier"]) - reach_idx)
            b_dist = abs(tier_order.index(b["tier"]) - reach_idx)
            return a if a_dist < b_dist else b

        by_name[m["name"]] = prefer(prev, m)

    def sort_key(m: dict[str, Any]) -> tuple:
        return (
            0 if m.get("opportunity") else 1,
            -(m.get("trendIndex") or m.get("score") or 0),
            -(m.get("jobVolumeYoY") or 0),
            -(m.get("salaryGrowth5y") or 0),
        )

    ordered = sorted(by_name.values(), key=sort_key)
    return [m["name"] for m in ordered[:12]]


def sample_scores(year_obj: dict[str, Any], track_data: dict[str, Any], step: int = 25) -> list[int]:
    """200–750 分按 step 采样（默认每 25 分一档）。"""
    batches = year_obj.get("batches") or {}
    max_s = int(year_obj.get("maxScore") or 750)
    segs = track_data.get("segments") or []
    min_s = max(200, min(s["s"] for s in segs) if segs else 200)
    lo = max(200, min_s)
    hi = min(max_s, 750)
    out = list(range(lo, hi + 1, step))
    if hi not in out:
        out.append(hi)
    # 回归锚点
    for anchor in (619, 600, 697):
        if lo <= anchor <= hi and anchor not in out:
            out.append(anchor)
    return sorted(set(out))


def audit_case(
    case: CaseResult,
    tier_order: list[str],
    tier_pct: dict[str, float],
    physics_only_majors: set[str],
    history_only_majors: set[str],
    voc_only_major_names: set[str],
) -> None:
    p = case.percentile
    reach_idx = tier_order.index(case.reach_tier)

    for name in case.schools:
        if name in C9_NAMES and p is not None and p < 98:
            case.issues.append({
                "severity": "ERROR",
                "code": "C9_OVERREACH",
                "message": f"百分位 {p}% 仍推荐 C9「{name}」",
            })
        if name in TOP985 and p is not None and p < 96 and name not in C9_NAMES:
            case.issues.append({
                "severity": "WARN",
                "code": "985_STRETCH",
                "message": f"百分位 {p}% 推荐顶尖985「{name}」需人工核验",
            })

    if case.reach_tier in ("一本", "二本", "专科") and case.schools:
        high_tiers = {tier_order[i] for i in range(0, min(3, reach_idx))}
        for name in case.schools[:3]:
            sch = next((s for s in schools_global if s["name"] == name), None)
            if sch and sch["tier"] in high_tiers and p is not None and p < 95:
                case.issues.append({
                    "severity": "ERROR",
                    "code": "TIER_MISMATCH",
                    "message": f"稳妥层次 {case.reach_tier} 但 Top 推荐含 {sch['tier']}「{name}」",
                })

    if case.track in ("物理类", "综合类"):
        wrong = [m for m in case.majors[:8] if m in history_only_majors]
        if len(wrong) >= 3:
            case.issues.append({
                "severity": "ERROR",
                "code": "SUBJECT_LEAK_PHYSICS",
                "message": f"{case.track}推荐含过多历史类专属专业: {wrong[:5]}",
            })
    if case.track in ("历史类",):
        wrong = [m for m in case.majors[:8] if m in physics_only_majors]
        if len(wrong) >= 3:
            case.issues.append({
                "severity": "ERROR",
                "code": "SUBJECT_LEAK_HISTORY",
                "message": f"历史类推荐含过多物理类专属专业: {wrong[:5]}",
            })

    if case.segment_source in ("model_estimate", "model") and p is not None and p > 90:
        case.issues.append({
            "severity": "ERROR",
            "code": "MODEL_SEGMENT_HIGH",
            "message": "高分段使用模型估算一分一段，位次不可用于填报",
        })

    if reach_idx < tier_order.index("专科") and any(m in voc_only_major_names for m in case.majors[:8]):
        bad = [m for m in case.majors[:8] if m in voc_only_major_names]
        case.issues.append({
            "severity": "ERROR",
            "code": "VOC_MAJOR_HIGH_SCORE",
            "message": f"本科层次仍推荐高职专业: {bad[:5]}",
        })

    if p is not None and p < tier_pct.get("二本", 65) and not any(
        n for n in case.schools  # noqa: SIM103
    ):
        if case.reach_tier not in ("专科",):
            case.issues.append({
                "severity": "WARN",
                "code": "LOW_SCORE_NO_SCHOOL",
                "message": f"低分段({p}%)无本科推荐，需确认是否应展示专科",
            })


def main() -> None:
    global schools_global
    manifest = load_json(DATA / "manifest.json")
    catalog = load_json(DATA / "major_catalog.json")
    schools_global = manifest.get("schools") or []
    majors_all = catalog.get("majors") or []
    tier_order = manifest.get("tierOrder") or []
    tier_pct = manifest.get("tierPercentile") or {}

    physics_only = {
        m["name"] for m in majors_all
        if major_matches_subject(m, "物理类") and not major_matches_subject(m, "历史类")
    }
    history_only = {
        m["name"] for m in majors_all
        if major_matches_subject(m, "历史类") and not major_matches_subject(m, "物理类")
    }
    voc_only_major_names = {
        m["name"] for m in majors_all
        if (m.get("catalogType") or "") in ("vocational", "vocational_undergraduate")
        and m["name"] not in {
            x["name"] for x in majors_all
            if (x.get("catalogType") or "undergraduate") == "undergraduate"
        }
    }

    results: list[CaseResult] = []
    issue_rows: list[dict[str, str]] = []

    for prov_path in sorted((DATA / "provinces").glob("*.json")):
        province = prov_path.stem
        pdata = load_json(prov_path)
        year_obj = pdata.get("years", {}).get(YEAR)
        if not year_obj:
            continue
        for track in tracks_for_province(province, int(YEAR)):
            track_data = year_obj.get("tracks", {}).get(track)
            if not track_data and track == "综合类":
                track_data = year_obj.get("tracks", {}).get("物理类") or year_obj.get("tracks", {}).get("历史类")
            if not track_data:
                continue
            segs = build_segments(track_data.get("segments") or [])
            total = track_data.get("totalCandidates") or 0
            source = track_data.get("source") or track_data.get("confidence") or "unknown"
            sampled = sample_scores(year_obj, track_data)
            for score in sampled:
                p = percentile_at(score, segs)
                rank = cumulative_at(score, segs, total)
                reach, reach_idx = reach_idx_for_score(
                    score, p, year_obj.get("batches") or {}, tier_order, tier_pct
                )
                sch = recommend_schools(score, p, reach, reach_idx, schools_global, tier_order, tier_pct)
                maj = recommend_majors(score, p, reach, reach_idx, majors_all, track, tier_order, tier_pct, province)
                case = CaseResult(
                    province=province,
                    track=track,
                    score=score,
                    percentile=p,
                    rank=rank,
                    reach_tier=reach,
                    segment_source=str(source),
                    schools=sch,
                    majors=maj,
                )
                audit_case(case, tier_order, tier_pct, physics_only, history_only, voc_only_major_names)
                results.append(case)
                for iss in case.issues:
                    issue_rows.append({
                        "province": province,
                        "track": track,
                        "score": str(score),
                        "percentile": str(p),
                        "rank": str(rank),
                        "reach_tier": reach,
                        "severity": iss["severity"],
                        "code": iss["code"],
                        "message": iss["message"],
                        "schools": " | ".join(sch[:5]),
                        "majors": " | ".join(maj[:5]),
                    })

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    detail_path = OUT_DIR / f"recommendations_{YEAR}_{ts}.json"
    detail_path.write_text(
        json.dumps(
            {
                "meta": {
                    "generatedAt": datetime.now().isoformat(timespec="seconds"),
                    "year": YEAR,
                    "cases": len(results),
                    "provinces": len({r.province for r in results}),
                },
                "cases": [r.__dict__ for r in results],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    csv_path = OUT_DIR / f"recommendations_{YEAR}_{ts}.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "省份", "科类", "分数", "百分位", "位次", "稳妥层次", "分段数据源",
            "推荐院校Top10", "推荐专业Top12", "问题数",
        ])
        for r in results:
            w.writerow([
                r.province, r.track, r.score, r.percentile, r.rank, r.reach_tier,
                r.segment_source,
                " | ".join(r.schools),
                " | ".join(r.majors),
                len(r.issues),
            ])

    issues_path = OUT_DIR / f"issues_{YEAR}_{ts}.csv"
    with issues_path.open("w", encoding="utf-8-sig", newline="") as f:
        if issue_rows:
            w = csv.DictWriter(f, fieldnames=list(issue_rows[0].keys()))
            w.writeheader()
            w.writerows(issue_rows)

    errors = sum(1 for row in issue_rows if row["severity"] == "ERROR")
    warns = sum(1 for row in issue_rows if row["severity"] == "WARN")
    print(f"Cases: {len(results)} | ERROR: {errors} | WARN: {warns}")
    print(f"Detail: {detail_path}")
    print(f"CSV: {csv_path}")
    print(f"Issues: {issues_path}")

    # 固定 bad case 回归
    beijing = next(
        (r for r in results if r.province == "北京" and r.track == "历史类" and r.score == 619),
        None,
    )
    if beijing:
        bad = [n for n in beijing.schools if n in C9_NAMES]
        print(f"\n[回归] 北京历史类619: reach={beijing.reach_tier} p={beijing.percentile} rank={beijing.rank}")
        print(f"  院校: {beijing.schools[:8]}")
        print(f"  C9误入: {bad or '无'}")


if __name__ == "__main__":
    main()

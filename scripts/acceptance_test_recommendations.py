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
from admission_filter_lib import recommend_floor_from_entry

from province_tracks import COMBINED_33_PROVINCES, major_match_tracks, tracks_for_province

NO_SEGMENT_EOL_PROVINCES = frozenset({"新疆", "西藏"})
YEAR = "2025"

ADMISSION_SOURCE = {
    "provider": "掌上高考 gaokao.cn",
    "url": "https://www.gaokao.cn/control-line",
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
    schools_chong: list[str]
    schools_wen: list[str]
    schools_bao: list[str]
    majors_chong: list[str]
    majors_wen: list[str]
    majors_bao: list[str]
    has_admission: bool
    issues: list[dict[str, str]] = field(default_factory=list)

    @property
    def schools(self) -> list[str]:
        return self.schools_chong + self.schools_wen + self.schools_bao

    @property
    def majors(self) -> list[str]:
        return self.majors_chong + self.majors_wen + self.majors_bao


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def admission_track_key(province: str, track: str) -> str:
    if province in COMBINED_33_PROVINCES or track == "综合类":
        return "综合类"
    if track in ("历史类", "文科"):
        return "历史类"
    return "物理类"


def province_admission_verified(admission_index: dict[str, Any] | None, province: str) -> bool:
    if not admission_index:
        return False
    verified = admission_index.get("meta", {}).get("verifiedProvinces") or []
    return province in verified


def admission_recommend_score(rec: dict[str, Any] | None) -> int | None:
    if not rec:
        return None
    return recommend_floor_from_entry(rec)


def lookup_admission(
    admission_index: dict[str, Any] | None,
    province: str,
    track: str,
    school_name: str,
) -> dict[str, Any] | None:
    if not admission_index:
        return None
    prov = admission_index.get("provinces", {}).get(province)
    if not prov:
        return None
    tkey = admission_track_key(province, track)
    return prov.get(tkey, {}).get(school_name)


def school_application_tag(score: int, avg_min: int) -> str | None:
    diff = avg_min - score
    if 5 <= diff <= 15:
        return "chong"
    if -12 <= diff <= 5:
        return "wen"
    if -30 <= diff < -12:
        return "bao"
    return None


def qs_rank_of(school: dict[str, Any]) -> int:
    return int(school.get("qsRank") or 99999)


def enrich_school(
    school: dict[str, Any],
    score: int,
    admission_index: dict[str, Any] | None,
    province: str,
    track: str,
) -> dict[str, Any] | None:
    rec = lookup_admission(admission_index, province, track, school["name"])
    ref_score = admission_recommend_score(rec)
    if ref_score is None:
        return None
    tag = school_application_tag(score, ref_score)
    if not tag:
        return None
    return {
        **school,
        "avgAdmission": ref_score,
        "admissionYears": rec.get("yearsRegular") or rec.get("years"),
        "appTag": {"key": tag},
    }


def bucket_schools(eligible: list[dict[str, Any]], quotas: dict[str, int]) -> dict[str, list[dict[str, Any]]]:
    def pick(key: str, n: int) -> list[dict[str, Any]]:
        return sorted(
            [s for s in eligible if s.get("appTag", {}).get("key") == key],
            key=lambda s: (qs_rank_of(s), s["name"]),
        )[:n]

    return {
        "chong": pick("chong", quotas["chong"]),
        "wen": pick("wen", quotas["wen"]),
        "bao": pick("bao", quotas["bao"]),
    }


def enrich_admission_entry(
    school_name: str,
    rec: dict[str, Any],
    score: int,
    manifest_by_name: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    if rec.get("isVocational"):
        return None
    avg = admission_recommend_score(rec)
    if avg is None:
        return None
    tag = school_application_tag(score, int(avg))
    if not tag:
        return None
    base = manifest_by_name.get(school_name)
    if base:
        school = dict(base)
    else:
        school = {
            "name": school_name,
            "tier": rec.get("tier") or "二本",
            "qsRank": 99999,
        }
    if school.get("tier") == "专科":
        return None
    return {
        **school,
        "avgAdmission": avg,
        "admissionYears": rec.get("yearsRegular") or rec.get("years"),
        "appTag": {"key": tag},
    }


def recommend_schools(
    score: int,
    province: str,
    track: str,
    schools: list[dict[str, Any]],
    admission_index: dict[str, Any] | None,
) -> dict[str, Any]:
    tkey = admission_track_key(province, track)
    prov_map = (admission_index or {}).get("provinces", {}).get(province, {}).get(tkey, {})
    has_admission = province_admission_verified(admission_index, province) and bool(prov_map)
    manifest_by_name = {s["name"]: s for s in schools}
    enriched = [
        s for s in (
            enrich_admission_entry(name, rec, score, manifest_by_name)
            for name, rec in prov_map.items()
        )
        if s is not None
    ]
    buckets = bucket_schools(enriched, {"chong": 3, "wen": 3, "bao": 5})
    return {
        "has_admission": has_admission,
        "chong": [s["name"] for s in buckets["chong"]],
        "wen": [s["name"] for s in buckets["wen"]],
        "bao": [s["name"] for s in buckets["bao"]],
    }


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


def tier_for_percentile(p: float | None, tier_order: list[str], tier_pct: dict[str, float]) -> str:
    if p is None:
        return "二本"
    for tier in tier_order:
        if tier in tier_pct and p >= tier_pct[tier]:
            return tier
    return "专科"


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


def major_catalog_allowed(major: dict[str, Any], reach_idx: int, tier_order: list[str]) -> bool:
    ct = major.get("catalogType") or "undergraduate"
    voc_idx = tier_order.index("专科")
    ug_only_idx = tier_order.index("二本") if "二本" in tier_order else voc_idx
    if ct in ("vocational", "vocational_undergraduate"):
        return reach_idx >= voc_idx
    if ct != "undergraduate" and reach_idx < ug_only_idx:
        return False
    return True


def major_bucket_key(major: dict[str, Any], reach_idx: int, tier_order: list[str]) -> str | None:
    major_idx = tier_order.index(major["tier"])
    if major_idx < 0:
        return None
    delta = major_idx - reach_idx
    if delta >= 1:
        return "chong"
    if delta == 0:
        return "wen"
    if delta <= -1:
        return "bao"
    return None


def bucket_majors(eligible: list[dict[str, Any]], quotas: dict[str, int]) -> dict[str, list[dict[str, Any]]]:
    def sort_trend(a: dict[str, Any], b: dict[str, Any]) -> int:
        ta = a.get("trendIndex") or a.get("score") or 0
        tb = b.get("trendIndex") or b.get("score") or 0
        if tb != ta:
            return tb - ta
        return -1 if a["name"] < b["name"] else (1 if a["name"] > b["name"] else 0)

    def pick(key: str, n: int) -> list[dict[str, Any]]:
        items = [m for m in eligible if m.get("appTag", {}).get("key") == key]
        return sorted(items, key=lambda m: (-(m.get("trendIndex") or m.get("score") or 0), m["name"]))[:n]

    return {
        "chong": pick("chong", quotas["chong"]),
        "wen": pick("wen", quotas["wen"]),
        "bao": pick("bao", quotas["bao"]),
    }


def recommend_majors(
    score: int,
    reach_idx: int,
    majors: list[dict[str, Any]],
    track: str,
    tier_order: list[str],
    province: str = "",
) -> dict[str, list[str]]:
    eligible = [
        m for m in majors
        if major_matches_subject(m, track, province)
        and major_catalog_allowed(m, reach_idx, tier_order)
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

    enriched: list[dict[str, Any]] = []
    for m in by_name.values():
        key = major_bucket_key(m, reach_idx, tier_order)
        if not key:
            continue
        enriched.append({**m, "appTag": {"key": key}})

    buckets = bucket_majors(enriched, {"chong": 4, "wen": 4, "bao": 4})
    return {
        "chong": [m["name"] for m in buckets["chong"]],
        "wen": [m["name"] for m in buckets["wen"]],
        "bao": [m["name"] for m in buckets["bao"]],
    }


def sample_scores(year_obj: dict[str, Any], track_data: dict[str, Any], step: int = 25) -> list[int]:
    max_s = int(year_obj.get("maxScore") or 750)
    segs = track_data.get("segments") or []
    min_s = max(200, min(s["s"] for s in segs) if segs else 200)
    lo = max(200, min_s)
    hi = min(max_s, 750)
    out = list(range(lo, hi + 1, step))
    if hi not in out:
        out.append(hi)
    for anchor in (619, 600, 587, 697):
        if lo <= anchor <= hi and anchor not in out:
            out.append(anchor)
    return sorted(set(out))


def audit_case(
    case: CaseResult,
    admission_index: dict[str, Any] | None,
    physics_only_majors: set[str],
    history_only_majors: set[str],
    voc_only_major_names: set[str],
) -> None:
    reach_idx = tier_order.index(case.reach_tier)

    if case.has_admission:
        for name in case.schools_chong + case.schools_wen:
            rec = lookup_admission(admission_index, case.province, case.track, name)
            ref_score = admission_recommend_score(rec)
            if ref_score is None:
                case.issues.append({
                    "severity": "ERROR",
                    "code": "SCHOOL_NO_ADMISSION",
                    "message": f"冲/稳推荐「{name}」无普通批投档参考分",
                })
                continue
            tag = school_application_tag(case.score, int(ref_score))
            if tag not in ("chong", "wen"):
                case.issues.append({
                    "severity": "ERROR",
                    "code": "SCHOOL_BUCKET_MISMATCH",
                    "message": f"「{name}」普通批参考分{ref_score}，与{case.score}分差{ref_score-case.score}，不应在冲/稳",
                })

        if case.province == "广西" and case.score == 634:
            bad = [
                n for n in case.schools_chong + case.schools_wen + case.schools_bao
                if n in ("北京大学", "清华大学")
            ]
            if bad:
                case.issues.append({
                    "severity": "ERROR",
                    "code": "GX634_C9_FORBIDDEN",
                    "message": f"广西634分不得推荐清北: {bad}",
                })

    if not province_admission_verified(admission_index, case.province) and (
        case.schools_chong or case.schools_wen or case.schools_bao
    ):
        case.issues.append({
            "severity": "ERROR",
            "code": "UNVERIFIED_HAS_RECOMMENDATION",
            "message": f"{case.province} 未验收官方投档，不应输出院校冲稳保",
        })

    if case.has_admission is False and case.province in (
        (admission_index or {}).get("meta", {}).get("verifiedProvinces") or []
    ):
        case.issues.append({
            "severity": "WARN",
            "code": "VERIFIED_NO_INDEX_TRACK",
            "message": f"{case.province}{case.track} 已验收但当前科类无索引",
        })

    if case.province == "北京" and case.score == 587:
        bad = [n for n in case.schools_chong + case.schools_wen if n == "安徽建筑大学"]
        if bad:
            case.issues.append({
                "severity": "ERROR",
                "code": "BEIJING587_ANHUI_JIANZHU",
                "message": "北京587分冲/稳桶误推安徽建筑大学（投档均分约504，diff=-83）",
            })

    if case.track in ("物理类",):
        wrong = [m for m in case.majors[:8] if m in history_only_majors]
        if len(wrong) >= 3:
            case.issues.append({
                "severity": "ERROR",
                "code": "SUBJECT_LEAK_PHYSICS",
                "message": f"{case.track}推荐含过多历史类专属专业: {wrong[:5]}",
            })
    if case.track in ("历史类", "综合类"):
        wrong = [m for m in case.majors[:8] if m in physics_only_majors and case.track == "历史类"]
        if len(wrong) >= 3:
            case.issues.append({
                "severity": "ERROR",
                "code": "SUBJECT_LEAK_HISTORY",
                "message": f"历史类推荐含过多物理类专属专业: {wrong[:5]}",
            })

    if case.segment_source in ("model_estimate", "model") and case.percentile is not None and case.percentile > 90:
        case.issues.append({
            "severity": "WARN",
            "code": "MODEL_SEGMENT_GAP" if case.province in NO_SEGMENT_EOL_PROVINCES else "MODEL_SEGMENT_HIGH",
            "message": (
                f"{case.province}暂无公开一分一段源，高分段为模型估算"
                if case.province in NO_SEGMENT_EOL_PROVINCES
                else "该省该年一分一段为模型估算，位次仅供参考"
            ),
        })

    if reach_idx < tier_order.index("专科") and any(m in voc_only_major_names for m in case.majors[:8]):
        bad = [m for m in case.majors[:8] if m in voc_only_major_names]
        case.issues.append({
            "severity": "ERROR",
            "code": "VOC_MAJOR_HIGH_SCORE",
            "message": f"本科层次仍推荐高职专业: {bad[:5]}",
        })


tier_order: list[str] = []


def main() -> None:
    import sys

    strict = "--strict" in sys.argv
    global tier_order
    manifest = load_json(DATA / "manifest.json")
    catalog = load_json(DATA / "major_catalog.json")
    schools_global = manifest.get("schools") or []
    majors_all = catalog.get("majors") or []
    tier_order = manifest.get("tierOrder") or []
    tier_pct = manifest.get("tierPercentile") or {}

    admission_path = DATA / "reference" / "gaokao_cn" / "admission_index.json"
    admission_index = load_json(admission_path) if admission_path.exists() else None

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
                sch = recommend_schools(score, province, track, schools_global, admission_index)
                maj = recommend_majors(score, reach_idx, majors_all, track, tier_order, province)
                case = CaseResult(
                    province=province,
                    track=track,
                    score=score,
                    percentile=p,
                    rank=rank,
                    reach_tier=reach,
                    segment_source=str(source),
                    schools_chong=sch["chong"],
                    schools_wen=sch["wen"],
                    schools_bao=sch["bao"],
                    majors_chong=maj["chong"],
                    majors_wen=maj["wen"],
                    majors_bao=maj["bao"],
                    has_admission=sch["has_admission"],
                )
                audit_case(case, admission_index, physics_only, history_only, voc_only_major_names)
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
                        "schools_chong": " | ".join(sch["chong"]),
                        "schools_wen": " | ".join(sch["wen"]),
                        "schools_bao": " | ".join(sch["bao"]),
                        "majors": " | ".join(case.majors[:5]),
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
                    "admissionIndex": bool(admission_index),
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
            "省份", "科类", "分数", "百分位", "位次", "稳妥层次", "分段数据源", "有投档索引",
            "冲刺院校", "稳妥院校", "保底院校",
            "冲刺专业", "稳妥专业", "保底专业", "问题数",
        ])
        for r in results:
            w.writerow([
                r.province, r.track, r.score, r.percentile, r.rank, r.reach_tier,
                r.segment_source, r.has_admission,
                " | ".join(r.schools_chong), " | ".join(r.schools_wen), " | ".join(r.schools_bao),
                " | ".join(r.majors_chong), " | ".join(r.majors_wen), " | ".join(r.majors_bao),
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

    bj587 = next(
        (r for r in results if r.province == "北京" and r.track == "综合类" and r.score == 587),
        None,
    )
    if bj587:
        bad = [n for n in bj587.schools_chong + bj587.schools_wen if n == "安徽建筑大学"]
        print(f"\n[回归] 北京综合类587: reach={bj587.reach_tier} p={bj587.percentile}")
        print(f"  冲刺: {bj587.schools_chong}")
        print(f"  稳妥: {bj587.schools_wen}")
        print(f"  保底: {bj587.schools_bao}")
        print(f"  安徽建筑大学误入冲/稳: {bad or '无'}")

    if admission_index:
        bj_count = len(admission_index.get("provinces", {}).get("北京", {}).get("综合类", {}))
        print(f"\n投档索引：北京综合类 {bj_count} 校")

    if strict and errors > 0:
        print(f"\n[STRICT] {errors} ERROR(s) — exit 1")
        sys.exit(1)


if __name__ == "__main__":
    main()

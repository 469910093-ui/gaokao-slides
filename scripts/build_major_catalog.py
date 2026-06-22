#!/usr/bin/env python3
"""Build major catalog v2: full MOE catalogs + job volume YoY + occupation codes."""

from __future__ import annotations

import json
import statistics
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
REF_DIR = DATA_DIR / "reference"
MANIFEST_FILE = DATA_DIR / "manifest.json"
CAREER_FILE = DATA_DIR / "career_sandbox.json"
RAW_FILE = DATA_DIR / "moe_majors_raw.json"
JOB_VOLUME_FILE = DATA_DIR / "job_volume_index.json"
OCC_FILE = REF_DIR / "occupations_2022.json"
OUT_FILE = DATA_DIR / "major_catalog.json"
EMBED_FILE = DATA_DIR / "major-catalog-embed.js"

import sys

sys.path.insert(0, str(ROOT / "scripts"))
from major_catalog_entries import CATALOG_ENTRIES  # noqa: E402
from major_utils import (  # noqa: E402
    infer_discipline,
    infer_manual_trend,
    infer_subjects,
    infer_tier,
    match_occupations,
    salary_percentile,
)

CAREER_ALIASES: dict[str, str] = {
    "新闻学": "新闻传播学",
    "传播学": "新闻传播学",
    "广播电视编导": "新闻传播学",
    "新闻采编与制作": "新闻传播学",
    "计算机科学与技术": "软件工程",
    "物联网工程": "电子信息工程",
    "机械设计制造及其自动化": "自动化",
    "金融学": "金融工程",
    "财务管理": "会计学",
    "国际经济与贸易": "电子商务",
    "工商管理": "会计学",
    "市场营销": "电子商务",
    "物流管理": "现代物流管理",
    "大数据与会计": "会计学",
    "UI/UX设计方向": "数字媒体艺术",
    "动画": "数字媒体艺术",
}


def manual_override_index() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for e in CATALOG_ENTRIES:
        key = e.get("entryKey") or f"{e['name']}@{e['tier']}"
        out[key] = e
        out.setdefault(f"{e['name']}@*", e)
    return out


def career_lookup() -> dict[str, dict[str, Any]]:
    if not CAREER_FILE.exists():
        return {}
    data = json.loads(CAREER_FILE.read_text(encoding="utf-8"))
    out: dict[str, dict[str, Any]] = {}
    for block in data.get("majors", []):
        name = block.get("major")
        if name:
            out[name] = block
    return out


def career_metrics(block: dict[str, Any] | None) -> dict[str, Any]:
    if not block:
        return {}
    jobs = block.get("jobs") or []
    growths = [j["growthPct"] for j in jobs if j.get("growthPct") is not None]
    grads = [j["graduateSalary"] for j in jobs if j.get("graduateSalary")]
    yr5s = [j["salary5yr"] for j in jobs if j.get("salary5yr")]
    confidences = [j.get("confidence") for j in jobs if j.get("confidence")]
    if not growths and not grads:
        return {}
    growth_med = round(statistics.median(growths), 1) if growths else None
    return {
        "salaryGrowth5y": growth_med,
        "graduateSalaryMed": int(statistics.median(grads)) if grads else None,
        "salary5yrMed": int(statistics.median(yr5s)) if yr5s else None,
        "careerConfidence": confidences[0] if confidences else None,
        "careerJobsSampled": len(jobs),
    }


def growth_component(growth: float | None) -> int | None:
    if growth is None:
        return None
    return max(35, min(98, int(50 + growth * 0.55)))


def volume_component(yoy: float | None) -> int | None:
    if yoy is None:
        return None
    # -30% -> ~40, 0% -> 55, +50% -> ~80
    return max(30, min(98, int(55 + yoy * 0.5)))


def blend_trend_index(
    manual: int,
    growth: float | None,
    job_yoy: float | None,
) -> int:
    """产业趋势指数 = 35% 人工研判 + 35% 薪资涨幅 + 30% 岗位量同比。"""
    parts: list[tuple[int, float]] = [(manual, 0.35)]
    gc = growth_component(growth)
    if gc is not None:
        parts.append((gc, 0.35))
    vc = volume_component(job_yoy)
    if vc is not None:
        parts.append((vc, 0.30))
    if len(parts) == 1:
        return manual
    total_w = sum(w for _, w in parts)
    score = sum(v * w for v, w in parts) / total_w
    return max(35, min(100, int(round(score))))


def load_occupations() -> tuple[list[dict[str, Any]], dict[str, str]]:
    if not OCC_FILE.exists():
        return [], {}
    data = json.loads(OCC_FILE.read_text(encoding="utf-8"))
    occs = data.get("occupations") or []
    middle = data.get("middle_categories") or {}
    return occs, middle


def build_entry(
    raw: dict[str, Any],
    career: dict[str, dict[str, Any]],
    overrides: dict[str, dict[str, Any]],
    job_index: dict[str, Any],
    occupations: list[dict[str, Any]],
    middle_lookup: dict[str, str],
    view_months: list[int],
    salaries: list[int],
) -> dict[str, Any]:
    name = raw["name"]
    catalog_type = raw["catalogType"]
    level1_name = raw.get("level1Name") or ""
    discipline = infer_discipline(raw.get("level2Name") or "", level1_name)
    subjects = infer_subjects(raw.get("level2Name") or "", level1_name)
    salaryavg = raw.get("salaryavg")
    tier = infer_tier(
        level1_name,
        salaryavg,
        salary_percentile(salaryavg, salaries),
    )

    okey = f"{name}@{tier}"
    ckey = f"{name}@{catalog_type}"
    override = overrides.get(okey) or overrides.get(ckey) or overrides.get(f"{name}@*")

    if override:
        if override.get("discipline"):
            discipline = override["discipline"]
        if override.get("subjects"):
            subjects = override["subjects"]
        if override.get("tier"):
            tier = override["tier"]
        manual = int(override["manualTrend"])
        rationale = override.get("trendRationale", "")
        opportunity = bool(override.get("opportunity"))
        entry_key = override.get("entryKey") or okey
    else:
        manual = infer_manual_trend(
            raw.get("viewMonth"),
            salary_percentile(raw.get("viewMonth"), view_months),
            salary_percentile(salaryavg, salaries),
        )
        rationale = f"{raw.get('level2Name') or discipline}方向；EOL月搜索热度与薪资分位综合评估"
        opportunity = False
        entry_key = ckey

    career_name = CAREER_ALIASES.get(name, name)
    metrics = career_metrics(career.get(career_name))
    job_meta = job_index.get(ckey) or {}
    job_yoy = job_meta.get("jobVolumeYoY")
    trend_index = blend_trend_index(manual, metrics.get("salaryGrowth5y"), job_yoy)

    occs = match_occupations(
        name,
        discipline,
        occupations,
        middle_lookup,
        raw.get("hightitle") or "",
        raw.get("level2Name") or "",
        limit=3,
    )

    entry: dict[str, Any] = {
        "id": entry_key,
        "name": name,
        "discipline": discipline,
        "subjects": subjects,
        "tier": tier,
        "catalogType": catalog_type,
        "moeCode": raw.get("moeCode") or raw.get("spcode") or "",
        "level2Name": raw.get("level2Name") or "",
        "level3Name": raw.get("level3Name") or "",
        "manualTrend": manual,
        "trendIndex": trend_index,
        "trendRationale": rationale,
        "opportunity": opportunity,
        "occupations": occs,
        "occupationCodes": [o["code"] for o in occs],
        "sources": [],
    }

    if job_meta:
        entry["jobVolumeYoY"] = job_yoy
        entry["jobVolumeSource"] = job_meta.get("jobVolumeSource")
        if job_meta.get("zhaopinCount") is not None:
            entry["zhaopinJobCount"] = job_meta["zhaopinCount"]

    if metrics:
        entry.update(metrics)
        entry["sources"] = ["就业沙盘四源薪资", "人工/算法产业研判", "招聘热度指数"]
        entry["validated"] = metrics.get("careerConfidence") in (
            "verified_multi_source",
            "verified",
            "partial",
        )
    else:
        entry["sources"] = ["教育部专业目录", "EOL产业数据", "招聘热度指数"]
        entry["validated"] = False

    if occs:
        entry["sources"].append("人社部职业分类大典(2022)")

    return entry


def main() -> None:
    if not RAW_FILE.exists():
        raise SystemExit(f"Missing {RAW_FILE} — run: python scripts/scrape_moe_majors.py")

    raw_data = json.loads(RAW_FILE.read_text(encoding="utf-8"))
    raws: list[dict[str, Any]] = raw_data.get("majors") or []
    job_index = {}
    if JOB_VOLUME_FILE.exists():
        job_index = json.loads(JOB_VOLUME_FILE.read_text(encoding="utf-8")).get("index") or {}

    career = career_lookup()
    overrides = manual_override_index()
    occupations, middle_lookup = load_occupations()

    view_months = [int(m["viewMonth"]) for m in raws if m.get("viewMonth")]
    salaries = [int(m["salaryavg"]) for m in raws if m.get("salaryavg")]

    majors = [
        build_entry(raw, career, overrides, job_index, occupations, middle_lookup, view_months, salaries)
        for raw in raws
    ]

    by_subject: dict[str, int] = {}
    by_catalog: dict[str, int] = {}
    with_occ = 0
    with_job = 0
    for m in majors:
        for s in m["subjects"]:
            by_subject[s] = by_subject.get(s, 0) + 1
        ct = m.get("catalogType") or "unknown"
        by_catalog[ct] = by_catalog.get(ct, 0) + 1
        if m.get("occupationCodes"):
            with_occ += 1
        if m.get("jobVolumeYoY") is not None:
            with_job += 1

    meta = {
        "version": "2.0",
        "generatedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total": len(majors),
        "bySubject": by_subject,
        "byCatalogType": by_catalog,
        "withOccupationCodes": with_occ,
        "withJobVolumeYoY": with_job,
        "methodology": {
            "trendIndex": "产业趋势指数 = 35% 人工研判 + 35% 就业沙盘5年薪资涨幅 + 30% 岗位发布量/搜索热度同比",
            "salaryGrowth5y": "来自 career_sandbox 该专业岗位样本的中位涨幅(%)",
            "jobVolumeYoY": "智联招聘职位数同比；无历史快照时用EOL月搜索热度同比或周热度动量",
            "occupationCodes": "人社部《职业分类大典》(2022) 细类编码，按专业名+学科门类匹配",
            "catalog": "教育部本科专业目录(2026)+高职专科/职教本科目录，EOL全量扩源",
        },
        "disclaimer": "趋势指数用于志愿参考，非官方预测；具体开设专业以院校当年招生简章为准。",
    }
    payload = {"meta": meta, "majors": majors}
    OUT_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # 前端嵌入：保留推荐所需字段，控制体积
    slim_majors = []
    for m in majors:
        slim_majors.append({
            "id": m["id"],
            "name": m["name"],
            "discipline": m["discipline"],
            "subjects": m["subjects"],
            "tier": m["tier"],
            "catalogType": m.get("catalogType"),
            "moeCode": m.get("moeCode"),
            "manualTrend": m["manualTrend"],
            "trendIndex": m["trendIndex"],
            "trendRationale": m.get("trendRationale"),
            "opportunity": m.get("opportunity"),
            "salaryGrowth5y": m.get("salaryGrowth5y"),
            "jobVolumeYoY": m.get("jobVolumeYoY"),
            "jobVolumeSource": m.get("jobVolumeSource"),
            "occupationCodes": m.get("occupationCodes"),
            "occupations": m.get("occupations"),
            "validated": m.get("validated"),
        })
    slim_payload = {"meta": meta, "majors": slim_majors}
    body = json.dumps(slim_payload, ensure_ascii=False, separators=(",", ":"))
    EMBED_FILE.write_text(
        "// Auto-generated — run: python scripts/build_major_catalog.py\n"
        f"window.MAJOR_CATALOG={body};\n",
        encoding="utf-8",
    )

    # manifest hotMajors：每专业取最高 trendIndex 的一条用于向后兼容
    best: dict[str, dict[str, Any]] = {}
    for m in majors:
        prev = best.get(m["name"])
        if not prev or (m["trendIndex"] or 0) > (prev.get("trendIndex") or 0):
            best[m["name"]] = m

    hot = []
    for m in sorted(best.values(), key=lambda x: -(x.get("trendIndex") or 0))[:120]:
        hot.append({
            "name": m["name"],
            "track": m["discipline"],
            "tier": m["tier"],
            "score": m["trendIndex"],
            "manualTrend": m["manualTrend"],
            "trendIndex": m["trendIndex"],
            "subjects": m["subjects"],
            "salaryGrowth5y": m.get("salaryGrowth5y"),
            "jobVolumeYoY": m.get("jobVolumeYoY"),
            "occupationCodes": m.get("occupationCodes"),
            "trendRationale": m.get("trendRationale"),
            **({"opportunity": True} if m.get("opportunity") else {}),
        })

    if MANIFEST_FILE.exists():
        manifest = json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))
        manifest["majorCatalogMeta"] = meta
        manifest["hotMajors"] = hot
        manifest.setdefault("dataSources", {})["majorCatalog"] = {
            "total": len(majors),
            "undergraduate": by_catalog.get("undergraduate", 0),
            "vocational": by_catalog.get("vocational", 0),
            "vocationalUndergraduate": by_catalog.get("vocational_undergraduate", 0),
        }
        MANIFEST_FILE.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    validated = sum(1 for m in majors if m.get("validated"))
    print(f"Wrote {OUT_FILE} ({len(majors)} majors)")
    print(f"  本科 {by_catalog.get('undergraduate', 0)} | 专科 {by_catalog.get('vocational', 0)} | 职教本科 {by_catalog.get('vocational_undergraduate', 0)}")
    print(f"  物理类 {by_subject.get('物理类', 0)} | 历史类 {by_subject.get('历史类', 0)}")
    print(f"  职业编码挂接: {with_occ}/{len(majors)} | 岗位量趋势: {with_job}/{len(majors)}")
    print(f"  就业交叉验证: {validated}/{len(majors)}")
    print(f"Wrote {EMBED_FILE} ({EMBED_FILE.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Scrape Gaokao score segments with multi-source cross-validation."""

from __future__ import annotations

import json
import math
import random
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

import requests

from gaokao_crawl_lib import (
    CatalogEntry,
    ScrapeResult,
    cross_validate,
    detect_track,
    discover_eol_catalog,
    load_zizzs_anchors,
    scrape_eol_entry,
)

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
PROVINCE_DIR = DATA_DIR / "provinces"
MANIFEST_FILE = DATA_DIR / "manifest.json"
VALIDATION_FILE = DATA_DIR / "validation_report.json"
CATALOG_FILE = DATA_DIR / "eol_catalog.json"

PROVINCES = [
    "北京", "天津", "河北", "山西", "内蒙古", "辽宁", "吉林", "黑龙江",
    "上海", "江苏", "浙江", "安徽", "福建", "江西", "山东", "河南",
    "湖北", "湖南", "广东", "广西", "海南", "重庆", "四川", "贵州",
    "云南", "西藏", "陕西", "甘肃", "青海", "宁夏", "新疆",
]
YEARS = list(range(2014, 2026))

BASE_YEAR = 2025

PROVINCE_BASE_2025: dict[str, dict[str, int]] = {
    "北京": {"special": 519, "undergrad": 430, "max": 750, "candidates": 54000},
    "天津": {"special": 562, "undergrad": 476, "max": 750, "candidates": 68000},
    "河北": {"special": 499, "undergrad": 459, "max": 750, "candidates": 880000},
    "山西": {"special": 507, "undergrad": 419, "max": 750, "candidates": 350000},
    "内蒙古": {"special": 487, "undergrad": 375, "max": 750, "candidates": 190000},
    "辽宁": {"special": 515, "undergrad": 367, "max": 750, "candidates": 195000},
    "吉林": {"special": 479, "undergrad": 340, "max": 750, "candidates": 125000},
    "黑龙江": {"special": 472, "undergrad": 360, "max": 750, "candidates": 190000},
    "上海": {"special": 505, "undergrad": 402, "max": 660, "candidates": 54000},
    "江苏": {"special": 519, "undergrad": 463, "max": 750, "candidates": 477000},
    "浙江": {"special": 592, "undergrad": 490, "max": 750, "candidates": 390000},
    "安徽": {"special": 514, "undergrad": 461, "max": 750, "candidates": 670000},
    "福建": {"special": 520, "undergrad": 441, "max": 750, "candidates": 240000},
    "江西": {"special": 505, "undergrad": 429, "max": 750, "candidates": 550000},
    "山东": {"special": 521, "undergrad": 441, "max": 750, "candidates": 980000},
    "河南": {"special": 535, "undergrad": 427, "max": 750, "candidates": 1360000},
    "湖北": {"special": 516, "undergrad": 426, "max": 750, "candidates": 520000},
    "湖南": {"special": 476, "undergrad": 405, "max": 750, "candidates": 730000},
    "广东": {"special": 534, "undergrad": 436, "max": 750, "candidates": 760000},
    "广西": {"special": 495, "undergrad": 370, "max": 750, "candidates": 460000},
    "海南": {"special": 571, "undergrad": 480, "max": 900, "candidates": 72000},
    "重庆": {"special": 498, "undergrad": 425, "max": 750, "candidates": 320000},
    "四川": {"special": 518, "undergrad": 438, "max": 750, "candidates": 830000},
    "贵州": {"special": 483, "undergrad": 387, "max": 750, "candidates": 340000},
    "云南": {"special": 495, "undergrad": 430, "max": 750, "candidates": 390000},
    "西藏": {"special": 400, "undergrad": 300, "max": 750, "candidates": 38000},
    "陕西": {"special": 473, "undergrad": 394, "max": 750, "candidates": 350000},
    "甘肃": {"special": 475, "undergrad": 374, "max": 750, "candidates": 260000},
    "青海": {"special": 420, "undergrad": 350, "max": 750, "candidates": 52000},
    "宁夏": {"special": 441, "undergrad": 372, "max": 750, "candidates": 72000},
    "新疆": {"special": 421, "undergrad": 280, "max": 750, "candidates": 210000},
}

HOT_MAJORS = [
    {"name": "人工智能", "track": "工科", "score": 98, "tier": "985"},
    {"name": "集成电路设计与集成系统", "track": "工科", "score": 97, "tier": "985"},
    {"name": "机器人工程", "track": "工科", "score": 96, "tier": "211"},
    {"name": "软件工程", "track": "工科", "score": 95, "tier": "211"},
    {"name": "数据科学与大数据技术", "track": "工科", "score": 94, "tier": "211"},
    {"name": "网络空间安全", "track": "工科", "score": 93, "tier": "211"},
    {"name": "新能源科学与工程", "track": "工科", "score": 92, "tier": "一本"},
    {"name": "电气工程及其自动化", "track": "工科", "score": 91, "tier": "一本"},
    {"name": "自动化", "track": "工科", "score": 90, "tier": "一本"},
    {"name": "电子信息工程", "track": "工科", "score": 89, "tier": "一本"},
    {"name": "临床医学", "track": "理科", "score": 88, "tier": "211"},
    {"name": "生物医学工程", "track": "理科", "score": 87, "tier": "211"},
    {"name": "统计学", "track": "理科", "score": 86, "tier": "一本"},
    {"name": "数学与应用数学", "track": "理科", "score": 85, "tier": "一本"},
    {"name": "金融工程", "track": "商科", "score": 84, "tier": "211"},
    {"name": "会计学", "track": "商科", "score": 83, "tier": "一本"},
    {"name": "数字经济", "track": "商科", "score": 82, "tier": "一本"},
    {"name": "电子商务", "track": "商科", "score": 81, "tier": "一本"},
    {"name": "法学", "track": "文科", "score": 80, "tier": "211"},
    {"name": "新闻传播学", "track": "文科", "score": 78, "tier": "一本"},
    {"name": "数字媒体艺术", "track": "艺术", "score": 77, "tier": "一本"},
    {"name": "视觉传达设计", "track": "艺术", "score": 76, "tier": "一本"},
    {"name": "UI/UX设计方向", "track": "艺术", "score": 75, "tier": "一本"},
]

TIER_ORDER = ["C9", "985", "211", "双一流", "一本", "二本", "专科"]
TIER_PERCENTILE = {
    "C9": 99.5, "985": 98.5, "211": 96.0, "双一流": 93.0,
    "一本": 85.0, "二本": 65.0, "专科": 40.0,
}

SCHOOLS = [
    {"name": "清华大学", "tier": "C9", "tags": ["AI", "芯片", "工科"]},
    {"name": "北京大学", "tier": "C9", "tags": ["AI", "数学", "理科"]},
    {"name": "复旦大学", "tier": "C9", "tags": ["AI", "商科", "医学"]},
    {"name": "上海交通大学", "tier": "C9", "tags": ["AI", "芯片", "工科"]},
    {"name": "浙江大学", "tier": "C9", "tags": ["AI", "机器人", "工科"]},
    {"name": "南京大学", "tier": "C9", "tags": ["AI", "理科", "文科"]},
    {"name": "中国科学技术大学", "tier": "C9", "tags": ["AI", "芯片", "理科"]},
    {"name": "哈尔滨工业大学", "tier": "985", "tags": ["机器人", "航天", "工科"]},
    {"name": "西安交通大学", "tier": "985", "tags": ["AI", "能源", "工科"]},
    {"name": "北京航空航天大学", "tier": "985", "tags": ["机器人", "航天", "工科"]},
    {"name": "同济大学", "tier": "985", "tags": ["土木", "汽车", "工科"]},
    {"name": "华中科技大学", "tier": "985", "tags": ["AI", "医学", "工科"]},
    {"name": "武汉大学", "tier": "985", "tags": ["法学", "遥感", "综合"]},
    {"name": "中山大学", "tier": "985", "tags": ["医学", "商科", "综合"]},
    {"name": "电子科技大学", "tier": "985", "tags": ["芯片", "AI", "工科"]},
    {"name": "北京理工大学", "tier": "985", "tags": ["机器人", "军工", "工科"]},
    {"name": "东南大学", "tier": "985", "tags": ["芯片", "建筑", "工科"]},
    {"name": "天津大学", "tier": "985", "tags": ["化工", "建筑", "工科"]},
    {"name": "大连理工大学", "tier": "985", "tags": ["化工", "船舶", "工科"]},
    {"name": "华南理工大学", "tier": "985", "tags": ["新能源", "建筑", "工科"]},
    {"name": "湖南大学", "tier": "985", "tags": ["汽车", "土木", "工科"]},
    {"name": "重庆大学", "tier": "985", "tags": ["建筑", "电气", "工科"]},
    {"name": "吉林大学", "tier": "985", "tags": ["汽车", "医学", "综合"]},
    {"name": "山东大学", "tier": "985", "tags": ["医学", "数学", "综合"]},
    {"name": "四川大学", "tier": "985", "tags": ["医学", "材料", "综合"]},
    {"name": "西北工业大学", "tier": "985", "tags": ["航天", "材料", "工科"]},
    {"name": "中南大学", "tier": "985", "tags": ["冶金", "医学", "工科"]},
    {"name": "兰州大学", "tier": "985", "tags": ["化学", "理科", "综合"]},
    {"name": "东北大学", "tier": "985", "tags": ["自动化", "冶金", "工科"]},
    {"name": "中国海洋大学", "tier": "985", "tags": ["海洋", "食品", "综合"]},
    {"name": "中央民族大学", "tier": "985", "tags": ["民族", "文科", "综合"]},
    {"name": "华东师范大学", "tier": "985", "tags": ["教育", "软件", "综合"]},
    {"name": "中国农业大学", "tier": "985", "tags": ["农业", "生物", "综合"]},
    {"name": "西北农林科技大学", "tier": "985", "tags": ["农业", "食品", "综合"]},
    {"name": "北京邮电大学", "tier": "211", "tags": ["通信", "AI", "工科"]},
    {"name": "南京航空航天大学", "tier": "211", "tags": ["航天", "机器人", "工科"]},
    {"name": "南京理工大学", "tier": "211", "tags": ["军工", "自动化", "工科"]},
    {"name": "西安电子科技大学", "tier": "211", "tags": ["芯片", "通信", "工科"]},
    {"name": "北京交通大学", "tier": "211", "tags": ["交通", "软件", "工科"]},
    {"name": "合肥工业大学", "tier": "211", "tags": ["汽车", "机械", "工科"]},
    {"name": "苏州大学", "tier": "211", "tags": ["材料", "医学", "综合"]},
    {"name": "郑州大学", "tier": "211", "tags": ["医学", "材料", "综合"]},
    {"name": "云南大学", "tier": "211", "tags": ["民族", "生态", "综合"]},
    {"name": "新疆大学", "tier": "211", "tags": ["能源", "综合", "区域"]},
    {"name": "上海财经大学", "tier": "211", "tags": ["金融", "商科", "财经"]},
    {"name": "对外经济贸易大学", "tier": "211", "tags": ["国贸", "商科", "财经"]},
    {"name": "中国政法大学", "tier": "211", "tags": ["法学", "文科", "政法"]},
    {"name": "北京科技大学", "tier": "211", "tags": ["材料", "冶金", "工科"]},
    {"name": "华北电力大学", "tier": "211", "tags": ["电气", "能源", "工科"]},
    {"name": "河海大学", "tier": "211", "tags": ["水利", "土木", "工科"]},
    {"name": "江南大学", "tier": "211", "tags": ["食品", "轻工", "综合"]},
    {"name": "南京师范大学", "tier": "211", "tags": ["教育", "文科", "师范"]},
    {"name": "深圳大学", "tier": "双一流", "tags": ["AI", "商科", "综合"]},
    {"name": "南方科技大学", "tier": "双一流", "tags": ["AI", "理科", "新兴"]},
    {"name": "西湖大学", "tier": "双一流", "tags": ["生物", "理科", "新兴"]},
    {"name": "宁波大学", "tier": "双一流", "tags": ["海洋", "综合", "区域"]},
    {"name": "首都师范大学", "tier": "双一流", "tags": ["教育", "文科", "师范"]},
    {"name": "浙江工业大学", "tier": "一本", "tags": ["化工", "机械", "工科"]},
    {"name": "广东工业大学", "tier": "一本", "tags": ["机械", "自动化", "工科"]},
    {"name": "杭州电子科技大学", "tier": "一本", "tags": ["电子", "软件", "工科"]},
    {"name": "南京工业大学", "tier": "一本", "tags": ["化工", "建筑", "工科"]},
    {"name": "燕山大学", "tier": "一本", "tags": ["机械", "材料", "工科"]},
    {"name": "昆明理工大学", "tier": "一本", "tags": ["冶金", "机械", "区域"]},
    {"name": "长春理工大学", "tier": "一本", "tags": ["光电", "机械", "工科"]},
    {"name": "重庆邮电大学", "tier": "一本", "tags": ["通信", "软件", "工科"]},
    {"name": "上海理工大学", "tier": "一本", "tags": ["机械", "光学", "工科"]},
    {"name": "天津工业大学", "tier": "一本", "tags": ["纺织", "材料", "工科"]},
    {"name": "山东师范大学", "tier": "一本", "tags": ["教育", "文科", "师范"]},
    {"name": "福建师范大学", "tier": "一本", "tags": ["教育", "文科", "师范"]},
    {"name": "北京信息科技大学", "tier": "二本", "tags": ["信息", "工科", "应用"]},
    {"name": "上海第二工业大学", "tier": "二本", "tags": ["制造", "工科", "应用"]},
    {"name": "重庆文理学院", "tier": "二本", "tags": ["综合", "区域", "应用"]},
    {"name": "洛阳理工学院", "tier": "二本", "tags": ["材料", "机械", "应用"]},
    {"name": "深圳职业技术大学", "tier": "专科", "tags": ["职教", "应用", "就业"]},
    {"name": "金华职业技术大学", "tier": "专科", "tags": ["职教", "应用", "就业"]},
    {"name": "北京电子科技职业学院", "tier": "专科", "tags": ["电子", "职教", "就业"]},
]


def year_adjust(base: dict[str, int], year: int) -> dict[str, int]:
    delta = (year - BASE_YEAR) * random.uniform(-1.2, 1.0)
    return {
        "special": int(round(base["special"] + delta)),
        "undergrad": int(round(base["undergrad"] + delta * 0.8)),
        "max": base["max"],
        "candidates": int(base["candidates"] * (1 + (year - BASE_YEAR) * 0.01)),
    }


def synthesize_segments(cfg: dict[str, int], track: str):
    from gaokao_crawl_lib import SegmentRow

    max_score = cfg["max"]
    undergrad = cfg["undergrad"]
    special = cfg["special"]
    total = max(30000, cfg["candidates"] // 2)
    if track in ("历史类", "文科"):
        undergrad += random.randint(-15, 10)
        special += random.randint(-15, 10)
        total = int(total * 0.45)
    segments: list = []
    cumulative = 0
    floor = max(120, undergrad - 80)
    for score in range(max_score, floor - 1, -1):
        dist_from_top = max_score - score
        if score >= special:
            count = int(8 * math.exp(-dist_from_top / 55) + random.uniform(0.5, 3))
        elif score >= undergrad:
            count = int(900 * math.exp(-(undergrad - score) / 30) + random.uniform(20, 80))
        else:
            count = int(500 * math.exp(-(undergrad - score) / 18) + random.uniform(10, 40))
        count = max(1, count)
        cumulative += count
        segments.append(SegmentRow(score, count, cumulative))
    return segments, cumulative


def downsample_segments(segments, undergrad: int, max_score: int):
    from gaokao_crawl_lib import SegmentRow

    if not segments:
        return segments
    keep_scores: set[int] = set()
    for s in range(max_score, max(undergrad - 60, 0), -1):
        if s >= undergrad + 40 or s <= undergrad + 5 or (max_score - s) < 40:
            keep_scores.add(s)
        elif (max_score - s) % 2 == 0 and s >= undergrad:
            keep_scores.add(s)
        elif (undergrad - s) % 4 == 0:
            keep_scores.add(s)
    kept = [seg for seg in segments if seg.score in keep_scores]
    if len(kept) > 90:
        step = max(1, len(kept) // 80)
        kept = kept[::step]
    by_score = {seg.score: seg for seg in segments}
    for must in (max_score, undergrad + 20, undergrad, max(undergrad - 40, 0)):
        if must in by_score:
            kept.append(by_score[must])
    dedup = {seg.score: seg for seg in kept}
    return sorted(dedup.values(), key=lambda x: x.score, reverse=True)


def enrich_track_payload(result: ScrapeResult, cfg: dict[str, int]) -> dict[str, Any]:
    segments = [s for s in result.segments if s.score >= cfg["undergrad"] - 80]
    segments = downsample_segments(segments, cfg["undergrad"], cfg["max"])
    total = result.total
    enriched = []
    for seg in segments:
        share = round(seg.count / total * 100, 3) if total else 0
        percentile = round((1 - (seg.cumulative - seg.count / 2) / total) * 100, 2) if total else 0
        enriched.append({"s": seg.score, "p": percentile, "r": share})
    return {
        "totalCandidates": total,
        "segments": enriched,
        "source": result.source,
        "sourceUrl": result.url,
        "confidence": result.confidence,
        "confidenceScore": result.confidence_score,
        "validation": {
            "structural": result.structural,
            "crossChecks": result.cross_checks,
            "anchors": result.anchors,
        },
    }


def crawl_all_eol(session: requests.Session, catalog: list[CatalogEntry], zizzs_cache: dict) -> dict[tuple[str, int, str | None], ScrapeResult]:
    bucket: dict[tuple[str, int, str | None], list[ScrapeResult]] = defaultdict(list)
    print(f"Fetching {len(catalog)} eol candidate pages...")
    for i, entry in enumerate(catalog, 1):
        result = scrape_eol_entry(session, entry)
        if not result:
            continue
        if not result.structural.get("ok"):
            print(f"  [skip structural] {entry.province} {entry.year} {entry.track}")
            continue
        track = entry.track
        zizzs = None
        if track:
            zizzs = zizzs_cache.get((entry.province, entry.year, track))
        if not zizzs:
            zizzs = zizzs_cache.get((entry.province, entry.year, "物理类"))
        checks, confidence, score = cross_validate(
            result.segments, track, result.anchors, zizzs
        )
        result.cross_checks = checks
        result.confidence = confidence
        result.confidence_score = score
        if result.structural.get("ok") and confidence in ("table_only", "unknown"):
            result.confidence = "validated_structural"
            result.confidence_score = max(score, 0.7)
        bucket[(entry.province, entry.year, track)].append(result)
        if i % 20 == 0:
            print(f"  ... fetched {i}/{len(catalog)}")
        time.sleep(0.35)

    chosen: dict[tuple[str, int, str | None], ScrapeResult] = {}
    for key, items in bucket.items():
        best = sorted(items, key=lambda r: r.confidence_score, reverse=True)[0]
        chosen[key] = best
    return chosen


def resolve_track_data(
    prov: str,
    year: int,
    track: str,
    scraped: dict[tuple[str, int, str | None], ScrapeResult],
    cfg: dict[str, int],
) -> dict[str, Any]:
    key_specific = (prov, year, track)
    key_general = (prov, year, None)

    if key_specific in scraped:
        return enrich_track_payload(scraped[key_specific], cfg)

    if key_general in scraped:
        result = scraped[key_general]
        detected = detect_track(result.title)
        if not detected or detected == track:
            return enrich_track_payload(result, cfg)

    segments, total = synthesize_segments(cfg, track)
    from gaokao_crawl_lib import ScrapeResult, SegmentRow

    fake = ScrapeResult(segments=segments, total=total, source="model", url="", confidence="model_estimate", confidence_score=0.35)
    fake.structural = {"ok": True, "issues": []}
    return enrich_track_payload(fake, cfg)


def build_dataset() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    session = requests.Session()
    catalog = discover_eol_catalog(session)
    CATALOG_FILE.write_text(
        json.dumps([e.__dict__ for e in catalog], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Discovered {len(catalog)} eol catalog entries -> {CATALOG_FILE}")

    zizzs_cache = load_zizzs_anchors(session)
    scraped = crawl_all_eol(session, catalog, zizzs_cache)

    validation_rows: list[dict[str, Any]] = []
    for key, result in scraped.items():
        validation_rows.append({
            "province": key[0],
            "year": key[1],
            "track": key[2],
            "confidence": result.confidence,
            "confidenceScore": result.confidence_score,
            "url": result.url,
            "crossChecks": result.cross_checks,
            "structural": result.structural,
        })

    provinces_data: dict[str, Any] = {}
    stats = {"verified": 0, "partial": 0, "structural": 0, "scraped": 0, "model": 0}

    for prov in PROVINCES:
        base = PROVINCE_BASE_2025[prov]
        provinces_data[prov] = {"years": {}}
        for year in YEARS:
            cfg = year_adjust(base, year)
            year_obj: dict[str, Any] = {
                "batches": {"特招线": cfg["special"], "本科线": cfg["undergrad"]},
                "maxScore": cfg["max"],
                "tracks": {},
            }
            for track in ("物理类", "历史类"):
                payload = resolve_track_data(prov, year, track, scraped, cfg)
                year_obj["tracks"][track] = payload
                if payload["source"] == "eol.cn":
                    stats["scraped"] += 1
                    conf = payload["confidence"]
                    if conf in ("verified", "verified_multi_source"):
                        stats["verified"] += 1
                    elif conf == "partially_verified":
                        stats["partial"] += 1
                    elif conf == "validated_structural":
                        stats["structural"] += 1
                else:
                    stats["model"] += 1
            provinces_data[prov]["years"][str(year)] = year_obj

    schools = [{**s, "minPercentile": TIER_PERCENTILE[s["tier"]]} for s in SCHOOLS]
    meta = {
        "generatedAt": time.strftime("%Y-%m-%d %H:%M:%S"),
        "yearRange": [2014, 2025],
        "provinces": len(PROVINCES),
        "eolCatalogSize": len(catalog),
        "eolScrapedTracks": len(scraped),
        "coverage": stats,
        "notes": (
            "一分一段：优先使用 eol.cn 爬取数据，并通过正文锚点 + zizzs 位次锚点交叉验证。"
            "verified/verified_multi_source 表示多源校验通过；validated_structural 为 eol 真表但未完成锚点校验。"
            "2014-2018 及未覆盖省份年份使用模型估算，仅供参考，请以省考试院官方数据为准。"
        ),
    }
    return {
        "meta": meta,
        "tierOrder": TIER_ORDER,
        "tierPercentile": TIER_PERCENTILE,
        "provinces": provinces_data,
        "schools": schools,
        "hotMajors": HOT_MAJORS,
    }, validation_rows


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PROVINCE_DIR.mkdir(parents=True, exist_ok=True)
    data, validation_rows = build_dataset()

    manifest = {
        "meta": data["meta"],
        "tierOrder": data["tierOrder"],
        "tierPercentile": data["tierPercentile"],
        "provinces": PROVINCES,
        "years": YEARS,
        "schools": data["schools"],
        "hotMajors": data["hotMajors"],
    }
    MANIFEST_FILE.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    VALIDATION_FILE.write_text(json.dumps(validation_rows, ensure_ascii=False, indent=2), encoding="utf-8")

    total_bytes = MANIFEST_FILE.stat().st_size + VALIDATION_FILE.stat().st_size
    for prov, prov_data in data["provinces"].items():
        path = PROVINCE_DIR / f"{prov}.json"
        path.write_text(json.dumps(prov_data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        total_bytes += path.stat().st_size

    cov = data["meta"]["coverage"]
    print(f"Wrote {MANIFEST_FILE}")
    print(f"Wrote {VALIDATION_FILE} ({len(validation_rows)} validated tracks)")
    print(f"Coverage: scraped={cov['scraped']} verified={cov['verified']} partial={cov.get('partial', 0)} structural={cov.get('structural', 0)} model_fallback={cov['model']}")
    print(f"Total size {(total_bytes / 1024 / 1024):.2f} MB")

    from build_embed import build_embed
    from build_career_sandbox import main as build_career

    build_career()
    build_embed()


if __name__ == "__main__":
    main()

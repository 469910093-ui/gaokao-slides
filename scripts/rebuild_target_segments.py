#!/usr/bin/env python3
"""
补齐指定省份 2014-2025 一分一段真表（EOL HTML / Markdown / 图片 OCR）。
用法: python scripts/rebuild_target_segments.py
"""
from __future__ import annotations

import json
import time
from collections import defaultdict
from pathlib import Path

import requests

from gaokao_crawl_lib import (
    COMBINED_SEGMENT_PROVINCES,
    CatalogEntry,
    discover_eol_catalog,
    load_zizzs_anchors,
    pick_best_scrape,
)
from scrape_gaokao_data import (
    PROVINCE_BASE_2025,
    PROVINCES,
    YEARS,
    enrich_track_payload,
    resolve_track_data,
    year_adjust,
)

ROOT = Path(__file__).resolve().parents[1]
PROVINCE_DIR = ROOT / "data" / "provinces"
MANIFEST_FILE = ROOT / "data" / "manifest.json"

# 苏州→江苏，武汉→湖北
TARGET_PROVINCES = [
    "北京", "上海", "浙江", "广东", "四川", "山东", "云南", "广西",
    "江苏", "湖北", "辽宁", "吉林", "黑龙江",
]


def crawl_target_catalog(
    session: requests.Session,
    catalog: list[CatalogEntry],
    zizzs_cache: dict,
) -> dict[tuple[str, int, str | None], object]:
    from scrape_gaokao_data import crawl_all_eol  # reuse validation pipeline

    filtered = [e for e in catalog if e.province in TARGET_PROVINCES]
    print(f"Target catalog entries: {len(filtered)} / {len(catalog)}")

    # 临时替换 discover 输出：直接喂给 crawl 逻辑
    bucket: dict[tuple[str, int, str | None], list] = defaultdict(list)
    from gaokao_crawl_lib import (
        cross_validate,
        detect_track,
        maybe_calibrate_segments,
        scrape_eol_entry,
    )

    for i, entry in enumerate(filtered, 1):
        result = scrape_eol_entry(session, entry)
        if not result or not result.structural.get("ok"):
            continue
        detected = detect_track(result.title) or entry.track
        track = detected
        zizzs = None
        if track:
            zizzs = zizzs_cache.get((entry.province, entry.year, track))
        if not zizzs:
            zizzs = zizzs_cache.get((entry.province, entry.year, "物理类"))
        checks, confidence, score = cross_validate(
            result.segments, track, result.anchors, zizzs
        )
        result.segments, result.total, checks, confidence, score = maybe_calibrate_segments(
            result.segments, result.total, track, result.anchors, zizzs, checks, confidence, score
        )
        result.cross_checks = checks
        result.confidence = confidence
        result.confidence_score = score
        if result.structural.get("ok") and confidence in ("table_only", "unknown"):
            result.confidence = "validated_structural"
            result.confidence_score = max(score, 0.8)
        bucket[(entry.province, entry.year, track)].append(result)
        if i % 15 == 0:
            print(f"  ... scraped {i}/{len(filtered)}")
        time.sleep(0.25)

    chosen = {key: pick_best_scrape(items) for key, items in bucket.items()}
    print(f"Scraped tracks: {len(chosen)}")
    return chosen


def main() -> None:
    session = requests.Session()
    catalog = discover_eol_catalog(session)
    (ROOT / "data" / "eol_catalog.json").write_text(
        json.dumps([e.__dict__ for e in catalog], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    zizzs_cache = load_zizzs_anchors(session)
    scraped = crawl_target_catalog(session, catalog, zizzs_cache)

    stats = {"eol": 0, "model": 0}
    for prov in TARGET_PROVINCES:
        if prov not in PROVINCES:
            continue
        path = PROVINCE_DIR / f"{prov}.json"
        pdata = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"years": {}}
        for year in YEARS:
            cfg = year_adjust(PROVINCE_BASE_2025[prov], year)
            year_obj = pdata.setdefault("years", {}).setdefault(str(year), {
                "batches": {"特招线": cfg["special"], "本科线": cfg["undergrad"]},
                "maxScore": cfg["max"],
                "tracks": {},
            })
            year_obj["batches"] = {"特招线": cfg["special"], "本科线": cfg["undergrad"]}
            year_obj["maxScore"] = cfg["max"]
            for track in ("物理类", "历史类"):
                payload = resolve_track_data(prov, year, track, scraped, cfg, zizzs_cache)
                year_obj["tracks"][track] = payload
                if payload.get("source", "").startswith("eol"):
                    stats["eol"] += 1
                else:
                    stats["model"] += 1
        path.write_text(json.dumps(pdata, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        print(f"Updated {prov}")

    print(f"Track slots: eol={stats['eol']} model={stats['model']}")

    from build_embed import build_embed

    build_embed()
    print("Done.")


if __name__ == "__main__":
    main()

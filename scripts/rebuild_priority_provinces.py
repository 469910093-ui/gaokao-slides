#!/usr/bin/env python3
"""
重爬指定省份 2014-2025 一分一段（EOL + zizzs 交叉验证），并归档掌上高考投档线参考。
用法: python scripts/rebuild_priority_provinces.py
      python scripts/rebuild_priority_provinces.py --provinces 江西,新疆 --years 2024,2025
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from gaokao_crawl_lib import (  # noqa: E402
    CatalogEntry,
    cross_validate,
    detect_track,
    discover_eol_catalog,
    load_zizzs_anchors,
    maybe_calibrate_segments,
    pick_best_scrape,
    scrape_eol_entry,
)
from province_tracks import tracks_for_province  # noqa: E402
from scrape_gaokao_data import (  # noqa: E402
    PROVINCE_BASE_2025,
    PROVINCES,
    YEARS,
    resolve_track_data,
    year_adjust,
)

PROVINCE_DIR = ROOT / "data" / "provinces"
ADMISSION_DIR = ROOT / "data" / "reference" / "gaokao_cn"

# 用户指定优先补齐省份（江西重复已去重）
DEFAULT_PROVINCES = [
    "江西", "新疆", "西藏", "贵州", "青海", "甘肃", "内蒙古",
    "陕西", "重庆", "湖南", "湖北", "安徽", "福建",
]


def crawl_province_catalog(
    session: requests.Session,
    catalog: list[CatalogEntry],
    zizzs_cache: dict,
    target_provinces: list[str],
) -> dict[tuple[str, int, str | None], object]:
    filtered = [e for e in catalog if e.province in target_provinces]
    print(f"Target catalog entries: {len(filtered)} / {len(catalog)}")

    bucket: dict[tuple[str, int, str | None], list] = defaultdict(list)
    for i, entry in enumerate(filtered, 1):
        result = scrape_eol_entry(session, entry)
        if not result or not result.structural.get("ok"):
            continue
        detected = detect_track(result.title) or entry.track
        track = detected
        zizzs = zizzs_cache.get((entry.province, entry.year, track)) if track else None
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
        if i % 20 == 0:
            print(f"  ... scraped {i}/{len(filtered)}")
        time.sleep(0.28)

    chosen = {key: pick_best_scrape(items) for key, items in bucket.items()}
    print(f"Scraped tracks: {len(chosen)}")
    return chosen


def crawl_admissions_for_provinces(
    session: requests.Session,
    provinces: list[str],
    years: list[int],
) -> None:
    """归档掌上高考院校投档最低分（参考）。"""
    from scrape_gaokao_cn import crawl_control_lines_from_admissions, crawl_province_admissions

    ADMISSION_DIR.mkdir(parents=True, exist_ok=True)
    manifest: dict = {
        "source": "https://www.gaokao.cn/",
        "years": years,
        "provinces": provinces,
        "files": {},
    }
    for year in years:
        for prov in provinces:
            if prov not in PROVINCES:
                continue
            tracks = tracks_for_province(prov, year)
            all_rows: list[dict] = []
            for track in tracks:
                api_track = "综合" if track == "综合类" else track
                try:
                    rows = crawl_province_admissions(session, prov, year, api_track)
                    all_rows.extend(rows)
                    print(f"  admissions {prov} {year} {track}: {len(rows)} rows")
                except Exception as exc:  # noqa: BLE001
                    print(f"  [warn] admissions {prov} {year} {track}: {exc}")
                time.sleep(1.0)
            if not all_rows:
                continue
            out = ADMISSION_DIR / f"{prov}_{year}_admissions.json"
            out.write_text(json.dumps(all_rows, ensure_ascii=False, indent=2), encoding="utf-8")
            lines = crawl_control_lines_from_admissions(all_rows)
            manifest["files"][f"{prov}_{year}"] = {
                "admissions": str(out.relative_to(ROOT)),
                "controlLines": len(lines),
                "rows": len(all_rows),
            }
    (ADMISSION_DIR / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def patch_province_years(
    prov: str,
    years: list[int],
    scraped: dict,
    zizzs_cache: dict,
) -> dict[str, int]:
    path = PROVINCE_DIR / f"{prov}.json"
    pdata = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"years": {}}
    stats = {"eol": 0, "model": 0}
    for year in years:
        cfg = year_adjust(PROVINCE_BASE_2025[prov], year)
        year_obj = pdata.setdefault("years", {}).setdefault(str(year), {
            "batches": {"特招线": cfg["special"], "本科线": cfg["undergrad"]},
            "maxScore": cfg["max"],
            "tracks": {},
        })
        year_obj["batches"] = {"特招线": cfg["special"], "本科线": cfg["undergrad"]}
        year_obj["maxScore"] = cfg["max"]
        for track in tracks_for_province(prov, year):
            payload = resolve_track_data(prov, year, track, scraped, cfg, zizzs_cache)
            year_obj["tracks"][track] = payload
            if str(payload.get("source", "")).startswith("eol"):
                stats["eol"] += 1
            else:
                stats["model"] += 1
                if not payload.get("sourceNote"):
                    payload["sourceNote"] = "公开渠道暂无该省该年一分一段，位次为模型估算"
                payload["dataGap"] = True
    path.write_text(json.dumps(pdata, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return stats


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provinces", default=",".join(DEFAULT_PROVINCES))
    parser.add_argument("--years", default="2014-2025")
    parser.add_argument("--skip-admissions", action="store_true")
    args = parser.parse_args()
    target = [p.strip() for p in args.provinces.split(",") if p.strip()]
    if "-" in args.years and "," not in args.years:
        lo, hi = args.years.split("-", 1)
        years = list(range(int(lo), int(hi) + 1))
    else:
        years = [int(y.strip()) for y in args.years.split(",") if y.strip()]

    session = requests.Session()
    catalog = discover_eol_catalog(session)
    (ROOT / "data" / "eol_catalog.json").write_text(
        json.dumps([e.__dict__ for e in catalog], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    zizzs_cache = load_zizzs_anchors(session)
    scraped = crawl_province_catalog(session, catalog, zizzs_cache, target)

    total_eol = total_model = 0
    for prov in target:
        if prov not in PROVINCES:
            print(f"Skip unknown province: {prov}")
            continue
        st = patch_province_years(prov, years, scraped, zizzs_cache)
        total_eol += st["eol"]
        total_model += st["model"]
        print(f"Updated {prov}: eol={st['eol']} model={st['model']}")

    if not args.skip_admissions:
        recent = [y for y in years if y >= 2023]
        print(f"Crawling gaokao.cn admissions for {len(target)} provinces, years {recent}...")
        crawl_admissions_for_provinces(session, target, recent)

    from build_embed import build_embed

    build_embed()
    print(f"Done. tracks eol={total_eol} model={total_model}")


if __name__ == "__main__":
    main()

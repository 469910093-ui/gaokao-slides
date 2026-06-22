#!/usr/bin/env python3
"""
对 2025 仍缺 eol 真表的省份：尝试 catalog 全部 URL + 回退上一年 eol 真表写入 2025。
"""
from __future__ import annotations

import json
import time
from collections import defaultdict
from pathlib import Path

import requests

from gaokao_crawl_lib import (
    CatalogEntry,
    discover_eol_catalog,
    load_zizzs_anchors,
    pick_best_scrape,
    scrape_eol_entry,
    cross_validate,
    maybe_calibrate_segments,
    detect_track,
)
from scrape_gaokao_data import PROVINCE_BASE_2025, enrich_track_payload, resolve_track_data, year_adjust

ROOT = Path(__file__).resolve().parents[1]
PROVINCE_DIR = ROOT / "data" / "provinces"
YEAR = 2025


def log(msg: str) -> None:
    print(msg, flush=True)


def model_slots() -> list[tuple[str, str]]:
    out = []
    for path in sorted(PROVINCE_DIR.glob("*.json")):
        prov = path.stem
        data = json.loads(path.read_text(encoding="utf-8"))
        yo = data.get("years", {}).get(str(YEAR), {})
        for track in ("物理类", "历史类", "综合类"):
            td = yo.get("tracks", {}).get(track, {})
            src = str(td.get("source") or "")
            if not src.startswith("eol"):
                out.append((prov, track))
    return out


def crawl_province_entries(session, entries, zizzs_cache):
    bucket: dict[tuple[str, int, str | None], list] = defaultdict(list)
    for i, entry in enumerate(entries, 1):
        result = scrape_eol_entry(session, entry)
        if not result or not result.structural.get("ok"):
            continue
        track = detect_track(result.title) or entry.track
        zizzs = zizzs_cache.get((entry.province, entry.year, track or "物理类"))
        checks, confidence, score = cross_validate(result.segments, track, result.anchors, zizzs)
        result.segments, result.total, checks, confidence, score = maybe_calibrate_segments(
            result.segments, result.total, track, result.anchors, zizzs, checks, confidence, score
        )
        result.cross_checks = checks
        result.confidence = confidence
        result.confidence_score = score
        bucket[(entry.province, entry.year, track)].append(result)
        if i % 8 == 0:
            log(f"    ... {i}/{len(entries)}")
        time.sleep(0.15)
    return {k: pick_best_scrape(v) for k, v in bucket.items()}


def main() -> None:
    session = requests.Session()
    catalog = discover_eol_catalog(session)
    zizzs_cache = load_zizzs_anchors(session)
    slots = model_slots()
    provs = sorted({p for p, _ in slots})
    log(f"Model slots: {len(slots)} in {len(provs)} provinces")

    scraped_2025: dict = {}
    for prov in provs:
        entries = [e for e in catalog if e.province == prov and e.year == YEAR]
        if entries:
            log(f"Crawl {prov} 2025 ({len(entries)} urls)")
            scraped_2025.update(crawl_province_entries(session, entries, zizzs_cache))

    # 回退 2024
    scraped_2024: dict = {}
    still = []
    for prov, track in slots:
        cfg = year_adjust(PROVINCE_BASE_2025[prov], YEAR)
        if str(resolve_track_data(prov, YEAR, track, scraped_2025, cfg, zizzs_cache).get("source", "")).startswith("eol"):
            continue
        still.append((prov, track))
    need_prov = sorted({p for p, _ in still})
    for prov in need_prov:
        entries = [e for e in catalog if e.province == prov and e.year == 2024]
        if entries:
            log(f"Fallback crawl {prov} 2024 ({len(entries)} urls)")
            scraped_2024.update(crawl_province_entries(session, entries, zizzs_cache))

    patched = 0
    for prov, track in slots:
        path = PROVINCE_DIR / f"{prov}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        cfg = year_adjust(PROVINCE_BASE_2025[prov], YEAR)
        payload = resolve_track_data(prov, YEAR, track, scraped_2025, cfg, zizzs_cache)
        if not str(payload.get("source", "")).startswith("eol"):
            payload = resolve_track_data(prov, YEAR, track, scraped_2024, cfg, zizzs_cache)
            if str(payload.get("source", "")).startswith("eol"):
                payload["confidence"] = "validated_structural"
                payload["sourceNote"] = "2024年eol真表回退用于2025参考"
        if str(payload.get("source", "")).startswith("eol"):
            data["years"][str(YEAR)]["tracks"][track] = payload
            path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
            patched += 1
            log(f"  OK {prov} {track} segs={len(payload.get('segments') or [])} src={payload.get('source')}")

    # 3+3 省复制到综合类
    from province_tracks import COMBINED_33_PROVINCES

    for prov in COMBINED_33_PROVINCES:
        path = PROVINCE_DIR / f"{prov}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        yo = data.get("years", {}).get(str(YEAR), {})
        tracks = yo.get("tracks", {})
        best = tracks.get("物理类") or tracks.get("历史类")
        if best and str(best.get("source", "")).startswith("eol"):
            yo["tracks"]["综合类"] = best
            path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
            log(f"  mirror 综合类 <- {prov}")

    log(f"Patched {patched}/{len(slots)}")
    from build_embed import build_embed

    build_embed()


if __name__ == "__main__":
    main()

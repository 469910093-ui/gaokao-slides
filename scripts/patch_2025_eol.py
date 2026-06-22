#!/usr/bin/env python3
"""Patch 2025 model tracks by scraping eol catalog (incl. OCR)."""
from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
from pathlib import Path

import requests

from gaokao_crawl_lib import (
    CatalogEntry,
    detect_track,
    discover_eol_catalog,
    load_zizzs_anchors,
    pick_best_scrape,
    scrape_eol_entry,
    cross_validate,
    maybe_calibrate_segments,
)
from scrape_gaokao_data import (
    PROVINCE_BASE_2025,
    enrich_track_payload,
    year_adjust,
)

ROOT = Path(__file__).resolve().parents[1]
PROVINCE_DIR = ROOT / "data" / "provinces"


def log(msg: str) -> None:
    print(msg, flush=True)


def main() -> None:
    session = requests.Session()
    log("Discovering catalog...")
    catalog = discover_eol_catalog(session)
    (ROOT / "data" / "eol_catalog.json").write_text(
        json.dumps([e.__dict__ for e in catalog], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    zizzs_cache = load_zizzs_anchors(session)

    # Find 2025 model slots
    targets: list[tuple[str, str]] = []
    for path in sorted(PROVINCE_DIR.glob("*.json")):
        prov = path.stem
        data = json.loads(path.read_text(encoding="utf-8"))
        yo = data.get("years", {}).get("2025", {})
        for track in ("物理类", "历史类"):
            td = yo.get("tracks", {}).get(track, {})
            src = str(td.get("source") or "")
            if not src.startswith("eol"):
                targets.append((prov, track))

    log(f"2025 model slots to patch: {len(targets)}")
    provs_needed = sorted({p for p, _ in targets})
    entries = [e for e in catalog if e.year == 2025 and e.province in provs_needed]
    log(f"Catalog entries for those provinces: {len(entries)}")

    bucket: dict[tuple[str, int, str | None], list] = defaultdict(list)
    for i, entry in enumerate(entries, 1):
        result = scrape_eol_entry(session, entry)
        if not result or not result.structural.get("ok"):
            continue
        track = detect_track(result.title) or entry.track
        zizzs = zizzs_cache.get((entry.province, entry.year, track or "物理类"))
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
        if i % 10 == 0:
            log(f"  scraped {i}/{len(entries)}")
        time.sleep(0.2)

    scraped = {k: pick_best_scrape(v) for k, v in bucket.items()}
    log(f"Scraped track keys: {len(scraped)}")

    from scrape_gaokao_data import resolve_track_data, COMBINED_SEGMENT_PROVINCES

    patched = 0
    for prov, track in targets:
        path = PROVINCE_DIR / f"{prov}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        cfg = year_adjust(PROVINCE_BASE_2025[prov], 2025)
        payload = resolve_track_data(prov, 2025, track, scraped, cfg, zizzs_cache)
        src = payload.get("source", "")
        if str(src).startswith("eol"):
            data["years"]["2025"]["tracks"][track] = payload
            path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
            patched += 1
            log(f"  OK {prov} {track} -> {src} segs={len(payload.get('segments') or [])}")
        else:
            log(f"  MISS {prov} {track} still model")

    log(f"Patched {patched}/{len(targets)}")
    from build_embed import build_embed

    build_embed()


if __name__ == "__main__":
    main()

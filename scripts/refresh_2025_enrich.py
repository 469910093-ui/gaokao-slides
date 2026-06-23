#!/usr/bin/env python3
"""Re-scrape 2025 eol catalog and re-apply enrich (fixes rank drift after pipeline changes)."""
from __future__ import annotations

import json
import time
from collections import defaultdict
from pathlib import Path

import requests

from gaokao_crawl_lib import (
    cross_validate,
    detect_track,
    discover_eol_catalog,
    load_zizzs_anchors,
    maybe_calibrate_segments,
    pick_best_scrape,
    scrape_eol_entry,
)
from province_tracks import tracks_for_province
from scrape_gaokao_data import PROVINCE_BASE_2025, PROVINCES, resolve_track_data, year_adjust

ROOT = Path(__file__).resolve().parents[1]
PROVINCE_DIR = ROOT / "data" / "provinces"


def main() -> None:
    session = requests.Session()
    catalog = discover_eol_catalog(session)
    zizzs_cache = load_zizzs_anchors(session)
    entries = [e for e in catalog if e.year == 2025]
    print(f"2025 catalog entries: {len(entries)}")

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
        if i % 15 == 0:
            print(f"  ... {i}/{len(entries)}")
        time.sleep(0.22)

    scraped = {k: pick_best_scrape(v) for k, v in bucket.items()}
    print(f"Scraped keys: {len(scraped)}")

    for prov in PROVINCES:
        path = PROVINCE_DIR / f"{prov}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        cfg = year_adjust(PROVINCE_BASE_2025[prov], 2025)
        yo = data.setdefault("years", {}).setdefault("2025", {
            "batches": {"特招线": cfg["special"], "本科线": cfg["undergrad"]},
            "maxScore": cfg["max"],
            "tracks": {},
        })
        yo["batches"] = {"特招线": cfg["special"], "本科线": cfg["undergrad"]}
        yo["maxScore"] = cfg["max"]
        for track in tracks_for_province(prov, 2025):
            payload = resolve_track_data(prov, 2025, track, scraped, cfg, zizzs_cache)
            yo["tracks"][track] = payload
        path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        print(f"  refreshed {prov}")

    from build_embed import build_embed

    build_embed()
    print("Done.")


if __name__ == "__main__":
    main()

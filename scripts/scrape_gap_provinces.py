#!/usr/bin/env python3
"""对缺表省份全量爬 catalog 并写入 2025。"""
import json
import time
from collections import defaultdict
from pathlib import Path

import requests

from gaokao_crawl_lib import (
    CatalogEntry,
    discover_eol_catalog,
    detect_track,
    scrape_eol_entry,
    cross_validate,
    maybe_calibrate_segments,
    pick_best_scrape,
    load_zizzs_anchors,
)
from scrape_gaokao_data import PROVINCE_BASE_2025, resolve_track_data, year_adjust

TARGETS = ["山西", "新疆", "宁夏", "江西", "贵州", "西藏"]
ROOT = Path(__file__).resolve().parents[1]
PROV_DIR = ROOT / "data" / "provinces"


def main() -> None:
    session = requests.Session()
    catalog = discover_eol_catalog(session)
    zizzs = load_zizzs_anchors(session)
    entries = [e for e in catalog if e.province in TARGETS and e.year >= 2023]
    print(f"entries {len(entries)}", flush=True)
    bucket: dict = defaultdict(list)
    for i, e in enumerate(entries, 1):
        r = scrape_eol_entry(session, e)
        if not r or not r.structural.get("ok"):
            continue
        track = detect_track(r.title) or e.track
        checks, conf, score = cross_validate(r.segments, track, r.anchors, zizzs.get((e.province, e.year, track or "物理类")))
        r.segments, r.total, checks, conf, score = maybe_calibrate_segments(
            r.segments, r.total, track, r.anchors, zizzs.get((e.province, e.year, track or "物理类")), checks, conf, score
        )
        r.cross_checks = checks
        r.confidence = conf
        r.confidence_score = score
        bucket[(e.province, e.year, track)].append(r)
        if i % 10 == 0:
            print(f"  {i}/{len(entries)}", flush=True)
        time.sleep(0.15)
    scraped = {k: pick_best_scrape(v) for k, v in bucket.items()}
    print(f"scraped keys {len(scraped)}", flush=True)
    for prov in TARGETS:
        path = PROV_DIR / f"{prov}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        cfg = year_adjust(PROVINCE_BASE_2025[prov], 2025)
        for track in ("物理类", "历史类"):
            payload = resolve_track_data(prov, 2025, track, scraped, cfg, zizzs)
            if not str(payload.get("source", "")).startswith("eol"):
                payload = resolve_track_data(prov, 2024, track, scraped, cfg, zizzs)
            if not str(payload.get("source", "")).startswith("eol"):
                payload = resolve_track_data(prov, 2023, track, scraped, cfg, zizzs)
            if str(payload.get("source", "")).startswith("eol"):
                data["years"]["2025"]["tracks"][track] = payload
                print(f"OK {prov} {track} {payload['source']} segs={len(payload.get('segments') or [])}", flush=True)
        path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    from build_embed import build_embed
    build_embed()


if __name__ == "__main__":
    main()

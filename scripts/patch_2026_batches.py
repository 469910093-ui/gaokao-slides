#!/usr/bin/env python3
"""将 2026 年各省批次线写入 province JSON，并基于新线生成一分一段估算。"""
from __future__ import annotations

import json
import time
from pathlib import Path

from gaokao_crawl_lib import ScrapeResult
from province_tracks import tracks_for_province
from scrape_gaokao_data import (
    CHSI_BATCH_URL,
    MANIFEST_FILE,
    PROVINCE_DIR,
    PROVINCES,
    YEARS,
    enrich_track_payload,
    province_cfg,
    synthesize_segments,
    track_batches_for_year,
)

YEAR = 2026
SUMMARY_FILE = Path(__file__).resolve().parents[1] / "data" / "batch-summary-2026.json"


def model_track_payload(cfg: dict[str, int], track: str) -> dict:
    segments, total = synthesize_segments(cfg, track)
    fake = ScrapeResult(
        segments=segments,
        total=total,
        source="model",
        url=CHSI_BATCH_URL,
        confidence="model_estimate",
        confidence_score=0.72,
    )
    fake.structural = {"ok": True, "issues": []}
    payload = enrich_track_payload(fake, cfg)
    payload["batchSource"] = "official_2026_chsi"
    return payload


def build_summary() -> dict:
    rows = []
    for prov in PROVINCES:
        path = PROVINCE_DIR / f"{prov}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        yo = data.get("years", {}).get(str(YEAR), {})
        track_batches = yo.get("trackBatches") or {}
        rows.append({
            "province": prov,
            "maxScore": yo.get("maxScore", 750),
            "tracks": track_batches,
            "batchSource": yo.get("batchSource", "official_2026_chsi"),
        })
    return {
        "year": YEAR,
        "source": "阳光高考",
        "sourceUrl": CHSI_BATCH_URL,
        "generatedAt": time.strftime("%Y-%m-%d %H:%M:%S"),
        "provinces": rows,
    }


def main() -> None:
    for prov in PROVINCES:
        path = PROVINCE_DIR / f"{prov}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        track_batches = track_batches_for_year(prov, YEAR)
        default_track = tracks_for_province(prov, YEAR)[0]
        default_cfg = province_cfg(prov, YEAR, default_track)
        default_batches = track_batches.get(default_track) or {
            "特招线": default_cfg["special"],
            "本科线": default_cfg["undergrad"],
        }
        yo: dict = {
            "batches": dict(default_batches),
            "trackBatches": track_batches,
            "maxScore": default_cfg["max"],
            "tracks": {},
            "batchSource": "official_2026_chsi",
            "batchSourceUrl": CHSI_BATCH_URL,
        }
        for track in tracks_for_province(prov, YEAR):
            cfg = province_cfg(prov, YEAR, track)
            yo["tracks"][track] = model_track_payload(cfg, track)
        data.setdefault("years", {})[str(YEAR)] = yo
        path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        tb = track_batches.get(default_track, default_batches)
        print(f"  patched {prov}: 特招线={tb['特招线']} 本科线={tb['本科线']}")

    summary = build_summary()
    SUMMARY_FILE.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {SUMMARY_FILE}")

    manifest = json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))
    manifest["years"] = YEARS
    manifest["meta"]["yearRange"] = [min(YEARS), max(YEARS)]
    manifest["meta"]["generatedAt"] = time.strftime("%Y-%m-%d %H:%M:%S")
    note = (
        "2026 批次线已按阳光高考/各省考试院公布更新（2026-06-26）；"
        "2026 一分一段暂无官方全量表，暂以新批次线锚定的模型估算，正式一分一段公布后请重跑 refresh。"
    )
    base_notes = manifest["meta"].get("notes", "")
    if "2026-06-26" not in base_notes:
        manifest["meta"]["notes"] = f"{base_notes} {note}".strip()
    MANIFEST_FILE.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Updated {MANIFEST_FILE}")

    from build_embed import build_embed

    build_embed()
    print("Done.")


if __name__ == "__main__":
    main()

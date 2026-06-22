#!/usr/bin/env python3
"""Recompute segment counts from cumulative ranks and rebuild gaokao-embed.js."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from gaokao_crawl_lib import (
    SegmentRow,
    normalize_segment_rows,
    percentile_from_cumulative,
    densify_segments,
    smooth_segment_counts,
)  # noqa: E402

PROVINCE_DIR = ROOT / "data" / "provinces"


def fix_segments(segments: list[dict], total: int) -> list[dict]:
    rows = [SegmentRow(s["s"], s.get("n", 0), s.get("c", 0)) for s in segments]
    fixed = normalize_segment_rows(rows)
    fixed = densify_segments(fixed, step=2)
    fixed = smooth_segment_counts(fixed, window=5)
    out = []
    for seg in sorted(fixed, key=lambda x: x.score):
        share = round(seg.count / total * 100, 4) if total else 0
        pct = percentile_from_cumulative(seg.cumulative, seg.count, total)
        out.append({
            "s": seg.score,
            "p": pct,
            "r": share,
            "c": seg.cumulative,
            "n": seg.count,
        })
    return out


def main() -> None:
    count = 0
    for path in sorted(PROVINCE_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        changed = False
        for year_obj in data.get("years", {}).values():
            for track_data in year_obj.get("tracks", {}).values():
                segs = track_data.get("segments") or []
                if not segs:
                    continue
                total = track_data.get("totalCandidates") or max((s.get("c", 0) for s in segs), default=0)
                new_segs = fix_segments(segs, total)
                if new_segs != segs:
                    track_data["segments"] = new_segs
                    changed = True
                    count += 1
        if changed:
            path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
            print(f"fixed {path.name}")

    print(f"updated {count} track payloads")
    from build_embed import build_embed

    build_embed()


if __name__ == "__main__":
    main()

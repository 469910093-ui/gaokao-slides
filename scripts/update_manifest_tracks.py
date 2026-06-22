#!/usr/bin/env python3
"""Add provinceTracks to manifest.json without full rescrape."""
import json
from pathlib import Path

from province_tracks import TRACK_LABELS, tracks_for_province

ROOT = Path(__file__).resolve().parents[1]
manifest_path = ROOT / "data" / "manifest.json"
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
provinces = manifest.get("provinces") or []
manifest["provinceTracks"] = {
    p: [{"value": t, "label": TRACK_LABELS.get(t, t)} for t in tracks_for_province(p, 2025)]
    for p in provinces
}
manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
print("Updated provinceTracks for", len(provinces), "provinces")

#!/usr/bin/env python3
"""Sync schools/hotMajors from scrape constants into manifest.json and rebuild embed."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from scrape_gaokao_data import HOT_MAJORS, SCHOOLS, TIER_PERCENTILE  # noqa: E402

MANIFEST = ROOT / "data" / "manifest.json"


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    schools = [{**s, "minPercentile": TIER_PERCENTILE[s["tier"]]} for s in SCHOOLS]
    manifest["schools"] = schools
    manifest["hotMajors"] = HOT_MAJORS
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"synced {len(schools)} schools, {len(HOT_MAJORS)} majors")

    from build_embed import build_embed

    build_embed()


if __name__ == "__main__":
    main()

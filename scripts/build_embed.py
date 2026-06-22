#!/usr/bin/env python3
"""Bundle manifest + province JSON into a single JS file for file:// usage."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
MANIFEST_FILE = DATA_DIR / "manifest.json"
PROVINCE_DIR = DATA_DIR / "provinces"
CAREER_FILE = DATA_DIR / "career_sandbox.json"
EMBED_FILE = DATA_DIR / "gaokao-embed.js"
CAREER_EMBED_FILE = DATA_DIR / "career-embed.js"


def build_embed() -> Path:
    manifest = json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))
    provinces: dict[str, object] = {}
    for path in sorted(PROVINCE_DIR.glob("*.json")):
        provinces[path.stem] = json.loads(path.read_text(encoding="utf-8"))

    payload = {"manifest": manifest, "provinces": provinces}
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    EMBED_FILE.write_text(
        "// Auto-generated — do not edit. Run: python scripts/build_embed.py\n"
        f"window.GAOKAO_EMBED={body};\n",
        encoding="utf-8",
    )
    size_mb = EMBED_FILE.stat().st_size / 1024 / 1024
    print(f"Wrote {EMBED_FILE} ({size_mb:.2f} MB, {len(provinces)} provinces)")

    if CAREER_FILE.exists():
        career = json.loads(CAREER_FILE.read_text(encoding="utf-8"))
        cbody = json.dumps(career, ensure_ascii=False, separators=(",", ":"))
        CAREER_EMBED_FILE.write_text(
            "// Auto-generated career sandbox embed\n"
            f"window.CAREER_EMBED={cbody};\n",
            encoding="utf-8",
        )
        print(f"Wrote {CAREER_EMBED_FILE} ({CAREER_EMBED_FILE.stat().st_size / 1024:.1f} KB)")
    return EMBED_FILE


if __name__ == "__main__":
    build_embed()

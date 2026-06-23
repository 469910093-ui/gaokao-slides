#!/usr/bin/env python3
"""Build nationwide school name index for意向大学 search (admission + manifest + vocational)."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
MANIFEST = DATA / "manifest.json"
SHARD_DIR = DATA / "reference" / "gaokao_cn" / "admission_by_province"
VOCATIONAL = DATA / "schools_vocational.json"
OUT_JSON = DATA / "schools_search_index.json"
OUT_EMBED = DATA / "schools-search-embed.js"


def collect_names() -> dict[str, set[str]]:
    sources: dict[str, set[str]] = {
        "manifest": set(),
        "admission": set(),
        "vocational": set(),
    }

    if MANIFEST.exists():
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        sources["manifest"] = {s["name"] for s in manifest.get("schools", []) if s.get("name")}

    if SHARD_DIR.exists():
        for path in SHARD_DIR.glob("*.json"):
            shard = json.loads(path.read_text(encoding="utf-8"))
            for track_map in (shard.get("tracks") or {}).values():
                if isinstance(track_map, dict):
                    sources["admission"].update(track_map.keys())

    if VOCATIONAL.exists():
        voc = json.loads(VOCATIONAL.read_text(encoding="utf-8"))
        sources["vocational"] = {s["name"] for s in voc.get("schools", []) if s.get("name")}

    return sources


def build() -> Path:
    sources = collect_names()
    all_names = sorted(sources["manifest"] | sources["admission"] | sources["vocational"])

    schools = []
    for name in all_names:
        src = []
        if name in sources["manifest"]:
            src.append("manifest")
        if name in sources["admission"]:
            src.append("admission")
        if name in sources["vocational"]:
            src.append("vocational")
        schools.append({"name": name, "sources": src})

    payload = {
        "meta": {
            "generatedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total": len(schools),
            "manifestCount": len(sources["manifest"]),
            "admissionUniqueCount": len(sources["admission"]),
            "vocationalCount": len(sources["vocational"]),
            "notes": (
                "全国校名检索索引：投档归档院校 + 推荐清单 + 高职库并集。"
                "不含全国所有高校；未出现在任何数据源中的院校需手动核对官方名称。"
            ),
        },
        "schools": schools,
    }
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    OUT_EMBED.write_text(
        "// Auto-generated — run: python scripts/build_school_search_index.py\n"
        f"window.SCHOOLS_SEARCH_INDEX={body};\n",
        encoding="utf-8",
    )
    print(
        f"Wrote {OUT_JSON.name}: {len(schools)} schools "
        f"(manifest {len(sources['manifest'])}, admission {len(sources['admission'])}, "
        f"vocational {len(sources['vocational'])})"
    )
    print(f"Wrote {OUT_EMBED.name} ({OUT_EMBED.stat().st_size / 1024:.1f} KB)")
    return OUT_JSON


if __name__ == "__main__":
    build()

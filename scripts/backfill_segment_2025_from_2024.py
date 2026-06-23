#!/usr/bin/env python3
"""2025 一分一段为 model 时，用同省 2024 已验收 eol 真表回退（仅升级 confidence）。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROVINCE_DIR = ROOT / "data" / "provinces"
sys.path.insert(0, str(ROOT / "scripts"))

from province_tracks import COMBINED_33_PROVINCES, tracks_for_province  # noqa: E402

CONF_RANK = {
    "verified": 0,
    "verified_multi_source": 0,
    "partial": 1,
    "partially_verified": 1,
    "validated_structural": 2,
    "scraped": 3,
    "structural": 3,
    "failed_validation": 4,
    "conflict": 4,
    "model_estimate": 5,
    "model": 5,
    "no_track": 9,
}


def better(conf: str) -> bool:
    return CONF_RANK.get(conf, 9) <= 2


def main() -> None:
    upgraded = 0
    for path in sorted(PROVINCE_DIR.glob("*.json")):
        prov = path.stem
        data = json.loads(path.read_text(encoding="utf-8"))
        y24 = data.get("years", {}).get("2024", {})
        y25 = data.get("years", {}).get("2025")
        if not y25 or not y24:
            continue
        t24 = y24.get("tracks", {})
        t25 = y25.setdefault("tracks", {})
        changed = False
        for track in tracks_for_province(prov, 2025):
            cur = t25.get(track)
            if not cur:
                continue
            cur_conf = cur.get("confidence") or "model_estimate"
            if CONF_RANK.get(cur_conf, 9) <= 2:
                continue
            src = t24.get(track)
            if not src:
                if track == "综合类":
                    src = t24.get("物理类") or t24.get("历史类")
            if not src:
                continue
            src_conf = src.get("confidence") or "model_estimate"
            src_src = str(src.get("source") or "")
            if not src_src.startswith("eol") and not better(src_conf):
                continue
            if CONF_RANK.get(src_conf, 9) >= CONF_RANK.get(cur_conf, 9):
                continue
            payload = json.loads(json.dumps(src, ensure_ascii=False))
            payload["sourceNote"] = "2024年一分一段真表回退用于2025参考"
            if src_conf in ("verified", "verified_multi_source", "partial", "partially_verified"):
                payload["confidence"] = src_conf
            else:
                payload["confidence"] = "validated_structural"
            t25[track] = payload
            upgraded += 1
            changed = True
            print(f"  {prov} {track}: {cur_conf} -> {payload['confidence']}")

        if prov in COMBINED_33_PROVINCES:
            best = t25.get("物理类") or t25.get("历史类") or t25.get("综合类")
            if best and (best.get("confidence") or "") in (
                "verified", "verified_multi_source", "partial", "validated_structural",
            ):
                t25["综合类"] = best
                changed = True

        if changed:
            path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")

    print(f"Upgraded {upgraded} province-track slots")
    from build_embed import build_embed

    build_embed()


if __name__ == "__main__":
    main()

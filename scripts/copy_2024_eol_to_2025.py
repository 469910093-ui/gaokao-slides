#!/usr/bin/env python3
"""将已有 2024 eol 真表复制到 2025 缺表轨道（优于 model 估算）。"""
import json
from pathlib import Path

from province_tracks import tracks_for_province

ROOT = Path(__file__).resolve().parents[1]
PROV_DIR = ROOT / "data" / "provinces"


def main() -> None:
    copied = 0
    for path in sorted(PROV_DIR.glob("*.json")):
        prov = path.stem
        data = json.loads(path.read_text(encoding="utf-8"))
        y24 = data.get("years", {}).get("2024", {}).get("tracks", {})
        y25 = data.setdefault("years", {}).setdefault("2025", {})
        t25 = y25.setdefault("tracks", {})
        for track in tracks_for_province(prov, 2025):
            cur = t25.get(track, {})
            src = str(cur.get("source") or "")
            if src.startswith("eol"):
                continue
            # 综合类可复用物/历或 2024 综合
            src_data = y24.get(track)
            if not src_data or not str(src_data.get("source", "")).startswith("eol"):
                if track == "综合类":
                    src_data = y24.get("物理类") or y24.get("历史类")
                else:
                    src_data = y24.get(track)
            if not src_data or not str(src_data.get("source", "")).startswith("eol"):
                continue
            payload = dict(src_data)
            payload["sourceNote"] = "2024年eol真表用于2025参考（官方2025表暂未获取）"
            t25[track] = payload
            copied += 1
            print(f"  {prov} {track} <- 2024 eol ({len(payload.get('segments') or [])} segs)")
        path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    # 3+1+2 省：2025 物/历仍 model 时，也尝试 2024 同轨
    for path in sorted(PROV_DIR.glob("*.json")):
        prov = path.stem
        if prov in {"北京", "天津", "上海", "浙江", "山东", "海南"}:
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        y24 = data.get("years", {}).get("2024", {}).get("tracks", {})
        t25 = data.get("years", {}).get("2025", {}).get("tracks", {})
        if not t25:
            continue
        changed = False
        for track in ("物理类", "历史类"):
            cur = t25.get(track, {})
            if str(cur.get("source", "")).startswith("eol"):
                continue
            src_data = y24.get(track)
            if src_data and str(src_data.get("source", "")).startswith("eol"):
                payload = dict(src_data)
                payload["sourceNote"] = "2024年eol真表用于2025参考"
                data["years"]["2025"]["tracks"][track] = payload
                changed = True
                copied += 1
                print(f"  {prov} {track} <- 2024 eol")
        if changed:
            path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    print(f"Copied {copied} tracks")
    from build_embed import build_embed

    build_embed()


if __name__ == "__main__":
    main()

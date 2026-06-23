"""一分一段表：位次 → 分数换算（用于仅公布位次的省份官方投档表）。"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROVINCE_JSON = ROOT / "data" / "provinces"


@lru_cache(maxsize=64)
def _load_province(name: str) -> dict:
    path = PROVINCE_JSON / f"{name}.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _pick_track(tracks: dict, preferred: str | None) -> str | None:
    if not tracks:
        return None
    if preferred and preferred in tracks:
        return preferred
    for key in ("综合类", "物理类", "历史类"):
        if key in tracks:
            return key
    return next(iter(tracks))


def rank_to_score(
    province: str,
    year: int,
    rank: int,
    track: str | None = None,
) -> int | None:
    """根据累计位次 c 反查对应分数 s（segments 按分数降序）。"""
    if rank is None or rank <= 0:
        return None
    data = _load_province(province)
    year_data = data.get("years", {}).get(str(year)) or data.get("years", {}).get(year)
    if not year_data:
        return None
    tracks = year_data.get("tracks", {})
    track_key = _pick_track(tracks, track)
    if not track_key:
        return None
    segments = tracks[track_key].get("segments", [])
    if not segments:
        return None
    for seg in segments:
        cum = seg.get("c")
        if cum is not None and cum >= rank:
            return int(seg["s"])
    # 位次超出表末：取最低分
    if segments:
        return int(segments[-1]["s"])
    return None

"""各省高考科类体系：3+3 综合 / 3+1+2 物历 / 老高考文理。"""
from __future__ import annotations

# 3+3 综合改革（一分一段通常不分文理）
COMBINED_33_PROVINCES = frozenset({
    "北京", "天津", "上海", "浙江", "山东", "海南",
})

# 3+1+2 及已并轨为新高考科类名「物理类/历史类」的省份（默认）
# 老高考仍用「理科/文科」口径的省份（新疆 transitional）
ARTS_SCIENCE_PROVINCES = frozenset({
    "新疆",
})

TRACK_LABELS: dict[str, str] = {
    "综合类": "综合类（不分文理）",
    "物理类": "物理类 / 理科",
    "历史类": "历史类 / 文科",
    "理科": "理科",
    "文科": "文科",
}


def tracks_for_province(province: str, year: int = 2025) -> list[str]:
    """返回某省某年应展示的科类轨道键名。"""
    if province in COMBINED_33_PROVINCES:
        return ["综合类"]
    if province in ARTS_SCIENCE_PROVINCES and year <= 2024:
        return ["理科", "文科"]
    return ["物理类", "历史类"]


def legacy_track_keys(province: str, year: int = 2025) -> list[str]:
    """数据文件中可能存在的兼容键（含旧键名）。"""
    primary = tracks_for_province(province, year)
    extra: list[str] = []
    if province in COMBINED_33_PROVINCES:
        extra = ["物理类", "历史类"]
    elif province in ARTS_SCIENCE_PROVINCES:
        extra = ["物理类", "历史类"]
    out: list[str] = []
    for t in primary + extra:
        if t not in out:
            out.append(t)
    return out


def resolve_track_data_key(province: str, year: int, ui_track: str) -> str:
    """UI 科类 -> JSON tracks 内实际键（兼容旧数据）。"""
    year_obj_tracks = None  # caller passes tracks dict when needed
    _ = year_obj_tracks
    if ui_track in ("物理类", "历史类") and province in COMBINED_33_PROVINCES:
        return "综合类"
    if ui_track == "理科" and province in ARTS_SCIENCE_PROVINCES:
        return "理科"
    if ui_track == "文科" and province in ARTS_SCIENCE_PROVINCES:
        return "文科"
    return ui_track


def pick_track_payload(tracks: dict, province: str, year: int, ui_track: str) -> dict | None:
    """从 years[year].tracks 取当前科类数据，含旧键回退。"""
    if not tracks:
        return None
    key = resolve_track_data_key(province, year, ui_track)
    if key in tracks:
        return tracks[key]
    if ui_track in tracks:
        return tracks[ui_track]
    if province in COMBINED_33_PROVINCES:
        for alt in ("综合类", "物理类", "历史类"):
            if alt in tracks:
                return tracks[alt]
    return None


def major_match_tracks(ui_track: str, province: str) -> list[str]:
    """专业推荐时视为可选的科类列表。"""
    if ui_track == "综合类" or (province in COMBINED_33_PROVINCES and ui_track in ("物理类", "历史类", "综合类")):
        return ["物理类", "历史类", "综合类"]
    if ui_track == "理科":
        return ["物理类", "理科"]
    if ui_track == "文科":
        return ["历史类", "文科"]
    return [ui_track]


def scrape_output_tracks(province: str, year: int) -> list[str]:
    """爬取写入 province JSON 时应生成的轨道键。"""
    primary = tracks_for_province(province, year)
    if province in COMBINED_33_PROVINCES:
        return primary
    return primary

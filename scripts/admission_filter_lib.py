"""投档行清洗：仅保留本省主批次、合理分数区间，对齐省考试院/阳光高考口径。"""

from __future__ import annotations

import re
from typing import Any

from province_tracks import COMBINED_33_PROVINCES

# 各省普通本科主批次（与省考试院公布口径一致）
PRIMARY_UNDERGRAD_BATCH: dict[str, str] = {
    "北京": "本科批",
    "天津": "本科批",
    "上海": "本科批",
    "浙江": "平行录取一段",
    "山东": "普通类一段",
    "海南": "本科批",
}

# 非本省批次名（掌上高考 API 常混入外省投档行）
FOREIGN_BATCH_MARKERS = frozenset({
    "平行录取一段",
    "平行录取二段",
    "普通类一段",
    "普通类二段",
    "普通类平行录取",
})

OFFICIAL_REFERENCES = {
    "chsi": {
        "name": "阳光高考",
        "url": "https://gaokao.chsi.com.cn/",
    },
    "note": "投档分经本省主批次与分数区间校验；填报请以各省招生考试院、院校招生网公布为准。",
}

PROVINCE_EXAM_PORTALS: dict[str, str] = {
    "北京": "https://www.bjeea.cn/",
    "天津": "https://www.zhaokao.net/",
    "河北": "http://www.hebeea.edu.cn/",
    "山西": "http://www.sxkszx.cn/",
    "内蒙古": "https://www.nm.zsks.cn/",
    "辽宁": "https://www.lnzsks.com/",
    "吉林": "https://www.jleea.com.cn/",
    "黑龙江": "https://www.lzk.hl.cn/",
    "上海": "https://www.shmeea.edu.cn/",
    "江苏": "https://www.jseea.cn/",
    "浙江": "https://www.zjzs.net/",
    "安徽": "https://www.ahzsks.cn/",
    "福建": "https://www.eeafj.cn/",
    "江西": "http://www.jxeea.cn/",
    "山东": "http://www.sdzk.cn/",
    "河南": "http://www.haeea.cn/",
    "湖北": "http://www.hbea.edu.cn/",
    "湖南": "https://www.hneeb.cn/",
    "广东": "https://eea.gd.gov.cn/",
    "广西": "https://www.gxeea.cn/",
    "海南": "https://ea.hainan.gov.cn/",
    "重庆": "https://www.cqksy.cn/",
    "四川": "https://www.sceea.cn/",
    "贵州": "http://zsksy.guizhou.gov.cn/",
    "云南": "https://www.ynzs.cn/",
    "西藏": "http://zsks.edu.xizang.gov.cn/",
    "陕西": "https://www.sneea.cn/",
    "甘肃": "https://www.ganseea.cn/",
    "青海": "http://www.qhjyks.com/",
    "宁夏": "https://www.nxjyks.cn/",
    "新疆": "https://www.xjzk.gov.cn/",
}

SCORE_MIN = 250
SCORE_MAX = 750


def primary_undergrad_batch(province: str) -> str:
    return PRIMARY_UNDERGRAD_BATCH.get(province, "本科批")


def track_key_from_filename(fname: str) -> str:
    m = re.match(r"admissions_.+_\d+_(.+)\.json$", fname)
    key = m.group(1) if m else "综合类"
    if key in ("综合", "综合类"):
        return "综合类"
    return key


def normalize_track(row_track: str | None, file_track: str) -> str:
    t = row_track or file_track
    if file_track in ("综合", "综合类") or t in ("综合", "综合类"):
        return "综合类"
    if "历史" in str(t) or "文科" in str(t):
        return "历史类"
    if "物理" in str(t) or "理科" in str(t):
        return "物理类"
    return file_track


def parse_min_score(raw: Any) -> int | None:
    if raw in (None, "", "-"):
        return None
    try:
        v = int(float(str(raw).strip()))
        return v if v > 0 else None
    except (TypeError, ValueError):
        return None


def is_plausible_score(score: int, province: str) -> bool:
    """剔除 API 中 >750 的异常投档分（如混批/字段错位）。"""
    if score < SCORE_MIN or score > SCORE_MAX:
        return False
    if province in COMBINED_33_PROVINCES and score > 720:
        # 3+3 省满分 750，极少数专业组可略高于 700，>720 视为脏数据
        return False
    return True


def row_is_undergrad_primary(province: str, row: dict[str, Any]) -> bool:
    batch = str(row.get("batch") or "").strip()
    if not batch:
        return False
    primary = primary_undergrad_batch(province)
    if batch != primary:
        return False
    if batch in FOREIGN_BATCH_MARKERS and province not in PRIMARY_UNDERGRAD_BATCH:
        return False
    level = str(row.get("level") or "")
    batch_name = batch
    if "专科" in level or "专科" in batch_name:
        return False
    return True


def filter_admission_row(province: str, row: dict[str, Any]) -> bool:
    if (row.get("province") or "").strip() != province:
        return False
    if not row_is_undergrad_primary(province, row):
        return False
    score = parse_min_score(row.get("minScore"))
    if score is None or not is_plausible_score(score, province):
        return False
    return True

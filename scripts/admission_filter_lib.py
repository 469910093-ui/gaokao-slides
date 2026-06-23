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
    "四川": "本科一批",
    "河南": "本科批",
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
    "河南": "https://gaokao.haedu.cn/",
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

# 非普通志愿计划（专项/定向/合作等）— 不进推荐索引
SPECIAL_PLAN_MARKERS = frozenset({
    "国家专项",
    "地方专项",
    "高校专项",
    "定向",
    "预科",
    "民族班",
    "少数民族",
    "中外合作",
    "校企合作",
    "护理",
    "单列",
    "征集志愿",
    "蒙授",
    "边防",
    "内地班",
    "援疆",
    "援藏",
})

C9_SCHOOLS = frozenset({
    "北京大学",
    "清华大学",
    "复旦大学",
    "上海交通大学",
    "浙江大学",
    "南京大学",
    "中国科学技术大学",
    "哈尔滨工业大学",
    "西安交通大学",
})

# 同年同校普通组内：最低分与次低分差距 ≥ 此值则剔除最低（防漏标专项）
REGULAR_FLOOR_OUTLIER_GAP = 20
# 无标注组若低于已标注普通组最低分超过此值，视为专项污染
REGULAR_UNLABELED_BELOW_LABELED = 15


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


def is_plausible_score(score: int, province: str, row: dict[str, Any] | None = None) -> bool:
    """剔除 API 中 >750 的异常投档分（如混批/字段错位）。"""
    if score < SCORE_MIN or score > SCORE_MAX:
        return False
    if province in COMBINED_33_PROVINCES and score > 720:
        # 官方仅公布位次、由一分一段换算的分可能 >720（如山东），保留
        if row and row.get("minRank") and row.get("source") == "province_exam_portal_direct":
            return True
        # 3+3 省掌上高考 API 偶有 >720 脏数据（字段错位/外省批）
        return False
    return True


def row_is_undergrad_primary(province: str, row: dict[str, Any]) -> bool:
    batch = str(row.get("batch") or "").strip()
    if not batch:
        return False
    primary = primary_undergrad_batch(province)
    if province == "河南":
        # 2024 及以前为本科一批；2025 年起合并为本科批（datacenter pc=1）
        if batch not in (primary, "本科一批") or "二批" in batch:
            return False
    elif province == "陕西":
        allowed = {primary, "本科一批", "本科二批", "本科批次", "本科批"}
        if batch not in allowed or "专科" in batch:
            return False
    elif batch != primary:
        return False
    if batch in FOREIGN_BATCH_MARKERS and province not in PRIMARY_UNDERGRAD_BATCH:
        return False
    level = str(row.get("level") or "")
    batch_name = batch
    if "专科" in level or "专科" in batch_name:
        return False
    return True


def admission_row_text(row: dict[str, Any]) -> str:
    return " ".join(
        str(row.get(k) or "")
        for k in ("groupInfo", "groupName", "batch", "schoolName", "level")
    )


def row_is_special_plan(row: dict[str, Any]) -> bool:
    text = admission_row_text(row)
    return any(m in text for m in SPECIAL_PLAN_MARKERS)


def drop_low_outliers(scores: list[int], gap: int = REGULAR_FLOOR_OUTLIER_GAP) -> list[int]:
    """剔除同年同校普通组内的极低值（多为漏标专项）。"""
    vals = sorted(scores)
    while len(vals) >= 2 and vals[1] - vals[0] >= gap:
        vals.pop(0)
    return vals


def regular_floor_from_rows(rows: list[dict[str, Any]]) -> int | None:
    """同年同校：普通专业组最低投档分（剔除专项与极低值）。"""
    labeled: list[int] = []
    unlabeled: list[int] = []
    for row in rows:
        if row_is_special_plan(row):
            continue
        score = parse_min_score(row.get("minScore"))
        if score is None:
            continue
        info = str(row.get("groupInfo") or row.get("groupName") or "").strip()
        if info:
            labeled.append(score)
        else:
            unlabeled.append(score)

    if labeled:
        candidates = drop_low_outliers(labeled)
        if not candidates:
            return None
        floor = min(candidates)
        if unlabeled:
            unl = drop_low_outliers(unlabeled)
            if unl:
                low_unl = min(unl)
                if floor - low_unl <= REGULAR_UNLABELED_BELOW_LABELED:
                    floor = min(floor, low_unl)
        return floor

    candidates = drop_low_outliers(unlabeled)
    return min(candidates) if candidates else None


def filter_admission_row(province: str, row: dict[str, Any]) -> bool:
    if (row.get("province") or "").strip() != province:
        return False
    if not row_is_undergrad_primary(province, row):
        return False
    score = parse_min_score(row.get("minScore"))
    if score is None or not is_plausible_score(score, province, row):
        return False
    return True


def filter_regular_admission_row(province: str, row: dict[str, Any]) -> bool:
    """推荐索引用：主批次 + 非专项 + 合理分数。"""
    if not filter_admission_row(province, row):
        return False
    if row_is_special_plan(row):
        return False
    return True


def recommend_floor_from_entry(entry: dict[str, Any]) -> int | None:
    """推荐算法使用的普通批参考分（优先最近一年）。"""
    latest = entry.get("latestFloor")
    if latest is not None:
        return int(latest)
    years = entry.get("yearsRegular") or entry.get("years")
    if years:
        vals = [int(v) for v in years.values()]
        return round(sum(vals) / len(vals))
    legacy = entry.get("avgMin3y")
    return int(legacy) if legacy is not None else None


def parse_admission_file_key(fname: str) -> tuple[str, int, str] | None:
    """(省, 年, 归一化科类) — 用于同键多文件去重。"""
    m = re.match(r"admissions_(.+)_(\d{4})_(.+?)(?:_official)?\.json$", fname)
    if not m:
        return None
    province, year_s, _raw_track = m.group(1), m.group(2), m.group(3)
    return province, int(year_s), track_key_from_filename(fname.replace("_official", ""))


def admission_file_priority(fname: str) -> tuple[int, int]:
    """同省同年同科类时优先 official > _综合.json > _综合类.json。"""
    if "_official.json" in fname:
        return (0, 0)
    if fname.endswith("_综合.json"):
        return (1, 0)
    if fname.endswith("_综合类.json"):
        return (2, 0)
    return (3, 0)


def select_admission_archive_files(ref_dir) -> list:
    """每个 (省, 年, 科类) 只保留一份归档，避免旧文件拉低 floor。"""
    from pathlib import Path

    ref = Path(ref_dir)
    chosen: dict[tuple[str, int, str], object] = {}
    for path in sorted(ref.glob("admissions_*.json")):
        key = parse_admission_file_key(path.name)
        if key is None:
            continue
        prev = chosen.get(key)
        if prev is None or admission_file_priority(path.name) < admission_file_priority(prev.name):
            chosen[key] = path
    return sorted(chosen.values(), key=lambda p: p.name)


def select_official_archive_files(ref_dir) -> list:
    """推荐索引仅使用各省考试院 _official.json。"""
    from pathlib import Path

    ref = Path(ref_dir)
    chosen: dict[tuple[str, int, str], object] = {}
    for path in sorted(ref.glob("admissions_*_official.json")):
        key = parse_admission_file_key(path.name)
        if key is None:
            continue
        chosen[key] = path
    return sorted(chosen.values(), key=lambda p: p.name)


def official_provinces_in_ref(ref_dir) -> set[str]:
    from pathlib import Path

    out: set[str] = set()
    for path in Path(ref_dir).glob("admissions_*_official.json"):
        key = parse_admission_file_key(path.name)
        if key:
            out.add(key[0])
    return out

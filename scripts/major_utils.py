# -*- coding: utf-8 -*-
"""Shared helpers for MOE major catalog build pipeline."""

from __future__ import annotations

import re
from typing import Any

# EOL level2_name -> 简化学科门类
LEVEL2_DISCIPLINE: dict[str, str] = {
    "哲学": "文科",
    "经济学": "商科",
    "法学": "文科",
    "教育学": "文科",
    "文学": "文科",
    "历史学": "文科",
    "理学": "理科",
    "工学": "工科",
    "农学": "理科",
    "医学": "医科",
    "管理学": "商科",
    "艺术学": "艺术",
    "交叉学科": "工科",
}

# 物理类为主 / 历史类为主 / 双轨
LEVEL2_SUBJECTS: dict[str, list[str]] = {
    "哲学": ["历史类"],
    "经济学": ["物理类", "历史类"],
    "法学": ["历史类"],
    "教育学": ["历史类"],
    "文学": ["历史类"],
    "历史学": ["历史类"],
    "理学": ["物理类"],
    "工学": ["物理类"],
    "农学": ["物理类"],
    "医学": ["物理类", "历史类"],
    "管理学": ["历史类"],
    "艺术学": ["历史类"],
    "交叉学科": ["物理类", "历史类"],
}

# 高职大类（EOL level2_name 可能是「装备制造大类」等）
VOCATIONAL_PHYSICS_HINTS = (
    "装备", "电子", "信息", "计算机", "机械", "建筑", "土木", "交通", "能源",
    "化工", "材料", "汽车", "航空", "船舶", "水利", "测绘", "公安", "医学",
    "生物", "农业", "林业", "畜牧", "渔业", "资源", "环境", "轻工", "纺织",
)
VOCATIONAL_HISTORY_HINTS = (
    "财经", "商贸", "旅游", "文化", "艺术", "传媒", "教育", "体育", "公共",
    "社会", "民政", "法律", "文秘", "语言", "新闻",
)

TIER_ORDER = ["C9", "985", "211", "双一流", "一本", "二本", "专科"]

# 学科门类 -> 默认人社部职业中类编码（middle 字段，如 2-02）
DISCIPLINE_OCCUPATION_MIDDLE: dict[str, list[str]] = {
    "工科": ["2-02", "2-06", "2-04"],
    "理科": ["2-01", "2-02"],
    "医科": ["2-05", "2-07"],
    "文科": ["2-08", "2-09", "2-01"],
    "商科": ["2-06", "3-01", "2-07"],
    "艺术": ["2-09", "4-08", "2-14"],
}

LEVEL2_OCCUPATION_MIDDLE: dict[str, list[str]] = {
    "哲学": ["2-01"],
    "经济学": ["2-06", "2-07"],
    "法学": ["2-08", "3-01"],
    "教育学": ["2-08", "2-09"],
    "文学": ["2-08", "2-09"],
    "历史学": ["2-01", "2-08"],
    "理学": ["2-01", "2-02"],
    "工学": ["2-02", "2-06"],
    "农学": ["2-03", "5-05"],
    "医学": ["2-05", "2-07"],
    "管理学": ["2-06", "3-01"],
    "艺术学": ["2-09", "4-08"],
}

VOCATIONAL_GATE_OCCUPATION_MIDDLE: dict[str, list[str]] = {
    "农林牧渔": ["5-05", "2-03"],
    "资源环境与安全": ["2-02", "2-28"],
    "能源动力与材料": ["2-02", "6-31"],
    "土木建筑": ["2-02", "6-29"],
    "水利": ["2-02", "5-05"],
    "装备制造": ["2-02", "6-31"],
    "生物与化工": ["2-02", "6-11"],
    "轻工纺织": ["2-02", "6-23"],
    "食品药品与粮食": ["2-02", "2-05"],
    "交通运输": ["2-02", "4-02"],
    "电子与信息": ["2-02", "2-10"],
    "医药卫生": ["2-05", "2-07"],
    "财经商贸": ["2-06", "3-01"],
    "旅游": ["4-07", "4-03"],
    "文化艺术": ["2-09", "4-08"],
    "新闻传播": ["2-09", "2-08"],
    "教育与体育": ["2-08", "2-09"],
    "公安与司法": ["3-02", "2-08"],
    "公共管理与服务": ["3-01", "3-03"],
}


def normalize_major_name(name: str) -> str:
    return re.sub(r"\s+", "", (name or "").strip())


def infer_discipline(level2_name: str, level1_name: str = "") -> str:
    l2 = (level2_name or "").strip()
    if l2 in LEVEL2_DISCIPLINE:
        return LEVEL2_DISCIPLINE[l2]
    if "医" in l2:
        return "医科"
    if any(k in l2 for k in ("工", "制造", "装备", "电子", "信息", "计算机")):
        return "工科"
    if any(k in l2 for k in ("文", "语言", "新闻", "教育", "法律")):
        return "文科"
    if any(k in l2 for k in ("财", "商", "管理", "经济")):
        return "商科"
    if "艺术" in l2 or "传媒" in l2:
        return "艺术"
    if "本科(职业)" in (level1_name or ""):
        return "工科"
    return "工科" if "专科" in (level1_name or "") else "商科"


def infer_subjects(level2_name: str, level1_name: str = "") -> list[str]:
    l2 = (level2_name or "").strip()
    if l2 in LEVEL2_SUBJECTS:
        return list(LEVEL2_SUBJECTS[l2])
    if "专科" in (level1_name or "") or "高职" in (level1_name or ""):
        phys = any(h in l2 for h in VOCATIONAL_PHYSICS_HINTS)
        hist = any(h in l2 for h in VOCATIONAL_HISTORY_HINTS)
        if phys and not hist:
            return ["物理类"]
        if hist and not phys:
            return ["历史类"]
        return ["物理类", "历史类"]
    if "本科(职业)" in (level1_name or ""):
        return ["物理类", "历史类"]
    return ["物理类", "历史类"]


def infer_tier(level1_name: str, salaryavg: int | None, pct: float | None) -> str:
    l1 = level1_name or ""
    if "专科" in l1 or "高职" in l1:
        return "专科"
    if pct is None:
        return "二本" if "职业" in l1 else "一本"
    if pct >= 0.92:
        return "985"
    if pct >= 0.82:
        return "211"
    if pct >= 0.65:
        return "一本"
    if pct >= 0.45:
        return "二本"
    return "专科"


def salary_percentile(salaryavg: int | None, all_salaries: list[int]) -> float | None:
    if salaryavg is None or not all_salaries:
        return None
    below = sum(1 for s in all_salaries if s <= salaryavg)
    return below / len(all_salaries)


def infer_manual_trend(
    view_month: int | None,
    view_pct: float | None,
    salary_pct: float | None,
) -> int:
    """无人工研判时，用搜索热度 + 薪资分位估算基础趋势分。"""
    vm = view_pct if view_pct is not None else 0.5
    sp = salary_pct if salary_pct is not None else 0.5
    score = 42 + vm * 38 + sp * 20
    return max(35, min(88, int(round(score))))


def occupation_keywords(name: str, hightitle: str = "") -> list[str]:
    base = normalize_major_name(name)
    parts = [base, normalize_major_name(hightitle)]
    for suffix in ("与技术", "技术", "工程", "科学", "学", "类", "方向"):
        if base.endswith(suffix) and len(base) > len(suffix) + 1:
            parts.append(base[: -len(suffix)])
    out: list[str] = []
    for p in parts:
        if len(p) >= 2 and p not in out:
            out.append(p)
    return out


def match_occupations(
    name: str,
    discipline: str,
    occupations: list[dict[str, Any]],
    middle_lookup: dict[str, str],
    hightitle: str = "",
    level2_name: str = "",
    limit: int = 3,
) -> list[dict[str, str]]:
    """按专业名关键词 + 学科默认中类，匹配人社部职业大典细类编码。"""
    keywords = occupation_keywords(name, hightitle)
    scored: list[tuple[int, dict[str, Any]]] = []
    for occ in occupations:
        oname = occ.get("name") or ""
        score = 0
        for kw in keywords:
            if len(kw) >= 2 and kw in oname:
                score += len(kw) * 2
            if len(kw) >= 2 and oname in kw:
                score += len(oname)
        if score > 0:
            scored.append((score, occ))
    scored.sort(key=lambda x: (-x[0], x[1].get("code", "")))
    picked: list[dict[str, str]] = []
    seen: set[str] = set()
    for _, occ in scored[: limit * 2]:
        code = occ.get("code") or ""
        if not code or code in seen:
            continue
        seen.add(code)
        picked.append({
            "code": code,
            "name": occ.get("name") or "",
            "middleCode": occ.get("middle") or "",
            "middleName": middle_lookup.get(occ.get("middle") or "", ""),
        })
        if len(picked) >= limit:
            break

    if len(picked) < limit:
        mids = LEVEL2_OCCUPATION_MIDDLE.get((level2_name or "").strip(), [])
        if not mids:
            for gate, gate_mids in VOCATIONAL_GATE_OCCUPATION_MIDDLE.items():
                if gate in (level2_name or ""):
                    mids = gate_mids
                    break
        if not mids:
            mids = DISCIPLINE_OCCUPATION_MIDDLE.get(discipline, [])
        for mid in mids:
            for occ in occupations:
                if occ.get("middle") != mid:
                    continue
                code = occ.get("code") or ""
                if code in seen:
                    continue
                seen.add(code)
                picked.append({
                    "code": code,
                    "name": occ.get("name") or "",
                    "middleCode": mid,
                    "middleName": middle_lookup.get(mid, ""),
                })
                if len(picked) >= limit:
                    break
            if len(picked) >= limit:
                break
    return picked

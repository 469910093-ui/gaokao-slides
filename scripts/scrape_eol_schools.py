#!/usr/bin/env python3
"""Crawl vocational (高职专科) colleges from eol.cn gkcx API."""

from __future__ import annotations

import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
OUT_FILE = DATA_DIR / "schools_vocational.json"
EMBED_FILE = DATA_DIR / "schools-vocational-embed.js"

API_URL = "https://api.eol.cn/gkcx/api/"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Origin": "https://gkcx.eol.cn",
    "Referer": "https://gkcx.eol.cn/school/search",
}

# eol school_type=6001 → 高职（专科）院校
VOCATIONAL_SCHOOL_TYPE = "6001"

PROVINCE_NORMALIZE = {
    "内蒙古自治区": "内蒙古",
    "广西壮族自治区": "广西",
    "西藏自治区": "西藏",
    "宁夏回族自治区": "宁夏",
    "新疆维吾尔自治区": "新疆",
}


def normalize_province(name: str) -> str:
    if not name:
        return name
    name = name.strip()
    if name in PROVINCE_NORMALIZE:
        return PROVINCE_NORMALIZE[name]
    for suffix in ("省", "市", "自治区"):
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return name


def infer_tags(item: dict[str, Any]) -> list[str]:
    tags = ["专科", "高职"]
    dh = str(item.get("doublehigh") or "")
    if dh and dh not in ("0", "null", "None"):
        tags.append("双高计划")
    type_name = item.get("type_name") or ""
    mapping = {
        "理工": "工科",
        "师范": "师范",
        "财经": "财经",
        "医药": "医科",
        "农业": "农业",
        "政法": "政法",
        "艺术": "艺术",
        "体育": "体育",
        "语言": "语言",
        "民族": "民族",
        "综合": "综合",
    }
    for key, tag in mapping.items():
        if key in type_name:
            tags.append(tag)
            break
    nature = item.get("nature_name") or ""
    if nature:
        tags.append(nature)
    return tags[:5]


def fetch_page(page: int, size: int = 20) -> dict[str, Any]:
    payload = {
        "access_token": "",
        "page": page,
        "size": size,
        "request_type": 1,
        "sort": "view_total",
        "uri": "apidata/api/gk/school/lists",
        "school_type": VOCATIONAL_SCHOOL_TYPE,
        "keyword": "",
        "province_id": "",
        "type": "",
        "admissions": "",
        "central": "",
        "department": "",
        "dual_class": "",
        "f211": "",
        "f985": "",
        "is_dual_class": "",
        "nature": "",
    }
    for attempt in range(3):
        try:
            resp = requests.post(API_URL, data=payload, headers=HEADERS, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            if data.get("data"):
                return data
        except Exception as exc:  # noqa: BLE001
            if attempt == 2:
                raise RuntimeError(f"page {page} failed: {exc}") from exc
            time.sleep(1.5)
    raise RuntimeError(f"page {page} empty response")


def parse_view_total(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).strip().lower()
    if not text:
        return 0
    mult = 1
    if text.endswith("w"):
        mult = 10000
        text = text[:-1]
    elif text.endswith("k"):
        mult = 1000
        text = text[:-1]
    try:
        return int(float(text) * mult)
    except ValueError:
        return 0


def transform_item(item: dict[str, Any]) -> dict[str, Any]:
    dh = str(item.get("doublehigh") or "")
    return {
        "name": item.get("name", "").strip(),
        "province": normalize_province(item.get("province_name") or ""),
        "city": (item.get("city_name") or "").strip(),
        "tier": "专科",
        "type": (item.get("type_name") or "").strip(),
        "nature": (item.get("nature_name") or "").strip(),
        "tags": infer_tags(item),
        "minPercentile": 40.0,
        "doubleHigh": bool(dh and dh not in ("0", "")),
        "schoolId": item.get("school_id"),
        "viewTotal": parse_view_total(item.get("view_total")),
    }


def crawl_vocational() -> list[dict[str, Any]]:
    first = fetch_page(1)
    total = int(first["data"].get("numFound") or 0)
    size = 20
    pages = max(1, (total + size - 1) // size)
    rows = [transform_item(x) for x in first["data"].get("item") or []]

    for page in range(2, pages + 1):
        data = fetch_page(page)
        batch = data["data"].get("item") or []
        rows.extend(transform_item(x) for x in batch)
        if page % 25 == 0:
            print(f"  page {page}/{pages} ({len(rows)} schools)")
        time.sleep(0.12)

    # dedupe by name + province
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for row in rows:
        key = f"{row['province']}::{row['name']}"
        if key in seen or not row["name"]:
            continue
        seen.add(key)
        unique.append(row)
    return unique


def build_embed(schools: list[dict[str, Any]], meta: dict[str, Any]) -> None:
    payload = {"meta": meta, "schools": schools}
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    EMBED_FILE.write_text(
        "// Auto-generated — do not edit. Run: python scripts/scrape_eol_schools.py\n"
        f"window.SCHOOLS_VOCATIONAL={body};\n",
        encoding="utf-8",
    )


def main() -> None:
    print("Crawling vocational colleges from eol.cn (school_type=6001)...")
    schools = crawl_vocational()
    by_prov: dict[str, int] = {}
    for s in schools:
        by_prov[s["province"]] = by_prov.get(s["province"], 0) + 1

    meta = {
        "generatedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source": "中国教育在线 gkcx.eol.cn API",
        "schoolType": VOCATIONAL_SCHOOL_TYPE,
        "total": len(schools),
        "note": (
            "全国普通高等学校高职（专科）院校完整名录（API 口径）。"
            "教育部 2025 年 6 月公布约 1489 所，与本数据源数量接近，差异来自更名/升格/统计时点。"
        ),
        "byProvince": dict(sorted(by_prov.items(), key=lambda x: (-x[1], x[0]))),
        "doubleHighCount": sum(1 for s in schools if s.get("doubleHigh")),
    }
    OUT_FILE.write_text(
        json.dumps({"meta": meta, "schools": schools}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    build_embed(schools, meta)
    print(f"Wrote {OUT_FILE} ({len(schools)} schools, {len(by_prov)} provinces)")
    print(f"Wrote {EMBED_FILE} ({EMBED_FILE.stat().st_size / 1024:.1f} KB)")
    print(f"双高计划院校: {meta['doubleHighCount']} 所")


if __name__ == "__main__":
    main()

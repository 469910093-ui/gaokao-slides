#!/usr/bin/env python3
"""Crawl full undergraduate + vocational major catalogs from eol.cn gkcx API."""

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
REF_DIR = DATA_DIR / "reference"
OUT_FILE = DATA_DIR / "moe_majors_raw.json"
MOE_UNDERGRAD_URL = (
    "https://huggingface.co/datasets/XuehangCang/china-undergraduate-majors-2026/"
    "resolve/main/china-undergraduate-majors-2026.json"
)
MOE_UNDERGRAD_MIRROR = (
    "https://ghproxy.net/https://huggingface.co/datasets/XuehangCang/"
    "china-undergraduate-majors-2026/resolve/main/china-undergraduate-majors-2026.json"
)

API_URL = "https://api.eol.cn/gkcx/api/"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Origin": "https://gkcx.eol.cn",
    "Referer": "https://gkcx.eol.cn/special",
}

# level1: 1=本科普通 2=专科高职 230=本科职业
LEVEL1_CONFIG = [
    ("1", "本科(普通)", "undergraduate"),
    ("2", "专科(高职)", "vocational"),
    ("230", "本科(职业)", "vocational_undergraduate"),
]


def fetch_page(level1: str, page: int, size: int = 50) -> dict[str, Any]:
    data = {
        "uri": "apidata/api/gkv3/special/lists",
        "request_type": 1,
        "page": page,
        "size": size,
        "level1": level1,
        "keyword": "",
        "sort": "view_total",
        "access_token": "",
        "signsafe": "",
    }
    for attempt in range(3):
        try:
            r = requests.post(API_URL, data=data, headers=HEADERS, timeout=30)
            r.raise_for_status()
            j = r.json()
            if j.get("message", "").startswith("成功"):
                return j.get("data") or {}
        except Exception as exc:
            print(f"  [warn] level1={level1} page={page} attempt={attempt + 1}: {exc}")
            time.sleep(1.5 * (attempt + 1))
    return {}


def crawl_level1(level1: str, label: str, catalog_type: str) -> list[dict[str, Any]]:
    first = fetch_page(level1, 1, 50)
    total = int(first.get("numFound") or 0)
    pages = max(1, (total + 49) // 50)
    print(f"  {label}: {total} majors, {pages} pages")
    items: list[dict[str, Any]] = list(first.get("item") or [])
    for page in range(2, pages + 1):
        chunk = fetch_page(level1, page, 50)
        items.extend(chunk.get("item") or [])
        if page % 5 == 0:
            print(f"    page {page}/{pages}")
        time.sleep(0.25)
    out: list[dict[str, Any]] = []
    for raw in items:
        name = (raw.get("name") or "").strip()
        if not name:
            continue
        out.append({
            "specialId": raw.get("special_id") or raw.get("id"),
            "name": name,
            "spcode": raw.get("spcode") or "",
            "degree": raw.get("degree") or "",
            "level1": raw.get("level1") or level1,
            "level1Name": raw.get("level1_name") or label,
            "level2Name": raw.get("level2_name") or "",
            "level3Name": raw.get("level3_name") or "",
            "catalogType": catalog_type,
            "hightitle": raw.get("hightitle") or name,
            "limitYear": raw.get("limit_year") or "",
            "salaryavg": int(raw["salaryavg"]) if raw.get("salaryavg") else None,
            "fivesalaryavg": int(raw["fivesalaryavg"]) if raw.get("fivesalaryavg") else None,
            "viewTotal": int(raw["view_total"]) if raw.get("view_total") else None,
            "viewMonth": int(raw["view_month"]) if raw.get("view_month") else None,
            "viewWeek": int(raw["view_week"]) if raw.get("view_week") else None,
            "rank": int(raw["rank"]) if str(raw.get("rank") or "").isdigit() else None,
        })
    return out


def load_moe_undergrad_codes() -> dict[str, dict[str, Any]]:
    """教育部本科专业目录官方代码（按专业名索引）。"""
    REF_DIR.mkdir(parents=True, exist_ok=True)
    cache = REF_DIR / "china-undergraduate-majors-2026.json"
    if not cache.exists():
        for url in (MOE_UNDERGRAD_MIRROR, MOE_UNDERGRAD_URL):
            try:
                r = requests.get(url, timeout=90)
                if r.ok and r.content[:1] == b"[":
                    cache.write_bytes(r.content)
                    print(f"Downloaded MOE undergrad catalog -> {cache}")
                    break
            except Exception as exc:
                print(f"  [warn] MOE download {url}: {exc}")
    if not cache.exists():
        return {}
    try:
        tree = json.loads(cache.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        cache.unlink(missing_ok=True)
        return {}
    by_name: dict[str, dict[str, Any]] = {}
    for gate in tree:
        gate_name = gate.get("name") or ""
        for cls in gate.get("major_classes") or []:
            cls_name = cls.get("name") or ""
            for m in cls.get("majors") or []:
                n = (m.get("name") or "").strip()
                if not n:
                    continue
                by_name[n] = {
                    "moeCode": m.get("code") or "",
                    "baseCode": m.get("base_code") or "",
                    "gate": gate_name,
                    "class": cls_name,
                    "isSpecial": bool(m.get("is_special")),
                    "isControlled": bool(m.get("is_controlled")),
                }
    return by_name


def merge_moe_codes(majors: list[dict[str, Any]], moe_by_name: dict[str, dict[str, Any]]) -> None:
    for m in majors:
        if m["catalogType"] != "undergraduate":
            continue
        official = moe_by_name.get(m["name"])
        if official:
            m["moeCode"] = official["moeCode"]
            m["moeGate"] = official["gate"]
            m["moeClass"] = official["class"]
            m["moeIsSpecial"] = official["isSpecial"]
            m["moeIsControlled"] = official["isControlled"]
        elif m.get("spcode"):
            m["moeCode"] = m["spcode"]


MOE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
}

UNDERGRAD_ROW_RE = re.compile(
    r"<td>\s*(\d+)\s*</td>\s*"
    r"<td>\s*([^<]+?)\s*</td>\s*"
    r"<td>\s*([^<]+?)\s*</td>\s*"
    r"<td>\s*([^<]+?)\s*</td>\s*"
    r"<td>\s*([^<]+?)\s*</td>\s*"
    r"<td>\s*([^<]+?)\s*</td>",
    re.S,
)


def fetch_official_undergrad() -> list[dict[str, Any]]:
    """教育部 jxjy.moe.edu.cn 本科专业目录（845）。"""
    print("Fetching MOE official undergraduate catalog (jxjy.moe.edu.cn)...")
    out: list[dict[str, Any]] = []
    for page in range(1, 90):
        r = requests.get(
            "https://jxjy.moe.edu.cn/home/basic",
            params={"type": 1, "page": page},
            headers=MOE_HEADERS,
            timeout=30,
        )
        r.raise_for_status()
        rows = UNDERGRAD_ROW_RE.findall(r.text)
        if not rows:
            break
        for _, name, code, gate, cls, ctrl in rows:
            name = name.strip()
            if not name:
                continue
            out.append({
                "name": name,
                "moeCode": code.strip(),
                "level2Name": gate.strip(),
                "level3Name": cls.strip(),
                "level1Name": "本科(普通)",
                "catalogType": "undergraduate",
                "hightitle": name,
                "moeControlled": "国控" in ctrl,
            })
        time.sleep(0.15)
    print(f"  official undergrad: {len(out)}")
    return out


def fetch_official_vocational() -> list[dict[str, Any]]:
    """教育部 zyyxzy.moe.edu.cn 高职专科专业目录（802）。"""
    print("Fetching MOE official vocational catalog (zyyxzy.moe.edu.cn)...")
    out: list[dict[str, Any]] = []
    for page in range(1, 15):
        r = requests.get(
            "https://zyyxzy.moe.edu.cn/home/gz",
            params={"page": page},
            headers=MOE_HEADERS,
            timeout=30,
        )
        r.raise_for_status()
        tds = re.findall(r"<td[^>]*>\s*([^<]+?)\s*</td>", r.text)
        data_cells = [c.strip() for c in tds if c.strip() and c.strip() not in ("专业大类", "专业类", "专业代码", "专业名称", "备注")]
        i = 0
        while i + 3 < len(data_cells):
            gate, cls, code, name = data_cells[i : i + 4]
            if re.fullmatch(r"\d{6}", code):
                out.append({
                    "name": name.strip(),
                    "moeCode": code.strip(),
                    "level2Name": gate.strip(),
                    "level3Name": cls.strip(),
                    "level1Name": "专科(高职)",
                    "catalogType": "vocational",
                    "hightitle": name.strip(),
                })
                i += 4
            else:
                i += 1
        time.sleep(0.15)
    # 去重
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for m in out:
        key = f"{m['moeCode']}@{m['name']}"
        if key in seen:
            continue
        seen.add(key)
        deduped.append(m)
    print(f"  official vocational: {len(deduped)}")
    return deduped


def enrich_from_eol(target: dict[str, Any], eol: dict[str, Any]) -> None:
    for k in (
        "specialId", "spcode", "degree", "salaryavg", "fivesalaryavg",
        "viewTotal", "viewMonth", "viewWeek", "rank", "hightitle", "limitYear",
    ):
        if eol.get(k) is not None and target.get(k) is None:
            target[k] = eol[k]
    if eol.get("level3Name") and not target.get("level3Name"):
        target["level3Name"] = eol["level3Name"]


def merge_official_and_eol(
    official: list[dict[str, Any]],
    eol_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_name: dict[str, dict[str, Any]] = {m["name"]: dict(m) for m in official}
    by_code: dict[str, dict[str, Any]] = {
        m["moeCode"]: m for m in official if m.get("moeCode")
    }
    for e in eol_items:
        hit = by_name.get(e["name"]) or by_code.get(e.get("spcode") or e.get("moeCode") or "")
        if hit:
            enrich_from_eol(hit, e)
        else:
            by_name[e["name"]] = dict(e)
    return list(by_name.values())


def main() -> None:
    print("Crawling eol.cn major catalogs (enrichment)...")
    eol_majors: list[dict[str, Any]] = []
    eol_by_type: dict[str, list[dict[str, Any]]] = {}
    for level1, label, ctype in LEVEL1_CONFIG:
        batch = crawl_level1(level1, label, ctype)
        eol_by_type[ctype] = batch
        eol_majors.extend(batch)

    print("Merging with MOE official catalogs...")
    undergrad = merge_official_and_eol(
        fetch_official_undergrad(),
        eol_by_type.get("undergraduate", []),
    )
    vocational = merge_official_and_eol(
        fetch_official_vocational(),
        eol_by_type.get("vocational", []),
    )
    # 职教本科暂无独立官方分页表，保留 EOL 全量
    voc_undergrad = list(eol_by_type.get("vocational_undergraduate", []))

    all_majors = undergrad + vocational + voc_undergrad
    moe_by_name = load_moe_undergrad_codes()
    merge_moe_codes(all_majors, moe_by_name)

    counts = {
        "undergraduate": len(undergrad),
        "vocational": len(vocational),
        "vocational_undergraduate": len(voc_undergrad),
    }

    payload = {
        "meta": {
            "generatedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "source": (
                "教育部 jxjy/zyyxzy 官方目录 + eol.cn gkv3/special/lists 产业数据 enrichment"
            ),
            "total": len(all_majors),
            "byCatalogType": counts,
            "moeUndergradOfficial": len(moe_by_name) or len(undergrad),
        },
        "majors": all_majors,
    }
    OUT_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUT_FILE} ({len(all_majors)} majors)")
    print(
        f"  本科普通 {counts.get('undergraduate', 0)} | "
        f"专科高职 {counts.get('vocational', 0)} | "
        f"职教本科 {counts.get('vocational_undergraduate', 0)}"
    )


if __name__ == "__main__":
    main()

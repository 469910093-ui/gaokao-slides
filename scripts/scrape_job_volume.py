#!/usr/bin/env python3
"""Track recruitment demand proxies and compute job posting volume YoY.

Primary: 智联招聘 fe-api numFound (全国)
Fallback: eol 专业搜索热度(view_month) 快照同比
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
RAW_FILE = DATA_DIR / "moe_majors_raw.json"
SNAPSHOT_FILE = DATA_DIR / "job_volume_snapshots.json"
OUT_FILE = DATA_DIR / "job_volume_index.json"

ZHAOPIN_API = "https://fe-api.zhaopin.com/c/i/sou"
CITY_NATIONAL = "489"  # 全国
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://sou.zhaopin.com/",
}

# 全量爬取招聘平台过慢；按搜索热度优先采样，其余用 EOL 同比
TOP_SAMPLE = 120
REQUEST_DELAY = 0.2
ZHAOPIN_FAIL_ABORT = 5


def load_snapshots() -> dict[str, Any]:
    if SNAPSHOT_FILE.exists():
        return json.loads(SNAPSHOT_FILE.read_text(encoding="utf-8"))
    return {"history": []}


def save_snapshots(data: dict[str, Any]) -> None:
    SNAPSHOT_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def fetch_zhaopin_count(keyword: str) -> int | None:
    try:
        r = requests.get(
            ZHAOPIN_API,
            params={"kw": keyword, "cityId": CITY_NATIONAL, "pageSize": 1, "start": 0},
            headers=HEADERS,
            timeout=20,
        )
        j = r.json()
        n = (j.get("data") or {}).get("numFound")
        if n is None:
            return None
        n = int(n)
        if n >= 999999:
            return None
        return n
    except Exception:
        return None


def pick_keyword(major: dict[str, Any]) -> str:
    ht = (major.get("hightitle") or "").strip()
    name = (major.get("name") or "").strip()
    if ht and ht != name and len(ht) <= 12:
        return ht
    return name


def compute_yoy(current: float, baseline: float | None) -> float | None:
    if baseline is None or baseline <= 0:
        return None
    return round((current - baseline) / baseline * 100, 1)


def find_baseline_snapshot(
    history: list[dict[str, Any]],
    major_key: str,
    days: int = 365,
) -> dict[str, Any] | None:
    if not history:
        return None
    target = datetime.now() - timedelta(days=days)
    candidates = [
        h for h in history
        if h.get("majorKey") == major_key and h.get("capturedAt")
    ]
    if not candidates:
        return None
    parsed: list[tuple[datetime, dict[str, Any]]] = []
    for c in candidates:
        try:
            dt = datetime.strptime(c["capturedAt"][:10], "%Y-%m-%d")
            parsed.append((dt, c))
        except ValueError:
            continue
    if not parsed:
        return None
    parsed.sort(key=lambda x: x[0])
    # 最接近 target 且早于今天的记录
    before = [p for p in parsed if p[0] <= datetime.now()]
    if not before:
        return parsed[0][1]
    return min(before, key=lambda p: abs((p[0] - target).days))[1]


def main() -> None:
    if not RAW_FILE.exists():
        raise SystemExit(f"Missing {RAW_FILE} — run scripts/scrape_moe_majors.py first")

    raw = json.loads(RAW_FILE.read_text(encoding="utf-8"))
    majors: list[dict[str, Any]] = raw.get("majors") or []
    majors_sorted = sorted(
        majors,
        key=lambda m: (m.get("viewMonth") or 0, m.get("viewTotal") or 0),
        reverse=True,
    )
    sample_keys = {
        f"{m['name']}@{m['catalogType']}"
        for m in majors_sorted[:TOP_SAMPLE]
    }

    snap = load_snapshots()
    history: list[dict[str, Any]] = snap.get("history") or []
    today = datetime.now().strftime("%Y-%m-%d")
    index: dict[str, Any] = {}
    zhaopin_ok = 0
    zhaopin_fail_streak = 0
    zhaopin_disabled = False

    print(f"Building job volume index for {len(majors)} majors (zhaopin sample={len(sample_keys)})...")
    for i, m in enumerate(majors):
        key = f"{m['name']}@{m['catalogType']}"
        keyword = pick_keyword(m)
        view_month = m.get("viewMonth")
        view_week = m.get("viewWeek")

        zhaopin_count = None
        if key in sample_keys and not zhaopin_disabled:
            zhaopin_count = fetch_zhaopin_count(keyword)
            if zhaopin_count is not None:
                zhaopin_ok += 1
                zhaopin_fail_streak = 0
            else:
                zhaopin_fail_streak += 1
                if zhaopin_fail_streak >= ZHAOPIN_FAIL_ABORT:
                    zhaopin_disabled = True
                    print("  [info] zhaopin API unavailable, using EOL heat YoY/momentum only")
            time.sleep(REQUEST_DELAY)

        # 周热度折算月环比（短期动量）
        momentum = None
        if view_month and view_week and view_month > 0:
            momentum = round((view_week * 4.33 / view_month - 1) * 100, 1)

        baseline = find_baseline_snapshot(history, key, days=365)
        yoy_eol = compute_yoy(float(view_month or 0), float(baseline["viewMonth"]) if baseline else None)
        yoy_zhaopin = None
        if zhaopin_count is not None and baseline and baseline.get("zhaopinCount"):
            yoy_zhaopin = compute_yoy(float(zhaopin_count), float(baseline["zhaopinCount"]))

        job_volume_yoy = yoy_zhaopin if yoy_zhaopin is not None else yoy_eol
        source = "智联招聘职位数同比" if yoy_zhaopin is not None else (
            "EOL搜索热度同比" if yoy_eol is not None else "EOL周热度动量(代理)"
        )
        if job_volume_yoy is None and momentum is not None:
            job_volume_yoy = momentum

        index[key] = {
            "keyword": keyword,
            "zhaopinCount": zhaopin_count,
            "viewMonth": view_month,
            "viewWeek": view_week,
            "jobVolumeMomentum": momentum,
            "jobVolumeYoY": job_volume_yoy,
            "jobVolumeSource": source,
        }

        # 每日快照（去重）
        if not any(
            h.get("majorKey") == key and h.get("capturedAt", "").startswith(today)
            for h in history
        ):
            history.append({
                "majorKey": key,
                "capturedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "viewMonth": view_month,
                "viewWeek": view_week,
                "zhaopinCount": zhaopin_count,
            })

        if (i + 1) % 200 == 0:
            print(f"  processed {i + 1}/{len(majors)}")

    # 保留近 400 天快照
    cutoff = datetime.now() - timedelta(days=400)
    trimmed: list[dict[str, Any]] = []
    for h in history:
        try:
            dt = datetime.strptime(h["capturedAt"][:19], "%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
        if dt >= cutoff:
            trimmed.append(h)
    snap["history"] = trimmed
    snap["meta"] = {
        "updatedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "zhaopinSampleHits": zhaopin_ok,
    }
    save_snapshots(snap)

    out = {
        "meta": {
            "generatedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total": len(index),
            "zhaopinSampleHits": zhaopin_ok,
            "methodology": (
                "优先使用智联招聘全国职位数同比；若无历史快照则用EOL专业月搜索热度同比；"
                "首次构建时用周热度动量作代理"
            ),
        },
        "index": index,
    }
    OUT_FILE.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUT_FILE} (zhaopin real counts: {zhaopin_ok}/{len(sample_keys)})")


if __name__ == "__main__":
    main()

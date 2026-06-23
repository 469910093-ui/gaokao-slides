#!/usr/bin/env python3
"""断点续爬 gaokao.cn 投档数据并重建 admission_index + 底表导出。"""

from __future__ import annotations

import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
REF = ROOT / "data" / "reference" / "gaokao_cn"

ALL_PROVINCES = [
    "北京", "天津", "河北", "山西", "内蒙古", "辽宁", "吉林", "黑龙江",
    "上海", "江苏", "浙江", "安徽", "福建", "江西", "山东", "河南",
    "湖北", "湖南", "广东", "广西", "海南", "重庆", "四川", "贵州",
    "云南", "西藏", "陕西", "甘肃", "青海", "宁夏", "新疆",
]


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=ROOT, check=True)


def missing_provinces(years: list[int]) -> list[str]:
    sys.path.insert(0, str(SCRIPTS))
    from province_tracks import COMBINED_33_PROVINCES  # noqa: WPS433

    have: set[tuple[str, int]] = set()
    for path in REF.glob("admissions_*.json"):
        m = re.match(r"admissions_(.+)_(\d+)_(.+)\.json$", path.name)
        if not m:
            continue
        prov, year_s, _track = m.group(1), m.group(2), m.group(3)
        try:
            rows = __import__("json").loads(path.read_text(encoding="utf-8"))
        except Exception:
            rows = []
        if rows:
            have.add((prov, int(year_s)))

    missing: list[str] = []
    for year in years:
        for prov in ALL_PROVINCES:
            if (prov, year) not in have:
                if prov not in missing:
                    missing.append(prov)
    return missing


def main() -> None:
    years = [2024, 2025]
    gaps = missing_provinces(years)
    print(f"Missing province-years to fetch: {len(gaps)} provinces", flush=True)
    if gaps:
        for i, prov in enumerate(gaps, 1):
            print(f"\n=== [{i}/{len(gaps)}] {prov} ===", flush=True)
            run([
                sys.executable, "-u", str(SCRIPTS / "scrape_gaokao_cn.py"),
                "--provinces", prov,
                "--years", ",".join(str(y) for y in years),
                "--skip-existing",
                "--pause", "10",
                "--page-sleep", "4",
            ])
            time.sleep(15)
    else:
        print("All 2024/2025 province files present, rebuilding index only.", flush=True)

    run([sys.executable, str(SCRIPTS / "build_admission_index.py")])
    run([sys.executable, str(SCRIPTS / "export_admission_basetable.py")])
    run([sys.executable, str(SCRIPTS / "verify_admission_index.py")])
    print("Done: admission_index refreshed", flush=True)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Audit eol vs model track slots for target 13 provinces."""
import json
from pathlib import Path

TARGETS = [
    "北京", "上海", "浙江", "广东", "四川", "山东", "云南", "广西",
    "江苏", "湖北", "辽宁", "吉林", "黑龙江",
]
ROOT = Path(__file__).resolve().parents[1]
PROV_DIR = ROOT / "data" / "provinces"

summary = {}
for prov in TARGETS:
    path = PROV_DIR / f"{prov}.json"
    if not path.exists():
        print(prov, "MISSING FILE")
        continue
    data = json.loads(path.read_text(encoding="utf-8"))
    eol = model = 0
    gaps = []
    for year in range(2014, 2026):
        yo = data.get("years", {}).get(str(year), {})
        for track in ("物理类", "历史类"):
            src = yo.get("tracks", {}).get(track, {}).get("source", "missing")
            if str(src).startswith("eol"):
                eol += 1
            else:
                model += 1
                gaps.append(f"{year}/{track}")
    summary[prov] = {"eol": eol, "model": model, "gaps": gaps}
    print(f"{prov}: eol={eol} model={model}  gaps={len(gaps)}")

print("--- TOTAL ---")
print("eol", sum(v["eol"] for v in summary.values()))
print("model", sum(v["model"] for v in summary.values()))

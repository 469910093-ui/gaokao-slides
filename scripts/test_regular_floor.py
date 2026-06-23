#!/usr/bin/env python3
"""regular_floor_from_rows 回归：带 groupInfo 的官方行须参与 floor 计算。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from admission_filter_lib import filter_regular_admission_row, regular_floor_from_rows  # noqa: E402


def test_beijing_official_has_floors() -> None:
    rows = json.loads(
        (ROOT / "data/reference/gaokao_cn/admissions_北京_2025_综合_official.json").read_text(encoding="utf-8")
    )
    kept = [r for r in rows if filter_regular_admission_row("北京", r)]
    assert len(kept) > 500
    with_floor = sum(1 for r in kept if regular_floor_from_rows([r]) is not None)
    assert with_floor == len(kept), f"expected all rows to yield floor, got {with_floor}/{len(kept)}"


def test_group_info_rows_counted() -> None:
    row = {
        "groupInfo": "专业组01",
        "minScore": 600,
        "schoolName": "测试大学",
        "batch": "本科批",
        "province": "北京",
    }
    assert regular_floor_from_rows([row]) == 600


if __name__ == "__main__":
    test_beijing_official_has_floors()
    test_group_info_rows_counted()
    print("ok")

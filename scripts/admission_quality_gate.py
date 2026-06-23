#!/usr/bin/env python3
"""
投档数据质量门禁：锚点校验 + 推荐验收 + 官方 floor 交叉验证。

用法:
  python scripts/admission_quality_gate.py --strict
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
DATA = ROOT / "data"
REF = DATA / "reference" / "gaokao_cn"

sys.path.insert(0, str(SCRIPTS))

from admission_filter_lib import (  # noqa: E402
    PROVINCE_EXAM_PORTALS,
    recommend_floor_from_entry,
)

ANCHORS_PATH = SCRIPTS / "admission_anchors.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def check_recommendation_anchors(index: dict[str, Any]) -> list[dict[str, str]]:
    from acceptance_test_recommendations import recommend_schools, load_json as lj

    anchors = load_json(ANCHORS_PATH).get("recommendation", [])
    manifest = lj(DATA / "manifest.json")
    schools = manifest.get("schools") or []
    issues: list[dict[str, str]] = []
    for spec in anchors:
        province = spec["province"]
        track = spec["track"]
        score = int(spec["score"])
        forbidden = set(spec.get("mustNotRecommend") or [])
        rec = recommend_schools(score, province, track, schools, index)
        if not rec.get("has_admission"):
            issues.append({
                "severity": "WARN",
                "code": "ANCHOR_NO_ADMISSION",
                "message": f"{province}{track}{score}分：省份未开放投档推荐，跳过锚点",
            })
            continue
        picked = set(rec["chong"] + rec["wen"] + rec["bao"])
        bad = picked & forbidden
        if bad:
            issues.append({
                "severity": "ERROR",
                "code": "RECOMMENDATION_ANCHOR",
                "message": f"{province}{track}{score}分不得推荐: {sorted(bad)}，实际: {sorted(picked)[:6]}",
            })
    return issues


def check_floor_anchors(index: dict[str, Any]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    for spec in load_json(ANCHORS_PATH).get("floorMin", []):
        province = spec["province"]
        track = spec["track"]
        school = spec["school"]
        year = str(spec["year"])
        min_expected = int(spec["minScore"])
        entry = (
            index.get("provinces", {})
            .get(province, {})
            .get(track, {})
            .get(school)
        )
        if not entry:
            issues.append({
                "severity": "ERROR",
                "code": "FLOOR_ANCHOR_MISSING",
                "message": f"{province}{track}{school} 无索引条目",
            })
            continue
        actual = (entry.get("yearsRegular") or entry.get("years") or {}).get(year)
        if actual is None:
            issues.append({
                "severity": "ERROR",
                "code": "FLOOR_ANCHOR_YEAR",
                "message": f"{province}{track}{school} 缺 {year} 年普通批 floor",
            })
            continue
        if int(actual) < min_expected:
            issues.append({
                "severity": "ERROR",
                "code": "FLOOR_ANCHOR_LOW",
                "message": f"{province}{track}{school} {year} floor={actual} < 锚点{min_expected}",
            })
    return issues


def check_c9_pollution(index: dict[str, Any]) -> list[dict[str, str]]:
    """清北 floor 不得低于本省特控线 + 80（专项污染探测）。"""
    top2 = frozenset({"北京大学", "清华大学"})
    issues: list[dict[str, str]] = []
    for prov_path in sorted((DATA / "provinces").glob("*.json")):
        province = prov_path.stem
        pdata = load_json(prov_path)
        yo = pdata.get("years", {}).get("2025") or pdata.get("years", {}).get("2024")
        if not yo:
            continue
        batches = yo.get("batches") or {}
        special = batches.get("特招线") or batches.get("特殊类型控制线")
        if special is None:
            continue
        threshold = int(special) + 80
        for track, schools in (index.get("provinces", {}).get(province) or {}).items():
            for school in top2:
                entry = schools.get(school)
                if not entry:
                    continue
                floor = recommend_floor_from_entry(entry)
                if floor is not None and floor < threshold:
                    issues.append({
                        "severity": "ERROR",
                        "code": "C9_SPECIAL_POLLUTION",
                        "message": (
                            f"{province}{track}{school} 普通批参考分{floor} "
                            f"< 特控线{special}+80={threshold}，疑似专项污染"
                        ),
                    })
    return issues


def check_province_coverage(index: dict[str, Any]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    status = index.get("meta", {}).get("provinceStatus") or {}
    for prov, st in status.items():
        if st.get("status") != "verified":
            continue
    # 未验收省份不得标记 has_admission — 由 acceptance 脚本检查
    verified = set(index.get("meta", {}).get("verifiedProvinces") or [])
    for prov_path in sorted((DATA / "provinces").glob("*.json")):
        province = prov_path.stem
        if province in verified:
            continue
        # 非 verified 省：索引中不应有推荐用数据（build 已仅 official，但旧 embed 可能残留）
        for track, schools in (index.get("provinces", {}).get(province) or {}).items():
            if schools:
                issues.append({
                    "severity": "WARN",
                    "code": "UNVERIFIED_PROVINCE_DATA",
                    "message": f"{province}{track} 有 {len(schools)} 校索引但未在 verifiedProvinces",
                })
    return issues


def run_acceptance(strict: bool) -> int:
    cmd = [sys.executable, str(SCRIPTS / "acceptance_test_recommendations.py")]
    if strict:
        cmd.append("--strict")
    print("Running acceptance_test_recommendations.py ...")
    return subprocess.call(cmd)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true", help="存在 ERROR 时 exit 1")
    args = parser.parse_args()

    index_path = REF / "admission_index.json"
    if not index_path.exists():
        print("ERROR: admission_index.json 不存在，请先 build_admission_index.py")
        sys.exit(1)
    index = load_json(index_path)

    all_issues: list[dict[str, str]] = []
    all_issues.extend(check_recommendation_anchors(index))
    all_issues.extend(check_floor_anchors(index))
    all_issues.extend(check_c9_pollution(index))
    all_issues.extend(check_province_coverage(index))

    errors = [i for i in all_issues if i["severity"] == "ERROR"]
    warns = [i for i in all_issues if i["severity"] == "WARN"]

    print(f"\nGate checks: ERROR={len(errors)} WARN={len(warns)}")
    for iss in all_issues[:30]:
        print(f"  [{iss['severity']}] {iss['code']}: {iss['message']}")
    if len(all_issues) > 30:
        print(f"  ... and {len(all_issues) - 30} more")

    acc_code = run_acceptance(args.strict)
    if acc_code != 0:
        print(f"acceptance_test_recommendations exited {acc_code}")
        sys.exit(acc_code)

    if errors and args.strict:
        sys.exit(1)
    print("\nQuality gate passed.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""核验已验收省份官方投档归档：年份覆盖、来源域名、分数区间。"""
from __future__ import annotations

import json
import time
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
REF = ROOT / "data" / "reference" / "gaokao_cn"
OUT = ROOT / "data" / "acceptance" / "admission_source_audit.json"

sys_path = ROOT / "scripts"
import sys

sys.path.insert(0, str(sys_path))
from admission_filter_lib import PROVINCE_EXAM_PORTALS, filter_regular_admission_row  # noqa: E402

YEARS = (2023, 2024, 2025)
VERIFIED = [
    "上海", "北京", "四川", "山东", "广西", "江苏", "河北", "浙江", "湖南", "贵州", "陕西",
]


PORTAL_ALT_HOSTS: dict[str, list[str]] = {
    "陕西": ["sneac.com", "sneea.cn"],
    "贵州": ["zsksy.guizhou.gov.cn", "guizhou.gov.cn"],
    "广西": ["gxeea.cn"],
}


def portal_host(province: str) -> str:
    url = PROVINCE_EXAM_PORTALS.get(province, "")
    return urlparse(url).netloc.lower().replace("www.", "")


def portal_hosts(province: str) -> list[str]:
    hosts = []
    primary = portal_host(province)
    if primary:
        hosts.append(primary)
    hosts.extend(PORTAL_ALT_HOSTS.get(province, []))
    return hosts


def host_matches_portal(netloc: str, allowed: list[str]) -> bool:
    netloc = netloc.lower().replace("www.", "")
    for h in allowed:
        h = h.lower().replace("www.", "")
        if h in netloc or netloc.endswith("." + h):
            return True
    return "chsi.com.cn" in netloc or netloc.endswith(".gov.cn")


def audit_file(path: Path) -> dict:
    province = path.name.split("_")[1]
    rows = json.loads(path.read_text(encoding="utf-8"))
    hosts = portal_hosts(province)
    issues: list[dict] = []
    kept = 0
    bad_url = 0
    bad_score = 0
    for row in rows:
        if not filter_regular_admission_row(province, row):
            continue
        kept += 1
        url = (row.get("sourceUrl") or "").strip()
        if url:
            netloc = urlparse(url).netloc.lower().replace("www.", "")
            if hosts and not host_matches_portal(netloc, hosts):
                bad_url += 1
                if bad_url <= 3:
                    issues.append({"kind": "SOURCE_HOST", "school": row.get("schoolName"), "url": url})
        score = row.get("minScore")
        if score is not None and (score < 100 or score > 900):
            bad_score += 1
    return {
        "file": path.name,
        "province": province,
        "rows": len(rows),
        "regularRows": kept,
        "badSourceHost": bad_url,
        "badScore": bad_score,
        "issues": issues,
    }


def main() -> None:
    files = sorted(REF.glob("admissions_*_official.json"))
    by_prov_year: dict[str, set[int]] = defaultdict(set)
    file_audits = []
    for path in files:
        parts = path.stem.removeprefix("admissions_").removesuffix("_official").split("_")
        if len(parts) < 3:
            continue
        prov, year_s = parts[0], parts[1]
        try:
            year = int(year_s)
        except ValueError:
            continue
        if year in YEARS:
            by_prov_year[prov].add(year)
        if prov in VERIFIED and year in YEARS:
            file_audits.append(audit_file(path))

    coverage_issues = []
    for prov in VERIFIED:
        missing = [y for y in YEARS if y not in by_prov_year.get(prov, set())]
        if missing:
            coverage_issues.append({"province": prov, "missingYears": missing})

    report = {
        "generatedAt": time.strftime("%Y-%m-%d %H:%M:%S"),
        "years": list(YEARS),
        "verifiedProvinces": VERIFIED,
        "coverageIssues": coverage_issues,
        "filesAudited": len(file_audits),
        "sourceIssues": [a for a in file_audits if a["badSourceHost"] or a["badScore"]],
        "summary": {
            "coverageOk": len(coverage_issues) == 0,
            "sourceHostProblems": sum(a["badSourceHost"] for a in file_audits),
            "scoreProblems": sum(a["badScore"] for a in file_audits),
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Coverage issues: {len(coverage_issues)}")
    for c in coverage_issues:
        print(f"  {c['province']}: missing {c['missingYears']}")
    print(f"Source host problems: {report['summary']['sourceHostProblems']}")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()

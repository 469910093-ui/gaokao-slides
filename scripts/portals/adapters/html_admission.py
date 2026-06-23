"""HTML 投档表解析（北京考试院等院校+专业组表）。"""

from __future__ import annotations

import re
from typing import Any

from bs4 import BeautifulSoup

from admission_filter_lib import primary_undergrad_batch
from portals.types import AdmissionRow, Artifact, ParseResult

_SCORE_RE = re.compile(r"^\d{2,3}$")


def _first_total_score(cells: list[str], start: int = 5) -> int | None:
    for i in range(start, min(start + 4, len(cells))):
        raw = cells[i].strip()
        if _SCORE_RE.fullmatch(raw):
            v = int(raw)
            if 250 <= v <= 750:
                return v
    return None


def parse_beijing_style_html_table(
    html: str,
    *,
    province: str,
    year: int,
    track: str,
    batch: str | None,
    source_url: str,
) -> list[AdmissionRow]:
    """解析北京教育考试院「院校+专业组+总分」HTML 表。"""
    soup = BeautifulSoup(html, "html.parser")
    batch_name = batch or primary_undergrad_batch(province)
    rows: list[AdmissionRow] = []

    for table in soup.find_all("table"):
        for tr in table.find_all("tr"):
            cells = [c.get_text(strip=True) for c in tr.find_all("td")]
            if len(cells) < 6:
                continue
            # 序号 | 院校代码 | 院校名 | 专业组 | 选科 | 总分 | ...
            if not cells[0].isdigit():
                continue
            school_code = cells[1]
            school_name = cells[2]
            if not school_name or school_name.isdigit():
                continue
            group_name = cells[3]
            group_info = cells[4] if len(cells) > 4 else ""
            score = _first_total_score(cells, 5)
            if score is None:
                continue
            rows.append(
                AdmissionRow(
                    province=province,
                    year=year,
                    track=track,
                    schoolName=school_name,
                    minScore=score,
                    batch=batch_name,
                    groupName=f"（{group_name}）" if group_name and not group_name.startswith("（") else group_name,
                    groupInfo=group_info,
                    schoolCode=school_code,
                    sourceUrl=source_url,
                )
            )
    return rows


def parse_html_admission(artifact: Artifact, html: str) -> ParseResult:
    track = artifact.track or "综合类"
    rows = parse_beijing_style_html_table(
        html,
        province=artifact.province,
        year=artifact.year,
        track=track,
        batch=artifact.batch,
        source_url=artifact.url,
    )
    return ParseResult(artifact=artifact, rows=rows, parser="html_beijing_style")

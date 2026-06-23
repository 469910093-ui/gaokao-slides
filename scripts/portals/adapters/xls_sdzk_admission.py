"""山东省 sdzk.cn 投档 XLS（专业+院校，公布最低位次）。"""

from __future__ import annotations

import io
import re
from typing import Any

from admission_filter_lib import primary_undergrad_batch
from portals.rank_score import rank_to_score
from portals.types import AdmissionRow, Artifact, ParseResult

_SCHOOL_RE = re.compile(r"^([A-Za-z]?\d{3,5})(.+)$")


def _parse_school_cell(raw: str) -> tuple[str, str]:
    text = (raw or "").replace("\n", "").strip()
    m = _SCHOOL_RE.match(text)
    if m:
        return m.group(2).strip(), m.group(1).strip()
    return text, ""


def _parse_rank(raw: Any) -> int | None:
    if raw is None or raw == "":
        return None
    try:
        v = int(float(raw))
        return v if v > 0 else None
    except (TypeError, ValueError):
        return None


def parse_xls_sdzk_admission(artifact: Artifact, data: bytes) -> ParseResult:
    try:
        import xlrd  # type: ignore
    except ImportError as exc:
        raise RuntimeError("需要 xlrd: pip install xlrd") from exc

    batch_name = artifact.batch or primary_undergrad_batch(artifact.province)
    track = artifact.track or "综合类"
    book = xlrd.open_workbook(file_contents=data)
    sheet = book.sheet_by_index(0)
    rows: list[AdmissionRow] = []
    warnings: list[str] = []
    no_score = 0

    for i in range(sheet.nrows):
        if sheet.ncols < 4:
            continue
        # 2023/2024: 空列 + 专业 | 院校 | 计划数 | 位次（5列）
        # 2025+: 专业 | 院校 | 计划数 | 位次（4列）
        if sheet.ncols >= 5:
            major_col, school_col, rank_col = 1, 2, 4
        else:
            major_col, school_col, rank_col = 0, 1, 3
        major_raw = str(sheet.cell_value(i, major_col)).strip()
        school_raw = str(sheet.cell_value(i, school_col)).strip()
        if not school_raw or school_raw in ("院校代号+名称", "院校代号及名称"):
            continue
        school, code = _parse_school_cell(school_raw)
        if not school or len(school) < 2:
            continue
        rank = _parse_rank(sheet.cell_value(i, rank_col))
        if rank is None:
            continue
        score = rank_to_score(artifact.province, artifact.year, rank, track)
        if score is None:
            no_score += 1
            continue
        major = major_raw.replace("\n", "").strip()[:80]
        rows.append(
            AdmissionRow(
                province=artifact.province,
                year=artifact.year,
                track=track,
                schoolName=school,
                minScore=score,
                minRank=rank,
                batch=batch_name,
                groupName=major[:40] if major else "",
                groupInfo=major,
                schoolCode=code,
                sourceUrl=artifact.url,
            )
        )

    if no_score:
        warnings.append(f"{no_score} 行有位次但无法从一分一段换算分数")
    return ParseResult(artifact=artifact, rows=rows, parser="xls_xlrd_sdzk", warnings=warnings)

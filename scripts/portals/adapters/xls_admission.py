"""旧版 .xls 投档表解析（江苏省教育考试院等）。"""

from __future__ import annotations

import io
import re
from typing import Any

from admission_filter_lib import primary_undergrad_batch, parse_min_score
from portals.types import AdmissionRow, Artifact, ParseResult

_GROUP_RE = re.compile(r"^(.+?)(\d{1,3})专业组(?:[（(](.+?)[）)])?$")


def _split_school_group(raw: str) -> tuple[str, str, str]:
    text = (raw or "").replace("\n", "").strip()
    m = _GROUP_RE.match(text)
    if m:
        return m.group(1).strip(), f"（{m.group(2)}）", (m.group(3) or "").strip()
    if "专业组" in text:
        school, rest = text.split("专业组", 1)
        return school.strip(), "专业组", rest.strip("()（）")
    return text, "", ""


def parse_xls_admission(artifact: Artifact, data: bytes) -> ParseResult:
    try:
        import xlrd  # type: ignore
    except ImportError as exc:
        raise RuntimeError("需要 xlrd: pip install xlrd") from exc

    batch_name = artifact.batch or primary_undergrad_batch(artifact.province)
    track = artifact.track or "物理类"
    book = xlrd.open_workbook(file_contents=data)
    sheet = book.sheet_by_index(0)
    rows: list[AdmissionRow] = []

    for i in range(sheet.nrows):
        cells = [sheet.cell_value(i, j) for j in range(sheet.ncols)]
        if len(cells) < 3:
            continue
        code = str(cells[0]).strip().replace(".0", "")
        if not code.isdigit() or len(code) < 4:
            continue
        group_raw = str(cells[1]).strip()
        score = parse_min_score(cells[2])
        if score is None or not group_raw:
            continue
        school, group_name, group_info = _split_school_group(group_raw)
        if not school:
            continue
        rows.append(
            AdmissionRow(
                province=artifact.province,
                year=artifact.year,
                track=track,
                schoolName=school,
                minScore=score,
                batch=batch_name,
                groupName=group_name,
                groupInfo=group_info,
                schoolCode=code[:4],
                sourceUrl=artifact.url,
            )
        )

    return ParseResult(artifact=artifact, rows=rows, parser="xls_xlrd_jiangsu")

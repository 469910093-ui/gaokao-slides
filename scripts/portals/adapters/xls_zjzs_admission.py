"""浙江省教育考试院一段平行投档 XLS（院校+专业，含分数线与位次）。"""

from __future__ import annotations

import io

from admission_filter_lib import parse_min_score, primary_undergrad_batch
from portals.types import AdmissionRow, Artifact, ParseResult


def parse_xls_zjzs_admission(artifact: Artifact, data: bytes) -> ParseResult:
    try:
        import xlrd  # type: ignore
    except ImportError as exc:
        raise RuntimeError("需要 xlrd: pip install xlrd") from exc

    batch_name = artifact.batch or primary_undergrad_batch(artifact.province)
    track = artifact.track or "综合类"
    book = xlrd.open_workbook(file_contents=data)
    sheet = book.sheet_by_index(0)
    rows: list[AdmissionRow] = []

    for i in range(sheet.nrows):
        if sheet.ncols < 6:
            continue
        code = str(sheet.cell_value(i, 0)).strip().replace(".0", "")
        school = str(sheet.cell_value(i, 1)).strip()
        major_code = str(sheet.cell_value(i, 2)).strip().replace(".0", "")
        major = str(sheet.cell_value(i, 3)).strip()
        score = parse_min_score(sheet.cell_value(i, 5))
        rank_raw = sheet.cell_value(i, 6) if sheet.ncols > 6 else None
        if not code.isdigit() or code in ("学校代号",):
            continue
        if not school or score is None:
            continue
        rank = None
        try:
            rank = int(float(rank_raw)) if rank_raw not in (None, "") else None
        except (TypeError, ValueError):
            rank = None
        rows.append(
            AdmissionRow(
                province=artifact.province,
                year=artifact.year,
                track=track,
                schoolName=school,
                minScore=score,
                minRank=rank,
                batch=batch_name,
                groupName=major[:40] if major else major_code,
                groupInfo=major,
                schoolCode=code,
                sourceUrl=artifact.url,
            )
        )

    return ParseResult(artifact=artifact, rows=rows, parser="xls_zjzs")

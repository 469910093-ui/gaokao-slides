"""贵州省招生考试院 PDF 投档表（院校+专业，末列为投档最低分与位次）。"""

from __future__ import annotations

import re

from admission_filter_lib import primary_undergrad_batch
from portals.adapters.pdf_admission import extract_pdf_text
from portals.types import AdmissionRow, Artifact, ParseResult

_LINE_RE = re.compile(
    r"^\d+\s+(\d{4})\s+(.+?)\s+(\d{3})\s+(.+?)\s+一般统考生"
    r"(?:\s+\d+){0,2}\s+(\d{3})\s+(\d+)\s*$"
)


def parse_pdf_guizhou_admission(artifact: Artifact, data: bytes) -> ParseResult:
    batch_name = artifact.batch or primary_undergrad_batch(artifact.province)
    track = artifact.track or "物理类"
    text = extract_pdf_text(data)
    rows: list[AdmissionRow] = []

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        m = _LINE_RE.match(line)
        if not m:
            continue
        code, school, major_code, major, score_s, rank_s = m.groups()
        score = int(score_s)
        if not (200 <= score <= 750):
            continue
        try:
            rank = int(rank_s)
        except ValueError:
            rank = None
        rows.append(
            AdmissionRow(
                province=artifact.province,
                year=artifact.year,
                track=track,
                schoolName=school.strip(),
                minScore=score,
                minRank=rank,
                batch=batch_name,
                groupName=major[:40],
                groupInfo=major.strip(),
                schoolCode=code,
                sourceUrl=artifact.url,
            )
        )

    return ParseResult(artifact=artifact, rows=rows, parser="pdf_guizhou")

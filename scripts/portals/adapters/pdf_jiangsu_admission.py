"""解析江苏考试院 PDF 投档线（2025 起 PDF 格式）。"""
from __future__ import annotations

import re
from typing import Any

from admission_filter_lib import parse_min_score, primary_undergrad_batch
from portals.types import AdmissionRow, Artifact, ParseResult

def _parse_line(line: str) -> AdmissionRow | None:
    line = re.sub(r"[■□◆\u25a0]", "", line)
    line = re.sub(r"\s+", " ", line.strip())
    if not line or line.startswith("院校") or "代号" in line or len(line) < 12:
        return None
    m = re.match(r"^(\d{4})\s+(.+)$", line)
    if not m:
        return None
    code, rest = m.group(1), m.group(2)
    gm = re.search(r"(\d{1,2})专业组(?:[（(]([^）)]*)[）)])?", rest)
    if not gm:
        return None
    school = rest[: gm.start()].strip()
    group_no = gm.group(1)
    group_info = (gm.group(2) or "").strip()
    after = rest[gm.end() :]
    scores = [int(x) for x in re.findall(r"\b(\d{2,3})\b", after)]
    score = None
    for s in scores:
        if s >= 400:
            score = s
            break
    if score is None or not school:
        return None
    return AdmissionRow(
        province="江苏",
        year=0,
        track="",
        schoolName=school,
        minScore=score,
        batch="",
        groupName=f"（{group_no}）",
        groupInfo=group_info,
        schoolCode=code[:4],
        sourceUrl="",
    )


def parse_pdf_jiangsu_admission(artifact: Artifact, data: bytes) -> ParseResult:
    try:
        import pdfplumber  # type: ignore
    except ImportError as exc:
        raise RuntimeError("需要 pdfplumber: pip install pdfplumber") from exc

    batch_name = artifact.batch or primary_undergrad_batch(artifact.province)
    track = artifact.track or "物理类"
    rows: list[AdmissionRow] = []

    import io

    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            for raw in text.splitlines():
                row = _parse_line(raw)
                if row is None:
                    continue
                row.province = artifact.province
                row.year = artifact.year
                row.track = track
                row.batch = batch_name
                row.sourceUrl = artifact.url
                rows.append(row)

    return ParseResult(artifact=artifact, rows=rows, parser="pdf_jiangsu")

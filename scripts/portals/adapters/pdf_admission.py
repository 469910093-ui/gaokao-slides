"""PDF 投档表解析。"""

from __future__ import annotations

import io
import re
from typing import Any

from admission_filter_lib import primary_undergrad_batch
from portals.types import AdmissionRow, Artifact, ParseResult

_LINE_RE = re.compile(
    r"^\s*(\d+)\s+(\d{4})\s+(.+?)\s+(\d{2})\s+(.+?)\s+(\d{3})\b"
)


def _parse_pdf_text_lines(
    text: str,
    *,
    province: str,
    year: int,
    track: str,
    batch: str | None,
    source_url: str,
) -> list[AdmissionRow]:
    batch_name = batch or primary_undergrad_batch(province)
    rows: list[AdmissionRow] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("序号"):
            continue
        m = _LINE_RE.match(line)
        if not m:
            # 北京 PDF 常见：序号 code 校名 组号 选科 分数
            parts = line.split()
            if len(parts) < 6 or not parts[0].isdigit():
                continue
            try:
                score = int(parts[5])
            except ValueError:
                continue
            if not (250 <= score <= 750):
                continue
            school_name = parts[2]
            if school_name.isdigit():
                continue
            rows.append(
                AdmissionRow(
                    province=province,
                    year=year,
                    track=track,
                    schoolName=school_name,
                    minScore=score,
                    batch=batch_name,
                    groupName=f"（{parts[3]}）",
                    groupInfo=parts[4],
                    schoolCode=parts[1],
                    sourceUrl=source_url,
                )
            )
            continue
        seq, code, school, grp, info, score_s = m.groups()
        score = int(score_s)
        if not (250 <= score <= 750):
            continue
        rows.append(
            AdmissionRow(
                province=province,
                year=year,
                track=track,
                schoolName=school.strip(),
                minScore=score,
                batch=batch_name,
                groupName=f"（{grp}）",
                groupInfo=info.strip(),
                schoolCode=code,
                sourceUrl=source_url,
            )
        )
    return rows


def extract_pdf_text(data: bytes) -> str:
    try:
        import pdfplumber  # type: ignore
    except ImportError as exc:
        raise RuntimeError("需要 pdfplumber: pip install pdfplumber") from exc
    chunks: list[str] = []
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for page in pdf.pages:
            chunks.append(page.extract_text() or "")
    return "\n".join(chunks)


def parse_pdf_admission(artifact: Artifact, data: bytes) -> ParseResult:
    text = extract_pdf_text(data)
    track = artifact.track or "综合类"
    rows = _parse_pdf_text_lines(
        text,
        province=artifact.province,
        year=artifact.year,
        track=track,
        batch=artifact.batch,
        source_url=artifact.url,
    )
    return ParseResult(artifact=artifact, rows=rows, parser="pdf_text_lines")

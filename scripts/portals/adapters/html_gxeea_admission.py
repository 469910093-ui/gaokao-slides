"""广西招生考试院 HTML 投档表（院校代码+专业组+投档线）。"""

from __future__ import annotations

from bs4 import BeautifulSoup

from admission_filter_lib import parse_min_score, primary_undergrad_batch
from portals.types import AdmissionRow, Artifact, ParseResult


def parse_html_gxeea_admission(artifact: Artifact, html: str) -> ParseResult:
    batch_name = artifact.batch or primary_undergrad_batch(artifact.province)
    track = artifact.track or "物理类"
    soup = BeautifulSoup(html, "html.parser")
    rows: list[AdmissionRow] = []

    for tr in soup.find_all("tr"):
        cells = [c.get_text(strip=True) for c in tr.find_all("td")]
        if len(cells) < 4:
            continue
        code, school, group, score_raw = cells[0], cells[1], cells[2], cells[3]
        if not code.isdigit() or code == "院校代码":
            continue
        if not school or school.isdigit():
            continue
        score = parse_min_score(score_raw)
        if score is None:
            continue
        note = cells[4] if len(cells) > 4 else ""
        rows.append(
            AdmissionRow(
                province=artifact.province,
                year=artifact.year,
                track=track,
                schoolName=school,
                minScore=score,
                batch=batch_name,
                groupName=f"专业组{group}",
                groupInfo=note,
                schoolCode=code,
                sourceUrl=artifact.url,
            )
        )

    return ParseResult(artifact=artifact, rows=rows, parser="html_gxeea")

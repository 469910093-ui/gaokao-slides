"""上海市教育考试院本科普通批 PDF 投档线（含 580 分及以上封顶行）。"""

from __future__ import annotations

import io
import re

from admission_filter_lib import primary_undergrad_batch
from portals.adapters.pdf_admission import extract_pdf_text
from portals.types import AdmissionRow, Artifact, ParseResult

# 10302 同济大学(02) 576 243 ...
_SCORE_LINE = re.compile(
    r"(\d{5})\s+([\u4e00-\u9fffA-Za-z（）()·\-\d]+?\(\d{2}\))\s+(\d{3})\b"
)
_CAP_LINE = re.compile(
    r"(\d{5})\s+([\u4e00-\u9fffA-Za-z（）()·\-\d]+?\(\d{2}\))\s+580分及以上"
)


def _clean_pdf_noise(text: str) -> str:
    # 页眉水印拆字：考/育/教/院/市/海/试/上 等单字行
    lines: list[str] = []
    for raw in text.splitlines():
        s = raw.strip()
        if len(s) <= 1 and s in "考育教院市海试上":
            continue
        lines.append(s)
    return "\n".join(lines)


def parse_shmeea_pdf_admission(artifact: Artifact, data: bytes) -> ParseResult:
    batch_name = artifact.batch or primary_undergrad_batch(artifact.province)
    track = artifact.track or "综合类"
    text = _clean_pdf_noise(extract_pdf_text(data))
    flat = re.sub(r"\s+", " ", text)
    rows: list[AdmissionRow] = []
    seen: set[str] = set()

    for m in _SCORE_LINE.finditer(flat):
        code, group_label, score_s = m.groups()
        score = int(score_s)
        if not (400 <= score <= 750):
            continue
        school = re.sub(r"\(\d{2}\)$", "", group_label).strip()
        group_num = re.search(r"\((\d{2})\)$", group_label)
        group_name = f"（{group_num.group(1)}）" if group_num else group_label
        key = f"{code}:{score}"
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            AdmissionRow(
                province=artifact.province,
                year=artifact.year,
                track=track,
                schoolName=school,
                minScore=score,
                batch=batch_name,
                groupName=group_name,
                schoolCode=code[:5],
                sourceUrl=artifact.url,
            )
        )

    for m in _CAP_LINE.finditer(flat):
        code, group_label = m.groups()
        school = re.sub(r"\(\d{2}\)$", "", group_label).strip()
        group_num = re.search(r"\((\d{2})\)$", group_label)
        group_name = f"（{group_num.group(1)}）" if group_num else group_label
        key = f"{code}:580cap"
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            AdmissionRow(
                province=artifact.province,
                year=artifact.year,
                track=track,
                schoolName=school,
                minScore=580,
                batch=batch_name,
                groupName=group_name,
                groupInfo="580分及以上",
                schoolCode=code[:5],
                sourceUrl=artifact.url,
            )
        )

    return ParseResult(artifact=artifact, rows=rows, parser="shmeea_pdf")

"""河南教育考试院 datacenter 投档统计页 HTML 解析。"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from admission_filter_lib import parse_min_score, primary_undergrad_batch
from portals.types import AdmissionRow, Artifact, ParseResult

_CJK_RE = re.compile(r"[\u4e00-\u9fff]{2,}")


def _clean_school(raw: str) -> str:
    text = (raw or "").strip()
    text = re.sub(r"\(\d+\)$", "", text)
    return text.strip()


def parse_haeea_datacenter_html(artifact: Artifact, html: str) -> ParseResult:
    batch_name = artifact.batch or primary_undergrad_batch(artifact.province)
    track = artifact.track or "物理类"
    soup = BeautifulSoup(html, "html.parser")
    rows: list[AdmissionRow] = []

    for table in soup.find_all("table"):
        for tr in table.find_all("tr"):
            cells = [c.get_text(strip=True) for c in tr.find_all(["td", "th"])]
            if len(cells) < 3:
                continue
            # 院校代号 | 院校名称 | 计划数 | 投档最低分 | ...
            code = cells[0].replace(".0", "")
            if not re.fullmatch(r"\d{4}", code):
                continue
            school = ""
            score = None
            for c in cells[1:]:
                if not school and _CJK_RE.search(c) and "院校" not in c:
                    school = _clean_school(c)
                    continue
                if score is None:
                    score = parse_min_score(c)
            if not school:
                for c in cells[1:]:
                    if _CJK_RE.search(c):
                        school = _clean_school(c)
                        break
            if score is None:
                for c in reversed(cells):
                    s = parse_min_score(c)
                    if s is not None and s >= 150:
                        score = s
                        break
            if not school or score is None:
                continue
            rows.append(
                AdmissionRow(
                    province=artifact.province,
                    year=artifact.year,
                    track=track,
                    schoolName=school,
                    minScore=score,
                    batch=batch_name,
                    schoolCode=code,
                    sourceUrl=artifact.url,
                )
            )

    # GridView 无 table 时：按行文本模式
    if not rows:
        for tr in soup.find_all("tr"):
            tds = tr.find_all("td")
            if len(tds) < 4:
                continue
            texts = [t.get_text(strip=True) for t in tds]
            if not re.fullmatch(r"\d{4}", texts[0]):
                continue
            school = next((t for t in texts if _CJK_RE.search(t) and len(t) >= 2), "")
            nums = [parse_min_score(t) for t in texts]
            nums = [n for n in nums if n is not None and n >= 200]
            if not school or not nums:
                continue
            rows.append(
                AdmissionRow(
                    province=artifact.province,
                    year=artifact.year,
                    track=track,
                    schoolName=_clean_school(school),
                    minScore=min(nums),
                    batch=batch_name,
                    schoolCode=texts[0],
                    sourceUrl=artifact.url,
                )
            )

    return ParseResult(artifact=artifact, rows=rows, parser="haeea_datacenter_html")

"""陕西招生考试信息网 sneac HTML 投档统计表。"""
from __future__ import annotations

from bs4 import BeautifulSoup

from admission_filter_lib import parse_min_score, primary_undergrad_batch
from portals.types import AdmissionRow, Artifact, ParseResult


def _score_col_index(cells: list[str]) -> int | None:
    """表头含「最低分」列；否则倒数第二列常为投档最低分。"""
    for i, c in enumerate(cells):
        if "最低分" in c:
            return i
    if len(cells) >= 8:
        return 6
    if len(cells) >= 4:
        return len(cells) - 2
    return None


def parse_html_sneac_admission(artifact: Artifact, html: str) -> ParseResult:
    batch_name = artifact.batch or primary_undergrad_batch(artifact.province)
    track = artifact.track or "物理类"
    soup = BeautifulSoup(html, "html.parser")
    rows: list[AdmissionRow] = []
    score_idx: int | None = None

    for tr in soup.find_all("tr"):
        cells = [c.get_text(strip=True) for c in tr.find_all("td")]
        if not cells:
            continue
        if any("最低分" in c for c in cells):
            score_idx = _score_col_index(cells)
            continue
        if score_idx is None:
            score_idx = _score_col_index(cells)
        if score_idx is None or len(cells) <= score_idx:
            continue

        # 2024: 序号|科类|院校代号|院校名称|计划|投档人数|最低分|最低位次
        # 2025: 可能含院校专业组列，代号列位置略异
        code = ""
        school = ""
        if len(cells) >= 4 and cells[2].isdigit():
            code, school = cells[2], cells[3]
        elif len(cells) >= 3 and cells[1].isdigit():
            code, school = cells[1], cells[2]
        elif len(cells) >= 2 and cells[0].isdigit():
            code, school = cells[0], cells[1]

        if not code.isdigit() or len(code) < 3:
            continue
        if not school or school in ("院校名称", "科类"):
            continue

        score = parse_min_score(cells[score_idx])
        if score is None:
            continue

        rank_idx = score_idx + 1 if score_idx + 1 < len(cells) else None
        min_rank = None
        if rank_idx is not None:
            try:
                r = int(cells[rank_idx].replace(",", ""))
                if r > 0:
                    min_rank = r
            except ValueError:
                pass

        group_name = ""
        group_info = ""
        if len(cells) >= 6 and not cells[2].isdigit() and "专业组" in cells[2]:
            group_name = cells[2]
            school = cells[3] if len(cells) > 3 else school

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
                minRank=min_rank,
                sourceUrl=artifact.url,
            )
        )

    return ParseResult(artifact=artifact, rows=rows, parser="html_sneac")

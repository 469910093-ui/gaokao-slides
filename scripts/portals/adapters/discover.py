"""公告页链接发现。"""

from __future__ import annotations

import re
from typing import Iterable
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from portals.types import Artifact, ArtifactKind, DataKind

ADMISSION_KW = re.compile(
    r"投档|录取投档|平行志愿|院校投档|最低投档|投档线|投档分数"
)
SEGMENT_KW = re.compile(r"一分一段|成绩分布|分数分布|位次")
YEAR_RE = re.compile(r"(20\d{2})")
ATTACH_RE = re.compile(r"\.(pdf|xlsx?|xls|zip)$", re.I)


def classify_kind(url: str) -> ArtifactKind:
    low = url.lower()
    if low.endswith(".pdf"):
        return "pdf"
    if low.endswith(".xlsx"):
        return "xlsx"
    if low.endswith(".xls"):
        return "xls"
    if low.endswith(".zip"):
        return "zip"
    if low.endswith((".html", ".htm", ".shtml")):
        return "html"
    return "unknown"


def discover_from_html(
    html: str,
    *,
    province: str,
    base_url: str,
    default_year: int,
    sections: Iterable[str] | None = None,
) -> list[Artifact]:
    soup = BeautifulSoup(html, "html.parser")
    out: list[Artifact] = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        title = (a.get_text() or "").strip()
        href = a["href"].strip()
        if not title and not href:
            continue
        full = urljoin(base_url, href)
        if full in seen:
            continue
        is_adm = bool(ADMISSION_KW.search(title) or ADMISSION_KW.search(href))
        is_seg = bool(SEGMENT_KW.search(title))
        if not is_adm and not is_seg and not ATTACH_RE.search(href):
            continue
        if sections and not any(s in title for s in sections):
            # 仍保留强匹配投档关键词
            if not is_adm:
                continue
        seen.add(full)
        ym = YEAR_RE.search(title) or YEAR_RE.search(href)
        year = int(ym.group(1)) if ym else default_year
        data_kind: DataKind = "segments" if is_seg and not is_adm else "admissions"
        out.append(
            Artifact(
                province=province,
                year=year,
                title=title,
                url=full,
                kind=classify_kind(full),
                data_kind=data_kind,
                source_page=base_url,
            )
        )
    return out

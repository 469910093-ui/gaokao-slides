"""贵州省招生考试院官方投档解析器（本科批 PDF）。"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urljoin

from admission_filter_lib import PROVINCE_EXAM_PORTALS, primary_undergrad_batch
from portals.adapters.pdf_guizhou_admission import parse_pdf_guizhou_admission
from portals.base import ProvincePortalParser
from portals.fetch import fetch_text
from portals.types import Artifact, ParseResult

KNOWN_PAGES: dict[int, list[dict[str, Any]]] = {
    2025: [
        {
            "title": "贵州省2025年高考普通类本科批平行志愿投档情况",
            "page": "http://zsksy.guizhou.gov.cn/ygpt/tdqk/202507/t20250722_88320425.html",
        },
    ],
}


def _track_from_pdf_title(title: str) -> str:
    if "历史" in title:
        return "历史类"
    if "物理" in title:
        return "物理类"
    return "物理类"


def _pdfs_from_page(page: str, year: int, batch: str) -> list[Artifact]:
    html = fetch_text(page)
    base = page.rsplit("/", 1)[0] + "/"
    arts: list[Artifact] = []
    for m in re.finditer(r'href="([^"]+\.pdf)"[^>]*>([^<]*)', html, flags=re.I):
        href, title = m.group(1), (m.group(2) or "").strip()
        if "首选科目" not in title and "物理" not in title and "历史" not in title:
            # 附件名可能为空，稍后按顺序推断
            pass
        url = urljoin(base, href)
        arts.append(
            Artifact(
                province="贵州",
                year=year,
                title=title or "贵州省本科批平行志愿投档情况",
                url=url,
                kind="pdf",
                data_kind="admissions",
                track=_track_from_pdf_title(title),
                batch=batch,
                source_page=page,
            )
        )
    if len(arts) == 2:
        if arts[0].track == arts[1].track:
            arts[0].track = "物理类"
            arts[1].track = "历史类"
    return arts


class GuizhouPortalParser(ProvincePortalParser):
    province = "贵州"
    portal_url = PROVINCE_EXAM_PORTALS["贵州"]
    implementation = "full"

    def discover(self, year: int) -> list[Artifact]:
        batch = primary_undergrad_batch(self.province)
        found: dict[str, Artifact] = {}
        for spec in KNOWN_PAGES.get(year, []):
            try:
                for art in _pdfs_from_page(spec["page"], year, batch):
                    if "专科" in art.title or "征集" in art.title:
                        continue
                    art.title = spec.get("title", art.title) + f"（{art.track}）"
                    found[art.url] = art
            except Exception:
                continue
        return list(found.values())

    def parse(self, artifact: Artifact, raw: bytes | str) -> ParseResult:
        data = raw if isinstance(raw, bytes) else raw.encode("utf-8")
        return parse_pdf_guizhou_admission(artifact, data)

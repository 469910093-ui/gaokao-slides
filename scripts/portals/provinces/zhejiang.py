"""浙江省教育考试院官方投档解析器（一段平行投档 XLS）。"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urljoin

from admission_filter_lib import PROVINCE_EXAM_PORTALS, primary_undergrad_batch
from portals.adapters.discover import classify_kind
from portals.adapters.xls_zjzs_admission import parse_xls_zjzs_admission
from portals.base import ProvincePortalParser
from portals.fetch import fetch_text
from portals.types import Artifact, ParseResult

KNOWN_PAGES: dict[int, list[dict[str, Any]]] = {
    2024: [
        {
            "title": "浙江省2024年普通高校招生普通类第一段平行投档分数线表",
            "page": "https://www.zjzs.net/art/2024/7/21/art_45_9899.html",
        },
    ],
    2025: [
        {
            "title": "浙江省2025年普通高校招生普通类第一段平行投档分数线表",
            "page": "https://www.zjzs.net/art/2025/7/21/art_45_11467.html",
        },
    ],
}


def _xls_url_from_page(page: str) -> str | None:
    html = fetch_text(page)
    m = re.search(r'href="(/module/download/downfile\.jsp[^"]+)"', html)
    if not m:
        return None
    return urljoin("https://www.zjzs.net/", m.group(1))


class ZhejiangPortalParser(ProvincePortalParser):
    province = "浙江"
    portal_url = PROVINCE_EXAM_PORTALS["浙江"]
    implementation = "full"

    def discover(self, year: int) -> list[Artifact]:
        batch = primary_undergrad_batch(self.province)
        arts: list[Artifact] = []
        for spec in KNOWN_PAGES.get(year, []):
            page = spec["page"]
            try:
                xls_url = _xls_url_from_page(page)
            except Exception:
                continue
            if not xls_url:
                continue
            arts.append(
                Artifact(
                    province=self.province,
                    year=year,
                    title=spec["title"],
                    url=xls_url,
                    kind=classify_kind(xls_url),
                    data_kind="admissions",
                    track="综合类",
                    batch=batch,
                    source_page=page,
                )
            )
        return arts

    def parse(self, artifact: Artifact, raw: bytes | str) -> ParseResult:
        data = raw if isinstance(raw, bytes) else raw.encode("utf-8")
        return parse_xls_zjzs_admission(artifact, data)

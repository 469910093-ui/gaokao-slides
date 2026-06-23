"""北京教育考试院官方投档解析器（HTML + PDF）。"""

from __future__ import annotations

import re
from typing import Any

from admission_filter_lib import PROVINCE_EXAM_PORTALS, primary_undergrad_batch
from portals.adapters.discover import discover_from_html
from portals.adapters.html_admission import parse_html_admission
from portals.adapters.pdf_admission import parse_pdf_admission
from portals.base import ProvincePortalParser
from portals.fetch import fetch_text
from portals.types import Artifact, ParseResult

# 已人工核对的官方公告（优先于自动发现）
KNOWN_ARTIFACTS: dict[int, list[dict[str, Any]]] = {
    2023: [
        {
            "title": "2023年北京市高招本科普通批录取投档线",
            "url": "https://www.bjeea.cn/html/gkgz/tzgg/2023/0717/84120.html",
            "kind": "html",
        },
    ],
    2024: [
        {
            "title": "2024年北京市高招本科普通批录取投档线",
            "url": "https://www.bjeea.cn/html/gkgz/tzgg/2024/0720/85632.html",
            "kind": "html",
        },
    ],
    2025: [
        {
            "title": "2025年北京市高招本科普通批录取投档线",
            "url": "https://www.bjeea.cn/uploads/soft/250720/178-250H0201058.pdf",
            "kind": "pdf",
        },
    ],
}

LISTING_PAGES = [
    "https://www.bjeea.cn/html/gkgz/tzgg/",
    "https://www.bjeea.cn/html/gkgz/tzgg/2025/",
    "https://www.bjeea.cn/html/gkgz/tzgg/2024/",
    "https://www.bjeea.cn/html/gkgz/tzgg/2023/",
]


class BeijingPortalParser(ProvincePortalParser):
    province = "北京"
    portal_url = PROVINCE_EXAM_PORTALS["北京"]
    implementation = "full"

    def discover(self, year: int) -> list[Artifact]:
        batch = primary_undergrad_batch(self.province)
        found: dict[str, Artifact] = {}

        for spec in KNOWN_ARTIFACTS.get(year, []):
            art = Artifact(
                province=self.province,
                year=year,
                title=spec["title"],
                url=spec["url"],
                kind=spec["kind"],
                data_kind="admissions",
                track="综合类",
                batch=batch,
            )
            found[art.url] = art

        for page in LISTING_PAGES:
            if str(year) not in page and page.endswith("/tzgg/"):
                pass
            try:
                html = fetch_text(page)
            except Exception:
                continue
            for art in discover_from_html(
                html,
                province=self.province,
                base_url=page,
                default_year=year,
                sections=("本科普通批", "投档线", "投档"),
            ):
                if art.year != year:
                    ym = re.search(str(year), art.title)
                    if not ym:
                        continue
                if "本科普通批" not in art.title and "投档" not in art.title:
                    continue
                art.track = "综合类"
                art.batch = batch
                found[art.url] = art

        return list(found.values())

    def parse(self, artifact: Artifact, raw: bytes | str) -> ParseResult:
        if artifact.kind == "pdf":
            data = raw if isinstance(raw, bytes) else raw.encode("utf-8")
            return parse_pdf_admission(artifact, data)
        html = raw if isinstance(raw, str) else raw.decode("utf-8", errors="replace")
        return parse_html_admission(artifact, html)

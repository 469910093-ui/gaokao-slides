"""江苏省教育考试院官方投档解析器（招考信息页 + XLS）。"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urljoin

from admission_filter_lib import PROVINCE_EXAM_PORTALS, primary_undergrad_batch
from portals.adapters.discover import classify_kind
from portals.adapters.html_admission import parse_html_admission
from portals.adapters.pdf_admission import parse_pdf_admission
from portals.adapters.xls_admission import parse_xls_admission
from portals.adapters.xlsx_admission import parse_xlsx_admission
from portals.base import ProvincePortalParser
from portals.fetch import fetch_text
from portals.types import Artifact, ParseResult

# 人工核对：招考信息页 → XLS 附件
KNOWN_PAGES: dict[int, list[dict[str, Any]]] = {
    2023: [
        {"page": "https://www.jseea.cn/webfile/index/index_zkxx/2023-07-18/7086888854866628608.html"},
    ],
    2024: [
        {
            "page": "https://www.jseea.cn/webfile/index/index_zkxx/2024-07-18/7219509116052443136.html",
            "files": [
                {
                    "title": "江苏省2024年普通类本科批次平行志愿投档线（物理等科目类）",
                    "url": "https://www.jseea.cn/webfile/upload/2024/07-18/11-00-490856-746889704.xls",
                    "track": "物理类",
                },
                {
                    "title": "江苏省2024年普通类本科批次平行志愿投档线（历史等科目类）",
                    "url": "https://www.jseea.cn/webfile/upload/2024/07-18/09-11-430408314109108.xls",
                    "track": "历史类",
                },
            ],
        },
    ],
}

LISTING = [
    "https://www.jseea.cn/webfile/index/index_zkxx/",
]


def _track_from_title(title: str) -> str:
    if "历史" in title:
        return "历史类"
    if "物理" in title:
        return "物理类"
    return "物理类"


def _artifacts_from_page(year: int, page: str, batch: str) -> list[Artifact]:
    html = fetch_text(page)
    found: dict[str, Artifact] = {}
    for m in re.finditer(
        r'href=["\']([^"\']+\.xls[x]?)["\'][^>]*>([^<]+)',
        html,
        flags=re.I,
    ):
        href, title = m.group(1), m.group(2).strip()
        if "投档" not in title and "本科批次" not in title:
            continue
        if "提前" in title or "征求" in title:
            continue
        url = urljoin(page, href)
        found[url] = Artifact(
            province="江苏",
            year=year,
            title=title,
            url=url,
            kind=classify_kind(url),
            data_kind="admissions",
            track=_track_from_title(title),
            batch=batch,
            source_page=page,
        )
    return list(found.values())


class JiangsuPortalParser(ProvincePortalParser):
    province = "江苏"
    portal_url = PROVINCE_EXAM_PORTALS["江苏"]
    implementation = "full"

    def discover(self, year: int) -> list[Artifact]:
        batch = primary_undergrad_batch(self.province)
        found: dict[str, Artifact] = {}

        for block in KNOWN_PAGES.get(year, []):
            page = block["page"]
            for spec in block.get("files", []):
                art = Artifact(
                    province=self.province,
                    year=year,
                    title=spec["title"],
                    url=spec["url"],
                    kind=classify_kind(spec["url"]),
                    data_kind="admissions",
                    track=spec["track"],
                    batch=batch,
                    source_page=page,
                )
                found[art.url] = art
            if not block.get("files"):
                for art in _artifacts_from_page(year, page, batch):
                    found[art.url] = art

        for page in LISTING:
            try:
                html = fetch_text(page)
            except Exception:
                continue
            for m in re.finditer(
                r'href=["\']([^"\']+\.xls[x]?)["\'][^>]*>([^<]*投档[^<]*)',
                html,
                flags=re.I,
            ):
                href, title = m.group(1), m.group(2).strip()
                if str(year) not in title and str(year) not in href:
                    continue
                url = urljoin(page, href)
                track = "历史类" if "历史" in title else "物理类" if "物理" in title else "物理类"
                found[url] = Artifact(
                    province=self.province,
                    year=year,
                    title=title,
                    url=url,
                    kind=classify_kind(url),
                    data_kind="admissions",
                    track=track,
                    batch=batch,
                    source_page=page,
                )

        return list(found.values())

    def parse(self, artifact: Artifact, raw: bytes | str) -> ParseResult:
        if artifact.kind == "xls":
            data = raw if isinstance(raw, bytes) else raw.encode("utf-8")
            return parse_xls_admission(artifact, data)
        if artifact.kind == "xlsx":
            data = raw if isinstance(raw, bytes) else raw.encode("utf-8")
            return parse_xlsx_admission(artifact, data)
        if artifact.kind == "pdf":
            data = raw if isinstance(raw, bytes) else raw.encode("utf-8")
            return parse_pdf_admission(artifact, data)
        html = raw if isinstance(raw, str) else raw.decode("utf-8", errors="replace")
        return parse_html_admission(artifact, html)

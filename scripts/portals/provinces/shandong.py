"""山东省教育招生考试院官方投档解析器（sdzk.cn XLS + 位次换算）。"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urljoin

from admission_filter_lib import PROVINCE_EXAM_PORTALS, primary_undergrad_batch
from portals.adapters.discover import classify_kind
from portals.adapters.xls_sdzk_admission import parse_xls_sdzk_admission
from portals.base import ProvincePortalParser
from portals.fetch import fetch_text
from portals.types import Artifact, ParseResult

KNOWN_PAGES: dict[int, list[dict[str, Any]]] = {
    2023: [
        {
            "page": "https://www.sdzk.cn/NewsInfo.aspx?NewsID=6279",
            "title": "山东省2023年普通类常规批第1次志愿投档情况表",
            "files": [
                {
                    "title": "山东省2023年普通类常规批第1次志愿投档情况表",
                    "url": "https://www.sdzk.cn/Floadup/file/20230719/6382538122655052185031609.xls",
                },
            ],
        },
    ],
    2024: [
        {
            "page": "https://www.sdzk.cn/NewsInfo.aspx?NewsID=6656",
            "title": "山东省2024年普通类常规批第1次志愿投档情况表",
            "files": [
                {
                    "title": "山东省2024年普通类常规批第1次志愿投档情况表",
                    "url": "https://www.sdzk.cn/Floadup/file/20240719/6385700532268895241675882.xls",
                },
            ],
        },
    ],
    2025: [
        {
            "page": "https://www.sdzk.cn/NewsInfo.aspx?NewsID=6996",
            "title": "山东省2025年普通类常规批第1次志愿投档情况表",
            "files": [
                {
                    "title": "山东省2025年普通类常规批第1次志愿投档情况表",
                    "url": "https://www.sdzk.cn/Floadup/file/20250719/6388855130412530367357143.xls",
                },
            ],
        },
    ],
}

LISTING = "https://www.sdzk.cn/NewsInfo.aspx?ClassID=1067"


def _artifacts_from_page(year: int, page: str, batch: str, default_title: str = "") -> list[Artifact]:
    html = fetch_text(page)
    found: dict[str, Artifact] = {}
    for m in re.finditer(
        r'href=["\']([^"\']+\.xls)["\'][^>]*>([^<]*)',
        html,
        flags=re.I,
    ):
        href, title = m.group(1), (m.group(2) or default_title).strip()
        if "投档" not in title and "投档" not in html[max(0, m.start() - 200) : m.end() + 200]:
            continue
        if "第2次" in title or "第3次" in title or "征集" in title:
            continue
        url = urljoin(page, href)
        found[url] = Artifact(
            province="山东",
            year=year,
            title=title or default_title or f"山东省{year}年普通类常规批投档",
            url=url,
            kind=classify_kind(url),
            data_kind="admissions",
            track="综合类",
            batch=batch,
            source_page=page,
        )
    return list(found.values())


class ShandongPortalParser(ProvincePortalParser):
    province = "山东"
    portal_url = PROVINCE_EXAM_PORTALS["山东"]
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
                    track="综合类",
                    batch=batch,
                    source_page=page,
                )
                found[art.url] = art
            if not block.get("files"):
                for art in _artifacts_from_page(year, page, batch, block.get("title", "")):
                    found[art.url] = art

        try:
            html = fetch_text(LISTING)
            for m in re.finditer(
                r'NewsInfo\.aspx\?NewsID=(\d+)[^"\']*["\'][^>]*>([^<]*常规批[^<]*第1次[^<]*投档[^<]*)',
                html,
                flags=re.I,
            ):
                nid, title = m.group(1), m.group(2).strip()
                if str(year) not in title:
                    continue
                page = f"https://www.sdzk.cn/NewsInfo.aspx?NewsID={nid}"
                for art in _artifacts_from_page(year, page, batch, title):
                    found[art.url] = art
        except Exception:
            pass

        return list(found.values())

    def parse(self, artifact: Artifact, raw: bytes | str) -> ParseResult:
        data = raw if isinstance(raw, bytes) else raw.encode("utf-8")
        return parse_xls_sdzk_admission(artifact, data)

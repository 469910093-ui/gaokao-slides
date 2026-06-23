"""河北省教育考试院官方投档解析器（本科批平行志愿 XLSX）。"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urljoin

from admission_filter_lib import PROVINCE_EXAM_PORTALS, primary_undergrad_batch
from portals.adapters.discover import classify_kind
from portals.adapters.xlsx_hebei_admission import parse_xlsx_hebei_admission
from portals.base import ProvincePortalParser
from portals.fetch import fetch_text
from portals.types import Artifact, ParseResult

KNOWN_FILES: dict[int, list[dict[str, Any]]] = {
    2023: [
        {
            "title": "河北省2023年本科批历史科目组合平行志愿投档情况统计",
            "url": "http://file.hebeea.edu.cn/files/article/2023/07/20230725082954_71.xlsx",
            "track": "历史类",
        },
        {
            "title": "河北省2023年本科批物理科目组合平行志愿投档情况统计",
            "url": "http://file.hebeea.edu.cn/files/article/2023/07/20230725082954_586.xlsx",
            "track": "物理类",
        },
    ],
    2024: [
        {
            "title": "河北省2024年本科批历史科目组合平行志愿投档情况统计",
            "url": "http://file.hebeea.edu.cn/files/article/2024/07/20240722163024_223.xlsx",
            "track": "历史类",
        },
        {
            "title": "河北省2024年本科批物理科目组合平行志愿投档情况统计",
            "url": "http://file.hebeea.edu.cn/files/article/2024/07/20240722163024_933.xlsx",
            "track": "物理类",
        },
    ],
}

LISTING = "http://www.hebeea.edu.cn/html/zxgg/index.html"


def _track_from_title(title: str) -> str:
    if "历史" in title:
        return "历史类"
    if "物理" in title:
        return "物理类"
    return "物理类"


def _artifacts_from_listing(year: int, batch: str) -> list[Artifact]:
    html = fetch_text(LISTING)
    found: dict[str, Artifact] = {}
    for m in re.finditer(
        r'href=["\']([^"\']+\.xlsx?)["\'][^>]*>([^<]+)',
        html,
        flags=re.I,
    ):
        href, title = m.group(1), m.group(2).strip()
        if str(year) not in title and str(year) not in href:
            continue
        if "投档" not in title and "平行志愿" not in title:
            continue
        if "专科" in title or "征集" in title:
            continue
        url = urljoin(LISTING, href)
        found[url] = Artifact(
            province="河北",
            year=year,
            title=title,
            url=url,
            kind=classify_kind(url),
            data_kind="admissions",
            track=_track_from_title(title),
            batch=batch,
            source_page=LISTING,
        )
    return list(found.values())


class HebeiPortalParser(ProvincePortalParser):
    province = "河北"
    portal_url = PROVINCE_EXAM_PORTALS["河北"]
    implementation = "full"

    def discover(self, year: int) -> list[Artifact]:
        batch = primary_undergrad_batch(self.province)
        found: dict[str, Artifact] = {}

        for spec in KNOWN_FILES.get(year, []):
            art = Artifact(
                province=self.province,
                year=year,
                title=spec["title"],
                url=spec["url"],
                kind=classify_kind(spec["url"]),
                data_kind="admissions",
                track=spec["track"],
                batch=batch,
                source_page=LISTING,
            )
            found[art.url] = art

        try:
            for art in _artifacts_from_listing(year, batch):
                found[art.url] = art
        except Exception:
            pass

        return list(found.values())

    def parse(self, artifact: Artifact, raw: bytes | str) -> ParseResult:
        data = raw if isinstance(raw, bytes) else raw.encode("utf-8")
        return parse_xlsx_hebei_admission(artifact, data)

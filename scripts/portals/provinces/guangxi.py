"""广西招生考试院官方投档解析器（HTML 表）。"""

from __future__ import annotations

import re
from typing import Any

from admission_filter_lib import PROVINCE_EXAM_PORTALS, primary_undergrad_batch
from portals.adapters.html_gxeea_admission import parse_html_gxeea_admission
from portals.base import ProvincePortalParser
from portals.fetch import fetch_text
from portals.types import Artifact, ParseResult

KNOWN_ARTIFACTS: dict[int, list[dict[str, Any]]] = {
    2024: [
        {
            "title": "2024年本科普通批第一次平行投档最低分（首选物理科目组）",
            "url": "https://www.gxeea.cn/view/content_1013_30534.htm",
            "track": "物理类",
        },
        {
            "title": "2024年本科普通批第一次平行投档最低分（首选历史科目组）",
            "url": "https://www.gxeea.cn/view/content_1013_30535.htm",
            "track": "历史类",
        },
    ],
    2025: [
        {
            "title": "2025年本科普通批院校专业组投档最低分数线（首选物理科目组）",
            "url": "https://www.gxeea.cn/view/content_1013_31850.htm",
            "track": "物理类",
        },
        {
            "title": "2025年本科普通批院校专业组投档最低分数线（首选历史科目组）",
            "url": "https://www.gxeea.cn/view/content_1013_31851.htm",
            "track": "历史类",
        },
    ],
}


def _discover_from_home(year: int, batch: str) -> list[Artifact]:
    html = fetch_text("https://www.gxeea.cn/")
    found: dict[str, Artifact] = {}
    for m in re.finditer(
        r'href="(/view/content_\d+_\d+\.htm)"[^>]*>([^<]{8,120})',
        html,
    ):
        href, title = m.group(1), m.group(2).strip()
        if str(year) not in title:
            continue
        if "本科普通批" not in title or "投档" not in title:
            continue
        if "第一次" not in title:
            continue
        track = "物理类" if "物理" in title else "历史类" if "历史" in title else "物理类"
        url = "https://www.gxeea.cn" + href
        found[url] = Artifact(
            province="广西",
            year=year,
            title=title,
            url=url,
            kind="html",
            data_kind="admissions",
            track=track,
            batch=batch,
        )
    return list(found.values())


class GuangxiPortalParser(ProvincePortalParser):
    province = "广西"
    portal_url = PROVINCE_EXAM_PORTALS["广西"]
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
                kind="html",
                data_kind="admissions",
                track=spec["track"],
                batch=batch,
            )
            found[art.url] = art
        try:
            for art in _discover_from_home(year, batch):
                found[art.url] = art
        except Exception:
            pass
        return list(found.values())

    def parse(self, artifact: Artifact, raw: bytes | str) -> ParseResult:
        html = raw if isinstance(raw, str) else raw.decode("utf-8", errors="replace")
        return parse_html_gxeea_admission(artifact, html)

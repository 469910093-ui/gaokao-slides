"""湖南省教育考试院官方投档解析器（本科批 XLSX，需浏览器拉取）。"""

from __future__ import annotations

from typing import Any

from admission_filter_lib import PROVINCE_EXAM_PORTALS, primary_undergrad_batch
from portals.adapters.xlsx_hunan_admission import parse_xlsx_hunan_admission
from portals.base import ProvincePortalParser
from portals.types import Artifact, ParseResult

KNOWN_ARTIFACTS: dict[int, list[dict[str, Any]]] = {
    2024: [
        {
            "title": "湖南省2024年普通高校招生本科批(普通类)第一次投档分数线",
            "url": "https://www.hneeb.cn/hnxxg/741/742/2024072001.xlsx",
            "track": "综合类",
        },
    ],
    2025: [
        {
            "title": "湖南省2025年普通高校招生本科批(普通类)第一次投档分数线",
            "url": "https://www.hneeb.cn/hnxxg/741/742/2025072001.xlsx",
            "track": "综合类",
        },
    ],
}


class HunanPortalParser(ProvincePortalParser):
    province = "湖南"
    portal_url = PROVINCE_EXAM_PORTALS["湖南"]
    implementation = "full"

    def discover(self, year: int) -> list[Artifact]:
        batch = primary_undergrad_batch(self.province)
        arts: list[Artifact] = []
        for spec in KNOWN_ARTIFACTS.get(year, []):
            arts.append(
                Artifact(
                    province=self.province,
                    year=year,
                    title=spec["title"],
                    url=spec["url"],
                    kind="xlsx",
                    data_kind="admissions",
                    track=spec["track"],
                    batch=batch,
                )
            )
        return arts

    def parse(self, artifact: Artifact, raw: bytes | str) -> ParseResult:
        data = raw if isinstance(raw, bytes) else raw.encode("utf-8")
        return parse_xlsx_hunan_admission(artifact, data)

    def fetch_and_parse(self, artifact: Artifact) -> ParseResult:
        from portals.fetch_hneeb import fetch_hneeb_bytes

        raw = fetch_hneeb_bytes(artifact.url)
        return self.parse(artifact, raw)

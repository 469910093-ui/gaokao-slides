"""上海市教育考试院官方投档解析器。"""

from __future__ import annotations

from typing import Any

from admission_filter_lib import PROVINCE_EXAM_PORTALS, primary_undergrad_batch
from portals.adapters.shmeea_pdf_admission import parse_shmeea_pdf_admission
from portals.base import ProvincePortalParser
from portals.types import Artifact, ParseResult

KNOWN_ARTIFACTS: dict[int, list[dict[str, Any]]] = {
    2024: [
        {
            "title": "2024年上海市普通高校招生本科普通批次平行志愿院校专业组投档分数线",
            "url": "https://www.shmeea.edu.cn/download/20240719/198.pdf",
            "kind": "pdf",
        },
    ],
    2025: [
        {
            "title": "2025年上海市普通高校招生本科普通批次平行志愿院校专业组投档分数线",
            "url": "https://www.shmeea.edu.cn/download/20250719/186.pdf",
            "kind": "pdf",
        },
    ],
}


class ShanghaiPortalParser(ProvincePortalParser):
    province = "上海"
    portal_url = PROVINCE_EXAM_PORTALS["上海"]
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
                    kind=spec["kind"],
                    data_kind="admissions",
                    track="综合类",
                    batch=batch,
                )
            )
        return arts

    def parse(self, artifact: Artifact, raw: bytes | str) -> ParseResult:
        data = raw if isinstance(raw, bytes) else raw.encode("utf-8")
        return parse_shmeea_pdf_admission(artifact, data)

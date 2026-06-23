"""河南省教育考试院 datacenter 投档解析器（Playwright + 人工 Cookie）。"""

from __future__ import annotations

from typing import Any

from admission_filter_lib import PROVINCE_EXAM_PORTALS, primary_undergrad_batch
from portals.adapters.haeea_datacenter_admission import parse_haeea_datacenter_html
from portals.base import ProvincePortalParser
from portals.types import Artifact, ParseResult

DATACENTER_BASE = "https://datacenter.haeea.cn/PagePZQuery/ShowPZTDTJ.aspx"

# pc=1 本科批；kl=1 历史类，kl=5 物理类
KNOWN_QUERIES: dict[int, list[dict[str, Any]]] = {
    2024: [
        {"kl": 5, "track": "物理类", "title": "河南省2024年本科批物理类投档统计"},
        {"kl": 1, "track": "历史类", "title": "河南省2024年本科批历史类投档统计"},
    ],
    2025: [
        {"kl": 5, "track": "物理类", "title": "河南省2025年本科批物理类投档统计"},
        {"kl": 1, "track": "历史类", "title": "河南省2025年本科批历史类投档统计"},
    ],
}


def _artifact_url(year: int, kl: int) -> str:
    return f"{DATACENTER_BASE}?yearTip={year}&pc=1&kl={kl}"


class HenanPortalParser(ProvincePortalParser):
    province = "河南"
    portal_url = PROVINCE_EXAM_PORTALS["河南"]
    implementation = "full"

    def discover(self, year: int) -> list[Artifact]:
        batch = primary_undergrad_batch(self.province)
        found: dict[str, Artifact] = {}
        for spec in KNOWN_QUERIES.get(year, []):
            url = _artifact_url(year, spec["kl"])
            found[url] = Artifact(
                province=self.province,
                year=year,
                title=spec["title"],
                url=url,
                kind="html",
                data_kind="admissions",
                track=spec["track"],
                batch=batch,
                source_page="https://gaokao.haedu.cn/",
            )
        return list(found.values())

    def fetch_and_parse(self, artifact: Artifact) -> ParseResult:
        import sys
        from pathlib import Path

        scripts = Path(__file__).resolve().parents[2]
        if str(scripts) not in sys.path:
            sys.path.insert(0, str(scripts))
        from fetch_haeea import fetch_haeea_datacenter_html

        html = fetch_haeea_datacenter_html(artifact.url)
        return self.parse(artifact, html)

    def parse(self, artifact: Artifact, raw: bytes | str) -> ParseResult:
        html = raw if isinstance(raw, str) else raw.decode("utf-8", errors="replace")
        return parse_haeea_datacenter_html(artifact, html)

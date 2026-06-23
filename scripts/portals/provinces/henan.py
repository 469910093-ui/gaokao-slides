"""河南省教育考试院 datacenter 投档解析器（Playwright + 人工 Cookie）。"""

from __future__ import annotations

from typing import Any

from admission_filter_lib import PROVINCE_EXAM_PORTALS, primary_undergrad_batch
from portals.adapters.haeea_datacenter_admission import parse_haeea_datacenter_html
from portals.base import ProvincePortalParser
from portals.types import Artifact, ParseResult

# 投档统计 API（勿与录取查询 ShowPZLQ.aspx 混淆）
DATACENTER_BASE = "https://datacenter.haeea.cn/PagePZQuery/ShowPZTDTJ.aspx"

# 可在浏览器正常打开的官方索引页（内含 datacenter 链接）
OFFICIAL_INDEX: dict[int, str] = {
    2024: "https://gaokao.haedu.cn/501/552/2024/0721/135558.html",
    2025: "https://gaokao.haedu.cn/517/518/519/2026/0131/150719.html",
}

# pc=1：2024=本科一批，2025=本科批；kl=1 历史类，kl=5 物理类
KNOWN_QUERIES: dict[int, list[dict[str, Any]]] = {
    2024: [
        {"kl": 5, "track": "物理类", "title": "河南省2024年本科一批物理类平行投档分数线"},
        {"kl": 1, "track": "历史类", "title": "河南省2024年本科一批历史类平行投档分数线"},
    ],
    2025: [
        {"kl": 5, "track": "物理类", "title": "河南省2025年本科批物理类平行投档分数线"},
        {"kl": 1, "track": "历史类", "title": "河南省2025年本科批历史类平行投档分数线"},
    ],
}


def _artifact_url(year: int, kl: int) -> str:
    return f"{DATACENTER_BASE}?yearTip={year}&pc=1&kl={kl}"


def _batch_for_year(year: int) -> str:
    return "本科一批" if year <= 2024 else primary_undergrad_batch("河南")


class HenanPortalParser(ProvincePortalParser):
    province = "河南"
    portal_url = PROVINCE_EXAM_PORTALS["河南"]
    implementation = "full"

    def discover(self, year: int) -> list[Artifact]:
        batch = _batch_for_year(year)
        index_page = OFFICIAL_INDEX.get(year, "https://gaokao.haedu.cn/")
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
                source_page=index_page,
            )
        return list(found.values())

    def fetch_and_parse(self, artifact: Artifact) -> ParseResult:
        import sys
        from pathlib import Path

        scripts = Path(__file__).resolve().parents[2]
        if str(scripts) not in sys.path:
            sys.path.insert(0, str(scripts))
        from fetch_haeea import fetch_haeea_datacenter_html

        html = fetch_haeea_datacenter_html(
            artifact.url,
            referer=artifact.source_page or "https://gaokao.haedu.cn/",
        )
        return self.parse(artifact, html)

    def parse(self, artifact: Artifact, raw: bytes | str) -> ParseResult:
        html = raw if isinstance(raw, str) else raw.decode("utf-8", errors="replace")
        return parse_haeea_datacenter_html(artifact, html)

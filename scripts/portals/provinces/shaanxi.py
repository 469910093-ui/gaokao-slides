"""陕西省教育考试院官方投档解析器（sneac HTML 统计表）。"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urljoin

from admission_filter_lib import PROVINCE_EXAM_PORTALS, primary_undergrad_batch
from portals.adapters.discover import classify_kind
from portals.adapters.html_sneac_admission import parse_html_sneac_admission
from portals.base import ProvincePortalParser
from portals.fetch import fetch_text
from portals.types import Artifact, ParseResult

# 公告页 → 嵌入 htm 投档表（info/1374 或 info/1019）
KNOWN_ARTIFACTS: dict[int, list[dict[str, Any]]] = {
    2023: [
        {
            "title": "2023年陕西省普通高校招生本科一批录取正式投档（文史）",
            "url": "https://www.sneac.com/htm/2023/2023YBZS-WS.html",
            "track": "历史类",
            "batch": "本科一批",
        },
        {
            "title": "2023年陕西省普通高校招生本科一批录取正式投档（理工）",
            "url": "https://www.sneac.com/htm/2023/2023YBZS-LG.html",
            "track": "物理类",
            "batch": "本科一批",
        },
        {
            "title": "2023年陕西省普通高校招生本科二批录取正式投档（文史）",
            "url": "https://www.sneac.com/htm/2023/2023EBZS-WS.html",
            "track": "历史类",
            "batch": "本科二批",
        },
        {
            "title": "2023年陕西省普通高校招生本科二批录取正式投档（理工）",
            "url": "https://www.sneac.com/htm/2023/2023EBZS-LG.html",
            "track": "物理类",
            "batch": "本科二批",
        },
    ],
    2024: [
        {
            "title": "2024年陕西省普通高校招生本科一批录取正式投档（文史）",
            "url": "https://www.sneac.com/htm/2024/1BZS-WS.html",
            "track": "历史类",
            "batch": "本科一批",
            "source_page": "https://www.sneac.com/info/1374/18309.htm",
        },
        {
            "title": "2024年陕西省普通高校招生本科一批录取正式投档（理工）",
            "url": "https://www.sneac.com/htm/2024/1BZS-LG.html",
            "track": "物理类",
            "batch": "本科一批",
            "source_page": "https://www.sneac.com/info/1374/18309.htm",
        },
        {
            "title": "2024年陕西省普通高校招生本科二批录取正式投档（文史）",
            "url": "https://www.sneac.com/htm/2024/2024EBZS-WS.html",
            "track": "历史类",
            "batch": "本科二批",
            "source_page": "https://www.sneac.com/info/1374/18307.htm",
        },
        {
            "title": "2024年陕西省普通高校招生本科二批录取正式投档（理工）",
            "url": "https://www.sneac.com/htm/2024/2024EBZS-LG.html",
            "track": "物理类",
            "batch": "本科二批",
            "source_page": "https://www.sneac.com/info/1374/18307.htm",
        },
    ],
}

LNSJ_PAGE = "https://www.sneac.com/zt/xgkxsfwpt/lnsj.htm"


def _track_from_path(path: str) -> str:
    upper = path.upper()
    if "WS" in upper or "LS" in upper or "历史" in path or "文史" in path:
        return "历史类"
    return "物理类"


def _batch_from_title(title: str) -> str:
    if "二批" in title:
        return "本科二批"
    if "一批" in title:
        return "本科一批"
    if "本科批次" in title or "本科批" in title:
        return "本科批次"
    return primary_undergrad_batch("陕西")


def _discover_from_lnsj(year: int) -> list[Artifact]:
    html = fetch_text(LNSJ_PAGE)
    found: dict[str, Artifact] = {}
    for m in re.finditer(
        r'href="([^"]+)"[^>]*title="([^"]+)"',
        html,
        flags=re.I,
    ):
        href, title = m.group(1), m.group(2).strip()
        if str(year) not in title:
            continue
        if "投档" not in title and "正式投档" not in title:
            continue
        if "征集" in title or "专科" in title or "单招" in title:
            continue
        if "本科" not in title:
            continue
        page_url = urljoin(LNSJ_PAGE, href)
        try:
            page_html = fetch_text(page_url)
        except Exception:
            continue
        for hm in re.finditer(r'href="([^"]+\.html)"', page_html):
            hpath = hm.group(1)
            if "htm/" not in hpath:
                continue
            if "BZS" not in hpath.upper() and "BK" not in hpath.upper():
                continue
            table_url = urljoin(page_url, hpath)
            track = _track_from_path(hpath)
            batch = _batch_from_title(title)
            found[table_url] = Artifact(
                province="陕西",
                year=year,
                title=f"{title}（{track}）",
                url=table_url,
                kind=classify_kind(table_url),
                data_kind="admissions",
                track=track,
                batch=batch,
                source_page=page_url,
            )
    return list(found.values())


class ShaanxiPortalParser(ProvincePortalParser):
    province = "陕西"
    portal_url = PROVINCE_EXAM_PORTALS["陕西"]
    implementation = "full"

    def discover(self, year: int) -> list[Artifact]:
        found: dict[str, Artifact] = {}
        for spec in KNOWN_ARTIFACTS.get(year, []):
            art = Artifact(
                province=self.province,
                year=year,
                title=spec["title"],
                url=spec["url"],
                kind=classify_kind(spec["url"]),
                data_kind="admissions",
                track=spec["track"],
                batch=spec.get("batch") or primary_undergrad_batch(self.province),
                source_page=spec.get("source_page", spec["url"]),
            )
            found[art.url] = art
        for art in _discover_from_lnsj(year):
            found.setdefault(art.url, art)
        return list(found.values())

    def parse(self, artifact: Artifact, raw: bytes | str) -> ParseResult:
        html = raw if isinstance(raw, str) else raw.decode("utf-8", errors="replace")
        return parse_html_sneac_admission(artifact, html)

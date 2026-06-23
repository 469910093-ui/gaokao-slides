"""四川省教育考试院官方调档线解析器（公告页 JPG + OCR）。"""

from __future__ import annotations

import re
from typing import Any

from admission_filter_lib import PROVINCE_EXAM_PORTALS, primary_undergrad_batch
from portals.adapters.discover import classify_kind
from portals.adapters.sceea_image_admission import parse_sceea_admission_html
from portals.base import ProvincePortalParser
from portals.fetch import fetch_text
from portals.types import Artifact, ParseResult

# 本科一批/二批调档线（图片表）
KNOWN_PAGES: dict[int, list[dict[str, Any]]] = {
    2024: [
        {
            "title": "2024年普通高校招生本科一批调档线",
            "url": "https://www.sceea.cn/Html/202407/Newsdetail_3788.html",
            "batch": "本科一批",
            "track": "物理类",
        },
    ],
}


def _track_from_title(title: str) -> str:
    if "历史" in title or "文科" in title or "文史" in title:
        return "历史类"
    if "物理" in title or "理科" in title:
        return "物理类"
    return "物理类"


class SichuanPortalParser(ProvincePortalParser):
    province = "四川"
    portal_url = PROVINCE_EXAM_PORTALS["四川"]
    implementation = "full"

    def discover(self, year: int) -> list[Artifact]:
        batch_default = primary_undergrad_batch(self.province)
        found: dict[str, Artifact] = {}

        for spec in KNOWN_PAGES.get(year, []):
            art = Artifact(
                province=self.province,
                year=year,
                title=spec["title"],
                url=spec["url"],
                kind="html",
                data_kind="admissions",
                track=spec.get("track", "物理类"),
                batch=spec.get("batch", batch_default),
                source_page=spec["url"],
            )
            found[art.url] = art

        # 尝试从首页发现同 year 调档线公告
        try:
            html = fetch_text("https://www.sceea.cn/")
            for m in re.finditer(
                r'href=["\']([^"\']*Newsdetail_(\d+)\.html)["\'][^>]*>([^<]*调档线[^<]*)',
                html,
                flags=re.I,
            ):
                href, _nid, title = m.group(1), m.group(2), m.group(3).strip()
                if str(year) not in title:
                    continue
                if "专科" in title or "提前" in title:
                    continue
                url = href if href.startswith("http") else f"https://www.sceea.cn{href}"
                batch = "本科一批" if "一批" in title else "本科二批" if "二批" in title else batch_default
                found[url] = Artifact(
                    province=self.province,
                    year=year,
                    title=title,
                    url=url,
                    kind="html",
                    data_kind="admissions",
                    track=_track_from_title(title),
                    batch=batch,
                    source_page=url,
                )
        except Exception:
            pass

        return list(found.values())

    def parse(self, artifact: Artifact, raw: bytes | str) -> ParseResult:
        html = raw if isinstance(raw, str) else raw.decode("utf-8", errors="replace")
        return parse_sceea_admission_html(artifact, html)

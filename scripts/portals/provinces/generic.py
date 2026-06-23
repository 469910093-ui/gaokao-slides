"""通用考试院解析器（自动发现 + HTML/PDF/XLSX 适配）。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from admission_filter_lib import PROVINCE_EXAM_PORTALS, primary_undergrad_batch
from portals.adapters.discover import discover_from_html
from portals.adapters.html_admission import parse_beijing_style_html_table, parse_html_admission
from portals.adapters.pdf_admission import parse_pdf_admission
from portals.adapters.xlsx_admission import parse_xlsx_admission
from portals.base import ProvincePortalParser
from portals.fetch import fetch_text
from portals.types import Artifact, ParseResult
from province_tracks import tracks_for_province

REGISTRY_PATH = Path(__file__).resolve().parents[3] / "data" / "reference" / "gaokao_cn" / "portal_registry.json"


def load_registry() -> dict[str, Any]:
    if not REGISTRY_PATH.exists():
        return {"provinces": {}}
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


class GenericPortalParser(ProvincePortalParser):
    """按 registry 配置自动发现公告并尝试通用解析。"""

    implementation = "partial"

    def __init__(self, province: str, config: dict[str, Any] | None = None) -> None:
        self.province = province
        reg = load_registry().get("provinces", {}).get(province, {})
        self.config = config or reg
        self.portal_url = self.config.get("portal") or PROVINCE_EXAM_PORTALS.get(province, "")
        self.implementation = self.config.get("implementation", "stub")

    def discover(self, year: int) -> list[Artifact]:
        batch = primary_undergrad_batch(self.province)
        tracks = tracks_for_province(self.province, year)
        track = tracks[0] if tracks else "综合类"
        found: dict[str, Artifact] = {}

        for spec in self.config.get("knownArtifacts", {}).get(str(year), []):
            art = Artifact(
                province=self.province,
                year=year,
                title=spec.get("title", ""),
                url=spec["url"],
                kind=spec.get("kind", "html"),
                data_kind=spec.get("dataKind", "admissions"),
                track=spec.get("track", track),
                batch=spec.get("batch", batch),
            )
            found[art.url] = art

        for page in self.config.get("listingPages", []):
            try:
                html = fetch_text(page)
            except Exception:
                continue
            sections = tuple(self.config.get("discoverKeywords", ["投档", "平行志愿", "录取"]))
            for art in discover_from_html(
                html,
                province=self.province,
                base_url=page,
                default_year=year,
                sections=sections,
            ):
                if str(year) not in art.title and str(year) not in art.url:
                    continue
                art.track = track
                art.batch = batch
                found[art.url] = art

        return list(found.values())

    def parse(self, artifact: Artifact, raw: bytes | str) -> ParseResult:
        if artifact.kind == "pdf":
            data = raw if isinstance(raw, bytes) else raw.encode("utf-8")
            return parse_pdf_admission(artifact, data)
        if artifact.kind == "xls":
            from portals.adapters.xls_admission import parse_xls_admission

            data = raw if isinstance(raw, bytes) else raw.encode("utf-8")
            return parse_xls_admission(artifact, data)
        if artifact.kind in ("xlsx", "xls"):
            data = raw if isinstance(raw, bytes) else raw.encode("utf-8")
            return parse_xlsx_admission(artifact, data)
        html = raw if isinstance(raw, str) else raw.decode("utf-8", errors="replace")
        # 先尝试北京样式表（多数省考试院 HTML 表结构相近）
        rows = parse_beijing_style_html_table(
            html,
            province=artifact.province,
            year=artifact.year,
            track=artifact.track or "综合类",
            batch=artifact.batch,
            source_url=artifact.url,
        )
        if rows:
            return ParseResult(artifact=artifact, rows=rows, parser="html_beijing_style")
        return parse_html_admission(artifact, html)


class StubPortalParser(GenericPortalParser):
    implementation = "stub"

    def discover(self, year: int) -> list[Artifact]:
        return super().discover(year) if self.config.get("listingPages") else []

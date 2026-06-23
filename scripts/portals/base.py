"""考试院解析器基类。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from portals.types import AdmissionRow, Artifact, ParseResult


class ProvincePortalParser(ABC):
    province: str
    portal_url: str
    implementation: str = "stub"  # stub | partial | full

    @abstractmethod
    def discover(self, year: int) -> list[Artifact]:
        """发现指定年份的官方投档/一分一段公告。"""

    @abstractmethod
    def parse(self, artifact: Artifact, raw: bytes | str) -> ParseResult:
        """解析已下载资源为投档行。"""

    def fetch_and_parse(self, artifact: Artifact) -> ParseResult:
        from portals.fetch import fetch_bytes, fetch_text

        if artifact.kind in ("html", "unknown"):
            raw = fetch_text(artifact.url)
        else:
            raw = fetch_bytes(artifact.url)
        return self.parse(artifact, raw)

    def crawl_admissions(self, year: int) -> tuple[list[AdmissionRow], list[str]]:
        rows: list[AdmissionRow] = []
        errors: list[str] = []
        for art in self.discover(year):
            if art.data_kind != "admissions":
                continue
            try:
                result = self.fetch_and_parse(art)
                if result.rows:
                    rows.extend(result.rows)
                else:
                    errors.append(f"{art.url}: 0 rows ({result.parser})")
            except Exception as exc:
                errors.append(f"{art.url}: {exc}")
        return rows, errors

    def meta(self) -> dict[str, Any]:
        return {
            "province": self.province,
            "portalUrl": self.portal_url,
            "implementation": self.implementation,
        }

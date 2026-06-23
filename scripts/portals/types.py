"""考试院解析器共享类型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

ArtifactKind = Literal["html", "pdf", "xlsx", "xls", "zip", "unknown"]
DataKind = Literal["admissions", "segments", "control_lines"]


@dataclass
class Artifact:
    """考试院公告页上发现的一条可下载/可解析资源。"""

    province: str
    year: int
    title: str
    url: str
    kind: ArtifactKind
    data_kind: DataKind = "admissions"
    track: str | None = None
    batch: str | None = None
    source_page: str | None = None


@dataclass
class AdmissionRow:
    """与 scrape_gaokao_cn 归档行兼容的投档记录。"""

    province: str
    year: int
    track: str
    schoolName: str
    minScore: int
    batch: str
    groupName: str = ""
    groupInfo: str = ""
    minRank: int | None = None
    schoolCode: str = ""
    source: str = "province_exam_portal_direct"
    sourceUrl: str = ""
    level: str = "本科"
    provinceControlScore: int | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "province": self.province,
            "year": self.year,
            "track": self.track,
            "schoolName": self.schoolName,
            "minScore": self.minScore,
            "batch": self.batch,
            "groupName": self.groupName,
            "groupInfo": self.groupInfo,
            "level": self.level,
            "source": self.source,
            "sourceUrl": self.sourceUrl,
        }
        if self.minRank is not None:
            out["minRank"] = self.minRank
        if self.schoolCode:
            out["schoolCode"] = self.schoolCode
        if self.provinceControlScore is not None:
            out["provinceControlScore"] = self.provinceControlScore
        return out


@dataclass
class ParseResult:
    artifact: Artifact
    rows: list[AdmissionRow] = field(default_factory=list)
    parser: str = ""
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return len(self.rows) > 0

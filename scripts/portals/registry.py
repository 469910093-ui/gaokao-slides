"""31 省考试院解析器注册表。"""

from __future__ import annotations

from portals.base import ProvincePortalParser
from portals.provinces.beijing import BeijingPortalParser
from portals.provinces.hebei import HebeiPortalParser
from portals.provinces.jiangsu import JiangsuPortalParser
from portals.provinces.shandong import ShandongPortalParser
from portals.provinces.generic import GenericPortalParser, StubPortalParser, load_registry

_FULL: dict[str, type[ProvincePortalParser]] = {
    "北京": BeijingPortalParser,
    "江苏": JiangsuPortalParser,
    "山东": ShandongPortalParser,
    "河北": HebeiPortalParser,
}

# 已有 listing/known 配置、待逐步验收的省份
_PARTIAL_DEFAULT = GenericPortalParser


def get_parser(province: str) -> ProvincePortalParser:
    if province in _FULL:
        return _FULL[province]()
    reg = load_registry().get("provinces", {}).get(province, {})
    impl = reg.get("implementation", "stub")
    if impl == "full" and province in _FULL:
        return _FULL[province]()
    if impl in ("partial", "full") and (reg.get("listingPages") or reg.get("knownArtifacts")):
        return GenericPortalParser(province, reg)
    return StubPortalParser(province, reg)


def list_provinces() -> list[dict]:
    reg = load_registry()
    out = []
    for name, cfg in sorted(reg.get("provinces", {}).items()):
        out.append({
            "province": name,
            "implementation": cfg.get("implementation", "stub"),
            "portal": cfg.get("portal"),
            "tier": cfg.get("tier"),
        })
    return out

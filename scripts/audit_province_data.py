#!/usr/bin/env python3
"""盘点 31 省底层数据验收状态：一分一段 + 官方投档 + 冲稳保开放。"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REF = ROOT / "data" / "reference" / "gaokao_cn"
PROV_DIR = ROOT / "data" / "provinces"
OUT_JSON = ROOT / "data" / "acceptance" / "province_data_audit.json"
OUT_CSV = ROOT / "data" / "acceptance" / "province_data_audit.csv"

sys.path.insert(0, str(ROOT / "scripts"))
from province_tracks import tracks_for_province  # noqa: E402

CONF_RANK = {
    "verified": 0,
    "verified_multi_source": 0,
    "partial": 1,
    "validated_structural": 2,
    "scraped": 3,
    "structural": 3,
    "model_estimate": 4,
    "model": 4,
}


def official_inventory() -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    off: dict[str, list[str]] = defaultdict(list)
    non_off: dict[str, list[str]] = defaultdict(list)
    for path in REF.glob("admissions_*.json"):
        name = path.name
        body = name.removeprefix("admissions_").removesuffix(".json")
        if body.endswith("_official"):
            body = body.removesuffix("_official")
            is_off = True
        else:
            is_off = False
        parts = body.split("_")
        if len(parts) < 3:
            continue
        prov, year = parts[0], parts[1]
        track = "_".join(parts[2:])
        key = f"{year}/{track}"
        (off if is_off else non_off)[prov].append(key)
    return off, non_off


def segment_audit(prov: str) -> tuple[str, list[dict[str, str]]]:
    fp = PROV_DIR / f"{prov}.json"
    if not fp.exists():
        return "missing_file", []
    data = json.loads(fp.read_text(encoding="utf-8"))
    yo = data.get("years", {}).get("2025") or data.get("years", {}).get("2024") or {}
    tracks = yo.get("tracks", {})
    detail: list[dict[str, str]] = []
    for t in tracks_for_province(prov):
        td = tracks.get(t)
        if not td and t == "综合类":
            td = tracks.get("物理类") or tracks.get("历史类")
        if not td:
            detail.append({"track": t, "confidence": "no_track", "source": ""})
            continue
        detail.append({
            "track": t,
            "confidence": td.get("confidence") or "model_estimate",
            "source": td.get("source") or "",
        })
    if not detail:
        return "no_year_data", detail
    worst = max(detail, key=lambda x: CONF_RANK.get(x["confidence"], 9))["confidence"]
    return worst, detail


def main() -> None:
    manifest = json.loads((ROOT / "data/manifest.json").read_text(encoding="utf-8"))
    adm_meta_path = REF / "admission_index_meta.json"
    adm_meta = json.loads(adm_meta_path.read_text(encoding="utf-8")) if adm_meta_path.exists() else {}
    all_provs: list[str] = manifest["provinces"]
    verified_adm = set(adm_meta.get("verifiedProvinces") or [])
    official_adm = set(adm_meta.get("officialProvinces") or [])
    prov_status = adm_meta.get("provinceStatus") or {}
    off_files, non_off_files = official_inventory()

    rows: list[dict[str, object]] = []
    for prov in all_provs:
        seg_worst, seg_detail = segment_audit(prov)
        st = prov_status.get(prov, {})
        adm_code = st.get("status", "no_official_archive")
        if prov in official_adm and adm_code == "no_official_archive":
            adm_code = "unavailable"
        rows.append({
            "province": prov,
            "segment_worst_2025": seg_worst,
            "segment_tracks": seg_detail,
            "admission_verified": prov in verified_adm,
            "admission_official_archive": prov in official_adm,
            "admission_status": adm_code,
            "admission_reason": st.get("reason", ""),
            "admission_school_count": st.get("schoolCount"),
            "official_file_count": len(off_files.get(prov, [])),
            "non_official_file_count": len(non_off_files.get(prov, [])),
            "recommendation_open": prov in verified_adm,
            "overall_tier": _overall_tier(prov, seg_worst, prov in verified_adm, prov in official_adm, adm_code),
        })

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generatedAt": adm_meta.get("generatedAt"),
        "summary": {
            "total_provinces": len(all_provs),
            "admission_verified": len(verified_adm),
            "admission_official_archive": len(official_adm),
            "recommendation_closed": len(all_provs) - len(verified_adm),
            "segment_verified_or_partial": sum(
                1 for r in rows if r["segment_worst_2025"] in ("verified", "verified_multi_source", "partial")
            ),
            "segment_model_or_worse": sum(
                1 for r in rows if CONF_RANK.get(str(r["segment_worst_2025"]), 9) >= 4
            ),
        },
        "provinces": rows,
    }
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    import csv

    with OUT_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "province", "overall_tier", "recommendation_open",
                "admission_status", "admission_reason", "official_file_count",
                "segment_worst_2025", "non_official_file_count",
            ],
        )
        w.writeheader()
        for r in rows:
            w.writerow({k: r[k] for k in w.fieldnames})

    _print_report(payload, rows, verified_adm, official_adm, all_provs)
    print(f"\nWrote {OUT_JSON.relative_to(ROOT)}")
    print(f"Wrote {OUT_CSV.relative_to(ROOT)}")


def _overall_tier(
    prov: str,
    seg: str,
    adm_verified: bool,
    has_official: bool,
    adm_code: str,
) -> str:
    if adm_verified and seg in ("verified", "verified_multi_source", "partial"):
        return "L1_双验收"
    if adm_verified:
        return "L2_投档已验收_一分一段待加强"
    if has_official and adm_code == "unavailable":
        return "L3_有官方归档_索引未过"
    if has_official:
        return "L3_有官方归档"
    if seg in ("verified", "verified_multi_source", "partial"):
        return "L4_仅一分一段可信"
    if CONF_RANK.get(seg, 9) >= 4:
        return "L5_全未校验"
    return "L4_仅结构真表"


def _print_report(
    payload: dict,
    rows: list[dict],
    verified_adm: set[str],
    official_adm: set[str],
    all_provs: list[str],
) -> None:
    s = payload["summary"]
    print("=== 31 省底层数据验收盘点 ===\n")
    print(f"投档冲稳保已验收: {s['admission_verified']}/31 → {sorted(verified_adm)}")
    print(f"有 _official.json 归档: {s['admission_official_archive']}/31 → {sorted(official_adm)}")
    print(f"冲稳保关闭: {s['recommendation_closed']}/31")
    print(f"一分一段 verified/partial: {s['segment_verified_or_partial']}/31")
    print(f"一分一段 model 估算: {s['segment_model_or_worse']}/31\n")

    print("--- 分层 (overall_tier) ---")
    for tier, n in sorted(Counter(r["overall_tier"] for r in rows).items()):
        print(f"  {tier}: {n}")

    print("\n--- L1 双验收 (投档+一分一段均可信) ---")
    for r in rows:
        if r["overall_tier"] == "L1_双验收":
            print(f"  {r['province']}")

    print("\n--- L2 投档已验收但一分一段非 verified ---")
    for r in rows:
        if r["overall_tier"] == "L2_投档已验收_一分一段待加强":
            print(f"  {r['province']}: 一分一段={r['segment_worst_2025']}")

    print("\n--- L3 有官方投档归档但未进推荐索引 ---")
    for r in rows:
        if str(r["overall_tier"]).startswith("L3"):
            print(
                f"  {r['province']}: 官方文件{r['official_file_count']}个 | "
                f"{r['admission_reason'] or r['admission_status']}"
            )

    print("\n--- L5 全未校验 (无官方投档 + 一分一段 model) ---")
    for r in rows:
        if r["overall_tier"] == "L5_全未校验":
            print(f"  {r['province']}")

    print("\n--- 其余省份 (L4) ---")
    for r in rows:
        if r["overall_tier"] == "L4_仅一分一段可信":
            print(f"  {r['province']}: 一分一段={r['segment_worst_2025']}")
        elif r["overall_tier"] == "L4_仅结构真表":
            print(f"  {r['province']}: 一分一段={r['segment_worst_2025']}")


if __name__ == "__main__":
    main()

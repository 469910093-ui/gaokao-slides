"""Gaokao score-segment crawling: discovery, parsing, validation."""

from __future__ import annotations

import json
import math
import random
import re
import time
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote

import requests

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

EOL_INDEX_PAGES = [
    "https://gaokao.eol.cn/e_html/gk/gkfsd/",
    "https://gaokao.eol.cn/e_html/gk/gkfsd/2019.shtml",
    "https://gaokao.eol.cn/e_html/gk/gkfsd/2020.shtml",
    "https://gaokao.eol.cn/e_html/gk/gkfsd/2021.shtml",
    "https://gaokao.eol.cn/e_html/gk/gkfsd/2022.shtml",
    "https://gaokao.eol.cn/e_html/gk/gkfsd/2023.shtml",
    "https://gaokao.eol.cn/e_html/gk/gkfsd/2024.shtml",
    "https://gaokao.eol.cn/e_html/gk/gkfsd/2025.shtml",
]

PROVINCE_SLUG = {
    "北京": "bei_jing", "天津": "tian_jin", "河北": "he_bei", "山西": "shan_xi",
    "内蒙古": "nei_meng_gu", "辽宁": "liao_ning", "吉林": "ji_lin", "黑龙江": "hei_long_jiang",
    "上海": "shang_hai", "江苏": "jiang_su", "浙江": "zhe_jiang", "安徽": "an_hui",
    "福建": "fu_jian", "江西": "jiang_xi", "山东": "shan_dong", "河南": "he_nan",
    "湖北": "hu_bei", "湖南": "hu_nan", "广东": "guang_dong", "广西": "guang_xi",
    "海南": "hai_nan", "重庆": "chong_qing", "四川": "si_chuan", "贵州": "gui_zhou",
    "云南": "yun_nan", "西藏": "xi_zang", "陕西": "shan_xi_sheng", "甘肃": "gan_su",
    "青海": "qing_hai", "宁夏": "ning_xia", "新疆": "xin_jiang",
}
SLUG_TO_PROVINCE = {v: k for k, v in PROVINCE_SLUG.items()}
SLUG_TO_PROVINCE["nei_meng"] = "内蒙古"

TRACK_KEYWORDS = {
    "物理类": ["物理", "理科", "理工", "首选物理", "物理类", "物理等科目"],
    "历史类": ["历史", "文科", "文史", "首选历史", "历史类", "历史等科目"],
}

# Extra high-confidence URLs not always listed on index pages (verified working)
EOL_EXTRA_URLS: list[tuple[str, int, str | None, str]] = [
    ("江苏", 2024, "物理类", "https://gaokao.eol.cn/jiang_su/dongtai/202406/t20240625_2619080.shtml"),
    ("江苏", 2024, "历史类", "https://gaokao.eol.cn/jiang_su/dongtai/202406/t20240625_2619079.shtml"),
    ("四川", 2024, "物理类", "https://gaokao.eol.cn/si_chuan/dongtai/202406/t20240624_2618669.shtml"),
    ("河北", 2024, "物理类", "https://gaokao.eol.cn/he_bei/dongtai/202406/t20240625_2619073.shtml"),
    ("广东", 2024, "物理类", "https://gaokao.eol.cn/guang_dong/dongtai/202406/t20240626_2619547.shtml"),
]

# zizzs 对比分析页：提供关键分数段位次锚点（第二数据源）
ZIZZS_ANCHOR_PAGES: list[tuple[str, int, str, str]] = [
    # 2024
    ("江苏", 2024, "物理类", "https://www.zizzs.com/gk/gaokao/203076.html"),
    ("广东", 2024, "物理类", "https://www.zizzs.com/gk/gaokao/203615.html"),
    ("河南", 2024, "物理类", "https://www.zizzs.com/gk/gaokao/204234.html"),
    ("四川", 2024, "物理类", "https://www.zizzs.com/gk/gaokao/203187.html"),
    ("山东", 2024, "物理类", "https://www.zizzs.com/gk/gaokao/203064.html"),
    ("辽宁", 2024, "物理类", "https://www.zizzs.com/gk/gaokao/204554.html"),
    ("陕西", 2024, "物理类", "https://www.zizzs.com/gk/gaokao/204956.html"),
    # 2025（同页对比表取 2025 列）
    ("江苏", 2025, "物理类", "https://www.zizzs.com/gk/gaokao/203076.html"),
    ("广东", 2025, "物理类", "https://www.zizzs.com/gk/gaokao/203615.html"),
    ("河南", 2025, "物理类", "https://www.zizzs.com/gk/gaokao/204234.html"),
    ("四川", 2025, "物理类", "https://www.zizzs.com/gk/gaokao/203187.html"),
    ("山东", 2025, "物理类", "https://www.zizzs.com/gk/gaokao/203064.html"),
    ("辽宁", 2025, "物理类", "https://www.zizzs.com/gk/gaokao/204554.html"),
    ("陕西", 2025, "物理类", "https://www.zizzs.com/gk/gaokao/204956.html"),
]


@dataclass
class CatalogEntry:
    province: str
    year: int
    track: str | None
    title: str
    url: str


@dataclass
class SegmentRow:
    score: int
    count: int
    cumulative: int


@dataclass
class ScrapeResult:
    segments: list[SegmentRow]
    total: int
    source: str
    url: str
    title: str = ""
    anchors: dict[str, Any] = field(default_factory=dict)
    structural: dict[str, Any] = field(default_factory=dict)
    cross_checks: list[dict[str, Any]] = field(default_factory=list)
    confidence: str = "unknown"
    confidence_score: float = 0.0


def normalize_url(url: str) -> str:
    url = url.strip()
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("/"):
        return "https://gaokao.eol.cn" + url
    return url


def detect_track(title: str) -> str | None:
    for track, keys in TRACK_KEYWORDS.items():
        if any(k in title for k in keys):
            return track
    return None


def detect_year(title: str, url: str) -> int | None:
    m = re.search(r"(20\d{2})年", title or "")
    if m:
        return int(m.group(1))
    m = re.search(r"/dongtai/(20\d{2})\d{2}/", url)
    if m:
        return int(m.group(1))
    return None


def discover_eol_catalog(session: requests.Session) -> list[CatalogEntry]:
    seen: set[str] = set()
    entries: list[CatalogEntry] = []

    def add(url: str, title: str = "", prov: str | None = None, year: int | None = None, track: str | None = None):
        url = normalize_url(url)
        if url in seen or "/dongtai/20" not in url:
            return
        seen.add(url)
        slug_m = re.search(r"gaokao\.eol\.cn/([a-z0-9_]+)/dongtai/", url)
        if not slug_m:
            return
        province = prov or SLUG_TO_PROVINCE.get(slug_m.group(1))
        if not province:
            return
        yr = year or detect_year(title, url)
        if not yr or yr < 2014 or yr > 2026:
            return
        tr = track if track is not None else detect_track(title)
        entries.append(CatalogEntry(province, yr, tr, title, url))

    for page in EOL_INDEX_PAGES:
        try:
            r = session.get(page, headers=HEADERS, timeout=30)
            r.encoding = "utf-8"
            text = r.text
        except Exception as exc:  # noqa: BLE001
            print(f"  [warn] index fetch failed {page}: {exc}")
            continue
        for url in re.findall(r'href="([^"]+)"', text):
            if "/dongtai/20" not in url or not url.endswith(".shtml"):
                continue
            full = normalize_url(url)
            idx = text.find(url if not url.startswith("http") else url.split("gaokao.eol.cn")[-1])
            snippet = text[max(0, idx - 220): idx + 140] if idx >= 0 else ""
            title_m = re.search(r">([^<>]{4,160})</a>", snippet)
            title = title_m.group(1).strip() if title_m else ""
            add(full, title)

    for prov, year, track, url in EOL_EXTRA_URLS:
        add(url, "", prov, year, track)

    return entries


def parse_eol_table(html: str) -> tuple[list[SegmentRow], int]:
    rows = re.findall(
        r"<tr[^>]*>\s*<td[^>]*>([^<]+)</td>\s*<td[^>]*>(\d+)</td>\s*<td[^>]*>(\d+)</td>",
        html,
        flags=re.I,
    )
    if len(rows) < 10:
        # Excel-export style cells
        rows = []
        score_cells = re.findall(
            r'<td[^>]*x:num="(\d{2,4})"[^>]*>.*?(\d{2,4}).*?</td>\s*'
            r'<td[^>]*x:num="(\d+)"[^>]*>.*?</td>\s*'
            r'<td[^>]*x:num="(\d+)"[^>]*>',
            html,
            flags=re.I | re.S,
        )
        for score_s, _, count_s, cum_s in score_cells:
            rows.append((score_s, count_s, cum_s))

    segments: list[SegmentRow] = []
    total = 0
    for score_raw, count_s, cumulative_s in rows:
        score_raw = str(score_raw).strip().replace("\xa0", "")
        count = int(count_s)
        cumulative = int(cumulative_s)
        total = max(total, cumulative)
        if "-" in score_raw:
            parts = re.findall(r"\d+", score_raw)
            if len(parts) < 2:
                continue
            hi, lo = int(parts[0]), int(parts[1])
            if hi < lo:
                hi, lo = lo, hi
            segments.append(SegmentRow(hi, count, cumulative))
            if hi - lo > 1:
                per = max(1, count // max(1, hi - lo))
                for s in range(hi - 1, lo - 1, -1):
                    segments.append(SegmentRow(s, per, cumulative))
        elif re.fullmatch(r"\d{2,4}", score_raw):
            segments.append(SegmentRow(int(score_raw), count, cumulative))
        else:
            continue

    by_score: dict[int, SegmentRow] = {}
    for seg in segments:
        if seg.score not in by_score or seg.cumulative < by_score[seg.score].cumulative:
            by_score[seg.score] = seg
    ordered = sorted(by_score.values(), key=lambda x: x.score, reverse=True)
    if ordered:
        total = max(total, ordered[-1].cumulative)
    return ordered, total


def parse_eol_anchors(html: str) -> dict[str, Any]:
    text = " ".join(
        x for x in [
            re.search(r'<meta name="description" content="([^"]+)"', html, re.I).group(1)
            if re.search(r'<meta name="description" content="([^"]+)"', html, re.I) else "",
            re.search(r"<title>([^<]+)</title>", html, re.I).group(1)
            if re.search(r"<title>([^<]+)</title>", html, re.I) else "",
            re.search(r'<div class=TRS_Editor>(.*?)</div>', html, re.I | re.S).group(1)
            if re.search(r'<div class=TRS_Editor>(.*?)</div>', html, re.I | re.S) else "",
        ]
    )
    text = re.sub(r"<[^>]+>", " ", text)
    anchors: dict[str, Any] = {}

    for track_label, pattern in [
        ("物理类", r"物理类(\d{2,7})人超本科线"),
        ("历史类", r"历史类(\d{2,7})人超本科线"),
        ("物理类", r"物理类(\d{2,7})人过本科线"),
        ("历史类", r"历史类(\d{2,7})人过本科线"),
        (None, r"(\d{2,7})人超本科线"),
        (None, r"(\d{2,7})人过本科线"),
    ]:
        m = re.search(pattern, text)
        if m:
            anchors.setdefault("undergrad_over_count", {})[track_label or "general"] = int(m.group(1))

    line_patterns = [
        ("物理本科线", r"物理本科线(\d{3})分"),
        ("历史本科线", r"历史本科线(\d{3})分"),
        ("物理特招线", r"物理特招线(\d{3})分"),
        ("历史特招线", r"历史特招线(\d{3})分"),
        ("本科线", r"本科线(\d{3})分"),
        ("特招线", r"特招线(\d{3})分"),
    ]
    for key, pat in line_patterns:
        m = re.search(pat, text)
        if m:
            anchors[f"{key}_score"] = int(m.group(1))

    for pat in [
        r"共(\d{2,7})人",
        r"累计(\d{2,7})人",
        r"考生(\d{2,7})人",
        r"总计(\d{2,7})人",
    ]:
        m = re.search(pat, text)
        if m:
            anchors["total_stated"] = int(m.group(1))
            break
    return anchors


def parse_zizzs_anchors(html: str, year: int) -> dict[int, int]:
    """Parse zizzs comparison tables: score -> cumulative rank for a given year column."""
    anchors: dict[int, int] = {}
    plain = re.sub(r"<[^>]+>", " ", html)
    plain = re.sub(r"\s+", " ", plain)

    def add(score: int, rank: int) -> None:
        if 100 <= score <= 900 and rank > 0:
            anchors.setdefault(score, rank)

    # e.g. 2024年600分累计23,461人 / 600分对应位次207,063名
    for score_s, rank_s in re.findall(
        rf"{year}\s*年\s*(\d{{3}})\s*分[^0-9]{{0,24}}([\d,]+)\s*(?:人|名)",
        plain,
    ):
        add(int(score_s), int(rank_s.replace(",", "")))
    for score_s, rank_s in re.findall(
        rf"(\d{{3}})\s*分[^0-9]{{0,24}}{year}\s*年[^0-9]{{0,24}}([\d,]+)\s*(?:人|名)",
        plain,
    ):
        add(int(score_s), int(rank_s.replace(",", "")))
    for score_s, rank_s in re.findall(
        rf"(\d{{3}})\s*分累计[^0-9]{{0,12}}([\d,]+)\s*人",
        plain,
    ):
        add(int(score_s), int(rank_s.replace(",", "")))

    # Markdown / HTML table rows: | 600分 | 30,768名 | 34,888名 |
    rows = re.findall(r"\|[^\n|]+\|", plain)
    year_col: int | None = None
    for row in rows:
        if str(year) in row and ("年" in row or "累计" in row):
            cells = [c.strip() for c in row.split("|") if c.strip()]
            for idx, cell in enumerate(cells):
                if str(year) in cell:
                    year_col = idx
                    break
            if year_col is not None:
                break
    for row in rows:
        if "+" in row:
            continue
        score_m = re.search(r"(\d{3})\s*分", row)
        if not score_m:
            continue
        cells = [c.strip() for c in row.split("|") if c.strip()]
        if len(cells) < 2:
            continue
        col = year_col if year_col is not None and year_col < len(cells) else 1
        rank_m = re.search(r"([\d,]+)\s*(?:名|人)", cells[col])
        if rank_m:
            add(int(score_m.group(1)), int(rank_m.group(1).replace(",", "")))

    # Legacy HTML table cells (skip 650+ top-rank rows)
    for score_label, rank_s in re.findall(
        r"<td[^>]*>\s*<strong>([^<]+)</strong>\s*</td>\s*<td>([^<]+)</td>",
        html,
        flags=re.I,
    ):
        if "+" in score_label:
            continue
        if "分" not in score_label:
            continue
        score = int(re.sub(r"\D", "", score_label) or "0")
        rank_txt = rank_s.replace(",", "").replace("名", "").replace("以内", "").strip()
        if rank_txt.isdigit():
            add(score, int(rank_txt))
    return anchors


def cumulative_at(segments: list[SegmentRow], score: int) -> int | None:
    if not segments:
        return None
    exact = next((s.cumulative for s in segments if s.score == score), None)
    if exact is not None:
        return exact
    lower = [s for s in segments if s.score < score]
    if lower:
        return max(lower, key=lambda s: s.score).cumulative
    higher = [s for s in segments if s.score > score]
    if higher:
        seg = min(higher, key=lambda s: s.score)
        return seg.cumulative + seg.count
    return None


def validate_structural(segments: list[SegmentRow], total: int) -> dict[str, Any]:
    issues: list[str] = []
    if len(segments) < 15:
        issues.append("too_few_rows")
    prev_cum = 0
    mono_violations = 0
    for seg in sorted(segments, key=lambda s: s.score, reverse=True):
        if seg.cumulative < prev_cum:
            mono_violations += 1
            if mono_violations <= 3:
                issues.append(f"non_monotonic_at_{seg.score}")
        if seg.count < 0:
            issues.append(f"negative_count_at_{seg.score}")
        prev_cum = seg.cumulative
    if mono_violations > 8:
        issues.append("many_non_monotonic")
    if total <= 0:
        issues.append("invalid_total")
    elif prev_cum > 0 and abs(prev_cum - total) / total > 0.08:
        issues.append("total_mismatch")
    return {"ok": not issues, "issues": issues}


def compare_anchor(
    name: str,
    expected: int,
    actual: int | None,
    tolerance: float = 0.03,
) -> dict[str, Any]:
    if actual is None:
        return {"name": name, "ok": False, "expected": expected, "actual": None, "reason": "missing"}
    diff = abs(actual - expected) / max(expected, 1)
    return {
        "name": name,
        "ok": diff <= tolerance,
        "expected": expected,
        "actual": actual,
        "diff_pct": round(diff * 100, 2),
    }


def cross_validate(
    segments: list[SegmentRow],
    track: str | None,
    eol_anchors: dict[str, Any],
    zizzs_anchors: dict[int, int] | None,
) -> tuple[list[dict[str, Any]], str, float]:
    checks: list[dict[str, Any]] = []

    # Source 2: eol page text/meta anchors
    undergrad_score = None
    if track == "物理类":
        undergrad_score = eol_anchors.get("物理本科线_score") or eol_anchors.get("本科线_score")
    elif track == "历史类":
        undergrad_score = eol_anchors.get("历史本科线_score") or eol_anchors.get("本科线_score")
    else:
        undergrad_score = eol_anchors.get("本科线_score")

    over = eol_anchors.get("undergrad_over_count", {})
    expected_over = None
    if track and track in over:
        expected_over = over[track]
    elif over:
        expected_over = next(iter(over.values()))

    if undergrad_score and expected_over:
        actual = cumulative_at(segments, undergrad_score)
        checks.append(compare_anchor("eol_text_undergrad_cumulative", expected_over, actual, tolerance=0.02))

    total_stated = eol_anchors.get("total_stated")
    if total_stated and segments:
        bottom_cum = max(s.cumulative for s in segments)
        checks.append(compare_anchor("eol_text_total_candidates", total_stated, bottom_cum, tolerance=0.05))

    # Source 3: zizzs anchor ranks (pick up to 4 well-spaced scores)
    if zizzs_anchors:
        picked = sorted(zizzs_anchors.items(), key=lambda x: x[0], reverse=True)
        if len(picked) > 4:
            step = max(1, len(picked) // 4)
            picked = picked[::step][:4]
        for score, expected_rank in picked:
            actual = cumulative_at(segments, score)
            checks.append(compare_anchor(f"zizzs_rank_at_{score}", expected_rank, actual, tolerance=0.04))

    passed = [c for c in checks if c.get("ok")]
    if not checks:
        return checks, "table_only", 0.55
    ratio = len(passed) / len(checks)
    if ratio >= 0.99 and len(checks) >= 2:
        return checks, "verified_multi_source", 0.95
    if ratio >= 0.99:
        return checks, "verified", 0.9
    if ratio >= 0.75:
        return checks, "partially_verified", 0.8
    if ratio >= 0.5:
        return checks, "partially_verified", 0.7
    if ratio > 0:
        return checks, "conflict", 0.45
    return checks, "failed_validation", 0.2


def fetch_url(session: requests.Session, url: str) -> str | None:
    try:
        r = session.get(url, headers=HEADERS, timeout=30)
        r.encoding = r.apparent_encoding or "utf-8"
        r.raise_for_status()
        return r.text
    except Exception as exc:  # noqa: BLE001
        print(f"  [warn] fetch failed {url}: {exc}")
        return None


def scrape_eol_entry(session: requests.Session, entry: CatalogEntry) -> ScrapeResult | None:
    html = fetch_url(session, entry.url)
    if not html:
        return None
    segments, total = parse_eol_table(html)
    if len(segments) < 15:
        return None
    title_m = re.search(r"<title>([^<]+)</title>", html, re.I)
    title = entry.title or (title_m.group(1).strip() if title_m else "")
    anchors = parse_eol_anchors(html)
    structural = validate_structural(segments, total)
    return ScrapeResult(
        segments=segments,
        total=total,
        source="eol.cn",
        url=entry.url,
        title=title,
        anchors=anchors,
        structural=structural,
    )


def load_zizzs_anchors(session: requests.Session) -> dict[tuple[str, int, str], dict[int, int]]:
    cache: dict[tuple[str, int, str], dict[int, int]] = {}
    for prov, year, track, url in ZIZZS_ANCHOR_PAGES:
        html = fetch_url(session, url)
        if not html:
            continue
        # 203076 is 2024-2025 compare; take 2024 column first column after score
        parsed = parse_zizzs_anchors(html, year)
        if parsed:
            cache[(prov, year, track)] = parsed
        time.sleep(0.4)
    return cache


def pick_best_entry(entries: list[CatalogEntry]) -> CatalogEntry | None:
    if not entries:
        return None
    def score(e: CatalogEntry) -> tuple[int, int]:
        track_bonus = 1 if e.track else 0
        title_bonus = 1 if e.title and "一分一段" in e.title else 0
        return (track_bonus + title_bonus, e.year)
    return sorted(entries, key=score, reverse=True)[0]

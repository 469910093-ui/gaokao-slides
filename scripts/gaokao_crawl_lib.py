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
    "https://www.eol.cn/html/gk/gkfsd/index.shtml",
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
    "物理类": [
        "物理", "理科", "理工", "首选物理", "物理类", "物理等科目",
        "理科类", "理工类", "物理科目",
    ],
    "历史类": [
        "历史", "文科", "文史", "首选历史", "历史类", "历史等科目",
        "文科类", "文史类", "历史科目",
    ],
}

# 新高考综合改革省份：一分一段常不分文理，或仅公布「普通类/综合」
COMBINED_TRACK_HINTS = (
    "综合改革", "3+3", "3+1+2", "不分文理", "不再区分文理科",
    "普通类", "综合类", "统一划线",
)

# 2025 年起已实行「院校+专业」或综合分段的省份（两科类共用同一张表时取 general）
COMBINED_SEGMENT_PROVINCES = {
    "北京", "天津", "上海", "浙江", "山东", "海南",
    "河北", "辽宁", "江苏", "福建", "湖北", "湖南", "广东", "重庆",
    "安徽", "江西", "广西", "贵州", "吉林", "黑龙江", "甘肃",
}

# Extra high-confidence URLs not always listed on index pages (verified working)
EOL_EXTRA_URLS: list[tuple[str, int, str | None, str]] = [
    ("江苏", 2024, "物理类", "https://gaokao.eol.cn/jiang_su/dongtai/202406/t20240625_2619080.shtml"),
    ("江苏", 2024, "历史类", "https://gaokao.eol.cn/jiang_su/dongtai/202406/t20240625_2619079.shtml"),
    ("四川", 2024, "物理类", "https://gaokao.eol.cn/si_chuan/dongtai/202406/t20240624_2618669.shtml"),
    ("河北", 2024, "物理类", "https://gaokao.eol.cn/he_bei/dongtai/202406/t20240625_2619073.shtml"),
    ("广东", 2024, "物理类", "https://gaokao.eol.cn/guang_dong/dongtai/202406/t20240626_2619547.shtml"),
    ("河南", 2025, "物理类", "https://gaokao.eol.cn/he_nan/dongtai/202506/t20250625_2676859.shtml"),
    ("河南", 2025, "历史类", "https://gaokao.eol.cn/he_nan/dongtai/202506/t20250625_2676858.shtml"),
    ("上海", 2025, None, "https://gaokao.eol.cn/shang_hai/dongtai/202506/t20250623_2676341.shtml"),
    ("浙江", 2025, None, "https://gaokao.eol.cn/zhe_jiang/dongtai/202506/t20250625_2677143.shtml"),
    ("广东", 2025, None, "https://gaokao.eol.cn/guang_dong/dongtai/202506/t20250626_2677410.shtml"),
    ("湖北", 2025, None, "https://gaokao.eol.cn/hu_bei/dongtai/202506/t20250627_2677496.shtml"),
    ("山东", 2025, None, "https://gaokao.eol.cn/shan_dong/dongtai/202506/t20250626_2677288.shtml"),
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
    ("河北", 2025, "物理类", "https://www.zizzs.com/gk/gaokao/203615.html"),
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
    if not title:
        return None
    if any(h in title for h in COMBINED_TRACK_HINTS):
        return None
    phys_hits = sum(1 for k in TRACK_KEYWORDS["物理类"] if k in title)
    hist_hits = sum(1 for k in TRACK_KEYWORDS["历史类"] if k in title)
    if phys_hits and not hist_hits:
        return "物理类"
    if hist_hits and not phys_hits:
        return "历史类"
    if phys_hits and hist_hits:
        # 标题同时含「理科」「文科」等对比表述时，取更具体的类名
        for track, keys in TRACK_KEYWORDS.items():
            if any(k in title for k in keys if len(k) >= 3):
                return track
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

    return expand_sibling_entries(entries)


def expand_sibling_entries(entries: list[CatalogEntry], delta: int = 2) -> list[CatalogEntry]:
    """EOL 常将物理/历史类拆成相邻文章 ID，索引页易漏抓或标错科类。"""
    seen = {e.url for e in entries}
    out = list(entries)
    pat = re.compile(r"gaokao\.eol\.cn/([a-z0-9_]+)(/dongtai/\d{6}/t\d{8}_)(\d+)(\.shtml)$")

    for entry in entries:
        m = pat.search(entry.url)
        if not m:
            continue
        slug, mid, num_s, suffix = m.group(1), m.group(2), m.group(3), m.group(4)
        base_id = int(num_s)
        for off in range(-delta, delta + 1):
            if off == 0:
                continue
            sibling_id = base_id + off
            url = f"https://gaokao.eol.cn/{slug}{mid}{sibling_id}{suffix}"
            if url in seen:
                continue
            seen.add(url)
            out.append(CatalogEntry(entry.province, entry.year, None, "", url))
    return out


_ocr_engine: Any = None


def get_ocr_engine() -> Any:
    global _ocr_engine
    if _ocr_engine is None:
        from rapidocr_onnxruntime import RapidOCR

        _ocr_engine = RapidOCR()
    return _ocr_engine


def parse_markdown_segment_table(html: str) -> tuple[list[SegmentRow], int]:
    """部分页面以 Markdown 管道表形式嵌入。"""
    segments: list[SegmentRow] = []
    for score_raw, count_s, cum_s in re.findall(
        r"\|\s*(\d{2,4}(?:\s*[-~至]\s*\d{2,4})?)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|",
        html,
    ):
        score_raw = str(score_raw).strip()
        if "-" in score_raw or "~" in score_raw or "至" in score_raw:
            parts = re.findall(r"\d+", score_raw)
            if len(parts) < 2:
                continue
            score = max(int(parts[0]), int(parts[1]))
        else:
            score = int(score_raw)
        segments.append(SegmentRow(score, int(count_s), int(cum_s)))
    if len(segments) < 10:
        return [], 0
    by_score: dict[int, SegmentRow] = {}
    for seg in segments:
        cur = by_score.get(seg.score)
        if cur is None or seg.cumulative > cur.cumulative:
            by_score[seg.score] = seg
    ordered = sorted(by_score.values(), key=lambda s: s.score, reverse=True)
    total = max(s.cumulative for s in ordered)
    return ordered, total


def _cluster_ocr_rows(ocr_lines: list[Any], y_tol: float = 18.0) -> list[list[tuple[float, str]]]:
    cells: list[tuple[float, float, str]] = []
    for item in ocr_lines:
        box, text, _conf = item[0], str(item[1]).strip(), item[2]
        if not re.search(r"\d", text):
            continue
        y = (box[0][1] + box[2][1]) / 2
        x = (box[0][0] + box[2][0]) / 2
        cells.append((y, x, text))
    cells.sort(key=lambda c: (c[0], c[1]))
    rows: list[list[tuple[float, str]]] = []
    for y, x, text in cells:
        if not rows or abs(y - rows[-1][0][0]) > y_tol:
            rows.append([(x, text)])
        else:
            rows[-1].append((x, text))
    return rows


def _ocr_triple_valid(score: int, count: int, cumulative: int) -> bool:
    return (
        40 <= score <= 900
        and 0 < count < 500_000
        and 0 < cumulative < 50_000_000
    )


def _parse_ocr_column_triples(ocr_lines: list[Any], y_tol: float = 14.0) -> list[tuple[int, int, int]]:
    """按 x 坐标分三列（分数/人数/累计）再按 y 对齐行。"""
    cells: list[tuple[float, float, int]] = []
    for item in ocr_lines:
        box, text, _conf = item[0], str(item[1]).strip().replace(",", ""), item[2]
        nums = re.findall(r"\d+", text)
        if not nums:
            continue
        y = (box[0][1] + box[2][1]) / 2
        x = (box[0][0] + box[2][0]) / 2
        if len(nums) == 1 and re.fullmatch(r"\d{1,7}", text):
            cells.append((x, y, int(nums[0])))
        elif len(nums) >= 3:
            for idx, n in enumerate(nums[:3]):
                cells.append((x + idx * 8.0, y, int(n)))

    if len(cells) < 30:
        return []

    xs = sorted(c[0] for c in cells)
    q1, q2 = xs[len(xs) // 3], xs[2 * len(xs) // 3]
    cols: dict[int, list[tuple[float, int]]] = {0: [], 1: [], 2: []}
    for x, y, val in cells:
        col = 0 if x < q1 else (1 if x < q2 else 2)
        cols[col].append((y, val))

    if len(cols[0]) < 10:
        return []

    row_ys: list[float] = []
    for y, _val in sorted(cols[0], key=lambda t: t[0]):
        if not row_ys or abs(y - row_ys[-1]) > y_tol:
            row_ys.append(y)
        else:
            row_ys[-1] = (row_ys[-1] + y) / 2

    triples: list[tuple[int, int, int]] = []
    for row_y in row_ys:
        picked: list[int | None] = []
        for col in (0, 1, 2):
            near = [c for c in cols[col] if abs(c[0] - row_y) <= y_tol * 1.6]
            if not near:
                picked.append(None)
            else:
                picked.append(min(near, key=lambda c: abs(c[0] - row_y))[1])
        if all(v is not None for v in picked):
            score, count, cumulative = picked[0], picked[1], picked[2]  # type: ignore[misc]
            if _ocr_triple_valid(score, count, cumulative):
                triples.append((score, count, cumulative))
    return triples


def _parse_ocr_line_triples(ocr_lines: list[Any]) -> list[tuple[int, int, int]]:
    """单列 OCR 文本按连续三数字成组（分数-人数-累计）。"""
    nums: list[int] = []
    for item in ocr_lines:
        text = str(item[1]).strip().replace(",", "")
        if re.fullmatch(r"\d{1,7}", text):
            nums.append(int(text))
    triples: list[tuple[int, int, int]] = []
    i = 0
    while i + 2 < len(nums):
        score, count, cumulative = nums[i], nums[i + 1], nums[i + 2]
        if _ocr_triple_valid(score, count, cumulative):
            triples.append((score, count, cumulative))
            i += 3
        else:
            i += 1
    return triples


def _parse_ocr_regex_triples(ocr_lines: list[Any]) -> list[tuple[int, int, int]]:
    text = "\n".join(str(item[1]) for item in ocr_lines).replace(",", "")
    triples: list[tuple[int, int, int]] = []
    for m in re.finditer(r"(\d{2,4})\s+(\d{1,6})\s+(\d{1,7})", text):
        score, count, cumulative = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if _ocr_triple_valid(score, count, cumulative):
            triples.append((score, count, cumulative))
    return triples


def _filter_ocr_triples(triples: list[tuple[int, int, int]]) -> list[tuple[int, int, int]]:
    if not triples:
        return []

    candidates = [
        (s, c, cum)
        for s, c, cum in triples
        if 80 <= s <= 780 and 0 < c < 200_000 and 0 < cum < 10_000_000 and c <= cum + 500
    ]
    if len(candidates) < 10:
        return []

    scores = sorted(s for s, _, _ in candidates if 250 <= s <= 750)
    if len(scores) >= 20:
        peak = scores[min(len(scores) - 1, int(len(scores) * 0.995))]
    elif scores:
        peak = max(scores)
    else:
        peak = max(s for s, _, _ in candidates)

    lo = max(80, peak - 650)
    by_score: dict[int, tuple[int, int, int]] = {}
    for score, count, cumulative in candidates:
        if score < lo or score > peak + 20:
            continue
        cur = by_score.get(score)
        if cur is None:
            by_score[score] = (score, count, cumulative)
        else:
            # 同分取累计更大且人数更合理者
            if cumulative > cur[2] and count <= cumulative:
                by_score[score] = (score, count, cumulative)

    ordered = sorted(by_score.values(), key=lambda t: t[0], reverse=True)
    fixed: list[tuple[int, int, int]] = []
    prev_cum = 0
    for score, count, cumulative in ordered:
        cum = max(cumulative, prev_cum)
        if count > cum and prev_cum > 0:
            count = max(1, cum - prev_cum)
        fixed.append((score, count, cum))
        prev_cum = cum
    return fixed


def parse_eol_image_table(
    session: requests.Session,
    html: str,
    page_url: str,
) -> tuple[list[SegmentRow], int]:
    """TRS_Editor 内嵌 JPG/PNG 一分一段表 → OCR 解析。"""
    rels = re.findall(
        r'href="(\./W\d+\.(?:jpg|png|jpeg))"',
        html,
        flags=re.I,
    )
    if not rels:
        rels = re.findall(
            r'src="(\./W\d+\.(?:jpg|png|jpeg))"',
            html,
            flags=re.I,
        )
    if not rels:
        return [], 0

    base = page_url.rsplit("/", 1)[0] + "/"
    ocr = get_ocr_engine()
    triples: list[tuple[int, int, int]] = []

    for rel in dict.fromkeys(rels):
        img_url = base + rel.lstrip("./")
        try:
            img_bytes = session.get(img_url, headers=HEADERS, timeout=40).content
            ocr_out, _ = ocr(img_bytes)
        except Exception:  # noqa: BLE001
            continue
        if not ocr_out:
            continue
        col_triples = _parse_ocr_column_triples(ocr_out)
        line_triples = _parse_ocr_line_triples(ocr_out)
        regex_triples = _parse_ocr_regex_triples(ocr_out)
        triples.extend(col_triples)
        triples.extend(line_triples)
        triples.extend(regex_triples)

    triples = _filter_ocr_triples(triples)
    if len(triples) < 15:
        return [], 0

    ordered = [SegmentRow(s, c, cum) for s, c, cum in sorted(triples, key=lambda t: t[0], reverse=True)]
    total = max(s.cumulative for s in ordered)
    return ordered, total


def parse_eol_table(html: str) -> tuple[list[SegmentRow], int]:
    rows = re.findall(
        r"<tr[^>]*>\s*<td[^>]*>([^<]+)</td>\s*<td[^>]*>(\d+)</td>\s*<td[^>]*>(\d+)</td>",
        html,
        flags=re.I,
    )
    if len(rows) < 10:
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
        elif re.fullmatch(r"\d{2,4}", score_raw):
            segments.append(SegmentRow(int(score_raw), count, cumulative))

    by_score: dict[int, SegmentRow] = {}
    for seg in segments:
        if seg.score not in by_score or seg.cumulative < by_score[seg.score].cumulative:
            by_score[seg.score] = seg
    ordered = sorted(by_score.values(), key=lambda x: x.score, reverse=True)
    if ordered:
        total = max(total, ordered[-1].cumulative)
    return ordered, total


def parse_eol_segments_from_html(
    session: requests.Session,
    html: str,
    page_url: str,
) -> tuple[list[SegmentRow], int, str]:
    segments, total = parse_eol_table(html)
    if len(segments) >= 15:
        return segments, total, "html_table"
    segments, total = parse_markdown_segment_table(html)
    if len(segments) >= 15:
        return segments, total, "markdown_table"
    segments, total = parse_eol_image_table(session, html, page_url)
    if len(segments) >= 15:
        return segments, total, "image_ocr"
    return [], 0, "none"


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


def percentile_from_cumulative(cumulative: int, count: int, total: int) -> float:
    """超越考生占比：累计位次为从高分向下累计的人数。"""
    if total <= 0:
        return 0.0
    rank_mid = max(1, cumulative - count / 2)
    return round((1 - rank_mid / total) * 100, 2)


def normalize_segment_rows(segments: list[SegmentRow]) -> list[SegmentRow]:
    """按累计人数重建本段人数，合并平台假分段，消除 745+ 尖峰。"""
    if not segments:
        return segments

    by_score: dict[int, SegmentRow] = {}
    for seg in segments:
        cur = by_score.get(seg.score)
        if cur is None or seg.cumulative > cur.cumulative:
            by_score[seg.score] = seg

    ordered = sorted(by_score.values(), key=lambda s: s.score, reverse=True)
    mono: list[SegmentRow] = []
    for seg in ordered:
        if mono and seg.cumulative < mono[-1].cumulative:
            continue
        mono.append(seg)

    if not mono:
        return segments

    changes = [mono[0]]
    for seg in mono[1:]:
        if seg.cumulative != changes[-1].cumulative:
            changes.append(seg)

    fixed: list[SegmentRow] = []
    for i, seg in enumerate(changes):
        if i + 1 < len(changes):
            n = changes[i + 1].cumulative - seg.cumulative
        elif i > 0:
            n = seg.cumulative - changes[i - 1].cumulative
        else:
            n = seg.count
        fixed.append(SegmentRow(seg.score, max(0, n), seg.cumulative))
    return fixed


def densify_segments(segments: list[SegmentRow], step: int = 2) -> list[SegmentRow]:
    """在锚点之间插值累计人数，生成更密的分段曲线，消除图表断崖。"""
    if len(segments) < 2:
        return segments
    ordered = sorted(segments, key=lambda s: s.score)
    scores = [s.score for s in ordered]
    cums = [s.cumulative for s in ordered]
    min_s, max_s = scores[0], scores[-1]

    def cum_at(score: int) -> int:
        if score <= scores[0]:
            return cums[0]
        if score >= scores[-1]:
            return cums[-1]
        for i in range(len(scores) - 1):
            lo, hi = scores[i], scores[i + 1]
            if lo <= score <= hi:
                if hi == lo:
                    return cums[i]
                t = (score - lo) / (hi - lo)
                return int(round(cums[i] + (cums[i + 1] - cums[i]) * t))
        return cums[-1]

    dense_scores = list(range(max_s, min_s - 1, -step))
    dense_cums = [cum_at(s) for s in dense_scores]
    fixed: list[SegmentRow] = []
    for i, s in enumerate(dense_scores):
        if i + 1 < len(dense_scores):
            n = dense_cums[i + 1] - dense_cums[i]
        elif i > 0:
            n = dense_cums[i] - dense_cums[i - 1]
        else:
            n = 0
        fixed.append(SegmentRow(s, max(0, n), dense_cums[i]))
    return fixed


def smooth_segment_counts(segments: list[SegmentRow], window: int = 5, tail_keep: int = 24) -> list[SegmentRow]:
    """对本段人数做轻度滑动平均；高分尾段保持插值结果，避免人为尖峰/断崖。"""
    if len(segments) < window:
        return segments
    ordered = sorted(segments, key=lambda s: s.score, reverse=True)
    if len(ordered) <= tail_keep + window:
        return segments

    head = ordered[:tail_keep]
    body = ordered[tail_keep:]
    raw = [max(0, s.count) for s in body]
    half = window // 2
    smoothed_body_counts: list[int] = []
    for i in range(len(raw)):
        lo = max(0, i - half)
        hi = min(len(raw), i + half + 1)
        smoothed_body_counts.append(max(1, int(round(sum(raw[lo:hi]) / (hi - lo)))))

    target_total = ordered[-1].cumulative
    rebuilt: list[SegmentRow] = []
    cum = 0
    for seg, n in zip(ordered, [s.count for s in head] + smoothed_body_counts):
        cum += n
        rebuilt.append(SegmentRow(seg.score, n, cum))

    if rebuilt and rebuilt[-1].cumulative != target_total and rebuilt[-1].cumulative > 0:
        scale = target_total / rebuilt[-1].cumulative
        scaled: list[SegmentRow] = []
        cum = 0
        for seg in rebuilt:
            n = max(0, int(round(seg.count * scale)))
            cum += n
            scaled.append(SegmentRow(seg.score, n, cum))
        if scaled[-1].cumulative != target_total:
            scaled[-1] = SegmentRow(
                scaled[-1].score,
                scaled[-1].count + (target_total - scaled[-1].cumulative),
                target_total,
            )
        rebuilt = scaled
    return rebuilt


def calibrate_segments_to_anchors(
    segments: list[SegmentRow],
    total: int,
    anchors: dict[int, int],
) -> tuple[list[SegmentRow], int]:
    """用 zizzs 等锚点位次校准累计人数，修正 eol 表与第三方偏差。"""
    if not segments or not anchors:
        return segments, total
    ratios: list[float] = []
    for score, expected_rank in anchors.items():
        actual = cumulative_at(segments, score)
        if actual and actual > 0 and expected_rank > 0:
            ratios.append(expected_rank / actual)
    if not ratios:
        return segments, total
    ratio = sum(ratios) / len(ratios)
    if abs(ratio - 1) < 0.03:
        return segments, total
    calibrated: list[SegmentRow] = []
    prev_cum = 0
    for seg in sorted(segments, key=lambda s: s.score, reverse=True):
        new_cum = max(prev_cum, int(round(seg.cumulative * ratio)))
        new_count = max(1, new_cum - prev_cum) if new_cum > prev_cum else seg.count
        calibrated.append(SegmentRow(seg.score, new_count, new_cum))
        prev_cum = new_cum
    new_total = max(prev_cum, int(round(total * ratio)))
    return calibrated, new_total


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


def maybe_calibrate_segments(
    segments: list[SegmentRow],
    total: int,
    track: str | None,
    anchors: dict[str, Any],
    zizzs: dict[int, int] | None,
    checks: list[dict[str, Any]],
    confidence: str,
    score: float,
) -> tuple[list[SegmentRow], int, list[dict[str, Any]], str, float]:
    """仅在 zizzs 校准能提升交叉验证得分时才改写分段表。"""
    if score >= 0.8 or not zizzs or len(zizzs) < 2:
        return segments, total, checks, confidence, score
    cal_segs, cal_total = calibrate_segments_to_anchors(segments, total, zizzs)
    if not cal_segs:
        return segments, total, checks, confidence, score
    new_checks, new_conf, new_score = cross_validate(cal_segs, track, anchors, zizzs)
    if new_score > score:
        return cal_segs, cal_total, new_checks, new_conf, new_score
    return segments, total, checks, confidence, score


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
    segments, total, parse_kind = parse_eol_segments_from_html(session, html, entry.url)
    if len(segments) < 15:
        return None
    title_m = re.search(r"<title>([^<]+)</title>", html, re.I)
    html_title = title_m.group(1).strip() if title_m else ""
    if not html_title:
        h1 = re.search(r"<h1[^>]*>([^<]+)</h1>", html, re.I)
        if h1:
            html_title = h1.group(1).strip()
    title = html_title or entry.title or ""
    anchors = parse_eol_anchors(html)
    structural = validate_structural(segments, total)
    source = "eol.cn" if parse_kind != "image_ocr" else "eol.cn+ocr"
    return ScrapeResult(
        segments=segments,
        total=total,
        source=source,
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


def pick_best_scrape(items: list[ScrapeResult]) -> ScrapeResult:
    def quality(r: ScrapeResult) -> tuple[int, float, int]:
        return (len(r.segments), r.confidence_score, r.total or 0)

    return max(items, key=quality)


def pick_best_entry(entries: list[CatalogEntry]) -> CatalogEntry | None:
    if not entries:
        return None

    def score(e: CatalogEntry) -> tuple[int, int]:
        track_bonus = 1 if e.track else 0
        title_bonus = 1 if e.title and "一分一段" in e.title else 0
        return (track_bonus + title_bonus, e.year)

    return sorted(entries, key=score, reverse=True)[0]

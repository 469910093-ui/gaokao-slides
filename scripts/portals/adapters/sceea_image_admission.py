"""四川省教育考试院调档线 JPG 表格 OCR 解析。"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urljoin

import requests

from admission_filter_lib import primary_undergrad_batch
from portals.types import AdmissionRow, Artifact, ParseResult

_CODE_RE = re.compile(r"^\d{4}$")
_CJK_RE = re.compile(r"[\u4e00-\u9fff]{2,}")
_HEADER_TRACK = (
    (re.compile(r"理科|物理"), "物理类"),
    (re.compile(r"文科|文史|历史"), "历史类"),
)


def _get_ocr_engine() -> Any:
    from gaokao_crawl_lib import get_ocr_engine

    return get_ocr_engine()


def _ocr_cells(ocr_lines: list[Any]) -> list[tuple[float, float, str]]:
    cells: list[tuple[float, float, str]] = []
    for item in ocr_lines or []:
        box, text, _conf = item[0], str(item[1]).strip(), item[2]
        if not text:
            continue
        y = (box[0][1] + box[2][1]) / 2
        x = (box[0][0] + box[2][0]) / 2
        cells.append((y, x, text))
    return cells


def _cluster_rows(cells: list[tuple[float, float, str]], y_tol: float = 15.0) -> list[list[tuple[float, str]]]:
    if not cells:
        return []
    cells = sorted(cells, key=lambda c: (c[0], c[1]))
    rows: list[tuple[float, list[tuple[float, str]]]] = []
    for y, x, text in cells:
        if not rows or abs(y - rows[-1][0]) > y_tol:
            rows.append((y, [(x, text)]))
        else:
            avg_y = (rows[-1][0] + y) / 2
            rows[-1][1].append((x, text))
            rows[-1] = (avg_y, rows[-1][1])
    return [sorted(items, key=lambda t: t[0]) for _y, items in rows]


def _track_from_header(text: str, fallback: str) -> str:
    for pat, track in _HEADER_TRACK:
        if pat.search(text):
            return track
    return fallback


def _pick_score(cells: list[tuple[float, str]]) -> int | None:
    nums: list[tuple[float, int]] = []
    for x, text in cells:
        if re.fullmatch(r"\d{2,3}", text):
            v = int(text)
            if 150 <= v <= 750:
                nums.append((x, v))
    if not nums:
        return None
    # 调档线列在最右侧（x 最大）的 400+ 分
    hi = [p for p in nums if p[1] >= 400]
    if hi:
        return max(hi, key=lambda p: p[0])[1]
    return max(nums, key=lambda p: p[0])[1]


def _parse_table_row(cells: list[tuple[float, str]]) -> tuple[str, str, int] | None:
    texts = [t for _x, t in cells]
    code = next((t for t in texts if _CODE_RE.fullmatch(t)), None)
    if not code:
        return None
    names = [t for t in texts if _CJK_RE.search(t) and len(t) >= 2]
    # 去掉表头残留
    names = [n for n in names if "院校" not in n and "调档" not in n and "招生" not in n]
    if not names:
        return None
    school = max(names, key=len)
    score = _pick_score(cells)
    if score is None or score < 150:
        return None
    return code, school, score


def parse_sceea_image(
    image_bytes: bytes,
    *,
    province: str,
    year: int,
    track: str,
    batch: str,
    source_url: str,
) -> tuple[list[AdmissionRow], str]:
    ocr = _get_ocr_engine()
    ocr_out, _ = ocr(image_bytes)
    cells = _ocr_cells(ocr_out)
    header_text = " ".join(t for _y, _x, t in sorted(cells, key=lambda c: c[0])[:8])
    track = _track_from_header(header_text, track)
    rows: list[AdmissionRow] = []
    for row_cells in _cluster_rows(cells):
        parsed = _parse_table_row(row_cells)
        if not parsed:
            continue
        code, school, score = parsed
        rows.append(
            AdmissionRow(
                province=province,
                year=year,
                track=track,
                schoolName=school,
                minScore=score,
                batch=batch,
                schoolCode=code,
                sourceUrl=source_url,
            )
        )
    return rows, track


def extract_sceea_image_urls(html: str, page_url: str) -> list[str]:
    rels = re.findall(
        r'src=["\'](\.\./\.\./Upload/image/[^"\']+\.(?:jpg|jpeg|png))["\']',
        html,
        flags=re.I,
    )
    if not rels:
        rels = re.findall(
            r'src=["\'](/Upload/image/[^"\']+\.(?:jpg|jpeg|png))["\']',
            html,
            flags=re.I,
        )
        return [urljoin("https://www.sceea.cn", u) for u in dict.fromkeys(rels)]
    out: list[str] = []
    for rel in dict.fromkeys(rels):
        path = rel.replace("../../", "")
        out.append(urljoin("https://www.sceea.cn/", path))
    return out


def parse_sceea_admission_html(
    artifact: Artifact,
    html: str,
    session: requests.Session | None = None,
) -> ParseResult:
    batch_name = artifact.batch or primary_undergrad_batch(artifact.province)
    track = artifact.track or "物理类"
    sess = session or requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": artifact.source_page or "https://www.sceea.cn/",
    }
    urls = extract_sceea_image_urls(html, artifact.url)
    all_rows: list[AdmissionRow] = []
    warnings: list[str] = []
    for img_url in urls:
        try:
            resp = sess.get(img_url, headers=headers, timeout=60)
            resp.raise_for_status()
            img_rows, track = parse_sceea_image(
                resp.content,
                province=artifact.province,
                year=artifact.year,
                track=track,
                batch=batch_name,
                source_url=img_url,
            )
            all_rows.extend(img_rows)
        except Exception as exc:
            warnings.append(f"{img_url}: {exc}")

    return ParseResult(
        artifact=artifact,
        rows=all_rows,
        parser="sceea_image_ocr",
        warnings=warnings,
    )

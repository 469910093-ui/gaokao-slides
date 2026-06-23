#!/usr/bin/env python3
"""探测各省考试院首页/栏目页中的投档、一分一段公告链接。"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from admission_filter_lib import PROVINCE_EXAM_PORTALS

KW = re.compile(r"投档|一分一段|平行志愿|录取分数|最低分|控制分数线|省控线")
ATTACH = re.compile(r"\.(pdf|xlsx?|docx?|zip)$", re.I)


def probe(province: str, url: str) -> None:
    print(f"\n=== {province} {url}")
    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=25)
    r.encoding = r.apparent_encoding or "utf-8"
    soup = BeautifulSoup(r.text, "html.parser")
    seen: set[str] = set()
    hits: list[tuple[str, str, str]] = []
    for a in soup.find_all("a", href=True):
        text = (a.get_text() or "").strip()
        href = a["href"].strip()
        if not text and not href:
            continue
        full = urljoin(url, href)
        if full in seen:
            continue
        seen.add(full)
        if KW.search(text) or KW.search(href) or ATTACH.search(href):
            kind = "attach" if ATTACH.search(href) else "link"
            hits.append((kind, text[:80], full))
    print(f"status={r.status_code} bytes={len(r.text)} hits={len(hits)}")
    for kind, text, full in hits[:15]:
        print(f"  [{kind}] {text} -> {full}")


def main() -> None:
    targets = sys.argv[1:] or ["北京", "河南", "江苏", "浙江", "广东"]
    for p in targets:
        url = PROVINCE_EXAM_PORTALS.get(p)
        if not url:
            print(f"skip {p}: no portal")
            continue
        try:
            probe(p, url)
        except Exception as exc:
            print(f"ERR {p}: {exc}")


if __name__ == "__main__":
    main()

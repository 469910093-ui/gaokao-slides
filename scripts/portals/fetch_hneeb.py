"""湖南招生考试信息港下载（TLS 握手异常时用 Playwright）。"""

from __future__ import annotations

import requests
from pathlib import Path

from gaokao_crawl_lib import HEADERS
from portals.fetch import fetch_bytes as _fetch_bytes


def fetch_hneeb_bytes(url: str) -> bytes:
    try:
        return _fetch_bytes(url, use_cache=True)
    except (requests.RequestException, OSError):
        pass
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            "湖南考试院 HTTPS 握手失败，需 playwright: pip install playwright && playwright install chromium"
        ) from exc
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            ctx = browser.new_context(user_agent=HEADERS.get("User-Agent", ""))
            # APIRequestContext 走独立 TLS 栈，常可绕过 requests 握手失败
            resp = ctx.request.get(url, timeout=120_000)
            if resp.ok:
                body = resp.body()
                if body[:2] == b"PK":
                    return body
            page = ctx.new_page()
            with page.expect_download(timeout=120_000) as dl_info:
                page.goto(url, wait_until="commit", timeout=120_000)
            download = dl_info.value
            path = download.path()
            if path:
                data = Path(path).read_bytes()
                if data[:2] == b"PK":
                    return data
            raise RuntimeError(f"Playwright 下载非 xlsx: {url}")
        finally:
            browser.close()

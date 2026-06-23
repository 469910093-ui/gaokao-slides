"""河南 datacenter.haeea.cn Playwright 抓取（支持人工 Cookie）。"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_COOKIE_PATH = ROOT / "data" / "secrets" / "haeea_cookies.json"
WARMUP_URL = "https://gaokao.haedu.cn/"


def _cookie_path() -> Path | None:
    env = os.environ.get("HAEA_COOKIE_FILE", "").strip()
    if env:
        p = Path(env)
        return p if p.is_file() else None
    if DEFAULT_COOKIE_PATH.is_file():
        return DEFAULT_COOKIE_PATH
    return None


def load_playwright_cookies() -> list[dict[str, Any]]:
    """读取 Playwright 格式 Cookie JSON 数组。"""
    path = _cookie_path()
    if not path:
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "cookies" in data:
        data = data["cookies"]
    if not isinstance(data, list):
        raise ValueError(f"{path} 须为 Cookie 对象数组")
    out: list[dict[str, Any]] = []
    for c in data:
        if not isinstance(c, dict) or "name" not in c or "value" not in c:
            continue
        item = dict(c)
        item.setdefault("domain", ".haeea.cn")
        item.setdefault("path", "/")
        out.append(item)
    return out


def fetch_haeea_datacenter_html(
    url: str,
    timeout_ms: int = 90000,
    referer: str | None = None,
) -> str:
    """经 gaokao.haedu.cn 预热 + 可选 Cookie 访问 datacenter 投档统计页。"""
    from playwright.sync_api import sync_playwright

    cookies = load_playwright_cookies()
    warmup = referer or WARMUP_URL
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            locale="zh-CN",
        )
        if cookies:
            context.add_cookies(cookies)
        page = context.new_page()
        page.goto(warmup, wait_until="domcontentloaded", timeout=timeout_ms)
        page.goto(url, wait_until="networkidle", timeout=timeout_ms)
        html = page.content()
        browser.close()
        return html


def cookie_status() -> dict[str, Any]:
    path = _cookie_path()
    cookies = load_playwright_cookies() if path else []
    return {
        "cookieFile": str(path) if path else None,
        "cookieCount": len(cookies),
        "hint": (
            "在浏览器登录 datacenter.haeea.cn 后导出 Cookie 到 "
            f"{DEFAULT_COOKIE_PATH}（Playwright 格式 JSON 数组）"
        ),
    }

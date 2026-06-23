"""Playwright 抓取河南 datacenter 投档统计页 HTML。"""

from __future__ import annotations

import sys
from pathlib import Path

# 避免 scripts/portals/types.py 遮蔽标准库 types
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def fetch_haeea_datacenter_html(url: str, timeout_ms: int = 60000) -> str:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
        )
        page.goto("https://gaokao.haedu.cn/", wait_until="domcontentloaded", timeout=timeout_ms)
        page.goto(url, wait_until="networkidle", timeout=timeout_ms)
        html = page.content()
        browser.close()
        return html


if __name__ == "__main__":
    u = "https://datacenter.haeea.cn/PagePZQuery/ShowPZTDTJ.aspx?yearTip=2024&pc=1&kl=5"
    h = fetch_haeea_datacenter_html(u)
    print("len", len(h))
    print(h[:3000])

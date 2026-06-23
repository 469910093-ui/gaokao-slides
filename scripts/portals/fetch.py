"""带本地缓存的考试院资源下载。"""

from __future__ import annotations

import hashlib
import time
from pathlib import Path
from typing import Any

import requests

from gaokao_crawl_lib import HEADERS

ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = ROOT / "data" / "reference" / "gaokao_cn" / "official_cache"


def _cache_key(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()


def fetch_bytes(
    url: str,
    *,
    session: requests.Session | None = None,
    use_cache: bool = True,
    ttl_hours: int = 72,
) -> bytes:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    key = _cache_key(url)
    cache_path = CACHE_DIR / key
    meta_path = CACHE_DIR / f"{key}.meta"
    if use_cache and cache_path.exists() and meta_path.exists():
        try:
            saved_at = float(meta_path.read_text(encoding="utf-8").strip())
            if time.time() - saved_at < ttl_hours * 3600:
                return cache_path.read_bytes()
        except ValueError:
            pass
    sess = session or requests.Session()
    r = sess.get(url, headers=HEADERS, timeout=60)
    r.raise_for_status()
    data = r.content
    cache_path.write_bytes(data)
    meta_path.write_text(str(time.time()), encoding="utf-8")
    return data


def fetch_text(url: str, **kwargs: Any) -> str:
    data = fetch_bytes(url, **kwargs)
    for enc in ("utf-8", "gbk", "gb2312"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")

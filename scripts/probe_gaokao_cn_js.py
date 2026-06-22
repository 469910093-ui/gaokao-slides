#!/usr/bin/env python3
"""Find gaokao.cn control-line API from JS bundles."""
from __future__ import annotations

import re
import requests

HDR = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.gaokao.cn/"}
BASE = "https://api.zjzw.cn/web/api/"


def main() -> None:
    r = requests.get(
        "https://www.gaokao.cn/control-line?province=%E4%B8%8A%E6%B5%B7&year=2025",
        headers=HDR,
        timeout=30,
    )
    scripts = re.findall(r'src="([^"]+\.js)"', r.text)
    print("scripts", len(scripts))
    uris: set[str] = set()
    for rel in scripts[:12]:
        url = rel if rel.startswith("http") else "https://www.gaokao.cn" + rel
        try:
            js = requests.get(url, headers=HDR, timeout=30).text
        except Exception as exc:  # noqa: BLE001
            print("skip", url, exc)
            continue
        uris.update(re.findall(r"apidata/api/[a-zA-Z0-9_/]+", js))
    print("uris", len(uris))
    for u in sorted(uris):
        if any(k in u for k in ("line", "batch", "control", "segment", "rank", "province")):
            print(u)

    s = requests.Session()
    for uri in sorted(uris):
        if not any(k in uri for k in ("line", "control", "batch", "segment")):
            continue
        for extra in (
            {"province_id": 31, "year": 2025, "page": 1, "size": 20},
            {"province_id": 31, "year": 2025, "local_type_name": "综合", "page": 1, "size": 20},
            {"province": "上海", "year": 2025},
        ):
            p = {"uri": uri, **extra}
            try:
                rr = s.get(BASE, params=p, headers=HDR, timeout=12)
            except Exception:
                continue
            if rr.status_code == 200 and '"1064"' not in rr.text[:120] and rr.text.strip() not in ('{"code":"0000","message":"成功-success","data":""}',):
                if '"item"' in rr.text or '"list"' in rr.text or (isinstance(rr.json().get("data"), list) and rr.json()["data"]):
                    print("HIT", uri, extra, rr.text[:300])


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Test which eol URLs contain parseable score tables."""
import json
import re
import time
from pathlib import Path

import requests

HEADERS = {"User-Agent": "Mozilla/5.0"}
ROOT = Path(__file__).parent.parent
CATALOG = ROOT / "data" / "eol_catalog.json"


def parse_table(html: str):
    rows = re.findall(
        r"<tr[^>]*>\s*<td[^>]*>([^<]+)</td>\s*<td[^>]*>(\d+)</td>\s*<td[^>]*>(\d+)</td>",
        html,
        flags=re.I,
    )
    return len(rows)


def main():
    entries = json.loads(CATALOG.read_text(encoding="utf-8"))
    ok = []
    for e in entries:
        try:
            r = requests.get(e["url"], headers=HEADERS, timeout=25)
            n = parse_table(r.text)
            if n >= 20:
                e["rows"] = n
                ok.append(e)
                print("OK", e["province"], e["year"], e.get("track"), n, e["url"][-40:])
            else:
                print("skip", e["province"], e["year"], n)
        except Exception as exc:
            print("fail", e["url"], exc)
        time.sleep(0.35)
    out = ROOT / "data" / "eol_scrapable.json"
    out.write_text(json.dumps(ok, ensure_ascii=False, indent=2), encoding="utf-8")
    print("scrapable", len(ok), "/", len(entries))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""列出各省考试院 discover() 结果。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from portals.registry import get_parser, list_provinces


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provinces", default="北京,江苏")
    parser.add_argument("--years", default="2024")
    args = parser.parse_args()
    provinces = [p.strip() for p in args.provinces.split(",") if p.strip()]
    years = [int(y.strip()) for y in args.years.split(",") if y.strip()]

    for prov in provinces:
        p = get_parser(prov)
        print(f"\n== {prov} ({p.implementation}) ==")
        for year in years:
            arts = p.discover(year)
            print(f"  {year}: {len(arts)} artifacts")
            for a in arts:
                print(f"    [{a.kind}] {a.track} {a.title[:50]} -> {a.url[:90]}")

    print("\nRegistry:", len(list_provinces()), "provinces")


if __name__ == "__main__":
    main()

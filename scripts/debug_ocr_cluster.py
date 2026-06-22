#!/usr/bin/env python3
import re
import requests
from gaokao_crawl_lib import HEADERS, get_ocr_engine, _cluster_ocr_rows

url = "https://gaokao.eol.cn/shang_hai/dongtai/202506/t20250623_2676341.shtml"
html = requests.get(url, headers=HEADERS, timeout=30).text
rels = re.findall(r'href="(\./W\d+\.(?:jpg|png|jpeg))"', html, re.I)
base = url.rsplit("/", 1)[0] + "/"
ocr = get_ocr_engine()
rows3 = 0
for rel in rels[:1]:
    img = requests.get(base + rel.lstrip("./"), headers=HEADERS, timeout=40).content
    out, _ = ocr(img)
    rows = _cluster_ocr_rows(out)
    print("clusters", len(rows))
    for row in rows[:25]:
        nums = []
        for x, t in sorted(row, key=lambda t: t[0]):
            found = re.findall(r"\d+", t.replace(",", ""))
            if len(found) == 1:
                nums.append((x, int(found[0])))
            elif len(found) >= 2:
                for n in found[:3]:
                    nums.append((x, int(n)))
        if len(nums) >= 3:
            rows3 += 1
            vals = [n for _, n in sorted(nums, key=lambda t: t[0])][-3:]
            print(vals)
    print("rows3", rows3)

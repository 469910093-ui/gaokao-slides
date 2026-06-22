#!/usr/bin/env python3
"""Test line-triplet OCR parsing."""
import re
import requests
from gaokao_crawl_lib import HEADERS, get_ocr_engine

url = "https://gaokao.eol.cn/shang_hai/dongtai/202506/t20250623_2676341.shtml"
html = requests.get(url, headers=HEADERS, timeout=30).text
rels = re.findall(r'href="(\./W\d+\.(?:jpg|png|jpeg))"', html, re.I)
base = url.rsplit("/", 1)[0] + "/"
ocr = get_ocr_engine()


def valid_triple(s: int, c: int, cum: int) -> bool:
    return 100 <= s <= 900 and 0 < c < 500000 and 0 < cum < 50000000


def from_lines(ocr_out):
    nums: list[int] = []
    for item in ocr_out:
        text = str(item[1]).strip().replace(",", "")
        if re.fullmatch(r"\d{1,7}", text):
            nums.append(int(text))
    triples = []
    i = 0
    while i + 2 < len(nums):
        s, c, cum = nums[i], nums[i + 1], nums[i + 2]
        if valid_triple(s, c, cum):
            triples.append((s, c, cum))
            i += 3
        else:
            i += 1
    return triples


def from_regex(ocr_out):
    text = "\n".join(str(item[1]) for item in ocr_out)
    triples = []
    for m in re.finditer(r"(\d{2,4})\s+(\d{1,6})\s+(\d{1,7})", text.replace(",", "")):
        s, c, cum = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if valid_triple(s, c, cum):
            triples.append((s, c, cum))
    return triples


all_t = []
for rel in rels:
    img = requests.get(base + rel.lstrip("./"), headers=HEADERS, timeout=40).content
    out, _ = ocr(img)
    lt = from_lines(out)
    rt = from_regex(out)
    print(rel, "lines", len(lt), "regex", len(rt))
    all_t.extend(lt or rt)

by_score = {}
for s, c, cum in all_t:
    if s not in by_score or cum > by_score[s][2]:
        by_score[s] = (s, c, cum)
ordered = sorted(by_score.values(), key=lambda t: t[0], reverse=True)
print("merged", len(ordered), "top", ordered[:5], "bottom", ordered[-3:])

#!/usr/bin/env python3
"""Test OCR on Shanghai 2025 segment image."""
import io
import re
import requests
from gaokao_crawl_lib import HEADERS, parse_eol_table, SegmentRow

url = "https://gaokao.eol.cn/shang_hai/dongtai/202506/t20250623_2676341.shtml"
html = requests.get(url, headers=HEADERS, timeout=30).text
imgs = re.findall(r'href="(\./W\d+\.(?:jpg|png|jpeg))"', html, re.I)
print("images", imgs[:6])
base = url.rsplit("/", 1)[0] + "/"

from rapidocr_onnxruntime import RapidOCR

ocr = RapidOCR()
all_rows: list[tuple[int, int, int]] = []
for rel in imgs[:4]:
    img_url = base + rel[2:]
    data = requests.get(img_url, headers=HEADERS, timeout=30).content
    result, _ = ocr(data)
    if not result:
        continue
    text = "\n".join(line[1] for line in result)
    print("---", rel, "lines", len(result))
    for line in text.splitlines()[:15]:
        print(line)
    for m in re.finditer(r"(\d{2,4})\s+(\d{1,6})\s+(\d{1,7})", text):
        all_rows.append((int(m.group(1)), int(m.group(2)), int(m.group(3))))

print("parsed triples", len(all_rows), all_rows[:10])

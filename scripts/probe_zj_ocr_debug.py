#!/usr/bin/env python3
import re
import requests
from gaokao_crawl_lib import (
    HEADERS,
    get_ocr_engine,
    _parse_ocr_column_triples,
    _parse_ocr_line_triples,
    _parse_ocr_regex_triples,
    _filter_ocr_triples,
)

url = "https://gaokao.eol.cn/zhe_jiang/dongtai/202506/t20250625_2677143.shtml"
html = requests.get(url, headers=HEADERS, timeout=30).text
rels = re.findall(r'src="(\./W\d+\.(?:jpg|png|jpeg))"', html, re.I)
print("rels", rels)
base = url.rsplit("/", 1)[0] + "/"
ocr = get_ocr_engine()
all_raw = []
for rel in rels:
    img_url = base + rel.lstrip("./")
    img_bytes = requests.get(img_url, headers=HEADERS, timeout=40).content
    print(rel, "bytes", len(img_bytes))
    ocr_out, _ = ocr(img_bytes)
    print(" ocr lines", len(ocr_out) if ocr_out else 0)
    if not ocr_out:
        continue
    c = _parse_ocr_column_triples(ocr_out)
    l = _parse_ocr_line_triples(ocr_out)
    r = _parse_ocr_regex_triples(ocr_out)
    print(" col", len(c), "line", len(l), "regex", len(r))
    all_raw.extend(c or l or r)

print("raw total", len(all_raw))
filtered = _filter_ocr_triples(all_raw)
print("filtered", len(filtered), "sample", filtered[:5], filtered[-3:] if filtered else [])

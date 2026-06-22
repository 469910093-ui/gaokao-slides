#!/usr/bin/env python3
import re
import requests

URLS = [
    ("上海", "https://gaokao.eol.cn/shang_hai/dongtai/202506/t20250623_2676341.shtml"),
    ("浙江", "https://gaokao.eol.cn/zhe_jiang/dongtai/202506/t20250625_2677143.shtml"),
    ("河南", "https://gaokao.eol.cn/he_nan/dongtai/202506/t20250625_2676859.shtml"),
]

for prov, url in URLS:
    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    r.encoding = "utf-8"
    t = r.text
    print("===", prov, "len", len(t))
    for key in ("<tr", "<td", "x:num", "TRS_Editor", "xlsx", "iframe", "累计", "本段"):
        print(" ", key, t.lower().count(key.lower()))
    files = re.findall(r'href="([^"]+\.(?:xlsx?|csv|pdf|xls))"', t, re.I)
    print(" files", files[:5])
    # paragraph rows
    paras = re.findall(r"<p[^>]*>([^<]{0,80})</p>", t)
    print(" paras sample", paras[:3])
    # any 3-digit score patterns with counts
    rows = re.findall(r"(\d{2,4})\s*[,，]?\s*(\d+)\s*[,，]?\s*(\d+)", t)
    print(" numeric triples", len(rows), rows[:3])

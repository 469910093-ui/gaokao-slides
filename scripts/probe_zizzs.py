#!/usr/bin/env python3
import re, requests
url="https://www.zizzs.com/gk/jiangsuxingaokao/166123.html"
r=requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=25)
r.encoding='utf-8'
text=r.text
rows=re.findall(r"<tr[^>]*>\s*<td[^>]*>([^<]+)</td>\s*<td[^>]*>(\d+)</td>\s*<td[^>]*>(\d+)</td>", text, re.I)
print('rows', len(rows), 'sample', rows[:3], rows[-3:] if rows else None)
# alt patterns
rows2=re.findall(r"<td[^>]*>(\d{3,4})</td>\s*<td[^>]*>(\d+)</td>\s*<td[^>]*>(\d+)</td>", text)
print('rows2', len(rows2))

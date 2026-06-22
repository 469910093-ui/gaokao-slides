import json, re, shutil, subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
LARK = shutil.which("lark-cli.cmd")
r = subprocess.run([LARK, "docs", "+fetch", "--api-version", "v2", "--doc", "VrSsdDs7uodjDZxK8zlcqUYBnec", "--detail", "with-ids", "--as", "user"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
data = json.loads(r.stdout[r.stdout.rfind('{\n  "ok"'):])
c = data["data"]["document"]["content"]
# sample h1 h3 img pattern
for m in re.finditer(r'<(h1|h3|img)[^>]*>', c):
    tag = m.group(0)[:120]
    if 'h1' in tag or 'h3' in tag or 'img' in tag:
        print(tag)
print('---')
print('h1 count', len(re.findall(r'<h1 ', c)))
print('h3 count', len(re.findall(r'<h3 ', c)))
print('img count', len(re.findall(r'<img ', c)))

import json, re, shutil, subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
LARK = shutil.which("lark-cli.cmd")
r = subprocess.run([LARK, "docs", "+fetch", "--api-version", "v2", "--doc", "VrSsdDs7uodjDZxK8zlcqUYBnec", "--detail", "with-ids", "--as", "user"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
data = json.loads(r.stdout[r.stdout.rfind('{\n  "ok"'):])
c = data["data"]["document"]["content"]
posts = re.split(r'(?=<h1 )', c)
for chunk in posts[1:3]:
    h1 = re.search(r'<h1[^>]*>([^<]+)</h1>', chunk)
    print('===', h1.group(1) if h1 else '?')
    for m in re.finditer(r'<h3 id="([^"]+)">([^<]+)</h3>', chunk):
        print(' ', m.group(2), m.group(1))

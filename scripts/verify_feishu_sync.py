import json, re, shutil, subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
LARK = shutil.which("lark-cli.cmd")
r = subprocess.run([LARK, "docs", "+fetch", "--api-version", "v2", "--doc", "VrSsdDs7uodjDZxK8zlcqUYBnec", "--detail", "with-ids", "--as", "user"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
c = json.loads(r.stdout[r.stdout.rfind('{\n  "ok"'):])["data"]["document"]["content"]
print("img after h1:", len(re.findall(r"</h1>\s*<img", c)))
print("img after h3:", len(re.findall(r"</h3>\s*<img", c)))
print("total img tags:", len(re.findall(r"<img ", c)))

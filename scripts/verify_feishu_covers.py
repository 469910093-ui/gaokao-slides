import json, re, subprocess, shutil
LARK = shutil.which("lark-cli.cmd")
r = subprocess.run(
    [LARK, "docs", "+fetch", "--api-version", "v2", "--doc", "VrSsdDs7uodjDZxK8zlcqUYBnec", "--detail", "with-ids", "--as", "user"],
    capture_output=True, text=True, encoding="utf-8",
    cwd=r"D:\Users\yaowenliang\Projects\xiaohongshu-gaokao-slides",
)
idx = r.stdout.rfind('{\n  "ok"')
data = json.loads(r.stdout[idx:])
content = data["data"]["document"]["content"]
for m in re.finditer(r'<h1 id="([^"]+)">第 (\d+) 篇', content):
    start = m.end()
    chunk = content[start : start + 400]
    print(f"POST {m.group(2)}: img_after_h1={'<img' in chunk}")
tail = content.split("第 09 篇")[-1]
print("images_after_post09", tail.count("<img"))

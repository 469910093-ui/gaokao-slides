#!/usr/bin/env python3
"""Replace cover images in Feishu doc with regenerated PNGs."""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC_ID = "VrSsdDs7uodjDZxK8zlcqUYBnec"
COVERS = ROOT / "publish" / "feishu" / "covers"
LARK = shutil.which("lark-cli.cmd") or shutil.which("lark-cli") or "lark-cli"


def run(args: list[str]) -> dict:
    cmd = [LARK if a == "lark-cli" else a for a in args]
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        print(r.stderr or r.stdout, file=sys.stderr)
        sys.exit(r.returncode)
    out = r.stdout.strip()
    idx = out.rfind('{\n  "ok"')
    if idx < 0:
        idx = out.rfind("{")
    return json.loads(out[idx:])


def fetch_content() -> str:
    r = subprocess.run(
        [LARK, "docs", "+fetch", "--api-version", "v2", "--doc", DOC_ID, "--detail", "with-ids", "--as", "user"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    out = r.stdout.strip()
    idx = out.rfind('{\n  "ok"')
    data = json.loads(out[idx:])
    return data["data"]["document"]["content"]


def main() -> None:
    content = fetch_content()
    pairs = re.findall(r'<h1 id="([^"]+)">第 (\d+) 篇[^<]*</h1>\s*<img id="([^"]+)"', content)
    if len(pairs) < 9:
        print(f"warn: found {len(pairs)} h1+img pairs", file=sys.stderr)

    for h1_id, num, img_id in sorted(pairs, key=lambda x: int(x[1]), reverse=True):
        num = f"{int(num):02d}"
        cover = COVERS / f"post-{num}-cover.png"
        if not cover.exists():
            print(f"missing {cover}", file=sys.stderr)
            continue
        run(
            [
                "lark-cli",
                "docs",
                "+update",
                "--api-version",
                "v2",
                "--as",
                "user",
                "--doc",
                DOC_ID,
                "--command",
                "block_delete",
                "--block-id",
                img_id,
            ]
        )
        data = run(
            [
                "lark-cli",
                "docs",
                "+media-insert",
                "--as",
                "user",
                "--doc",
                DOC_ID,
                "--file",
                f"publish/feishu/covers/post-{num}-cover.png",
                "--align",
                "center",
                "--width",
                "360",
                "--caption",
                f"POST {num} 小红书封面",
            ]
        )
        new_id = data.get("data", {}).get("block_id")
        if not new_id:
            print(f"no block_id for {num}", data, file=sys.stderr)
            continue
        run(
            [
                "lark-cli",
                "docs",
                "+update",
                "--api-version",
                "v2",
                "--as",
                "user",
                "--doc",
                DOC_ID,
                "--command",
                "block_move_after",
                "--block-id",
                h1_id,
                "--src-block-ids",
                new_id,
            ]
        )
        print(f"updated POST {num}")

    print("Done.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Upload post covers to Feishu doc end, then move each after its h1."""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC_ID = "VrSsdDs7uodjDZxK8zlcqUYBnec"
BLOCKS_FILE = ROOT / "publish" / "feishu" / "doc_blocks.txt"
COVERS = ROOT / "publish" / "feishu" / "covers"
LARK_CLI = shutil.which("lark-cli.cmd") or shutil.which("lark-cli") or "lark-cli"


def run(cmd: list[str]) -> dict:
    cmd = [LARK_CLI if c == "lark-cli" else c for c in cmd]
    print("$", " ".join(cmd[:8]), "...")
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        print(r.stderr or r.stdout, file=sys.stderr)
        sys.exit(r.returncode)
    # JSON may be last object in stdout
    out = r.stdout.strip()
    idx = out.rfind('{\n  "ok"')
    if idx < 0:
        idx = out.rfind("{")
    if idx >= 0:
        return json.loads(out[idx:])
    return {"raw": out}


def fetch_blocks() -> str:
    run(
        [
            LARK_CLI,
            "docs",
            "+fetch",
            "--api-version",
            "v2",
            "--doc",
            DOC_ID,
            "--detail",
            "with-ids",
            "--as",
            "user",
        ]
    )
    # refetch to file
    subprocess.run(
        [
            LARK_CLI,
            "docs",
            "+fetch",
            "--api-version",
            "v2",
            "--doc",
            DOC_ID,
            "--detail",
            "with-ids",
            "--as",
            "user",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    r = subprocess.run(
        [
            LARK_CLI,
            "docs",
            "+fetch",
            "--api-version",
            "v2",
            "--doc",
            DOC_ID,
            "--detail",
            "with-ids",
            "--as",
            "user",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    out = r.stdout.strip()
    idx = out.rfind('{\n  "ok"')
    if idx < 0:
        idx = out.rfind("{")
    data = json.loads(out[idx:])
    return data["data"]["document"]["content"]


def main() -> None:
    image_blocks: dict[str, str] = {"01": "doxcncxzxtNYea5WtQnM5acDROb"}
    for i in range(2, 10):
        num = f"{i:02d}"
        cover = COVERS / f"post-{num}-cover.png"
        data = run(
            [
                LARK_CLI,
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
                "320",
                "--caption",
                f"POST {num} 小红书封面",
            ]
        )
        block_id = data.get("data", {}).get("block_id")
        if not block_id:
            print(f"no block_id for {num}", data, file=sys.stderr)
            sys.exit(1)
        image_blocks[num] = block_id
        print(f"uploaded {num} -> {block_id}")

    xml = fetch_blocks()
    BLOCKS_FILE.write_text(xml, encoding="utf-8")
    h1s = re.findall(r'<h1 id="([^"]+)">第 (\d+) 篇', xml)
    if len(h1s) != 9:
        print(f"expected 9 h1, got {len(h1s)}", file=sys.stderr)

    # Move images after h1 (reverse order)
    for block_id, num in sorted(h1s, key=lambda x: int(x[1]), reverse=True):
        num = f"{int(num):02d}"
        img_id = image_blocks.get(num)
        if not img_id:
            continue
        run(
            [
                LARK_CLI,
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
                block_id,
                "--src-block-ids",
                img_id,
            ]
        )
        print(f"moved cover {num} after h1 {block_id}")

    print("All covers placed.")


if __name__ == "__main__":
    main()

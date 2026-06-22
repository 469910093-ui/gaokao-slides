#!/usr/bin/env python3
"""Insert/update 小红书发布包 callout after each post h1 in Feishu doc."""
from __future__ import annotations

import html
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

from build_feishu_xhs_doc import POSTS, PUBLISH, publish_xml

ROOT = Path(__file__).resolve().parents[1]
DOC_ID = "VrSsdDs7uodjDZxK8zlcqUYBnec"
LARK = shutil.which("lark-cli.cmd") or shutil.which("lark-cli") or "lark-cli"
MARKER = "小红书发布包（复制即用）"


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
    return json.loads(out[idx:]) if idx >= 0 else {"raw": out}


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
    return json.loads(out[idx:])["data"]["document"]["content"]


def delete_block(block_id: str) -> None:
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
            block_id,
        ]
    )


def insert_xml_after(anchor_id: str, xml_content: str) -> str:
    data = run(
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
            "block_insert_after",
            "--block-id",
            anchor_id,
            "--content",
            xml_content,
            "--doc-format",
            "xml",
        ]
    )
    ids = data.get("data", {}).get("block_ids") or []
    if isinstance(ids, list) and ids:
        return ids[0]
    children = data.get("data", {}).get("children") or []
    if children:
        return children[0].get("block_id", "") if isinstance(children[0], dict) else str(children[0])
    return ""


def move_after(anchor_id: str, block_id: str) -> None:
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
            anchor_id,
            "--src-block-ids",
            block_id,
        ]
    )


def publish_to_markdown(post: dict) -> str:
    pub = PUBLISH[post["id"]]
    last = post["slides"][-1]
    tags = last.get("hashtags", "")
    lines = [
        f"**📮 {MARKER}**",
        "",
        f"**标题**",
        pub["title"],
        "",
        "**正文**",
        pub["caption"],
        "",
        tags,
        "",
        "**首评/置顶评论**",
        pub["first_comment"],
        "",
        "**发布动作**：发笔记 → 自己抢首评 → 回复评论 → 简介挂工具",
    ]
    return "\n".join(lines)


def find_publish_callout(chunk: str) -> str | None:
    m = re.search(rf'<callout[^>]*>.*?{re.escape(MARKER)}.*?</callout>', chunk, re.S)
    if not m:
        return None
    idm = re.search(r'id="([^"]+)"', m.group(0))
    return idm.group(1) if idm else None


def main() -> None:
    content = fetch_content()
    chunks = re.split(r"(?=<h1 )", content)
    ok = 0
    for post in reversed(POSTS):
        pid = post["id"]
        num = int(pid)
        chunk = next((c for c in chunks if re.search(rf"<h1[^>]*>第 {num:02d} 篇", c)), None)
        if not chunk:
            print(f"skip POST {pid}: h1 not found", file=sys.stderr)
            continue
        h1m = re.search(r'<h1 id="([^"]+)">', chunk)
        if not h1m:
            continue
        h1_id = h1m.group(1)
        old_callout = find_publish_callout(chunk)
        if old_callout:
            delete_block(old_callout)
            time.sleep(0.2)
        xml_content = publish_xml(post)
        try:
            new_id = insert_xml_after(h1_id, xml_content)
            if new_id:
                time.sleep(0.15)
                move_after(h1_id, new_id)
            ok += 1
            print(f"OK POST {pid} 发布包")
        except SystemExit:
            print(f"FAIL POST {pid}: insert failed, use xhs_publish_pack.md", file=sys.stderr)
            sys.exit(1)
        time.sleep(0.25)
    print(f"Done. {ok}/9 publish packs synced.")
    print(f"https://trip.larkenterprise.com/docx/{DOC_ID}")


if __name__ == "__main__":
    main()

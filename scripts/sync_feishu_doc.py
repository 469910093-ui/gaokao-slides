#!/usr/bin/env python3
"""Sync covers + body slide PNGs into Feishu doc (after h1 / each h3)."""
from __future__ import annotations

import html
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC_ID = "VrSsdDs7uodjDZxK8zlcqUYBnec"
META_PATH = ROOT / "publish" / "feishu" / "feishu_doc_meta.json"
LARK = shutil.which("lark-cli.cmd") or shutil.which("lark-cli") or "lark-cli"
IMG_WIDTH = 360  # 3:4 preview width in Feishu


def run(args: list[str], fatal: bool = True) -> dict:
    cmd = [LARK if a == "lark-cli" else a for a in args]
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        if fatal:
            print(r.stderr or r.stdout, file=sys.stderr)
            sys.exit(r.returncode)
        return {"ok": False, "error": r.stderr or r.stdout}
    out = r.stdout.strip()
    idx = out.rfind('{\n  "ok"')
    if idx < 0:
        idx = out.rfind("{")
    if idx < 0:
        return {"raw": out}
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
    return json.loads(out[idx:])["data"]["document"]["content"]


def h3_slug(label: str) -> str | None:
    label = html.unescape(label).strip()
    if label == "封面":
        return "cover"
    m = re.match(r"(P\d+)", label, re.I)
    if m:
        return m.group(1).lower()
    return None


def slide_file(post_num: str, slug: str) -> Path | None:
    if slug == "cover":
        p = ROOT / "publish" / "feishu" / "covers" / f"post-{post_num}-cover.png"
    else:
        p = ROOT / "publish" / "feishu" / "slides" / f"post-{post_num}-{slug}.png"
    return p if p.exists() else None


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


def insert_image(rel_path: str, caption: str) -> str:
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
            rel_path.replace("\\", "/"),
            "--align",
            "center",
            "--width",
            str(IMG_WIDTH),
            "--caption",
            caption,
        ]
    )
    block_id = data.get("data", {}).get("block_id")
    if not block_id:
        raise RuntimeError(f"media-insert failed: {data}")
    return block_id


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


def parse_posts(content: str) -> list[dict]:
    chunks = re.split(r"(?=<h1 )", content)
    posts: list[dict] = []
    for chunk in chunks:
        h1m = re.search(r'<h1 id="([^"]+)">第 (\d+) 篇', chunk)
        if not h1m:
            continue
        post_num = f"{int(h1m.group(2)):02d}"
        cover_img = None
        cm = re.search(r'<h1[^>]*>[^<]*</h1>\s*<img id="([^"]+)"', chunk)
        if cm:
            cover_img = cm.group(1)
        h3s = []
        for m in re.finditer(r'<h3 id="([^"]+)">([^<]+)</h3>', chunk):
            label = html.unescape(m.group(2))
            slug = h3_slug(label)
            trailing_img = None
            tail = chunk[m.end() : m.end() + 120]
            im = re.match(r'\s*<img id="([^"]+)"', tail)
            if im:
                trailing_img = im.group(1)
            h3s.append(
                {
                    "id": m.group(1),
                    "label": label,
                    "slug": slug,
                    "img_id": trailing_img,
                }
            )
        posts.append(
            {
                "num": post_num,
                "h1_id": h1m.group(1),
                "cover_img_id": cover_img,
                "h3s": h3s,
            }
        )
    return posts


def replace_image_after(anchor_id: str, old_img_id: str | None, rel_path: str, caption: str) -> None:
    if old_img_id:
        delete_block(old_img_id)
        time.sleep(0.15)
    new_id = insert_image(rel_path, caption)
    time.sleep(0.15)
    move_after(anchor_id, new_id)


def main() -> None:
    if not META_PATH.exists():
        print("Run build_feishu_xhs_doc.py first.", file=sys.stderr)
        sys.exit(1)

    content = fetch_content()
    posts = parse_posts(content)
    if len(posts) != 9:
        print(f"warn: parsed {len(posts)} posts (expected 9)", file=sys.stderr)

    # Reverse order: later posts first to reduce anchor drift when deleting trailing imgs
    tasks: list[tuple[str, str, str | None, str, str, str]] = []
    for post in reversed(posts):
        num = post["num"]
        cover_rel = f"publish/feishu/covers/post-{num}-cover.png"
        tasks.append(("cover_h1", post["h1_id"], post["cover_img_id"], cover_rel, f"POST {num} 封面", num))
        for h3 in reversed(post["h3s"]):
            slug = h3["slug"]
            if not slug or slug == "cover":
                # 封面图已在 h1 下；「封面」小节只保留文案
                if h3["img_id"]:
                    delete_block(h3["img_id"])
                continue
            rel = f"publish/feishu/slides/post-{num}-{slug}.png"
            if not (ROOT / rel).exists():
                print(f"skip missing {rel} ({h3['label']})", file=sys.stderr)
                continue
            cap = f"POST {num} · {h3['label']}"
            tasks.append(("h3", h3["id"], h3["img_id"], rel, cap, num))

    ok = 0
    for kind, anchor, old_img, rel, cap, num in tasks:
        try:
            replace_image_after(anchor, old_img, rel, cap)
            ok += 1
            print(f"OK POST {num} · {cap}")
        except Exception as exc:
            print(f"FAIL POST {num} · {cap}: {exc}", file=sys.stderr)
            # refetch not needed if move failed on stale id — continue

    print(f"Done. {ok}/{len(tasks)} images synced.")
    print(f"https://trip.larkenterprise.com/docx/{DOC_ID}")


if __name__ == "__main__":
    main()

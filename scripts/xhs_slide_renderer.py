#!/usr/bin/env python3
"""
XHS listicle slides (3:4) — 纯正文：无 POST/页码/Hashtag，大字大 icon，铺满版面。
"""
from __future__ import annotations

import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from build_feishu_xhs_doc import (
    POSTS,
    ROOT,
    W,
    H,
    draw_text_block,
    line_metrics,
    load_font,
    measure_lines,
    wrap_cn,
)

SLIDES_OUT = ROOT / "publish" / "feishu" / "slides"

INK = "#1A1A1A"
BG = "#F7F3EA"
YELLOW = "#FFEB3B"
WHITE = "#FFFFFF"

PAD = 14
ICON_SIZE = 128
ICON_LANE = 136
FS_HOOK = 64
FS_ROW_TITLE = 50
FS_ROW_DESC = 40
FS_PAIR_TITLE = 44
FS_PAIR_BODY = 36
CARD_GAP = 8
HL_LINE_GAP = 10
DESC_LINE_GAP = 8
HL_DESC_GAP = 8
ROW_PAD_Y = 8
HOOK_AFTER_GAP = 10

EMOJI_LEAD = re.compile(
    r"^([\U0001F300-\U0001FAFF\U00002700-\U000027BF\U00002600-\U000026FF"
    r"❌✅📌💡🎯😰🏫⚠️🔥✨🎓📊🏥⚡🧭🛠️📝🔍👇]+)\s*"
)


def build_theme(accent: str) -> dict[str, str]:
    return {"bg": BG, "ink": INK, "yellow": YELLOW, "surface": WHITE, "accent": accent}


def slide_slug(label: str) -> str:
    m = re.match(r"(P\d+)", label, re.I)
    if m:
        return m.group(1).lower()
    return re.sub(r"[^\w\u4e00-\u9fff]+", "-", label).strip("-").lower() or "slide"


def strip_emoji(text: str) -> str:
    return EMOJI_LEAD.sub("", text).strip()


def split_highlight(text: str) -> tuple[str, str]:
    text = strip_emoji(text).strip()
    m = re.search(r"「([^」]+)」", text)
    if m:
        key = m.group(1)
        rest = text.replace(f"「{key}」", "").strip(" ，。：:—-")
        if rest.startswith(("：", ":")):
            rest = rest[1:].strip()
        return key, rest
    if "→" in text and "：" not in text and "——" not in text:
        a, b = text.split("→", 1)
        return a.strip(), b.strip()
    for sep in ("：", ":"):
        if sep in text:
            a, b = text.split(sep, 1)
            return a.strip(), b.strip()
    if "——" in text:
        a, b = text.split("——", 1)
        return a.strip(), b.strip()
    if "，" in text and len(text) > 24:
        a, b = text.split("，", 1)
        return a.strip(), b.strip()
    if len(text) <= 22:
        return text, ""
    return text[:20], text[20:].lstrip("，。 ")


def icon_kind(text: str, emoji: str = "") -> str:
    t = text + emoji
    rules = [
        ("ai", r"AI|人工智能|算法|模型"),
        ("chart", r"分|段|位次|表|数据|统计|薪资"),
        ("medical", r"医|护|临床|口腔|康复"),
        ("engineering", r"工|电|机械|芯片|自动化|制造"),
        ("money", r"商|会计|财|金融|经济"),
        ("school", r"校|志愿|专业|填报|选校"),
        ("search", r"查|翻|看|下载|搜"),
        ("warn", r"别|不要|坑|慎|❌|×"),
        ("check", r"✅|✓|可以|应该|收藏|截图"),
        ("pin", r"步骤|今晚|明天|行动|清单|评论|进群"),
        ("book", r"文科|法学|中文|新传"),
    ]
    for kind, pat in rules:
        if re.search(pat, t):
            return kind
    return "dot"


def text_col_w(card_w: int) -> int:
    return card_w - ICON_LANE - 20


def title_desc_fonts() -> tuple[ImageFont.FreeTypeFont, ImageFont.FreeTypeFont]:
    return load_font(FS_ROW_TITLE, bold=True), load_font(FS_ROW_DESC)


def draw_round_card(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], theme: dict[str, str], r: int = 16) -> None:
    draw.rounded_rectangle(box, radius=r, fill=theme["surface"], outline="#E0DAC8", width=2)


def draw_yellow_label(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    text: str,
    font: ImageFont.FreeTypeFont,
    theme: dict[str, str],
    max_w: int,
    line_gap: int = HL_LINE_GAP,
) -> tuple[int, int]:
    lines = wrap_cn(draw, text, font, max_w)
    cy = y
    total_h = 0
    pad_x, pad_y = 12, 10
    for line in lines:
        w, h, top = line_metrics(draw, line, font)
        draw.rectangle([x, cy + top - pad_y, x + w + pad_x * 2, cy + top + h + pad_y], fill=theme["yellow"])
        draw.text((x + pad_x, cy), line, fill=theme["ink"], font=font)
        cy += h + line_gap
        total_h += h + line_gap
    return cy - y, total_h


def measure_list_block(
    draw: ImageDraw.ImageDraw,
    highlight: str,
    desc: str,
    tw: int,
    title_font: ImageFont.FreeTypeFont,
    desc_font: ImageFont.FreeTypeFont,
) -> int:
    _, th = measure_lines(draw, wrap_cn(draw, highlight, title_font, tw), title_font, HL_LINE_GAP)
    desc_lines = wrap_cn(draw, desc, desc_font, tw) if desc else []
    _, dh = measure_lines(draw, desc_lines, desc_font, DESC_LINE_GAP) if desc else (0, 0)
    gap = HL_DESC_GAP if desc else 0
    return th + gap + dh + ROW_PAD_Y * 2


def draw_flat_icon(draw: ImageDraw.ImageDraw, cx: int, cy: int, size: int, kind: str, theme: dict[str, str]) -> None:
    s = size // 2
    ink = theme["ink"]
    fill = theme["yellow"]
    lw = max(4, size // 22)
    fs = max(22, size // 4)
    if kind == "ai":
        draw.rounded_rectangle([cx - s, cy - s, cx + s, cy + s], radius=12, outline=ink, width=lw)
        draw.text((cx - fs // 2, cy - fs), "AI", fill=ink, font=load_font(fs, bold=True))
    elif kind == "chart":
        bars = [0.45, 0.75, 0.35, 0.6]
        bw = max(12, size // 7)
        for i, ratio in enumerate(bars):
            bh = int(s * 1.6 * ratio)
            bx = cx - s + 10 + i * (bw + 8)
            draw.rectangle([bx, cy + s - bh, bx + bw, cy + s], fill=fill, outline=ink, width=2)
    elif kind == "medical":
        arm = max(14, size // 6)
        draw.rectangle([cx - arm // 2, cy - s + 8, cx + arm // 2, cy + s - 8], fill=fill, outline=ink, width=lw)
        draw.rectangle([cx - s + 8, cy - arm // 2, cx + s - 8, cy + arm // 2], fill=fill, outline=ink, width=lw)
    elif kind == "engineering":
        draw.polygon([(cx, cy - s), (cx + s, cy), (cx, cy + s), (cx - s, cy)], outline=ink, width=lw)
        draw.line([cx - s // 2, cy, cx + s // 2, cy], fill=ink, width=lw)
    elif kind == "money":
        draw.ellipse([cx - s + 6, cy - s + 6, cx + s - 6, cy + s - 6], outline=ink, width=lw)
        draw.text((cx - fs // 3, cy - fs // 2), "¥", fill=ink, font=load_font(fs, bold=True))
    elif kind == "school":
        draw.polygon(
            [(cx, cy - s + 8), (cx + s - 6, cy), (cx + s - 6, cy + s - 6), (cx - s + 6, cy + s - 6), (cx - s + 6, cy)],
            outline=ink,
            width=lw,
        )
    elif kind == "search":
        r = s - 10
        draw.ellipse([cx - r, cy - r, cx + r // 2, cy + r // 2], outline=ink, width=lw)
        draw.line([cx + r // 3, cy + r // 3, cx + s - 4, cy + s - 4], fill=ink, width=lw)
    elif kind == "warn":
        draw.polygon([(cx, cy - s + 6), (cx + s - 6, cy + s - 6), (cx - s + 6, cy + s - 6)], outline=ink, width=lw)
        draw.text((cx - fs // 4, cy - fs // 4), "!", fill=ink, font=load_font(fs, bold=True))
    elif kind == "check":
        draw.ellipse([cx - s + 8, cy - s + 8, cx + s - 8, cy + s - 8], outline=ink, width=lw)
        draw.line([cx - s // 3, cy, cx - 4, cy + s // 3], fill=ink, width=lw)
        draw.line([cx - 4, cy + s // 3, cx + s // 2, cy - s // 3], fill=ink, width=lw)
    elif kind == "book":
        draw.rounded_rectangle([cx - s + 8, cy - s + 8, cx + s - 8, cy + s - 8], radius=6, outline=ink, width=lw)
        draw.line([cx, cy - s + 14, cx, cy + s - 14], fill=ink, width=lw)
    elif kind == "pin":
        draw.ellipse([cx - s // 3, cy - s + 6, cx + s // 3, cy + 2], outline=ink, width=lw)
        draw.polygon([(cx, cy + s - 4), (cx - s // 3, cy + 6), (cx + s // 3, cy + 6)], fill=fill, outline=ink, width=2)
    else:
        r = max(16, size // 4)
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=fill, outline=ink, width=lw)


def fit_title_fill(
    draw: ImageDraw.ImageDraw,
    highlight: str,
    tw: int,
    max_block_h: int,
) -> ImageFont.FreeTypeFont:
    best = load_font(FS_ROW_TITLE, bold=True)
    best_bh = 0
    cap = min(128, FS_ROW_TITLE + max(48, int(max_block_h * 0.72)))
    for ts in range(cap, FS_ROW_TITLE - 4, -3):
        tf = load_font(ts, bold=True)
        lines = wrap_cn(draw, highlight, tf, tw)
        _, th = measure_lines(draw, lines, tf, HL_LINE_GAP)
        bh = th + ROW_PAD_Y * 2
        if bh <= max_block_h and bh >= best_bh:
            best_bh = bh
            best = tf
    return best


def fit_fonts_to_row(
    draw: ImageDraw.ImageDraw,
    highlight: str,
    desc: str,
    tw: int,
    max_block_h: int,
) -> tuple[ImageFont.FreeTypeFont, ImageFont.FreeTypeFont]:
    """在不超过行高的前提下，尽量放大标题/说明字号。"""
    if not desc.strip():
        return fit_title_fill(draw, highlight, tw, max_block_h), load_font(FS_ROW_DESC)

    best_tf, best_df = title_desc_fonts()
    best_bh = 0
    ts_cap = min(112, FS_ROW_TITLE + max(40, int(max_block_h * 0.55)))
    ds_cap = min(92, FS_ROW_DESC + max(28, int(max_block_h * 0.35)))
    for ts in range(ts_cap, FS_ROW_TITLE - 4, -3):
        for ds in range(min(ds_cap, ts - 6), FS_ROW_DESC - 4, -3):
            tf = load_font(ts, bold=True)
            df = load_font(ds)
            bh = measure_list_block(draw, highlight, desc, tw, tf, df)
            if bh <= max_block_h and bh >= best_bh:
                best_bh = bh
                best_tf, best_df = tf, df
    return best_tf, best_df


def draw_list_row(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    w: int,
    h: int,
    highlight: str,
    desc: str,
    kind: str,
    theme: dict[str, str],
) -> None:
    draw_round_card(draw, (x, y, x + w, y + h), theme)
    icon_sz = min(220, max(ICON_SIZE, int(h * 0.62)))
    icon_x = x + ICON_LANE // 2
    icon_y = y + h // 2
    draw_flat_icon(draw, icon_x, icon_y, icon_sz, kind, theme)

    tx = x + ICON_LANE + 6
    tw = text_col_w(w)
    inner_h = h - ROW_PAD_Y * 2
    title_font, desc_font = fit_fonts_to_row(draw, highlight, desc, tw, inner_h)
    block_h = measure_list_block(draw, highlight, desc, tw, title_font, desc_font)
    ty = y + max(ROW_PAD_Y, (h - block_h) // 2)
    label_h, _ = draw_yellow_label(draw, tx, ty, highlight, title_font, theme, tw)
    if desc:
        desc_lines = wrap_cn(draw, desc, desc_font, tw)
        draw_text_block(
            draw,
            desc_lines,
            desc_font,
            tx,
            ty + label_h + HL_DESC_GAP,
            theme["ink"],
            DESC_LINE_GAP,
            align="left",
            block_w=tw,
        )


def layout_frame(theme: dict[str, str]) -> dict:
    return {
        "pad": PAD,
        "ix0": PAD,
        "ix1": W - PAD,
        "cw": W - PAD * 2,
        "y0": PAD,
        "y_max": H - PAD,
        "theme": theme,
    }


def alloc_row_heights(
    draw: ImageDraw.ImageDraw,
    rows: list[tuple[str, str]],
    y0: int,
    y_max: int,
    cw: int,
) -> list[int]:
    if not rows:
        return []
    tw = text_col_w(cw)
    tf, df = title_desc_fonts()
    mins = [max(76, measure_list_block(draw, k, d, tw, tf, df)) for k, d in rows]
    gap_total = CARD_GAP * (len(rows) - 1)
    available = y_max - y0
    total_min = sum(mins) + gap_total
    if total_min >= available:
        per = max(76, (available - gap_total) // len(rows))
        return [per] * len(rows)
    extra = available - total_min
    share = extra // len(rows)
    rem = extra % len(rows)
    return [m + share + (1 if i < rem else 0) for i, m in enumerate(mins)]


def draw_hook(draw: ImageDraw.ImageDraw, frame: dict, hook: str, y: int, y_max: int | None = None) -> int:
    theme = frame["theme"]
    ix0, cw = frame["ix0"], frame["cw"]
    clean = strip_emoji(hook)
    key, rest = split_highlight(clean)
    if not key:
        key, rest = clean, ""

    max_hook_h = min(320, int((y_max - y) * 0.32)) if y_max else 260
    title_font = load_font(FS_HOOK, bold=True)
    lines = wrap_cn(draw, key, title_font, cw)
    for sz in range(FS_HOOK + 36, FS_HOOK - 8, -2):
        tf = load_font(sz, bold=True)
        trial = wrap_cn(draw, key, tf, cw)
        _, th = measure_lines(draw, trial, tf, HL_LINE_GAP)
        if th <= max_hook_h:
            title_font = tf
            lines = trial
            break

    cy = y
    for line in lines:
        w, h, top = line_metrics(draw, line, title_font)
        draw.rectangle([ix0, cy + top - 10, ix0 + w + 24, cy + top + h + 12], fill=theme["yellow"])
        draw.text((ix0 + 12, cy), line, fill=theme["ink"], font=title_font)
        cy += h + HL_LINE_GAP

    if rest:
        sf = load_font(FS_ROW_DESC)
        rest_lines = wrap_cn(draw, rest, sf, cw)
        cy += 4
        cy = draw_text_block(draw, rest_lines, sf, ix0, cy, theme["ink"], DESC_LINE_GAP, align="left", block_w=cw)
    return cy + HOOK_AFTER_GAP


def draw_rows(
    draw: ImageDraw.ImageDraw,
    frame: dict,
    items: list[tuple[str, str, str]],
    y: int,
    y_max: int,
) -> int:
    theme = frame["theme"]
    ix0, cw = frame["ix0"], frame["cw"]
    rows = [(h, d) for h, d, _ in items]
    heights = alloc_row_heights(draw, rows, y, y_max, cw)
    for (highlight, desc, kind), row_h in zip(items, heights):
        draw_list_row(draw, ix0, y, cw, row_h, highlight, desc, kind, theme)
        y += row_h + CARD_GAP
    return y


def draw_bullets(draw: ImageDraw.ImageDraw, frame: dict, bullets: list[str], y: int, y_max: int) -> int:
    items: list[tuple[str, str, str]] = []
    for raw in bullets:
        em = EMOJI_LEAD.match(raw.strip())
        emoji = em.group(1) if em else ""
        text = strip_emoji(raw)
        key, desc = split_highlight(text)
        items.append((key, desc, icon_kind(text, emoji)))
    return draw_rows(draw, frame, items, y, y_max)


def draw_body_paras(draw: ImageDraw.ImageDraw, frame: dict, body: str, y: int, y_max: int) -> int:
    ix0, cw = frame["ix0"], frame["cw"]
    theme = frame["theme"]
    lines_raw = [ln.strip() for ln in body.split("\n") if ln.strip()]

    if any("→" in ln for ln in lines_raw) and sum(1 for ln in lines_raw if "→" in ln) >= 4:
        items: list[tuple[str, str]] = []
        for line in lines_raw:
            for seg in re.split(r"[|｜]", line):
                if "→" in seg:
                    a, b = seg.split("→", 1)
                    items.append((a.strip(), b.strip()))
        gap = CARD_GAP
        cell_w = (cw - gap) // 2
        grid_h = y_max - y
        cell_h = (grid_h - gap) // 2
        icons = ["school", "engineering", "money", "book"]
        for idx, (left, right) in enumerate(items[:4]):
            col, row_i = idx % 2, idx // 2
            x = ix0 + col * (cell_w + gap)
            cy = y + row_i * (cell_h + gap)
            draw_list_row(draw, x, cy, cell_w, cell_h, left, right, icons[idx], theme)
        return y_max

    items = [(split_highlight(para)[0], split_highlight(para)[1], icon_kind(para)) for para in lines_raw]
    return draw_rows(draw, frame, items, y, y_max)


def draw_pairs(draw: ImageDraw.ImageDraw, frame: dict, pairs: list, y: int, y_max: int) -> int:
    theme = frame["theme"]
    ix0, cw = frame["ix0"], frame["cw"]
    gap = CARD_GAP
    cols = 2 if len(pairs) == 2 else 1
    col_w = (cw - gap) // 2 if cols == 2 else cw
    grid_rows = [pairs[i : i + cols] for i in range(0, len(pairs), cols)]
    for grid_row in grid_rows:
        rh = (y_max - y - gap * (len(grid_rows) - 1)) // len(grid_rows)
        for j, (title, bullet_items) in enumerate(grid_row):
            x = ix0 + j * (col_w + gap) if cols == 2 else ix0
            draw_round_card(draw, (x, y, x + col_w, y + rh), theme)
            title_clean = strip_emoji(title)
            tf = load_font(FS_PAIR_TITLE, bold=True)
            title_h, _ = draw_yellow_label(draw, x + 14, y + 14, title_clean, tf, theme, col_w - 28)
            bf = load_font(FS_PAIR_BODY)
            cy = y + 14 + title_h + 8
            for it in bullet_items:
                it_clean = strip_emoji(it)
                key, desc = split_highlight(it_clean)
                if not desc:
                    lh, _ = draw_yellow_label(draw, x + 14, cy, key, load_font(FS_ROW_TITLE, bold=True), theme, col_w - 28)
                    cy += lh + 6
                else:
                    line = f"——{desc}"
                    for ln in wrap_cn(draw, line, bf, col_w - 28):
                        draw.text((x + 14, cy), ln, fill=theme["ink"], font=bf)
                        cy += line_metrics(draw, ln, bf)[1] + DESC_LINE_GAP
            icon_k = "warn" if re.search(r"别|挤|❌", title) else "check"
            draw_flat_icon(draw, x + col_w - ICON_SIZE // 2 - 8, y + rh - ICON_SIZE // 2 - 8, ICON_SIZE - 16, icon_k, theme)
        y += rh + gap
    return y


def draw_steps(draw: ImageDraw.ImageDraw, frame: dict, steps: list, y: int, y_max: int) -> int:
    items = [(tag, text, icon_kind(tag + text)) for tag, text in steps]
    return draw_rows(draw, frame, items, y, y_max)


def draw_checklist(draw: ImageDraw.ImageDraw, frame: dict, items: list[str], y: int, y_max: int) -> int:
    return draw_bullets(draw, frame, items, y, y_max)


def draw_tip(draw: ImageDraw.ImageDraw, frame: dict, tip: str, y: int, y_max: int) -> int:
    key, desc = split_highlight(strip_emoji(tip))
    return draw_rows(draw, frame, [(key or tip, desc, "pin")], y, y_max)


def slide_row_items(slide: dict) -> list[tuple[str, str, str]]:
    """合并一页所有列表项（配图不含 CTA，CTA 仅保留在发布包）。"""
    items: list[tuple[str, str, str]] = []
    if slide.get("body"):
        for para in slide["body"].split("\n"):
            if para.strip():
                k, d = split_highlight(para.strip())
                items.append((k, d, icon_kind(para)))
    for raw in slide.get("bullets") or []:
        em = EMOJI_LEAD.match(raw.strip())
        emoji = em.group(1) if em else ""
        text = strip_emoji(raw)
        k, d = split_highlight(text)
        items.append((k, d, icon_kind(text, emoji)))
    for tag, text in slide.get("steps") or []:
        items.append((tag, text, icon_kind(tag + text)))
    for raw in slide.get("checklist") or []:
        em = EMOJI_LEAD.match(raw.strip())
        emoji = em.group(1) if em else ""
        text = strip_emoji(raw)
        k, d = split_highlight(text)
        items.append((k, d, icon_kind(text, emoji)))
    return items


def draw_content_slide(post: dict, slide: dict, path: Path) -> None:
    theme = build_theme(post["accent"])
    img = Image.new("RGB", (W, H), theme["bg"])
    draw = ImageDraw.Draw(img)
    frame = layout_frame(theme)
    y = frame["y0"]
    y_max = frame["y_max"]

    y = draw_hook(draw, frame, slide["hook"], y, y_max)

    is_closing = (
        bool(slide.get("checklist"))
        and not slide.get("pairs")
        and not slide.get("bullets")
        and not slide.get("steps")
    )
    if is_closing:
        items = slide_row_items(slide)
        if items:
            draw_rows(draw, frame, items, y, y_max)
        path.parent.mkdir(parents=True, exist_ok=True)
        img.save(path, "PNG")
        return

    heavy = sum(1 for k in ("bullets", "steps", "pairs", "checklist") if slide.get(k))
    body_cap = y + int((y_max - y) * (0.28 if heavy and slide.get("body") else 1.0))

    if slide.get("body") and not is_closing:
        y = draw_body_paras(draw, frame, slide["body"], y, body_cap if heavy else y_max)
    if slide.get("pairs"):
        y = draw_pairs(draw, frame, slide["pairs"], y, y_max)
    if slide.get("bullets"):
        y = draw_bullets(draw, frame, slide["bullets"], y, y_max)
    if slide.get("steps"):
        y = draw_steps(draw, frame, slide["steps"], y, y_max)
    if slide.get("checklist"):
        y = draw_checklist(draw, frame, slide["checklist"], y, y_max)
    if slide.get("tip"):
        y = draw_tip(draw, frame, slide["tip"], y, y_max)

    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "PNG")


def generate_all_slides() -> dict[str, list[str]]:
    import json

    manifest: dict[str, list[str]] = {}
    for post in POSTS:
        pid = post["id"]
        body_slides = [s for s in post["slides"] if s["label"] != "封面"]
        paths: list[str] = []
        for slide in body_slides:
            slug = slide_slug(slide["label"])
            out = SLIDES_OUT / f"post-{pid}-{slug}.png"
            draw_content_slide(post, slide, out)
            paths.append(str(out.relative_to(ROOT)).replace("\\", "/"))
        manifest[pid] = paths
    (SLIDES_OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


if __name__ == "__main__":
    m = generate_all_slides()
    print(f"Generated {sum(len(v) for v in m.values())} body slides -> {SLIDES_OUT}")

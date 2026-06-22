#!/usr/bin/env python3
"""Generate 5 Xiaohongshu-style HTML slide decks using frontend-slides conventions."""

from pathlib import Path

VIEWPORT_BASE_CSS = r"""/* ===========================================
   FIXED 16:9 STAGE: MANDATORY BASE STYLES
   =========================================== */
html, body {
    width: 100%;
    height: 100%;
    margin: 0;
    overflow: hidden;
    background: var(--stage-bg, #000);
}
.deck-viewport {
    position: fixed;
    inset: 0;
    overflow: hidden;
    background: var(--stage-bg, #1a1210);
}
.deck-stage {
    position: absolute;
    left: 0;
    top: 0;
    width: 1920px;
    height: 1080px;
    overflow: hidden;
    transform-origin: 0 0;
    background: var(--slide-bg, #fff8f4);
}
.slide {
    position: absolute;
    inset: 0;
    width: 1920px;
    height: 1080px;
    overflow: hidden;
    display: block;
    visibility: hidden;
    opacity: 0;
    pointer-events: none;
    background: var(--slide-bg, #fff8f4);
}
.slide.active, .slide.visible {
    visibility: visible;
    opacity: 1;
    pointer-events: auto;
    z-index: 1;
}
img, video, canvas, svg {
    max-width: 100%;
    max-height: 100%;
}
.deck-controls {
    position: fixed;
    left: 50%;
    bottom: 22px;
    transform: translateX(-50%);
    z-index: 1000;
}
@media print {
    html, body { width: 1920px; height: auto; overflow: visible; background: #fff; }
    .deck-viewport { position: static; overflow: visible; background: #fff; }
    .deck-stage { position: static; width: auto; height: auto; transform: none !important; background: none; }
    .slide {
        position: relative;
        display: block !important;
        visibility: visible !important;
        opacity: 1 !important;
        pointer-events: auto !important;
        width: 1920px;
        height: 1080px;
        break-after: page;
        page-break-after: always;
    }
    .slide:last-child { break-after: auto; page-break-after: auto; }
    .deck-controls { display: none !important; }
}
@media (prefers-reduced-motion: reduce) {
    *, *::before, *::after {
        animation-duration: 0.01ms !important;
        transition-duration: 0.2s !important;
    }
}"""

DECK_JS = r"""
class SlidePresentation {
    constructor() {
        this.slides = [...document.querySelectorAll('.slide')];
        this.current = 0;
        this.stage = document.getElementById('deckStage');
        this.counter = document.getElementById('slideCounter');
        this.setupStageScale();
        this.setupKeyboardNav();
        this.setupTouchNav();
        this.showSlide(0);
    }
    setupStageScale() {
        const scale = () => {
            const f = Math.min(window.innerWidth / 1920, window.innerHeight / 1080);
            const x = (window.innerWidth - 1920 * f) / 2;
            const y = (window.innerHeight - 1080 * f) / 2;
            this.stage.style.transform = `translate(${x}px, ${y}px) scale(${f})`;
        };
        scale();
        window.addEventListener('resize', scale);
    }
    setupKeyboardNav() {
        window.addEventListener('keydown', (e) => {
            if (['ArrowRight', 'ArrowDown', ' ', 'PageDown'].includes(e.key)) {
                e.preventDefault();
                this.showSlide(this.current + 1);
            }
            if (['ArrowLeft', 'ArrowUp', 'PageUp'].includes(e.key)) {
                e.preventDefault();
                this.showSlide(this.current - 1);
            }
            if (e.key === 'Home') this.showSlide(0);
            if (e.key === 'End') this.showSlide(this.slides.length - 1);
        });
    }
    setupTouchNav() {
        let startX = 0;
        this.stage.addEventListener('touchstart', (e) => { startX = e.changedTouches[0].screenX; }, { passive: true });
        this.stage.addEventListener('touchend', (e) => {
            const dx = e.changedTouches[0].screenX - startX;
            if (Math.abs(dx) > 50) this.showSlide(this.current + (dx < 0 ? 1 : -1));
        }, { passive: true });
    }
    showSlide(index) {
        this.current = Math.max(0, Math.min(index, this.slides.length - 1));
        this.slides.forEach((s, i) => {
            s.classList.toggle('active', i === this.current);
            s.classList.toggle('visible', i === this.current);
        });
        if (this.counter) this.counter.textContent = `${this.current + 1} / ${this.slides.length}`;
    }
    next() { this.showSlide(this.current + 1); }
    prev() { this.showSlide(this.current - 1); }
}
new SlidePresentation();
"""

THEME_CSS = r"""
:root {
    --stage-bg: #0d0d0d;
    --slide-bg: #fffdf5;
    --yellow: #ffe566;
    --yellow-deep: #ffd400;
    --red: #ff2442;
    --red-deep: #e01030;
    --ink: #141414;
    --text-primary: #141414;
    --text-secondary: #4a4a4a;
    --ok: #00b96b;
    --warn: #ff8a00;
    --card: #ffffff;
    --font-display: 'ZCOOL QingKe HuangYou', 'ZCOOL XiaoWei', cursive;
    --font-body: 'Noto Sans SC', sans-serif;
    --ease: cubic-bezier(0.16, 1, 0.3, 1);
    --stroke: 3px solid #141414;
    --shadow-pop: 8px 8px 0 #141414;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
.slide-inner {
    width: 1920px;
    height: 1080px;
    padding: 64px 88px;
    display: flex;
    flex-direction: column;
    position: relative;
    overflow: hidden;
}
.slide-inner::before {
    content: '';
    position: absolute;
    inset: 0;
    background:
        radial-gradient(circle at 12% 18%, rgba(255,228,102,0.55), transparent 22%),
        radial-gradient(circle at 88% 12%, rgba(255,36,66,0.18), transparent 20%),
        repeating-linear-gradient(-12deg, rgba(20,20,20,0.03) 0 8px, transparent 8px 16px);
    pointer-events: none;
}
.slide-inner::after {
    content: '干货';
    position: absolute;
    right: -20px;
    bottom: 120px;
    font: 700 180px/1 var(--font-display);
    color: rgba(255,36,66,0.05);
    transform: rotate(-18deg);
    pointer-events: none;
}
.cover-deco {
    position: absolute;
    inset: 0;
    pointer-events: none;
    z-index: 2;
}
.sticker {
    position: absolute;
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 14px 24px;
    border: var(--stroke);
    border-radius: 999px;
    box-shadow: var(--shadow-pop);
    font: 700 26px/1 var(--font-body);
    transform: rotate(-8deg);
}
.sticker-hot {
    top: 48px; right: 72px;
    background: var(--yellow);
    color: var(--ink);
}
.sticker-save {
    top: 130px; right: 96px;
    background: var(--red);
    color: #fff;
    transform: rotate(6deg);
    box-shadow: 6px 6px 0 #141414;
}
.badge {
    display: inline-flex;
    align-items: center;
    gap: 10px;
    padding: 14px 28px;
    border-radius: 12px;
    border: var(--stroke);
    background: var(--yellow);
    color: var(--ink);
    font: 800 28px/1 var(--font-body);
    letter-spacing: 0.06em;
    width: fit-content;
    box-shadow: var(--shadow-pop);
    transform: rotate(-2deg);
    position: relative;
    z-index: 3;
}
.title-slide .headline {
    font: 400 108px/1.05 var(--font-display);
    color: var(--ink);
    max-width: 1480px;
    margin-top: 40px;
    position: relative;
    z-index: 3;
    text-shadow: 4px 4px 0 #fff, 6px 6px 0 rgba(255,36,66,0.25);
}
.title-slide .headline .hl {
    display: inline;
    background: linear-gradient(180deg, transparent 58%, var(--yellow) 58%, var(--yellow) 92%, transparent 92%);
    box-decoration-break: clone;
}
.subtitle {
    font: 600 34px/1.55 var(--font-body);
    color: var(--text-secondary);
    max-width: 1180px;
    margin-top: 32px;
    padding: 22px 26px;
    background: rgba(255,255,255,0.88);
    border: 2px dashed rgba(20,20,20,0.18);
    border-radius: 18px;
    position: relative;
    z-index: 3;
}
.meta-row {
    display: flex;
    gap: 14px;
    margin-top: auto;
    flex-wrap: wrap;
    position: relative;
    z-index: 3;
}
.tag {
    padding: 12px 18px;
    border-radius: 999px;
    background: #fff;
    border: 2px solid var(--ink);
    font: 700 22px/1 var(--font-body);
    color: var(--red);
    box-shadow: 4px 4px 0 rgba(20,20,20,0.85);
}
.slide-no {
    position: absolute;
    top: 42px; right: 88px;
    font: 700 22px/1 var(--font-body);
    color: #fff;
    background: var(--ink);
    padding: 10px 16px;
    border-radius: 10px;
    z-index: 4;
}
h2.slide-title {
    font: 400 78px/1.08 var(--font-display);
    color: var(--ink);
    margin-bottom: 24px;
    position: relative;
    z-index: 3;
    display: inline-block;
    max-width: 92%;
}
h2.slide-title::after {
    content: '';
    position: absolute;
    left: 0; right: 0; bottom: 6px;
    height: 18px;
    background: var(--yellow);
    z-index: -1;
    transform: skewX(-8deg);
}
.lead {
    font: 600 32px/1.55 var(--font-body);
    color: var(--text-secondary);
    margin-bottom: 24px;
    position: relative;
    z-index: 3;
}
.bullets {
    list-style: none;
    display: flex;
    flex-direction: column;
    gap: 16px;
    position: relative;
    z-index: 3;
}
.bullets li {
    display: flex;
    gap: 16px;
    align-items: flex-start;
    font: 600 30px/1.42 var(--font-body);
    color: var(--text-primary);
    background: var(--card);
    border: var(--stroke);
    border-radius: 18px;
    padding: 22px 24px;
    box-shadow: 5px 5px 0 rgba(20,20,20,0.9);
}
.bullets li .icon {
    flex: 0 0 auto;
    font-size: 30px;
    line-height: 1.1;
    width: 48px; height: 48px;
    display: grid; place-items: center;
    background: var(--yellow);
    border: 2px solid var(--ink);
    border-radius: 12px;
}
.grid-2 {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 22px;
    flex: 1;
    position: relative;
    z-index: 3;
}
.card {
    background: var(--card);
    border: var(--stroke);
    border-radius: 22px;
    padding: 28px 30px;
    box-shadow: var(--shadow-pop);
}
.card h3 {
    font: 400 40px/1.1 var(--font-display);
    color: var(--red);
    margin-bottom: 14px;
}
.card p, .card li {
    font: 600 26px/1.5 var(--font-body);
    color: var(--text-primary);
}
.card ul { list-style: none; display: flex; flex-direction: column; gap: 10px; }
.quote-box {
    margin-top: auto;
    padding: 34px 38px;
    border: var(--stroke);
    background: linear-gradient(135deg, #fff 0%, #fff8d8 100%);
    border-radius: 24px;
    font: 400 42px/1.45 var(--font-display);
    color: var(--ink);
    box-shadow: var(--shadow-pop);
    position: relative;
    z-index: 3;
}
.quote-box::before {
    content: '“';
    position: absolute;
    top: -10px; left: 24px;
    font-size: 88px;
    color: var(--red);
    line-height: 1;
}
.compare {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 22px;
    position: relative;
    z-index: 3;
}
.compare .bad {
    border-top: 10px solid var(--warn);
    background: #fff9f0;
}
.compare .good {
    border-top: 10px solid var(--ok);
    background: #f2fff8;
}
.compare .card h3 { color: var(--ink); font-size: 34px; }
.cta-slide .cta {
    font: 400 72px/1.18 var(--font-display);
    color: var(--ink);
    max-width: 1400px;
    position: relative;
    z-index: 3;
}
.cta-slide .actions {
    margin-top: 36px;
    display: flex;
    gap: 18px;
    flex-wrap: wrap;
    position: relative;
    z-index: 3;
}
.cta-slide .action {
    padding: 20px 32px;
    border-radius: 16px;
    border: var(--stroke);
    background: var(--red);
    color: #fff;
    font: 800 30px/1 var(--font-body);
    box-shadow: var(--shadow-pop);
}
.cta-slide .hashtags {
    margin-top: auto;
    font: 600 24px/1.7 var(--font-body);
    color: var(--text-secondary);
    position: relative;
    z-index: 3;
}
.reveal {
    opacity: 0;
    transform: translateY(28px) scale(0.98);
    transition: opacity 0.55s var(--ease), transform 0.55s var(--ease);
}
.slide.visible .reveal {
    opacity: 1;
    transform: translateY(0) scale(1);
}
.reveal:nth-child(2) { transition-delay: 0.08s; }
.reveal:nth-child(3) { transition-delay: 0.16s; }
.reveal:nth-child(4) { transition-delay: 0.24s; }
.reveal:nth-child(5) { transition-delay: 0.32s; }
.deck-controls {
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 12px 20px;
    border-radius: 999px;
    border: 2px solid #fff;
    background: rgba(20,20,20,0.88);
    backdrop-filter: blur(8px);
    color: #fff;
    font: 600 16px/1 var(--font-body);
    box-shadow: 0 8px 24px rgba(0,0,0,0.28);
}
.deck-controls button {
    border: 2px solid #fff;
    background: var(--red);
    color: #fff;
    width: 42px;
    height: 42px;
    border-radius: 999px;
    cursor: pointer;
    font-size: 18px;
    font-weight: 800;
}
"""

DECKS = [
    {
        "filename": "post-01-no-never-unemploy.html",
        "title": "没有「永不失业」的专业",
        "slides": [
            {
                "type": "title",
                "badge": "高考出分 · 家长必读",
                "headline": "出分了先别慌！我把「10年不失业」这句话拆穿了",
                "subtitle": "AI 不是来抢专业的，是来抢岗位里重复的那部分活。",
                "tags": ["#高考出分", "#志愿填报", "#AI时代"],
            },
            {
                "type": "content",
                "title": "家长最吓人的一句话",
                "lead": "每年出分这几天，群里最常问：这个专业以后会不会被 AI 干掉？",
                "bullets": [
                    ("😰", "翻遍 AI 新闻、就业报告、亲戚建议，越看越乱"),
                    ("💡", "真正该问的不是「热不热」，而是能不能练到硬本事"),
                    ("🎯", "没有永远热门的专业，只有会不会持续升级的人"),
                ],
            },
            {
                "type": "compare",
                "title": "别问错问题",
                "bad": ["❌ 这个专业热不热？", "❌ 4年后还好不好找工作？"],
                "good": [
                    "✅ 能不能练到硬本事？",
                    "✅ 孩子愿不愿意学10年？",
                    "✅ 学校有没有真师资、真实习？",
                ],
            },
            {
                "type": "grid",
                "title": "更稳的方向参考",
                "cards": [
                    ("工科", "芯片、机器人、新能源、软件"),
                    ("理科", "数学、统计、材料、生物（多数要读研）"),
                    ("商科", "会计、金融、电商，别选空泛管理"),
                    ("文科", "法学、教育、传播 + 会用 AI 提效"),
                    ("艺术", "UI、品牌、数媒，别只会套模板"),
                ],
            },
            {
                "type": "quote",
                "title": "给家长的一句话",
                "quote": "别帮孩子押一个「永远热门」的名字，帮他把底座打牢。大学四年只是起点，会学习的人，换赛道都来得及。",
            },
            {
                "type": "cta",
                "cta": "收藏这篇，填志愿前对照一遍。转给那个「只想报热门」的家人。",
                "hashtags": "#高考出分 #志愿填报 #选专业 #家长必看 #AI时代 #升学规划",
            },
        ],
    },
    {
        "filename": "post-02-ai-traps.html",
        "title": "AI 时代选专业 5 个坑",
        "slides": [
            {
                "type": "title",
                "badge": "AI选专业 · 避坑指南",
                "headline": "AI 这么火，专业到底怎么选？这 5 个坑我家差点全踩",
                "subtitle": "人人都知道 AI 热，4 年后最卷的，可能正是名字最热的那批人。",
                "tags": ["#AI选专业", "#志愿填报", "#家长焦虑"],
            },
            {
                "type": "content",
                "title": "坑 1：只看专业名，不看学校培养",
                "bullets": [
                    ("🏫", "同样是「人工智能」，有的有实验室、有项目、有企业合作"),
                    ("⚠️", "有的就是新开专业、师资还在凑"),
                    ("📌", "学校质量 > 专业名字"),
                ],
            },
            {
                "type": "content",
                "title": "坑 2：数学物理不行，硬冲顶尖 AI/芯片",
                "bullets": [
                    ("📐", "AI 工程师、芯片工程师、数据工程师，底层都是数学、逻辑、编程"),
                    ("😣", "孩子痛苦 4 年，不如选更匹配的工科底座"),
                    ("✅", "能学下去，比名字好听重要得多"),
                ],
            },
            {
                "type": "compare",
                "title": "坑 3 & 4：文科没出路？商科只报泛管理？",
                "bad": [
                    "❌ 以为文科只能做模板写作、搬运",
                    "❌ 商科只报工商管理、市场营销",
                ],
                "good": [
                    "✅ 合规、品牌、用户研究更需要判断+表达",
                    "✅ 会计、金融、电商 + Python/SQL 更稳",
                ],
            },
            {
                "type": "content",
                "title": "坑 5：艺术生以为会 AI 出图就够了",
                "bullets": [
                    ("🎨", "Midjourney 谁都会用"),
                    ("💎", "值钱的是审美体系、品牌思维、作品集"),
                    ("🚀", "UI/UX、品牌设计、游戏美术比低端美工稳太多"),
                ],
            },
            {
                "type": "quote",
                "title": "选专业公式",
                "quote": "扎实底座 + 行业场景 + 会用 AI = 10 年后还能打。不是和 AI 比速度，是做 AI 替不了判断的那部分。",
            },
            {
                "type": "cta",
                "cta": "建议收藏，填志愿前一晚全家一起读。",
                "hashtags": "#AI选专业 #高考志愿填报 #家长焦虑 #填志愿攻略 #避坑指南",
            },
        ],
    },
    {
        "filename": "post-03-score-tiers.html",
        "title": "不同分数段怎么选专业",
        "slides": [
            {
                "type": "title",
                "badge": "分数段选专业 · 务实版",
                "headline": "出分后别只盯 985！不同分数段，10 年后更好就业的方向",
                "subtitle": "最怕的不是分不够高，是用错误的分数去赌一个错误的热门。",
                "tags": ["#分数段选专业", "#高考出分", "#家长必读"],
            },
            {
                "type": "card",
                "title": "高分段 650+",
                "subtitle": "关键词：平台 + 科研 + 深造机会",
                "bullets": [
                    "计算机 / 软件 / 人工智能 / 数据科学",
                    "电子信息、集成电路、智能科学",
                    "自动化、机器人、航空航天",
                    "临床医学（能接受长学制）",
                    "数学、物理（适合愿意深造）",
                ],
            },
            {
                "type": "card",
                "title": "中分段 550-650",
                "subtitle": "关键词：就业指向清晰，比名字好听更重要",
                "bullets": [
                    "电气、机械、自动化、物联网",
                    "能源、材料、化工（看区域产业）",
                    "会计、审计、金融、经济统计",
                    "医学技术、康复、药学",
                    "师范、法学、电子商务",
                ],
            },
            {
                "type": "card",
                "title": "相对低分段 本科线-550",
                "subtitle": "关键词：先就业，再升级",
                "bullets": [
                    "护理、康复",
                    "软件技术、数字媒体技术",
                    "电气、土木、机械（结合本地基建）",
                    "学前教育、社会工作、会计、电商运营",
                    "慎选：名字很新、就业路径模糊的交叉专业",
                ],
            },
            {
                "type": "content",
                "title": "家长请记住 3 句话",
                "bullets": [
                    ("1️⃣", "热门 4 年后可能饱和，冷门也可能因产业变香"),
                    ("2️⃣", "城市和产业，有时比学校名气更影响第一份工作"),
                    ("3️⃣", "孩子学不下去的专业，再热门也没用"),
                ],
            },
            {
                "type": "cta",
                "cta": "不是选一定发财的专业，是选愿意学、学得会、能不断升级的方向。",
                "hashtags": "#高考出分 #志愿填报 #分数段选专业 #升学规划 #填志愿干货",
            },
        ],
    },
    {
        "filename": "post-04-liberal-arts.html",
        "title": "文科生家长别慌",
        "slides": [
            {
                "type": "title",
                "badge": "文科生选专业",
                "headline": "我家文科生出分了…亲戚都说「文科没前途」？我把话说明白",
                "subtitle": "AI 冲击最大的不是「文科」，而是只会重复、不会判断的基础事务。",
                "tags": ["#文科生选专业", "#AI时代", "#家长焦虑"],
            },
            {
                "type": "compare",
                "title": "先分清：什么会被挤掉，什么依然值钱",
                "bad": ["❌ 模板写作、简单翻译、机械整理"],
                "good": [
                    "✅ 规则判断、信任沟通",
                    "✅ 复杂决策、跨文化表达",
                ],
            },
            {
                "type": "content",
                "title": "相对更有机会的方向",
                "bullets": [
                    ("⚖️", "法学：合规、知产、数据合规越来越重要"),
                    ("📣", "新传/广告：品牌策略、内容策略，不是纯搬运"),
                    ("🌍", "英语/小语种 + 经贸/法律/国际关系"),
                    ("📚", "教育学、社会工作：抗周期，偏公共服务"),
                    ("🗂️", "档案、信息管理：数字化方向"),
                ],
            },
            {
                "type": "content",
                "title": "文科生必须补的两项能力",
                "bullets": [
                    ("📊", "数据思维：Excel、基础 SQL、调研分析"),
                    ("🤖", "AI 工具：会用 AI 提效，但知道什么不能盲信"),
                ],
            },
            {
                "type": "quote",
                "title": "给文科生的策略",
                "quote": "「文科的脑子 + 数据的手 + AI 的工具」。别和 AI 比谁写得快，去做 AI 做不了的事：承担责任、处理模糊问题、建立信任。",
            },
            {
                "type": "cta",
                "cta": "文科不是不能就业，泛文科 + 无实习 + 无技能，才最难。",
                "hashtags": "#文科生选专业 #高考出分 #法学 #新传 #升学建议",
            },
        ],
    },
    {
        "filename": "post-05-three-tracks.html",
        "title": "工科 / 商科 / 艺术别用同一套逻辑",
        "slides": [
            {
                "type": "title",
                "badge": "分赛道选专业",
                "headline": "同样是出分选专业，工科/商科/艺术家长千万别用同一套逻辑！",
                "subtitle": "问题不是哪个最好，是你家孩子属于哪一类，却用了别人的选法。",
                "tags": ["#工科", "#商科", "#艺术生", "#AI时代"],
            },
            {
                "type": "card",
                "title": "工科生家长",
                "subtitle": "未来 10 年岗位增量最明确",
                "bullets": [
                    "✅ 计算机、软件、电子信息、自动化、电气",
                    "✅ 机器人、新能源、集成电路",
                    "⚠️ 别只看「人工智能」四个字",
                    "⚠️ 传统工科也要会编程、仿真、AI 工具",
                ],
            },
            {
                "type": "card",
                "title": "商科生家长",
                "subtitle": "低端事务岗最先被 AI 挤",
                "bullets": [
                    "✅ 会计、审计、财务管理",
                    "✅ 金融、经济统计、保险精算",
                    "✅ 电子商务、数字经济、国际贸易",
                    "❌ 只会做表、做 PPT 的空泛商科",
                ],
            },
            {
                "type": "card",
                "title": "艺术生家长",
                "subtitle": "AI 是工具，不是替代品",
                "bullets": [
                    "冲击大：低端插画、模板设计、无风格美工",
                    "✅ UI/UX、视觉传达（品牌向）",
                    "✅ 数字媒体艺术、动画、游戏美术",
                    "✅ 影视编导、摄影（有作品才说话）",
                ],
            },
            {
                "type": "content",
                "title": "填志愿前，全家只讨论 4 件事",
                "bullets": [
                    ("1", "孩子擅长什么"),
                    ("2", "孩子愿不愿意学"),
                    ("3", "学校这个专业强不强"),
                    ("4", "4 年后想就业还是深造"),
                ],
            },
            {
                "type": "cta",
                "cta": "比「热不热」重要的，永远是「适不适配」。收藏，填志愿前一晚全家开会用。",
                "hashtags": "#高考志愿填报 #选专业 #工科 #商科 #艺术生 #填志愿干货",
            },
        ],
    },
]


def render_slide(slide: dict, index: int, total: int) -> str:
    active = " active" if index == 0 else ""
    t = slide["type"]
    page_no = f'<span class="slide-no">{index + 1}/{total}</span>' if t != "title" else ""

    if t == "title":
        tags = "".join(f'<span class="tag">{x}</span>' for x in slide.get("tags", []))
        headline = slide["headline"]
        # highlight segment after punctuation for cover punch
        if "！" in headline:
            parts = headline.split("！", 1)
            headline_html = f'<span class="hl">{parts[0]}！</span>{parts[1]}'
        elif "？" in headline:
            parts = headline.split("？", 1)
            headline_html = f'<span class="hl">{parts[0]}？</span>{parts[1]}'
        else:
            headline_html = f'<span class="hl">{headline}</span>'
        return f"""
        <section class="slide title-slide{active}">
            <div class="slide-inner">
                <div class="cover-deco">
                    <span class="sticker sticker-hot">🔥 爆款干货</span>
                    <span class="sticker sticker-save">📌 建议收藏</span>
                </div>
                <div class="badge reveal">{slide['badge']}</div>
                <h1 class="headline reveal">{headline_html}</h1>
                <p class="subtitle reveal">{slide['subtitle']}</p>
                <div class="meta-row reveal">{tags}</div>
            </div>
        </section>"""

    if t == "content":
        items = "".join(
            f'<li class="reveal"><span class="icon">{icon}</span><span>{text}</span></li>'
            for icon, text in slide["bullets"]
        )
        lead = f'<p class="lead reveal">{slide["lead"]}</p>' if slide.get("lead") else ""
        return f"""
        <section class="slide{active}">
            <div class="slide-inner">
                {page_no}
                <h2 class="slide-title reveal">{slide['title']}</h2>
                {lead}
                <ul class="bullets">{items}</ul>
            </div>
        </section>"""

    if t == "compare":
        bad = "".join(f"<li>{x}</li>" for x in slide["bad"])
        good = "".join(f"<li>{x}</li>" for x in slide["good"])
        return f"""
        <section class="slide{active}">
            <div class="slide-inner">
                {page_no}
                <h2 class="slide-title reveal">{slide['title']}</h2>
                <div class="compare">
                    <div class="card bad reveal"><h3>❌ 别这样问</h3><ul>{bad}</ul></div>
                    <div class="card good reveal"><h3>✅ 应该这样问</h3><ul>{good}</ul></div>
                </div>
            </div>
        </section>"""

    if t == "grid":
        cards = "".join(
            f'<div class="card reveal"><h3>{title}</h3><p>{body}</p></div>'
            for title, body in slide["cards"]
        )
        return f"""
        <section class="slide{active}">
            <div class="slide-inner">
                {page_no}
                <h2 class="slide-title reveal">{slide['title']}</h2>
                <div class="grid-2">{cards}</div>
            </div>
        </section>"""

    if t == "card":
        items = "".join(f"<li>{x}</li>" for x in slide["bullets"])
        return f"""
        <section class="slide{active}">
            <div class="slide-inner">
                {page_no}
                <h2 class="slide-title reveal">{slide['title']}</h2>
                <p class="lead reveal">{slide['subtitle']}</p>
                <div class="card reveal"><ul>{items}</ul></div>
            </div>
        </section>"""

    if t == "quote":
        return f"""
        <section class="slide{active}">
            <div class="slide-inner">
                {page_no}
                <h2 class="slide-title reveal">{slide['title']}</h2>
                <div class="quote-box reveal">{slide['quote']}</div>
            </div>
        </section>"""

    if t == "cta":
        return f"""
        <section class="slide cta-slide{active}">
            <div class="slide-inner">
                <div class="cover-deco">
                    <span class="sticker sticker-hot">⭐ 转发家长群</span>
                </div>
                {page_no}
                <div class="cta reveal">{slide['cta']}</div>
                <div class="actions reveal">
                    <span class="action">👉 收藏</span>
                    <span class="action">📤 转发给爸妈</span>
                </div>
                <div class="hashtags reveal">{slide['hashtags']}</div>
            </div>
        </section>"""

    raise ValueError(f"Unknown slide type: {t}")


def render_deck(deck: dict) -> str:
    total = len(deck["slides"])
    slides_html = "".join(render_slide(s, i, total) for i, s in enumerate(deck["slides"]))
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{deck['title']}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@400;500;600;700;800&family=ZCOOL+QingKe+HuangYou&family=ZCOOL+XiaoWei&display=swap" rel="stylesheet">
  <style>
    {THEME_CSS}
    {VIEWPORT_BASE_CSS}
  </style>
</head>
<body>
  <div class="deck-viewport">
    <main class="deck-stage" id="deckStage">
      {slides_html}
    </main>
  </div>
  <div class="deck-controls">
    <button type="button" onclick="window.__deck && window.__deck.prev()">←</button>
    <span id="slideCounter">1 / {len(deck['slides'])}</span>
    <button type="button" onclick="window.__deck && window.__deck.next()">→</button>
    <span>空格/方向键翻页</span>
  </div>
  <script>
    window.__deck = null;
    {DECK_JS.replace('new SlidePresentation();', 'window.__deck = new SlidePresentation();')}
  </script>
</body>
</html>
"""


def render_index() -> str:
    post_cards = "".join(
        f"""
        <a class="deck-card" href="{d['filename']}">
          <div class="card-top">
            <span class="num">0{i}</span>
            <span class="pill">爆款封面</span>
          </div>
          <h2>{d['title']}</h2>
          <p>{len(d['slides'])} 页轮播 · 截图即发小红书</p>
        </a>"""
        for i, d in enumerate(DECKS, 1)
    )
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>高考选专业 · 小红书爆款封面合集</title>
  <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@400;600;700;800&family=ZCOOL+QingKe+HuangYou&display=swap" rel="stylesheet">
  <style>
    :root {{
      --bg: #fffdf5;
      --ink: #141414;
      --red: #ff2442;
      --yellow: #ffe566;
      --muted: #5a5a5a;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: 'Noto Sans SC', sans-serif;
      background:
        radial-gradient(circle at 10% 0%, rgba(255,229,102,0.65), transparent 24%),
        radial-gradient(circle at 95% 8%, rgba(255,36,66,0.14), transparent 18%),
        repeating-linear-gradient(-10deg, rgba(20,20,20,0.025) 0 10px, transparent 10px 20px),
        var(--bg);
      color: var(--ink);
      min-height: 100vh;
      padding: 40px 20px 72px;
    }}
    .wrap {{ max-width: 1140px; margin: 0 auto; }}
    .hero {{
      position: relative;
      padding: 34px 30px;
      border: 3px solid var(--ink);
      border-radius: 28px;
      background: linear-gradient(135deg, #fff 0%, #fff6d8 100%);
      box-shadow: 10px 10px 0 var(--ink);
      margin-bottom: 28px;
      overflow: hidden;
    }}
    .hero::after {{
      content: '必看';
      position: absolute;
      top: 18px; right: -28px;
      background: var(--red);
      color: #fff;
      font-weight: 800;
      padding: 10px 56px;
      transform: rotate(28deg);
      font-size: 14px;
      letter-spacing: 0.1em;
    }}
    .hero-badge {{
      display: inline-block;
      background: var(--yellow);
      border: 2px solid var(--ink);
      padding: 8px 14px;
      border-radius: 999px;
      font-weight: 800;
      font-size: 13px;
      margin-bottom: 14px;
      box-shadow: 4px 4px 0 var(--ink);
    }}
    h1 {{
      font-family: 'ZCOOL QingKe HuangYou', cursive;
      font-size: clamp(38px, 6vw, 64px);
      line-height: 1.08;
      max-width: 900px;
    }}
    h1 .hl {{
      background: linear-gradient(180deg, transparent 62%, var(--yellow) 62%, var(--yellow) 90%, transparent 90%);
    }}
    .intro {{ color: var(--muted); font-size: 17px; line-height: 1.75; margin-top: 14px; max-width: 860px; }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 18px;
    }}
    .deck-card {{
      display: block;
      text-decoration: none;
      color: inherit;
      background: #fff;
      border: 3px solid var(--ink);
      border-radius: 22px;
      padding: 22px;
      box-shadow: 7px 7px 0 var(--ink);
      transition: transform .18s ease;
    }}
    .deck-card:hover {{ transform: translate(-3px, -3px); }}
    .deck-card.featured {{
      background: linear-gradient(160deg, #fff 0%, #fff4d6 55%, #ffe3ea 100%);
      grid-column: 1 / -1;
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 16px;
      align-items: center;
    }}
    .card-top {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }}
    .num {{
      width: 44px; height: 44px; border-radius: 12px;
      display: grid; place-items: center;
      background: var(--yellow);
      border: 2px solid var(--ink);
      font-weight: 800;
    }}
    .pill {{
      font-size: 12px; font-weight: 800; color: var(--red);
      border: 2px solid var(--red); border-radius: 999px; padding: 4px 10px;
    }}
    .deck-card h2 {{
      font-family: 'ZCOOL QingKe HuangYou', cursive;
      font-size: 28px;
      line-height: 1.2;
      margin-bottom: 8px;
    }}
    .deck-card p {{ color: var(--muted); font-size: 14px; font-weight: 600; }}
    .featured-cta {{
      justify-self: end;
      background: var(--red);
      color: #fff;
      border: 2px solid var(--ink);
      padding: 14px 22px;
      border-radius: 14px;
      font-weight: 800;
      box-shadow: 5px 5px 0 var(--ink);
      white-space: nowrap;
    }}
    footer {{ margin-top: 34px; color: var(--muted); font-size: 13px; line-height: 1.7; }}
  </style>
</head>
<body>
  <div class="wrap">
    <section class="hero">
      <span class="hero-badge">🔥 祝愿心想事成！</span>
      <h1>高考出分选专业<br><span class="hl">爆帖轮播 + 分数选校工具</span></h1>
      <p class="intro">5 篇爆帖已统一换成高对比「封面海报」视觉：黄底高亮、贴纸标签、粗描边卡片。另附交互选校页，拖拽分数看院校与 10 年热门专业。</p>
    </section>
    <div class="grid">
      <a class="deck-card featured" href="selector.html">
        <div>
          <div class="card-top"><span class="num">★</span><span class="pill">交互工具</span></div>
          <h2>分数选校选专业 · 拖拽看推荐</h2>
          <p>31 省 · 2014-2025 · 院校分级 + 热门专业排序</p>
        </div>
        <span class="featured-cta">立即体验 →</span>
      </a>
      {post_cards}
    </div>
    <footer>技术说明：幻灯片为 16:9 固定画布（1920×1080），方向键/空格翻页后截图即可发小红书。选校工具需本地服务器打开。</footer>
  </div>
</body>
</html>
"""


def main():
    out = Path(__file__).parent
    for deck in DECKS:
        path = out / deck["filename"]
        path.write_text(render_deck(deck), encoding="utf-8")
        print(f"Wrote {path.name}")
    index_path = out / "index.html"
    index_path.write_text(render_index(), encoding="utf-8")
    print(f"Wrote {index_path.name}")


if __name__ == "__main__":
    main()

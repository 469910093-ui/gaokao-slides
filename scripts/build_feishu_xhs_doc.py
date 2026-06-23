#!/usr/bin/env python3
"""Generate XHS-style cover images and Feishu doc XML for all 9 posts."""
from __future__ import annotations

import html
import json
import re
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "publish" / "feishu"
COVERS = OUT_DIR / "covers"
XML_PATH = OUT_DIR / "feishu_xhs_posts.xml"
META_PATH = OUT_DIR / "feishu_doc_meta.json"

# Xiaohongshu carousel cover ratio 3:4
W, H = 1080, 1440

POSTS = [
    {
        "id": "01",
        "cover_title": "没有永不\n失业的专业",
        "cover_sub": "出分了先别慌",
        "accent": "#FF2442",
        "goal": "工具引流 · 表弟故事 · 焦虑破冰",
        "slides": [
            {
                "label": "封面",
                "hook": "出分了先别慌！我把「10年不失业」这句话拆穿了",
                "body": "AI 抢的不是专业名\n是岗位里重复的那部分活",
                "tags_preview": "高考出分 · 志愿填报 · 家长必看",
            },
            {
                "label": "P2 痛点",
                "hook": "群里最怕被问的一句",
                "body": "",
                "bullets": [
                    "「会不会被 AI 干掉？」：每年都有人问",
                    "越查越乱：缺的不是信息，是判断框架",
                    "💡 该问：孩子能不能练到硬本事",
                    "🎯 没有永远热门的专业，只有会不会升级的人",
                ],
            },
            {
                "label": "P3 换问题",
                "hook": "别问「热不热」，先换这 2 个问题",
                "body": "",
                "pairs": [
                    ("❌ 别这样问", ["这个专业热不热？", "4年后还好找工作吗？"]),
                    ("✅ 应该这样问", ["岗位核心能力是什么？", "孩子愿不愿意练 4 年？"]),
                ],
            },
            {
                "label": "P4 方向",
                "hook": "更稳的方向参考（不是铁饭碗清单）",
                "bullets": [
                    "需要现场判断：护理、康复、口腔、临床",
                    "需要系统能力：电气、自动化、网安、软工",
                    "需要创意+技术：UI/UX、数字媒体、游戏美术",
                    "需要数据+业务：会计、经济统计、电商运营",
                ],
            },
            {
                "label": "P5 行动",
                "hook": "给家长的一句话 + 今晚就能做",
                "body": "选专业不是赌运气，是帮孩子找到「愿意学 + 学得会 + 能升级」的路。",
                "steps": [
                    ("今晚", "查一分一段表，记录位次（别只看往年线）"),
                    ("明天", "列冲稳保各3所：+5分 / ±3分 / -10分"),
                    ("填志愿前", "就业沙盘看心仪专业 Top 岗位与 5 年薪资"),
                    ("定稿前", "全家 15 分钟会：擅长什么、愿不愿意学、学校强不强"),
                ],
            },
            {
                "label": "P6 收尾",
                "hook": "收藏这篇，按清单做，比空焦虑有用",
                "checklist": [
                    "截图保存 4 步实操清单",
                    "打开分数选校（省份+科类+分数）",
                    "就业沙盘核对心仪专业 Top 岗位",
                    "进群领冲稳保模板 + 交流",
                ],
                "cta": "评论区扣：省份+分数+科类 → 发你冲稳保清单",
                "hashtags": "#高考出分[话题]# #志愿填报[话题]# #选专业[话题]# #冲稳保[话题]# #填志愿攻略[话题]# #升学规划[话题]# #高考查分瞬间[话题]# #高考报考[话题]# #热门专业[话题]# #大学生一定要打破信息差[话题]#",
            },
        ],
    },
    {
        "id": "02",
        "cover_title": "AI选专业5个坑",
        "cover_sub": "我家差点全踩",
        "accent": "#FF2442",
        "goal": "避坑收藏 · 评论互动",
        "slides": [
            {
                "label": "封面",
                "hook": "AI 这么火，专业怎么选？这 5 个坑我家差点全踩",
                "body": "人人都知道 AI 热\n4 年后最卷的，可能是名字最热那批",
                "tags_preview": "AI选专业 · 避坑指南",
            },
            {
                "label": "P2 坑1",
                "hook": "坑 1：只看专业名，不看学校培养",
                "bullets": [
                    "🏫 同是「人工智能」，有的有实验室、项目、企业合作",
                    "⚠️ 有的就是新开专业、师资还在凑",
                    "📌 学校质量 > 专业名字",
                ],
            },
            {
                "label": "P3 坑2",
                "hook": "坑 2：数学物理不行，硬冲顶尖 AI/芯片",
                "bullets": [
                    "顶尖方向默认要扎实的数理基础",
                    "数学/物理/编程各打 1-5 分",
                    "有两项 ≤2，就别硬冲顶尖 AI/芯片",
                ],
            },
            {
                "label": "P4 坑3&4",
                "hook": "坑 3 & 4：文科没出路？商科只报泛管理？",
                "pairs": [
                    ("文科", ["❌ 会被挤掉：纯事务、无场景", "✅ 仍值钱：法学/新传/中文+实习+数据手"]),
                    ("商科", ["✅ 会计、审计、财管、经济统计", "❌ 只会做表做 PPT 的空泛管理"]),
                ],
            },
            {
                "label": "P5 坑5",
                "hook": "坑 5：艺术生以为会 AI 出图就够了",
                "bullets": [
                    "冲击大：低端插画、模板设计、无风格美工",
                    "✅ UI/UX、品牌视觉、数媒、游戏美术",
                    "✅ 影视编导、摄影——有作品才说话",
                ],
            },
            {
                "label": "P6 公式",
                "hook": "选专业公式 + 今晚就能做",
                "steps": [
                    ("Step1", "官网看培养方案：实验室/实习/竞赛"),
                    ("Step2", "数理编程自评，两项≤2别硬冲"),
                    ("Step3", "沙盘搜专业，看 Top3 岗位愿不愿意做"),
                    ("Step4", "每个意向至少备 1 个相近备选"),
                ],
            },
            {
                "label": "P7 收尾",
                "hook": "建议收藏，填志愿前一晚全家过一遍",
                "checklist": [
                    "每个意向专业查官网培养方案",
                    "沙盘对比 2 个专业岗位薪资",
                    "分数选校拉出冲稳保院校",
                    "转发给「只想报热门」的家人",
                ],
                "cta": "评论扣 1-5：你家最怕哪个坑？",
                "hashtags": "#AI选专业 #高考志愿填报 #家长焦虑 #填志愿攻略 #避坑指南 #高考出分 #选专业 #高三 #升学规划 #志愿填报技巧",
            },
        ],
    },
    {
        "id": "03",
        "cover_title": "分数段选专业",
        "cover_sub": "别只盯985",
        "accent": "#FF2442",
        "goal": "干货收藏 · 搜索引流",
        "slides": [
            {
                "label": "封面",
                "hook": "出分后别只盯 985！不同分数段，10 年后更好就业的方向",
                "body": "最怕的不是分不够高\n是用错误的分数去赌一个错误的热门",
                "tags_preview": "分数段选专业 · 务实版",
            },
            {
                "label": "P2 650+",
                "hook": "高分段 650+｜关键词：平台 + 科研 + 深造",
                "bullets": [
                    "计算机 / 软工 / AI / 数据科学",
                    "电子信息、集成电路、智能科学",
                    "自动化、机器人、航空航天",
                    "临床医学（能接受长学制）",
                    "数学、物理（适合愿意深造）",
                ],
                "tip": "📌 分数选校输入 650+，冲稳保各截 3 所",
            },
            {
                "label": "P3 550-650",
                "hook": "中分段 550-650｜就业指向清晰 > 名字好听",
                "bullets": [
                    "电气、机械、自动化、物联网",
                    "能源、材料、化工（看区域产业）",
                    "会计、审计、金融、经济统计",
                    "医学技术、康复、药学",
                    "师范、法学、电子商务",
                ],
                "tip": "📌 优先选本省有产业园区的专业",
            },
            {
                "label": "P4 本科线-550",
                "hook": "相对低分段｜关键词：先就业，再升级",
                "bullets": [
                    "护理、康复",
                    "软件技术、数字媒体技术",
                    "电气、土木、机械（结合本地基建）",
                    "学前教育、社工、会计、电商运营",
                    "慎选：名字很新、路径模糊的交叉专业",
                ],
                "tip": "📌 沙盘看应届 Top3 岗位薪资再决定",
            },
            {
                "label": "P5 三句话",
                "hook": "家长请记住 3 句话",
                "bullets": [
                    "1️⃣ 热门 4 年后可能饱和 → 查近 3 年招生人数",
                    "2️⃣ 城市产业比名气重要 → 列 3 个愿去的城市及产业",
                    "3️⃣ 学不下去再热也没用 → 问孩子愿不愿意学 4 年",
                ],
            },
            {
                "label": "P6 收尾",
                "hook": "不是选一定发财的专业，是选愿意学、学得会、能升级的",
                "checklist": [
                    "按分数段截图保存专业清单",
                    "分数选校看可达院校层级",
                    "每个分数段备 3 个学得下的专业",
                    "低分段优先选路径清晰的方向",
                ],
                "cta": "评论扣分数段：650+ / 550-650 / 本科线 → 发对应清单",
                "hashtags": "#高考出分 #志愿填报 #分数段选专业 #升学规划 #填志愿干货 #高三家长 #大学报考 #选专业 #高考志愿 #中分段考生",
            },
        ],
    },
    {
        "id": "04",
        "cover_title": "文科生家长别慌",
        "cover_sub": "我把话说明白",
        "accent": "#FF2442",
        "goal": "文科共鸣 · 收藏转发",
        "slides": [
            {
                "label": "封面",
                "hook": "我家文科生出分了…亲戚都说「文科没前途」？",
                "body": "AI 冲击最大的不是「文科」\n是只会重复、不会判断的基础事务",
                "tags_preview": "文科生选专业",
            },
            {
                "label": "P2 分清",
                "hook": "先分清：什么会被挤掉，什么依然值钱",
                "pairs": [
                    ("容易被挤掉", ["纯文案搬运", "无场景的事务岗", "不会用数据的泛文职"]),
                    ("依然值钱", ["法学+法考路径", "新传+作品+实习", "中文+考公/内容平台", "财会+证书+数字化"]),
                ],
            },
            {
                "label": "P3 方向",
                "hook": "相对更有机会的方向",
                "bullets": [
                    "法学：红圈所/法务/公检法（要熬证书）",
                    "新闻传播：平台运营、品牌、内容（要作品）",
                    "汉语言：考公、编辑、内容策划（面宽）",
                    "会计学/审计：事务所、企业财务（要证）",
                ],
            },
            {
                "label": "P4 两项能力",
                "hook": "文科生必须补的两项能力",
                "bullets": [
                    "📊 数据手：Excel 透视表 / 基础 SQL",
                    "🤖 AI 手：用 AI 写提纲，自己核对来源",
                    "没有这两样，再好的学校也难拉开差距",
                ],
            },
            {
                "label": "P5 行动",
                "hook": "给文科生的策略 + 本周行动",
                "steps": [
                    ("本周", "完成 1 个 Excel 或 SQL 小练习"),
                    ("本周", "用 AI 写调研提纲并自己核对数据"),
                    ("志愿前", "查目标专业实习/就业去向"),
                    ("定专业", "法学/新传/教育选能对接真实业务的"),
                ],
            },
            {
                "label": "P6 收尾",
                "hook": "文科不是不能就业\n泛文科 + 无实习 + 无技能，才最难",
                "checklist": [
                    "本周完成 1 个数据小练习",
                    "沙盘查看文科类专业岗位薪资",
                    "每个意向专业查实习去向",
                    "收藏本篇，填志愿前对照",
                ],
                "cta": "文科家长扣「文科」：说说你家最纠结哪个专业",
                "hashtags": "#文科生选专业 #高考出分 #法学 #新传 #升学建议 #志愿填报 #汉语言文学 #考公选专业 #高三文科 #家长必读",
            },
        ],
    },
    {
        "id": "05",
        "cover_title": "三赛道别混用",
        "cover_sub": "工科/商科/艺术",
        "accent": "#FF2442",
        "goal": "分赛道收藏 · 转发家人",
        "slides": [
            {
                "label": "封面",
                "hook": "工科/商科/艺术家长，千万别用同一套逻辑选专业！",
                "body": "问题不是哪个最好\n是你家孩子属于哪一类，却用了别人的选法",
                "tags_preview": "分赛道选专业",
            },
            {
                "label": "P2 工科",
                "hook": "工科生家长｜未来 10 年岗位增量最明确",
                "bullets": [
                    "✅ 计算机、软工、电子信息、自动化、电气",
                    "✅ 机器人、新能源、集成电路",
                    "⚠️ 别只看「人工智能」四个字",
                    "⚠️ 传统工科也要会编程、仿真、AI 工具",
                ],
                "tip": "📌 官网下载培养方案，看实验室/竞赛/企合作",
            },
            {
                "label": "P3 商科",
                "hook": "商科生家长｜低端事务岗最先被 AI 挤",
                "bullets": [
                    "✅ 会计、审计、财务管理",
                    "✅ 金融、经济统计、保险精算",
                    "✅ 电子商务、数字经济、国际贸易",
                    "❌ 只会做表、做 PPT 的空泛商科",
                ],
                "tip": "📌 课程含 Excel/SQL/Python 至少一门",
            },
            {
                "label": "P4 艺术",
                "hook": "艺术生家长｜AI 是工具，不是替代品",
                "bullets": [
                    "冲击大：低端插画、模板设计、无风格美工",
                    "✅ UI/UX、视觉传达（品牌向）",
                    "✅ 数字媒体艺术、动画、游戏美术",
                    "✅ 影视编导、摄影（有作品才说话）",
                ],
                "tip": "📌 同一命题做 2 版作品：手绘 vs AI 辅助",
            },
            {
                "label": "P5 四件事",
                "hook": "填志愿前，全家只讨论 4 件事",
                "bullets": [
                    "1 孩子擅长什么 → 列 3 门最轻松的高中科目",
                    "2 愿不愿意学 → 找大学课视频试看 30 分钟",
                    "3 学校强不强 → 查硕博点、重点实验室",
                    "4 就业还是深造 → 沙盘看岗位，决定考研友好度",
                ],
            },
            {
                "label": "P6 收尾",
                "hook": "比「热不热」重要的，永远是「适不适配」",
                "checklist": [
                    "工科/商科/艺术各截图保存清单",
                    "分数选校拉出可达院校",
                    "就业沙盘核对专业 Top 岗位",
                    "全家按 4 件事逐项打分",
                ],
                "cta": "评论扣赛道：工科 / 商科 / 艺术 → 发对应清单",
                "hashtags": "#高考志愿填报 #选专业 #工科 #商科 #艺术生 #填志愿干货 #分赛道 #高三家长 #升学规划 #高考出分",
            },
        ],
    },
    {
        "id": "06",
        "cover_title": "先过4关\n再谈喜欢",
        "cover_sub": "选专业研判清单",
        "accent": "#2563EB",
        "goal": "方法论收藏 · 工具导流",
        "slides": [
            {
                "label": "封面",
                "hook": "出分后选专业，先过 4 关再谈「喜不喜欢」",
                "body": "行业有没有坑 → 企业在招什么 → 同类差在哪 → 分数够报哪档\n顺序错了，越查越乱",
                "tags_preview": "选专业方法 · 研判清单",
            },
            {
                "label": "P2 第1关",
                "hook": "第 1 关：这个行业 5 年后还招不招人？",
                "bullets": [
                    "看岗位增量、产品形态、应届起薪区间",
                    "别只看热搜，看招聘学历要求是否抬高",
                    "2025 本科绿牌专业全是工科：电气、微电子、机械电子、新能源、车辆、机器人",
                ],
            },
            {
                "label": "P3 第2关",
                "hook": "第 2 关：标杆公司在招什么人？",
                "bullets": [
                    "智能软件→科大讯飞｜通信→华为",
                    "电网自动化→国电南瑞｜工控→汇川",
                    "医疗器械→迈瑞｜新能源车→比亚迪",
                    "生物医药→信达｜AI 平台→第四范式",
                ],
                "tip": "📌 各打开 1 家招聘页，截图学历/技能/实习要求",
            },
            {
                "label": "P4 第3关",
                "hook": "第 3 关：名字像，出路可能差很多",
                "bullets": [
                    "计科/软工/网安/物联网——出口不同",
                    "微电子 2024 届起薪约 7282 元/月（高薪榜第2）",
                    "临床/口腔/影像/护理——路径完全不同",
                    "金融/会计/工商管理——前三个偏证+数，工商最忌只会做表",
                ],
            },
            {
                "label": "P5 第4关",
                "hook": "第 4 关：这个分数，报哪档校才不浪费？",
                "bullets": [
                    "高分：冲学科评估+硕博点+重点实验室",
                    "中分：优先区域产业链对口",
                    "贴近本科线：路径清晰优先，慎选无实训的「智能XX」",
                    "电气类额外查：国网一批录用院校榜单",
                ],
            },
            {
                "label": "P6 打分表",
                "hook": "四关打分表｜全家 15 分钟会",
                "body": "喜欢是油门，四关是刹车；刹车失灵，再热也危险。",
                "bullets": [
                    "行业前景没过 3 分 → 换相近更稳方向",
                    "企业招聘没过 3 分 → 降级到更实操专业",
                    "专业差异没过 3 分 → 选细分里更明确的",
                    "分数匹配没过 3 分 → 调学校档位别硬冲名头",
                ],
            },
            {
                "label": "P7 收尾",
                "hook": "收藏四关清单，填志愿前全家过一遍",
                "checklist": [
                    "截图四关打分表",
                    "分数选校：省份+科类+分数",
                    "就业沙盘搜专业看 Top3 岗位",
                    "进群领四关打分表电子版",
                ],
                "cta": "评论扣「四关」→ 发打分表 + 交流群入口",
                "hashtags": "#选专业方法 #高考出分 #志愿填报 #家长必读 #填志愿干货 #升学规划 #高三 #大学专业 #高考志愿怎么填 #选专业不迷茫",
            },
        ],
    },
    {
        "id": "07",
        "cover_title": "22门类\n就业地图",
        "cover_sub": "一张图讲清出口",
        "accent": "#2563EB",
        "goal": "百科收藏 · 搜索长尾",
        "slides": [
            {
                "label": "封面",
                "hook": "孩子问「这个专业学啥、干啥」——22 门类一张图讲清",
                "body": "不是让你全背\n是填志愿时知道往哪查、问谁、对标哪家公司",
                "tags_preview": "大学专业字典",
            },
            {
                "label": "P2 信息赛道",
                "hook": "信息赛道（6 类）",
                "bullets": [
                    "计算机→智能软件企业",
                    "电子信息→通信/半导体",
                    "数学统计→AI/金融量化",
                    "新传→内容平台｜中文→内容/公务",
                    "外语→当工具更划算",
                ],
            },
            {
                "label": "P3 制造赛道",
                "hook": "制造与装备（7 类）",
                "bullets": [
                    "自动化 7108｜电气→电网新能源",
                    "机械电子→绿牌专业｜能源→比亚迪链",
                    "材料→面板半导体｜仪器→检测仪表",
                    "生医工→迈瑞类器械",
                ],
            },
            {
                "label": "P4 战略+健康",
                "hook": "国防战略 + 生命健康",
                "bullets": [
                    "航天/兵器/核工程→央企，选择面窄要早确认",
                    "医学→长学制｜药学→研发/注册分化大",
                    "动物医学→牧原类，地域性强",
                ],
            },
            {
                "label": "P5 经管法务",
                "hook": "经管法务（5 类）",
                "bullets": [
                    "法学→律所/法务｜财会→事务所",
                    "经济金融→要数学，无资源慎冲纯金融",
                    "工商管理→最忌空泛管理",
                    "马理论→体制/思政路径",
                ],
            },
            {
                "label": "P6 三张表",
                "hook": "填志愿必翻的三张公开表",
                "bullets": [
                    "绿牌专业（2025 本科）：电气、微电子、机械电子等",
                    "高薪 TOP10（2024 届）：信息安全 7599、软工 7092…全工科",
                    "国网一批录用校单 + 财富中国科技 50 强（看城市产业）",
                ],
                "tip": "📌 意向专业在表里各找 1 个坐标",
            },
            {
                "label": "P7 数据",
                "hook": "数据怎么说？（麦可思 2025 就业蓝皮书）",
                "bullets": [
                    "2024 届本科月均 6199 元",
                    "工学门类月均约 6841 元，领跑各学科",
                    "教育学约 5085 元，初始薪资偏低",
                ],
            },
            {
                "label": "P8 收尾",
                "hook": "专业不是名字，是毕业后第一天去哪张工位",
                "checklist": [
                    "截图保存 22 门类地图",
                    "分数选校按位次筛学校",
                    "沙盘按大类看薪资",
                ],
                "cta": "评论扣专业大类：信息 / 制造 / 经管 → 发细分清单",
                "hashtags": "#大学专业 #高考志愿填报 #选专业 #工科 #文科 #专业介绍 #高三家长 #填志愿 #升学规划 #高考出分",
            },
        ],
    },
    {
        "id": "08",
        "cover_title": "三条填报逻辑",
        "cover_sub": "理工/文史/医学",
        "accent": "#2563EB",
        "goal": "对照收藏 · 减少返工",
        "slides": [
            {
                "label": "封面",
                "hook": "650 分和 550 分都能报好志愿——但理工/文史/医学不是一套打分表",
                "body": "混用逻辑，是「分不算低、路却走窄」最常见原因",
                "tags_preview": "分类型选专业",
            },
            {
                "label": "P2 理工",
                "hook": "理工类：先定技能出口，再定学校牌子",
                "bullets": [
                    "企业招的是：代码/仿真/实验/产线上手能力",
                    "同分：有实验室校企合作的强校 > 无培养的顶尖冷门工科",
                    "第一梯队：计算机、电子信息、自动化、电气",
                    "2024 届工学月均约 6841 元，高于本科均值 6199",
                ],
            },
            {
                "label": "P3 文史",
                "hook": "文史经管：先定平台+场景，再定专业名",
                "bullets": [
                    "律所/媒体/事务所——学校圈层+实习权重高",
                    "考公面宽：中文、法学、计算机、财会",
                    "新传/广告：字节类平台，要作品不要只背理论",
                    "慎选：市场营销、行政管理等「不学也能做」",
                ],
            },
            {
                "label": "P4 医学",
                "hook": "医学类：先定能不能熬 8 年，再定学校",
                "bullets": [
                    "临床/口腔：质量高但本硕博+规培周期长",
                    "护理/康复/医技：就业更快，天花板不同",
                    "药学：研发 vs 流通，出口差很大",
                    "不能接受大五大六轮转，别看临床",
                ],
            },
            {
                "label": "P5 对照表",
                "hook": "三类家庭怎么选（一张表）",
                "bullets": [
                    "尽快就业→电气/软工/护理/会计",
                    "考公稳定→中文/法学/计算机/财会",
                    "冲高薪吃苦→微电子/网安/临床口腔",
                    "分数一般→机械电子/新能源/师范财会/护理康复",
                ],
            },
            {
                "label": "P6 收尾",
                "hook": "没有最好专业，只有最匹配你家时间、金钱、耐心的路",
                "checklist": [
                    "先圈定理工/文史/医学一条主赛道",
                    "沙盘对比 2 个专业应届岗位",
                    "分数选校只在该赛道里冲稳保",
                ],
                "cta": "评论扣类型：理工 / 文史 / 医学 → 发对应打分表",
                "hashtags": "#选专业 #医学 #工科 #文科 #高考志愿填报 #高三家长 #升学规划 #填志愿 #大学报考 #家长必读",
            },
        ],
    },
    {
        "id": "09",
        "cover_title": "四条出口\n分叉",
        "cover_sub": "考公/国企/民企/深造",
        "accent": "#2563EB",
        "goal": "出口决策 · 私域导流",
        "slides": [
            {
                "label": "封面",
                "hook": "想考公/进央企/去民企？报志愿那天就要分叉",
                "body": "出口不同，看的表不同\n用一张表硬选，四年后会返工",
                "tags_preview": "就业出口规划",
            },
            {
                "label": "P2 考公",
                "hook": "出口 ① 考公/事业编｜岗位适配面优先",
                "bullets": [
                    "面宽：中文、法学、计算机、财会",
                    "面窄但对口：药学、农学、部分医技——岗少",
                    "📌 下载近年职位表，搜专业关键词看可报岗位数",
                ],
            },
            {
                "label": "P3 国企",
                "hook": "出口 ② 央企/国企｜行业牌照+校招名录",
                "bullets": [
                    "电气→电网（对照国网录用校单）",
                    "航天/兵器/核工程→相关央企",
                    "石油/地质/铁道→地域性强",
                    "学校行业背景很重要",
                ],
            },
            {
                "label": "P4 民企",
                "hook": "出口 ③ 民企/外资｜技能+项目优先",
                "bullets": [
                    "高薪技能：网安、微电子、软工、自动化（高薪前十全工科）",
                    "信息安全约 7599、软工约 7092（2024 届半年收入）",
                    "新传→内容平台｜法学→律所｜财会→事务所",
                    "实习和项目比学校名气更决定第一份工作",
                ],
            },
            {
                "label": "P5 深造",
                "hook": "出口 ④ 深造/出国｜学科评估+保研率",
                "bullets": [
                    "默认深造友好：数学、物理、基础医学、材料、航空航天、药学研发",
                    "临床医学进三甲普遍要硕博",
                    "📌 查保研率、出国率、硕博点",
                ],
            },
            {
                "label": "P6 总表",
                "hook": "四出口对照总表",
                "bullets": [
                    "考公→下载职位表搜专业关键词",
                    "国企→行业校招名录+录用校单",
                    "民企→沙盘看岗位+实习项目",
                    "深造→保研率+实验室+硕博点",
                ],
            },
            {
                "label": "P7 收尾",
                "hook": "先选出口，再选专业；出口不定，专业越热越慌",
                "checklist": [
                    "全家定 1 个主出口（可备 1 个副出口）",
                    "按出口翻对应表",
                    "分数选校在出口清单里冲稳保",
                ],
                "cta": "评论扣出口：考公 / 国企 / 民企 / 深造 → 发对应资料包",
                "hashtags": "#考公 #央企 #选专业 #高考志愿 #就业规划 #志愿填报 #高三 #升学规划 #大学生就业 #填志愿攻略",
            },
        ],
    },
]


PUBLISH = {
    "01": {
        "title": "72小时定四年｜表弟表妹高考，我这个AI人+面试官出手了",
        "caption": (
            "表弟表妹今年高考。\n"
            "出分后最慌的不是分数，是接下来72小时——\n"
            "一个志愿，锁四年，甚至影响一辈子。\n\n"
            "于是本AI人发力了。\n\n"
            "作为AI从业者，也是资深大厂面试官，\n"
            "见过太多：能力强但学校不行，简历第一关就被刷；\n"
            "专业和岗位不适配，上岗没多久自信就被打击没了。\n\n"
            "深刻认同张雪峰那句话：\n"
            "文科看学校，理科看技术，商科看资源和资历。\n\n"
            "选专业很重要。\n"
            "与其问热不热、问兴趣（孩子自己也不知道），\n"
            "不如倒推——看招聘应届生要求、5年后薪资门槛，以终为始，少走弯路。\n\n"
            "我给家里孩子做了个免费工具：\n"
            "输入省份+分数，查历年院校（QS排名降序），冲稳保三档；\n"
            "附上就业沙盘，查岗位薪资。\n\n"
            "填志愿前三条：\n"
            "① 看省内位次，别只盯分数线\n"
            "② 冲稳保各备3所\n"
            "③ 关注「未来火、当下门槛还低」的专业\n\n"
            "工具要的戳我👇\n"
            "先声明：给家里人用的，不做商用，禁止盗版❌\n"
            "有额外需求私聊，能力范围内尽量帮。"
        ),
        "first_comment": (
            "工具入口在主页简介，不会的也可以私信我。\n"
            "扣：省份+分数+科类（例：江苏 585 物理类），看到会回。"
        ),
        "bio": (
            "AI从业者 · 大厂面试官\n"
            "表弟表妹今年高考，给他们做的免费选校查档工具\n"
            "📊 分数选校（冲稳保）· 💼 就业沙盘 → 主页链接\n"
            "家人自用，非商用 · 数据仅供参考"
        ),
    },
    "02": {
        "title": "AI 选专业 5 个坑，我家差点全踩（建议收藏）",
        "caption": (
            "AI 这么火，人人都想报热门——\n"
            "但 4 年后最卷的，可能就是名字最热那批。\n"
            "这篇把我家差点踩的 5 个坑全列出来了。\n"
            "👉 填志愿前一晚全家过一遍。\n"
            "工具在主页简介，数据仅供参考。"
        ),
        "first_comment": (
            "你最怕哪个坑？评论扣 1-5：\n"
            "1只看专业名 2硬冲AI 3文科焦虑 4商科泛管理 5艺术只会出图\n"
            "扣了的我整理对应避坑清单发你。"
        ),
    },
    "03": {
        "title": "别只盯 985｜650+ / 550-650 / 本科线，分别怎么选专业",
        "caption": (
            "最怕的不是分不够高，\n"
            "是用错误的分数去赌一个错误的热门。\n"
            "这篇按三个分数段列了更务实的方向（不是铁饭碗清单）。\n"
            "👉 建议截图保存，填志愿时对照。\n"
            "分数选校工具：主页简介"
        ),
        "first_comment": (
            "你娃在哪个分数段？评论扣：\n"
            "650+ / 550-650 / 本科线\n"
            "发你对应分数段专业清单（精简版）。"
        ),
    },
    "04": {
        "title": "文科生家长别慌：被挤掉的是事务岗，不是全部文科",
        "caption": (
            "亲戚说「文科没前途」？\n"
            "AI 冲击最大的是：只会重复、不会判断的基础事务。\n"
            "法学/新传/中文/财会 + 实习 + 数据手，依然值钱。\n"
            "👉 文科家长建议收藏转发。\n"
            "就业沙盘查岗位：主页简介"
        ),
        "first_comment": (
            "文科家长扣「文科」+ 最纠结的专业名，\n"
            "我按你的情况给 2 个备选方向参考（仅供参考）。"
        ),
    },
    "05": {
        "title": "工科/商科/艺术，千万别用同一套逻辑选专业",
        "caption": (
            "问题不是哪个赛道最好，\n"
            "是孩子属于哪一类，却用了别人的选法。\n"
            "这篇分三条赛道列清单 + 填志愿前全家讨论的 4 件事。\n"
            "👉 转发给「只想报热门」的家人。\n"
            "工具：主页简介"
        ),
        "first_comment": (
            "你家娃属于哪条赛道？评论扣：工科 / 商科 / 艺术\n"
            "发你对应赛道的专业清单截图版。"
        ),
    },
    "06": {
        "title": "选专业先过 4 关，再谈「喜不喜欢」（研判清单）",
        "caption": (
            "出分后别一上来就问喜不喜欢——\n"
            "顺序错了，越查越乱。\n"
            "行业→企业招聘→专业差异→分数匹配，四关过完再定。\n"
            "👉 收藏四关打分表，全家 15 分钟会。\n"
            "分数选校 + 沙盘：主页简介"
        ),
        "first_comment": (
            "四关打分表电子版 + 交流群入口。\n"
            "评论扣「四关」领取，填志愿前全家过一遍。"
        ),
    },
    "07": {
        "title": "22 个大学专业门类，一张图讲清学啥、干啥、去哪",
        "caption": (
            "孩子问「这个专业学啥、毕业干啥」——\n"
            "不用全背，填志愿时知道往哪查、对标哪家公司就行。\n"
            "信息 / 制造 / 经管 / 医学… 按赛道一张图。\n"
            "👉 建议收藏，查专业时翻。\n"
            "工具：主页简介"
        ),
        "first_comment": (
            "意向哪个大类？评论扣：信息 / 制造 / 经管 / 医学\n"
            "发你细分专业出口清单（精简版）。"
        ),
    },
    "08": {
        "title": "650 分和 550 分都能报好志愿，但理工/文史/医学不是一套表",
        "caption": (
            "混用填报逻辑，是「分不算低、路却走窄」最常见原因。\n"
            "理工看技能出口，文史看平台+场景，医学先问能不能熬 8 年。\n"
            "👉 先圈定一条主赛道，再冲稳保。\n"
            "沙盘对比岗位：主页简介"
        ),
        "first_comment": (
            "你家主赛道是？评论扣：理工 / 文史 / 医学\n"
            "发你对应类型的选专业打分表。"
        ),
    },
    "09": {
        "title": "考公/国企/民企/深造｜报志愿那天就要分叉",
        "caption": (
            "出口不同，看的表完全不同。\n"
            "用一张表硬选专业，四年后最容易返工。\n"
            "这篇把四条出口 + 各自要翻的表讲清了。\n"
            "👉 先全家定 1 个主出口，再选专业。\n"
            "工具：主页简介"
        ),
        "first_comment": (
            "全家更倾向哪条出口？评论扣：考公 / 国企 / 民企 / 深造\n"
            "发你对应资料包（职位表思路 / 校招名录 / 沙盘用法 / 保研率查询）。"
        ),
    },
}


@lru_cache(maxsize=512)
def load_font(size: int, bold: bool = False, emoji: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    if emoji:
        for path in [
            r"C:\Windows\Fonts\seguiemj.ttf",
            r"C:\Windows\Fonts\SegoeUIEmoji.ttf",
            r"C:\Windows\Fonts\NotoColorEmoji.ttf",
        ]:
            try:
                return ImageFont.truetype(path, size=size)
            except OSError:
                continue
    candidates = [
        r"C:\Windows\Fonts\msyhbd.ttc" if bold else r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\simhei.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def line_metrics(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> tuple[int, int, int]:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1], bbox[1]


def wrap_cn(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_w: int) -> list[str]:
    lines: list[str] = []
    current = ""
    for ch in text:
        trial = current + ch
        w, _, _ = line_metrics(draw, trial, font)
        if w > max_w and current:
            lines.append(current)
            current = ch
        else:
            current = trial
    if current:
        lines.append(current)
    # 避免末行单字悬空
    if len(lines) >= 2 and len(lines[-1]) == 1:
        prev, last = lines[-2], lines[-1]
        if len(prev) > 1:
            moved = prev[-1] + last
            trial_prev = prev[:-1]
            w1, _, _ = line_metrics(draw, trial_prev, font)
            w2, _, _ = line_metrics(draw, moved, font)
            if w1 <= max_w and w2 <= max_w:
                lines[-2] = trial_prev
                lines[-1] = moved
    return lines


def balance_title_lines(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_w: int) -> list[str]:
    one = wrap_cn(draw, text, font, max_w)
    if len(one) <= 1:
        return one
    if len(text) <= 8:
        return one
    best: list[str] | None = None
    best_score = 10**9
    for i in range(2, len(text)):
        l1, l2 = text[:i], text[i:]
        w1, _, _ = line_metrics(draw, l1, font)
        w2, _, _ = line_metrics(draw, l2, font)
        if w1 <= max_w and w2 <= max_w:
            score = abs(w1 - w2) + abs(len(l1) - len(l2)) * 8
            if score < best_score:
                best_score = score
                best = [l1, l2]
    if best and len(one) > 2:
        return best
    if best:
        return best
    return one


def measure_lines(
    draw: ImageDraw.ImageDraw, lines: list[str], font: ImageFont.FreeTypeFont, spacing: int
) -> tuple[int, int]:
    if not lines:
        return 0, 0
    widths: list[int] = []
    heights: list[int] = []
    for line in lines:
        w, h, _ = line_metrics(draw, line, font)
        widths.append(w)
        heights.append(h)
    total_h = sum(heights) + spacing * (len(lines) - 1)
    return max(widths), total_h


def fit_title(
    draw: ImageDraw.ImageDraw, text: str, max_w: int, max_h: int, min_size: int = 72, max_size: int = 148
) -> tuple[ImageFont.FreeTypeFont, list[str], int, int, int]:
    for size in range(max_size, min_size - 1, -4):
        font = load_font(size, bold=True)
        spacing = max(12, int(size * 0.12))
        if "\n" in text:
            lines = [ln for ln in text.split("\n") if ln.strip()]
        else:
            lines = balance_title_lines(draw, text, font, max_w)
        w, h = measure_lines(draw, lines, font, spacing)
        if w <= max_w and h <= max_h:
            return font, lines, spacing, w, h
    font = load_font(min_size, bold=True)
    spacing = max(12, int(min_size * 0.12))
    if "\n" in text:
        lines = [ln for ln in text.split("\n") if ln.strip()]
    else:
        lines = balance_title_lines(draw, text, font, max_w)
    w, h = measure_lines(draw, lines, font, spacing)
    return font, lines, spacing, w, h


def draw_text_block(
    draw: ImageDraw.ImageDraw,
    lines: list[str],
    font: ImageFont.FreeTypeFont,
    x: int,
    y: int,
    fill: str,
    spacing: int,
    align: str = "center",
    block_w: int | None = None,
) -> int:
    if not lines:
        return y
    cy = y
    for i, line in enumerate(lines):
        w, h, top = line_metrics(draw, line, font)
        if align == "center" and block_w:
            lx = x + (block_w - w) // 2
        else:
            lx = x
        draw.text((lx, cy - top), line, fill=fill, font=font)
        cy += h + (spacing if i < len(lines) - 1 else 0)
    return cy


def draw_cover(post: dict, path: Path) -> None:
    from xhs_slide_renderer import (
        CARD_GAP,
        PAD,
        build_theme,
        draw_list_row,
        icon_kind,
        strip_emoji,
    )

    theme = build_theme(post["accent"])
    ix0, cw = PAD, W - PAD * 2
    slide0 = post["slides"][0]
    body_lines = [ln.strip() for ln in slide0.get("body", "").split("\n") if ln.strip()]
    n_rows = len(body_lines) + 1  # sub card
    gap = CARD_GAP
    pad_y = PAD
    avail = H - pad_y * 2

    img = Image.new("RGB", (W, H), theme["bg"])
    draw = ImageDraw.Draw(img)

    title_max_h = int(avail * 0.42)
    title_font, title_lines, title_spacing, _, _ = fit_title(
        draw, post["cover_title"], cw, title_max_h, min_size=104, max_size=200
    )
    title_block = sum(
        line_metrics(draw, ln, title_font)[1] + title_spacing for ln in title_lines
    )

    list_avail = avail - title_block - gap * (n_rows + 1)
    row_h = max(100, list_avail // n_rows)
    sub_h = row_h

    cy = pad_y
    for line in title_lines:
        w, h, top = line_metrics(draw, line, title_font)
        draw.rectangle([ix0, cy + top - 10, ix0 + w + 24, cy + top + h + 12], fill=theme["yellow"])
        draw.text((ix0 + 12, cy), line, fill=theme["ink"], font=title_font)
        cy += h + title_spacing
    cy += gap

    sub = post["cover_sub"]
    sub_font = load_font(62 if len(sub) <= 12 else 52, bold=True)
    draw_list_row(draw, ix0, cy, cw, sub_h, sub, "", "pin", theme)
    cy += sub_h + gap

    for para in body_lines:
        line = strip_emoji(para).replace("「", "").replace("」", "")
        draw_list_row(draw, ix0, cy, cw, row_h, line, "", icon_kind(para), theme)
        cy += row_h + gap

    img.save(path, "PNG")


def esc(text: str) -> str:
    return html.escape(text, quote=False)


def publish_xml(post: dict) -> str:
    pub = PUBLISH.get(post["id"])
    if not pub:
        return ""
    last = post["slides"][-1]
    tags = last.get("hashtags", "")
    parts = [
        '<callout emoji="gift" background-color="light-purple" border-color="purple">',
        "<p><b>📮 小红书发布包（复制即用）</b></p>",
        f"<p><b>标题</b></p><p>{esc(pub['title'])}</p>",
        f"<p><b>正文</b></p>",
    ]
    for line in pub["caption"].split("\n"):
        if line.strip():
            parts.append(f"<p>{esc(line)}</p>")
    if tags:
        parts.append(f"<p>{esc(tags)}</p>")
    parts.append(f"<p><b>首评/置顶评论</b></p>")
    for line in pub["first_comment"].split("\n"):
        if line.strip():
            parts.append(f"<p>{esc(line)}</p>")
    parts.append(
        "<p><b>发布动作</b>：发笔记 → 自己抢首评 → 回复评论引流进群/私信 → 简介挂工具链接</p>"
    )
    parts.append("</callout>")
    return "".join(parts)


def slide_xml(slide: dict) -> str:
    parts: list[str] = []
    parts.append(f'<h3>{esc(slide["label"])}</h3>')
    parts.append(f'<callout emoji="pushpin" background-color="light-yellow" border-color="yellow"><p><b>{esc(slide["hook"])}</b></p></callout>')
    if slide.get("body"):
        for para in slide["body"].split("\n"):
            if para.strip():
                parts.append(f"<p>{esc(para)}</p>")
    if slide.get("tags_preview"):
        parts.append(f'<p><span text-color="gray">{esc(slide["tags_preview"])}</span></p>')
    for key in ("bullets", "checklist"):
        if slide.get(key):
            items = "".join(f"<li>{esc(x)}</li>" for x in slide[key])
            parts.append(f"<ul>{items}</ul>")
    if slide.get("pairs"):
        for title, items in slide["pairs"]:
            li = "".join(f"<li>{esc(x)}</li>" for x in items)
            parts.append(f"<p><b>{esc(title)}</b></p><ul>{li}</ul>")
    if slide.get("steps"):
        for tag, text in slide["steps"]:
            parts.append(f"<p><b>{esc(tag)}</b> · {esc(text)}</p>")
    if slide.get("tip"):
        parts.append(f'<callout emoji="bulb" background-color="light-blue"><p>{esc(slide["tip"])}</p></callout>')
    if slide.get("cta"):
        parts.append(f'<callout emoji="speech_balloon" background-color="light-green"><p><b>互动引导</b>：{esc(slide["cta"])}</p></callout>')
    if slide.get("hashtags"):
        parts.append('<hr/>')
        parts.append(f'<callout emoji="hash" background-color="light-gray"><p><b>发布用 Hashtag</b></p><p>{esc(slide["hashtags"])}</p></callout>')
        parts.append('<p><b>发布顺序</b>：收藏 → 转发家长群 → 评论区互动 → 私信/进群承接</p>')
    return "".join(parts)


def post_xml(post: dict) -> str:
    parts = [
        f'<h1>第 {post["id"]} 篇｜{esc(post["cover_title"])}</h1>',
        f'<p><span text-color="gray">轮播页数：{len(post["slides"])} 页 · 目标：{esc(post.get("goal", "收藏干货"))}</span></p>',
        publish_xml(post),
        '<p><b>【轮播配图说明】</b>每一小节 = 轮播 1 页。封面 + 正文图见下方；「封面」小节仅文案。</p>',
    ]
    for slide in post["slides"]:
        parts.append(slide_xml(slide))
    parts.append("<hr/>")
    return "".join(parts)


def build_publish_markdown() -> str:
    lines = [
        "# 高考选专业 · 小红书发布包（9 篇）",
        "",
        "> 配图：`publish/feishu/covers/` + `publish/feishu/slides/`（3:4 竖图）",
        "> 工具链接放主页简介，正文写「看简介」",
        "",
    ]
    for post in POSTS:
        pub = PUBLISH.get(post["id"], {})
        last = post["slides"][-1]
        tags = last.get("hashtags", "")
        lines += [
            f"## POST {post['id']}｜{post['cover_title'].replace(chr(10), '')}",
            f"**目标**：{post.get('goal', '')}",
            "",
            "### 标题（复制到小红书）",
            pub.get("title", ""),
            "",
            "### 正文（含 Hashtag）",
            pub.get("caption", ""),
            "",
            tags,
            "",
            "### 首评 / 置顶评论（发完立刻自己评）",
            pub.get("first_comment", ""),
            "",
        ]
        if pub.get("bio"):
            lines += [
                "### 个人简介（外链字段填工具首页）",
                pub.get("bio", ""),
                "",
                "链接：`https://469910093-ui.github.io/gaokao-slides/`",
                "",
            ]
        lines += [
            "### 轮播图顺序",
            f"1. `post-{post['id']}-cover.png`（封面）",
        ]
        for s in post["slides"]:
            if s["label"] == "封面":
                continue
            slug = re.match(r"(P\d+)", s["label"], re.I)
            fn = slug.group(1).lower() if slug else "slide"
            lines.append(f"- `post-{post['id']}-{fn}.png` · {s['label']}")
        lines += ["", "---", ""]
    return "\n".join(lines)


def build_xml() -> str:
    intro = """
<title>高考选专业 · 小红书爆帖文案全集（9篇）</title>
<callout emoji="bulb" background-color="light-yellow" border-color="yellow">
<p><b>使用说明</b></p>
<ul>
<li>按 POST 01→09 顺序发布，建议每 2 天 1 篇</li>
<li>每篇文首「发布包」含标题、正文、首评话术，复制即用</li>
<li>配图：本项目 HTML 轮播截图（16:9）或下方封面图（3:4）</li>
<li>工具导流：分数选校 selector · 就业沙盘 career-sandbox</li>
</ul>
</callout>
<p><b>系列目录</b></p>
<ol>
<li>01 没有「永不失业」的专业</li>
<li>02 AI 时代选专业 5 个坑</li>
<li>03 不同分数段怎么选专业</li>
<li>04 文科生家长别慌</li>
<li>05 工科/商科/艺术别混用逻辑</li>
<li>06 先过 4 关再谈喜欢（新增）</li>
<li>07 22 门类就业地图（新增）</li>
<li>08 理工/文史/医学三条逻辑（新增）</li>
<li>09 考公/国企/民企/深造四出口（新增）</li>
</ol>
<hr/>
"""
    body = "".join(post_xml(p) for p in POSTS)
    return intro + body


def main() -> None:
    COVERS.mkdir(parents=True, exist_ok=True)
    cover_paths: dict[str, str] = {}
    for post in POSTS:
        path = COVERS / f"post-{post['id']}-cover.png"
        draw_cover(post, path)
        cover_paths[post["id"]] = str(path.relative_to(ROOT)).replace("\\", "/")
    xml = build_xml()
    XML_PATH.write_text(xml, encoding="utf-8")
    publish_md = OUT_DIR / "xhs_publish_pack.md"
    publish_md.write_text(build_publish_markdown(), encoding="utf-8")

    # body slide PNGs (3:4 carousel pages)
    try:
        from xhs_slide_renderer import generate_all_slides

        slide_manifest = generate_all_slides()
        slide_count = sum(len(v) for v in slide_manifest.values())
    except Exception as exc:
        slide_manifest = {}
        slide_count = 0
        print(f"warn: body slides not generated: {exc}", file=__import__("sys").stderr)

    META_PATH.write_text(
        json.dumps(
            {
                "covers": cover_paths,
                "slides": slide_manifest,
                "xml": str(XML_PATH.relative_to(ROOT)).replace("\\", "/"),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Wrote {XML_PATH}")
    print(f"Wrote {publish_md}")
    print(f"Covers: {len(cover_paths)}")
    if slide_count:
        print(f"Body slides: {slide_count}")
    print("Tip: python sync_feishu_doc.py  # upload images to Feishu")


if __name__ == "__main__":
    main()

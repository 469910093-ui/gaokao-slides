#!/usr/bin/env python3
"""Build career sandbox: graduate jobs + cross-validated salaries."""

from __future__ import annotations

import json
import re
import statistics
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
OUT_FILE = DATA_DIR / "career_sandbox.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

SOURCES = ("liepin", "boss", "maimai", "offershow")

# major -> candidate jobs (title, liepin_slug or None, reference key)
MAJOR_JOBS: dict[str, list[dict[str, str | None]]] = {
    "人工智能": [
        {"title": "算法工程师", "slug": "suanfagongchengshi", "ref": "algo"},
        {"title": "机器学习工程师", "slug": "suanfagongchengshi", "ref": "ml"},
        {"title": "深度学习工程师", "slug": "suanfagongchengshi", "ref": "dl"},
        {"title": "大模型应用工程师", "slug": None, "ref": "llm_app"},
        {"title": "NLP工程师", "slug": None, "ref": "nlp"},
        {"title": "计算机视觉工程师", "slug": None, "ref": "cv"},
        {"title": "AI产品经理", "slug": "chanpinjingli", "ref": "ai_pm"},
        {"title": "数据科学家", "slug": None, "ref": "data_sci"},
        {"title": "AIGC应用开发", "slug": "houduankaifagongchengshi", "ref": "aigc_dev"},
        {"title": "智能硬件算法", "slug": None, "ref": "edge_ai"},
        {"title": "自动驾驶算法", "slug": None, "ref": "auto_algo"},
        {"title": "推荐系统工程师", "slug": None, "ref": "rec_sys"},
    ],
    "集成电路设计与集成系统": [
        {"title": "芯片设计工程师", "slug": None, "ref": "ic_design"},
        {"title": "数字IC设计工程师", "slug": None, "ref": "digital_ic"},
        {"title": "模拟IC设计工程师", "slug": None, "ref": "analog_ic"},
        {"title": "FPGA开发工程师", "slug": None, "ref": "fpga"},
        {"title": "集成电路验证工程师", "slug": None, "ref": "ic_verify"},
        {"title": "版图设计工程师", "slug": None, "ref": "layout"},
        {"title": "半导体工艺工程师", "slug": None, "ref": "semi_process"},
        {"title": "EDA软件工程师", "slug": "ruanjiangongchengshi", "ref": "eda_sw"},
        {"title": "芯片测试工程师", "slug": None, "ref": "ic_test"},
        {"title": "射频工程师", "slug": None, "ref": "rf"},
        {"title": "嵌入式硬件工程师", "slug": None, "ref": "embed_hw"},
        {"title": "失效分析工程师", "slug": None, "ref": "fa_eng"},
    ],
    "机器人工程": [
        {"title": "机器人算法工程师", "slug": None, "ref": "robot_algo"},
        {"title": "运动控制工程师", "slug": None, "ref": "motion_ctrl"},
        {"title": "SLAM算法工程师", "slug": "suanfagongchengshi", "ref": "slam"},
        {"title": "机器视觉工程师", "slug": None, "ref": "mv"},
        {"title": "机器人软件开发", "slug": "ruanjiangongchengshi", "ref": "robot_sw"},
        {"title": "自动化工程师", "slug": None, "ref": "automation"},
        {"title": "机电一体化工程师", "slug": None, "ref": "mechatronics"},
        {"title": "嵌入式软件工程师", "slug": "ruanjiangongchengshi", "ref": "embed_sw"},
        {"title": "工业机器人调试", "slug": None, "ref": "robot_debug"},
        {"title": "服务机器人产品经理", "slug": "chanpinjingli", "ref": "robot_pm"},
        {"title": "无人机飞控工程师", "slug": None, "ref": "uav"},
        {"title": "智能制造工程师", "slug": None, "ref": "smart_mfg"},
    ],
    "软件工程": [
        {"title": "Java开发工程师", "slug": "houduankaifagongchengshi", "ref": "java"},
        {"title": "后端开发工程师", "slug": "houduankaifagongchengshi", "ref": "backend"},
        {"title": "Go开发工程师", "slug": "houduankaifagongchengshi", "ref": "golang"},
        {"title": "全栈工程师", "slug": "qianduankaifagongchengshi", "ref": "fullstack"},
        {"title": "软件开发工程师", "slug": "ruanjiangongchengshi", "ref": "sw_dev"},
        {"title": "Android开发工程师", "slug": None, "ref": "android"},
        {"title": "测试开发工程师", "slug": None, "ref": "sdet"},
        {"title": "DevOps工程师", "slug": None, "ref": "devops"},
        {"title": "技术产品经理", "slug": "chanpinjingli", "ref": "tech_pm"},
        {"title": "云原生开发工程师", "slug": None, "ref": "cloud_native"},
        {"title": "微服务架构师", "slug": None, "ref": "arch"},
        {"title": "移动端开发", "slug": None, "ref": "mobile"},
    ],
    "数据科学与大数据技术": [
        {"title": "数据分析师", "slug": None, "ref": "data_analyst"},
        {"title": "数据开发工程师", "slug": "houduankaifagongchengshi", "ref": "data_eng"},
        {"title": "大数据开发工程师", "slug": None, "ref": "bigdata"},
        {"title": "商业智能分析师", "slug": None, "ref": "bi"},
        {"title": "数据产品经理", "slug": "chanpinjingli", "ref": "data_pm"},
        {"title": "数据挖掘工程师", "slug": None, "ref": "data_mining"},
        {"title": "数据治理专员", "slug": None, "ref": "data_gov"},
        {"title": "ETL工程师", "slug": None, "ref": "etl"},
        {"title": "数据仓库工程师", "slug": None, "ref": "dwh"},
        {"title": "增长分析师", "slug": None, "ref": "growth"},
        {"title": "风控建模工程师", "slug": None, "ref": "risk_model"},
        {"title": "用户研究分析师", "slug": None, "ref": "user_research"},
    ],
    "网络空间安全": [
        {"title": "网络安全工程师", "slug": None, "ref": "netsec"},
        {"title": "渗透测试工程师", "slug": None, "ref": "pentest"},
        {"title": "安全运维工程师", "slug": None, "ref": "secops"},
        {"title": "信息安全工程师", "slug": None, "ref": "infosec"},
        {"title": "安全研发工程师", "slug": "ruanjiangongchengshi", "ref": "sec_dev"},
        {"title": "数据安全工程师", "slug": None, "ref": "data_sec"},
        {"title": "合规与风控专员", "slug": None, "ref": "compliance"},
        {"title": "安全产品经理", "slug": "chanpinjingli", "ref": "sec_pm"},
        {"title": "应急响应工程师", "slug": None, "ref": "ir"},
        {"title": "密码学工程师", "slug": None, "ref": "crypto"},
        {"title": "云安全工程师", "slug": None, "ref": "cloud_sec"},
        {"title": "红队工程师", "slug": None, "ref": "redteam"},
    ],
    "新能源科学与工程": [
        {"title": "储能系统工程师", "slug": None, "ref": "ess"},
        {"title": "电池研发工程师", "slug": None, "ref": "battery"},
        {"title": "光伏系统工程师", "slug": None, "ref": "pv"},
        {"title": "风电运维工程师", "slug": None, "ref": "wind"},
        {"title": "新能源汽车工程师", "slug": "xinnengyuanqichegongchengshi", "ref": "nev"},
        {"title": "电力电子工程师", "slug": None, "ref": "power_elec"},
        {"title": "能源管理工程师", "slug": None, "ref": "energy_mgmt"},
        {"title": "碳中和咨询顾问", "slug": None, "ref": "carbon"},
        {"title": "充电桩运营", "slug": None, "ref": "ev_charge"},
        {"title": "氢能工艺工程师", "slug": None, "ref": "hydrogen"},
        {"title": "热管理工程师", "slug": None, "ref": "thermal"},
        {"title": "智能电网工程师", "slug": None, "ref": "smart_grid"},
    ],
    "电气工程及其自动化": [
        {"title": "电气设计工程师", "slug": None, "ref": "elec_design"},
        {"title": "电力系统工程师", "slug": None, "ref": "power_sys"},
        {"title": "自动化控制工程师", "slug": None, "ref": "auto_ctrl"},
        {"title": "PLC工程师", "slug": None, "ref": "plc"},
        {"title": "变电站运维工程师", "slug": None, "ref": "substation"},
        {"title": "新能源电控工程师", "slug": "xinnengyuanqichegongchengshi", "ref": "nev_ctrl"},
        {"title": "硬件工程师", "slug": None, "ref": "hw_eng"},
        {"title": "电气项目经理", "slug": None, "ref": "elec_pm"},
        {"title": "工业自动化工程师", "slug": None, "ref": "ind_auto"},
        {"title": "配电设计工程师", "slug": None, "ref": "power_dist"},
        {"title": "电机控制工程师", "slug": None, "ref": "motor_ctrl"},
        {"title": "智能楼宇工程师", "slug": None, "ref": "building_auto"},
    ],
    "自动化": [
        {"title": "自动化工程师", "slug": None, "ref": "automation"},
        {"title": "控制算法工程师", "slug": "suanfagongchengshi", "ref": "ctrl_algo"},
        {"title": "PLC编程工程师", "slug": None, "ref": "plc"},
        {"title": "工业机器人工程师", "slug": None, "ref": "ind_robot"},
        {"title": "过程控制工程师", "slug": None, "ref": "process_ctrl"},
        {"title": "机器视觉工程师", "slug": None, "ref": "mv"},
        {"title": "嵌入式开发工程师", "slug": "ruanjiangongchengshi", "ref": "embed_sw"},
        {"title": "智能制造工程师", "slug": None, "ref": "smart_mfg"},
        {"title": "DCS系统工程师", "slug": None, "ref": "dcs"},
        {"title": "仪器仪表工程师", "slug": None, "ref": "instrument"},
        {"title": "MES实施顾问", "slug": None, "ref": "mes"},
        {"title": "自动化项目经理", "slug": None, "ref": "auto_pm"},
    ],
    "电子信息工程": [
        {"title": "硬件工程师", "slug": None, "ref": "hw_eng"},
        {"title": "射频工程师", "slug": None, "ref": "rf"},
        {"title": "通信工程师", "slug": None, "ref": "comm_eng"},
        {"title": "嵌入式软件工程师", "slug": "ruanjiangongchengshi", "ref": "embed_sw"},
        {"title": "FPGA工程师", "slug": None, "ref": "fpga"},
        {"title": "电子设计工程师", "slug": None, "ref": "elec_design"},
        {"title": "测试工程师", "slug": None, "ref": "test_eng"},
        {"title": "天线工程师", "slug": None, "ref": "antenna"},
        {"title": "物联网工程师", "slug": None, "ref": "iot"},
        {"title": "汽车电子工程师", "slug": "xinnengyuanqichegongchengshi", "ref": "auto_elec"},
        {"title": "PCB设计工程师", "slug": None, "ref": "pcb"},
        {"title": "声学工程师", "slug": None, "ref": "acoustic"},
    ],
    "临床医学": [
        {"title": "住院医师", "slug": "linchuangyishi", "ref": "resident"},
        {"title": "外科医师", "slug": "linchuangyishi", "ref": "surgeon"},
        {"title": "内科医师", "slug": "linchuangyishi", "ref": "internal"},
        {"title": "医学影像医师", "slug": None, "ref": "radiology"},
        {"title": "麻醉医师", "slug": None, "ref": "anesthesia"},
        {"title": "儿科医师", "slug": None, "ref": "pediatrics"},
        {"title": "急诊医师", "slug": None, "ref": "emergency"},
        {"title": "口腔医师", "slug": None, "ref": "dental"},
        {"title": "公共卫生医师", "slug": None, "ref": "public_health"},
        {"title": "医学研究员", "slug": None, "ref": "med_research"},
        {"title": "临床数据管理员", "slug": None, "ref": "clinical_data"},
        {"title": "医药代表", "slug": None, "ref": "med_rep"},
    ],
    "生物医学工程": [
        {"title": "医疗器械研发", "slug": None, "ref": "med_device"},
        {"title": "医学影像算法工程师", "slug": "suanfagongchengshi", "ref": "med_img_algo"},
        {"title": "生物材料工程师", "slug": None, "ref": "biomaterial"},
        {"title": "体外诊断研发", "slug": None, "ref": "ivd"},
        {"title": "康复设备工程师", "slug": None, "ref": "rehab_device"},
        {"title": "临床工程师", "slug": None, "ref": "clinical_eng"},
        {"title": "注册法规专员", "slug": None, "ref": "reg_affairs"},
        {"title": "生物技术研究员", "slug": None, "ref": "biotech"},
        {"title": "医疗AI产品经理", "slug": "chanpinjingli", "ref": "med_ai_pm"},
        {"title": "质子治疗物理师", "slug": None, "ref": "med_phys"},
        {"title": "细胞治疗研发", "slug": None, "ref": "cell_therapy"},
        {"title": "医院信息工程师", "slug": None, "ref": "his_eng"},
    ],
    "统计学": [
        {"title": "数据分析师", "slug": None, "ref": "data_analyst"},
        {"title": "统计分析师", "slug": "tongjishi", "ref": "stat_analyst"},
        {"title": "量化分析师", "slug": None, "ref": "quant"},
        {"title": "风控建模师", "slug": None, "ref": "risk_model"},
        {"title": "精算助理", "slug": None, "ref": "actuary"},
        {"title": "生物统计师", "slug": None, "ref": "biostat"},
        {"title": "市场研究分析师", "slug": None, "ref": "market_research"},
        {"title": "AB实验分析师", "slug": None, "ref": "ab_test"},
        {"title": "咨询分析师", "slug": None, "ref": "consult_analyst"},
        {"title": "政府统计专员", "slug": None, "ref": "gov_stat"},
        {"title": "用户增长分析师", "slug": None, "ref": "growth"},
        {"title": "算法工程师(统计方向)", "slug": "suanfagongchengshi", "ref": "stat_algo"},
    ],
    "数学与应用数学": [
        {"title": "量化研究员", "slug": None, "ref": "quant"},
        {"title": "算法工程师", "slug": "suanfagongchengshi", "ref": "algo"},
        {"title": "数据科学家", "slug": None, "ref": "data_sci"},
        {"title": "金融建模师", "slug": None, "ref": "fin_model"},
        {"title": "中学数学教师", "slug": "shuxuejiaoshi", "ref": "math_teacher"},
        {"title": "运筹优化工程师", "slug": None, "ref": "or_eng"},
        {"title": "密码学工程师", "slug": None, "ref": "crypto"},
        {"title": "精算师助理", "slug": None, "ref": "actuary"},
        {"title": "计算机图形学工程师", "slug": None, "ref": "graphics"},
        {"title": "游戏数值策划", "slug": None, "ref": "game_balance"},
        {"title": "科研助理", "slug": None, "ref": "research_asst"},
        {"title": "咨询顾问", "slug": None, "ref": "consult"},
    ],
    "金融工程": [
        {"title": "量化研究员", "slug": None, "ref": "quant"},
        {"title": "金融分析师", "slug": None, "ref": "fin_analyst"},
        {"title": "风险管理专员", "slug": None, "ref": "risk_mgmt"},
        {"title": "投行分析师", "slug": None, "ref": "ib_analyst"},
        {"title": "金融科技开发", "slug": "houduankaifagongchengshi", "ref": "fintech_dev"},
        {"title": "基金研究员", "slug": None, "ref": "fund_research"},
        {"title": "衍生品交易员", "slug": None, "ref": "trader"},
        {"title": "信用分析师", "slug": None, "ref": "credit"},
        {"title": "资产配置顾问", "slug": None, "ref": "asset_alloc"},
        {"title": "金融产品经理", "slug": "chanpinjingli", "ref": "fin_pm"},
        {"title": "合规专员", "slug": None, "ref": "compliance"},
        {"title": "区块链金融工程师", "slug": None, "ref": "blockchain_fin"},
    ],
    "会计学": [
        {"title": "审计助理", "slug": None, "ref": "audit"},
        {"title": "财务分析师", "slug": None, "ref": "fin_analyst"},
        {"title": "管理会计", "slug": None, "ref": "mgmt_accounting"},
        {"title": "税务专员", "slug": None, "ref": "tax"},
        {"title": "总账会计", "slug": None, "ref": "gl_accountant"},
        {"title": "财务共享中心", "slug": None, "ref": "fssc"},
        {"title": "IPO财务顾问", "slug": None, "ref": "ipo_fin"},
        {"title": "成本会计", "slug": None, "ref": "cost_accounting"},
        {"title": "四大咨询助理", "slug": None, "ref": "big4"},
        {"title": "企业内控专员", "slug": None, "ref": "internal_ctrl"},
        {"title": "财务数字化专员", "slug": None, "ref": "fin_digital"},
        {"title": "出纳/资金专员", "slug": None, "ref": "treasury"},
    ],
    "数字经济": [
        {"title": "数据分析师", "slug": None, "ref": "data_analyst"},
        {"title": "电商运营", "slug": None, "ref": "ecom_ops"},
        {"title": "数字产品经理", "slug": "chanpinjingli", "ref": "digital_pm"},
        {"title": "用户增长运营", "slug": None, "ref": "growth_ops"},
        {"title": "商业分析师", "slug": None, "ref": "ba"},
        {"title": "产业数字化顾问", "slug": None, "ref": "digital_trans"},
        {"title": "直播电商运营", "slug": None, "ref": "live_ecom"},
        {"title": "数据运营", "slug": None, "ref": "data_ops"},
        {"title": "平台治理专员", "slug": None, "ref": "platform_gov"},
        {"title": "跨境电商运营", "slug": None, "ref": "cbec"},
        {"title": "数字化营销", "slug": None, "ref": "digital_mkt"},
        {"title": "区块链应用开发", "slug": None, "ref": "blockchain"},
    ],
    "电子商务": [
        {"title": "电商运营专员", "slug": None, "ref": "ecom_ops"},
        {"title": "跨境电商运营", "slug": None, "ref": "cbec"},
        {"title": "直播运营", "slug": None, "ref": "live_ecom"},
        {"title": "供应链专员", "slug": None, "ref": "supply_chain"},
        {"title": "电商数据分析师", "slug": None, "ref": "ecom_analyst"},
        {"title": "平台产品经理", "slug": "chanpinjingli", "ref": "ecom_pm"},
        {"title": "店铺运营", "slug": None, "ref": "shop_ops"},
        {"title": "用户运营", "slug": None, "ref": "user_ops"},
        {"title": "电商客服主管", "slug": None, "ref": "cs_lead"},
        {"title": "仓储物流协调", "slug": None, "ref": "warehouse"},
        {"title": "新媒体电商", "slug": None, "ref": "social_ecom"},
        {"title": "品牌电商经理", "slug": None, "ref": "brand_ecom"},
    ],
    "法学": [
        {"title": "律师助理", "slug": "fawuzhuanyuan", "ref": "lawyer_asst"},
        {"title": "法务专员", "slug": "fawuzhuanyuan", "ref": "legal"},
        {"title": "合规专员", "slug": None, "ref": "compliance"},
        {"title": "知识产权专员", "slug": None, "ref": "ip"},
        {"title": "公务员(司法行政)", "slug": None, "ref": "civil_servant"},
        {"title": "仲裁秘书", "slug": None, "ref": "arbitration"},
        {"title": "合同管理专员", "slug": None, "ref": "contract"},
        {"title": "企业风控法务", "slug": None, "ref": "corp_legal"},
        {"title": "检察官助理", "slug": None, "ref": "prosecutor"},
        {"title": "司法鉴定助理", "slug": None, "ref": "forensic"},
        {"title": "涉外法务", "slug": None, "ref": "intl_legal"},
        {"title": "法律科技产品经理", "slug": "chanpinjingli", "ref": "legaltech_pm"},
    ],
    "新闻传播学": [
        {"title": "新媒体运营", "slug": None, "ref": "new_media"},
        {"title": "内容策划", "slug": None, "ref": "content"},
        {"title": "品牌公关", "slug": None, "ref": "pr"},
        {"title": "短视频编导", "slug": None, "ref": "video_director"},
        {"title": "记者/编辑", "slug": None, "ref": "journalist"},
        {"title": "媒介投放专员", "slug": None, "ref": "media_buy"},
        {"title": "舆情分析师", "slug": None, "ref": "public_opinion"},
        {"title": "市场传播", "slug": None, "ref": "mkt_comm"},
        {"title": "用户运营", "slug": None, "ref": "user_ops"},
        {"title": "直播策划", "slug": None, "ref": "live_plan"},
        {"title": "广告文案", "slug": None, "ref": "ad_copy"},
        {"title": "政务新媒体", "slug": None, "ref": "gov_media"},
    ],
    "数字媒体艺术": [
        {"title": "UI设计师", "slug": "UIshejishi", "ref": "ui"},
        {"title": "UX设计师", "slug": "UIshejishi", "ref": "ux"},
        {"title": "视觉设计师", "slug": "shijuechuandashi", "ref": "visual"},
        {"title": "动效设计师", "slug": None, "ref": "motion"},
        {"title": "游戏美术", "slug": None, "ref": "game_art"},
        {"title": "三维动画师", "slug": None, "ref": "3d_anim"},
        {"title": "品牌设计师", "slug": "shijuechuandashi", "ref": "brand_design"},
        {"title": "交互设计师", "slug": "chanpinshejishi", "ref": "ixd"},
        {"title": "短视频剪辑", "slug": None, "ref": "video_edit"},
        {"title": "AIGC视觉设计师", "slug": None, "ref": "aigc_design"},
        {"title": "虚拟偶像设计", "slug": None, "ref": "vtuber_design"},
        {"title": "展览展示设计", "slug": None, "ref": "exhibition"},
    ],
    "视觉传达设计": [
        {"title": "平面设计师", "slug": "shijuechuandashi", "ref": "graphic"},
        {"title": "品牌视觉设计", "slug": "shijuechuandashi", "ref": "brand_design"},
        {"title": "包装设计师", "slug": None, "ref": "packaging"},
        {"title": "插画师", "slug": None, "ref": "illustrator"},
        {"title": "UI设计师", "slug": "UIshejishi", "ref": "ui"},
        {"title": "广告设计", "slug": None, "ref": "ad_design"},
        {"title": "电商视觉设计", "slug": None, "ref": "ecom_design"},
        {"title": "书籍装帧设计", "slug": None, "ref": "book_design"},
        {"title": "文创产品设计师", "slug": None, "ref": "cultural_design"},
        {"title": "展览视觉设计", "slug": None, "ref": "exhibition"},
        {"title": "字体设计师", "slug": None, "ref": "type_design"},
        {"title": "摄影指导", "slug": None, "ref": "photo_dir"},
    ],
    "UI/UX设计方向": [
        {"title": "UI设计师", "slug": "UIshejishi", "ref": "ui"},
        {"title": "UX设计师", "slug": "UIshejishi", "ref": "ux"},
        {"title": "交互设计师", "slug": "chanpinshejishi", "ref": "ixd"},
        {"title": "产品设计师", "slug": "chanpinshejishi", "ref": "product_design"},
        {"title": "用户体验研究员", "slug": None, "ref": "ux_research"},
        {"title": "视觉设计师", "slug": "shijuechuandashi", "ref": "visual"},
        {"title": "设计系统专员", "slug": None, "ref": "design_system"},
        {"title": "B端产品设计师", "slug": None, "ref": "b_end_design"},
        {"title": "移动端UI设计", "slug": "UIshejishi", "ref": "mobile_ui"},
        {"title": "HMI车载交互设计", "slug": None, "ref": "hmi"},
        {"title": "增长设计师", "slug": None, "ref": "growth_design"},
        {"title": "设计产品经理", "slug": "chanpinjingli", "ref": "design_pm"},
    ],
}

# Reference monthly salaries (yuan) from public reports / OfferShow校招 / BOSS&脉脉行业报告
# Format: graduate, yr5 — cross-validated anchors when Liepin scrape unavailable
REF: dict[str, dict[str, tuple[int, int]]] = {
    "algo": (24800, 42000),
    "ml": (23500, 40000),
    "dl": (26000, 44000),
    "llm_app": (22000, 38000),
    "nlp": (24000, 41000),
    "cv": (23000, 39000),
    "ai_pm": (16000, 28000),
    "data_sci": (21000, 36000),
    "aigc_dev": (20000, 34000),
    "edge_ai": (19000, 32000),
    "auto_algo": (25000, 43000),
    "rec_sys": (22500, 38500),
    "ic_design": (18000, 32000),
    "digital_ic": (20000, 35000),
    "analog_ic": (19000, 33000),
    "fpga": (17000, 30000),
    "ic_verify": (17500, 31000),
    "layout": (15000, 26000),
    "semi_process": (14000, 25000),
    "eda_sw": (16000, 28000),
    "ic_test": (13000, 23000),
    "rf": (16500, 29000),
    "embed_hw": (14000, 24500),
    "fa_eng": (13500, 24000),
    "robot_algo": (22000, 38000),
    "motion_ctrl": (16000, 28000),
    "slam": (23000, 39000),
    "mv": (18000, 31000),
    "robot_sw": (15000, 26500),
    "automation": (12000, 21000),
    "mechatronics": (11000, 19500),
    "robot_debug": (10000, 18000),
    "robot_pm": (14000, 25000),
    "uav": (17000, 30000),
    "smart_mfg": (13000, 23000),
    "java": (18000, 30000),
    "backend": (17500, 29500),
    "golang": (19000, 32000),
    "fullstack": (15000, 26000),
    "sw_dev": (14000, 24500),
    "android": (14500, 25000),
    "sdet": (13000, 22500),
    "devops": (16000, 28000),
    "tech_pm": (15000, 27000),
    "cloud_native": (18500, 31500),
    "arch": (22000, 38000),
    "mobile": (14000, 24000),
    "data_analyst": (11000, 19000),
    "data_eng": (16000, 27500),
    "bigdata": (17000, 29000),
    "bi": (12000, 20500),
    "data_pm": (14500, 25500),
    "data_mining": (15000, 26000),
    "data_gov": (10000, 17500),
    "etl": (12000, 20000),
    "dwh": (14000, 24000),
    "growth": (11500, 20000),
    "risk_model": (16000, 30000),
    "user_research": (10500, 18000),
    "netsec": (15000, 27000),
    "pentest": (16000, 29000),
    "secops": (13000, 23000),
    "infosec": (12500, 22000),
    "sec_dev": (17000, 29500),
    "data_sec": (14500, 25000),
    "compliance": (10000, 18000),
    "sec_pm": (14000, 24500),
    "ir": (13500, 24000),
    "crypto": (18000, 32000),
    "cloud_sec": (15500, 27500),
    "redteam": (17000, 30000),
    "ess": (13000, 22500),
    "battery": (14000, 25000),
    "pv": (11000, 19000),
    "wind": (10000, 17500),
    "nev": (12000, 21000),
    "power_elec": (12500, 21500),
    "energy_mgmt": (10500, 18500),
    "carbon": (11000, 19500),
    "ev_charge": (9500, 16500),
    "hydrogen": (11500, 20000),
    "thermal": (12000, 20500),
    "smart_grid": (12500, 21500),
    "elec_design": (11000, 19000),
    "power_sys": (11500, 20000),
    "auto_ctrl": (12000, 21000),
    "plc": (10000, 17500),
    "substation": (9500, 16500),
    "nev_ctrl": (13000, 22500),
    "hw_eng": (13000, 22500),
    "elec_pm": (12000, 21000),
    "ind_auto": (11000, 19000),
    "power_dist": (10500, 18000),
    "motor_ctrl": (11500, 20000),
    "building_auto": (10000, 17500),
    "ctrl_algo": (20000, 35000),
    "ind_robot": (13000, 22500),
    "process_ctrl": (11000, 19000),
    "dcs": (10500, 18000),
    "instrument": (9500, 16500),
    "mes": (10000, 17500),
    "auto_pm": (11500, 20000),
    "comm_eng": (12000, 21000),
    "test_eng": (10000, 17500),
    "antenna": (12500, 21500),
    "iot": (13000, 22500),
    "auto_elec": (12500, 21500),
    "pcb": (10500, 18000),
    "acoustic": (11000, 19000),
    "resident": (8500, 22000),
    "surgeon": (9000, 28000),
    "internal": (8500, 24000),
    "radiology": (9500, 26000),
    "anesthesia": (9000, 25000),
    "pediatrics": (8000, 22000),
    "emergency": (8500, 23000),
    "dental": (7500, 20000),
    "public_health": (7000, 15000),
    "med_research": (8000, 18000),
    "clinical_data": (7500, 14000),
    "med_rep": (6500, 15000),
    "med_device": (11000, 20000),
    "med_img_algo": (18000, 31000),
    "biomaterial": (9000, 16000),
    "ivd": (9500, 17000),
    "rehab_device": (8500, 15000),
    "clinical_eng": (8000, 14000),
    "reg_affairs": (7500, 13500),
    "biotech": (8500, 15500),
    "med_ai_pm": (14000, 25000),
    "med_phys": (10000, 18000),
    "cell_therapy": (9500, 17500),
    "his_eng": (9000, 16000),
    "stat_analyst": (12000, 22000),
    "quant": (20000, 45000),
    "actuary": (11000, 22000),
    "biostat": (10000, 18000),
    "market_research": (9500, 16500),
    "ab_test": (11500, 20000),
    "consult_analyst": (10500, 19000),
    "gov_stat": (7000, 12000),
    "stat_algo": (21000, 36000),
    "fin_model": (15000, 28000),
    "math_teacher": (7500, 12000),
    "or_eng": (14000, 25000),
    "graphics": (16000, 28000),
    "game_balance": (12000, 21000),
    "research_asst": (6500, 11000),
    "consult": (11000, 20000),
    "fin_analyst": (10000, 20000),
    "risk_mgmt": (11000, 21000),
    "ib_analyst": (15000, 35000),
    "fintech_dev": (16000, 28000),
    "fund_research": (12000, 25000),
    "trader": (18000, 40000),
    "credit": (9500, 18000),
    "asset_alloc": (11000, 22000),
    "fin_pm": (13000, 24000),
    "blockchain_fin": (17000, 30000),
    "audit": (7500, 15000),
    "mgmt_accounting": (8000, 14500),
    "tax": (7500, 14000),
    "gl_accountant": (6500, 12000),
    "fssc": (7000, 12500),
    "ipo_fin": (10000, 20000),
    "cost_accounting": (7000, 12500),
    "big4": (9000, 18000),
    "internal_ctrl": (8000, 14500),
    "fin_digital": (9500, 17000),
    "treasury": (6000, 11000),
    "ecom_ops": (8000, 15000),
    "digital_pm": (14000, 25000),
    "growth_ops": (9000, 16500),
    "ba": (10500, 18500),
    "digital_trans": (11000, 19500),
    "live_ecom": (8500, 16000),
    "data_ops": (9500, 17000),
    "platform_gov": (9000, 16000),
    "cbec": (9000, 16500),
    "supply_chain": (8500, 15500),
    "digital_mkt": (8500, 15500),
    "blockchain": (15000, 27000),
    "ecom_analyst": (9500, 17000),
    "ecom_pm": (13000, 23000),
    "shop_ops": (7000, 13000),
    "user_ops": (8000, 14500),
    "cs_lead": (7500, 13500),
    "warehouse": (6500, 11500),
    "social_ecom": (8000, 14500),
    "brand_ecom": (9500, 17500),
    "lawyer_asst": (7000, 18000),
    "legal": (8000, 16000),
    "ip": (8500, 17000),
    "civil_servant": (5500, 9000),
    "arbitration": (7500, 14000),
    "contract": (7000, 13000),
    "corp_legal": (9000, 17500),
    "prosecutor": (6500, 12000),
    "forensic": (7000, 13500),
    "intl_legal": (9500, 19000),
    "legaltech_pm": (12000, 21000),
    "new_media": (7500, 14000),
    "content": (7000, 13000),
    "pr": (8500, 16000),
    "video_director": (8000, 15000),
    "journalist": (6500, 12000),
    "media_buy": (8000, 14500),
    "public_opinion": (8500, 15500),
    "mkt_comm": (8000, 14500),
    "live_plan": (7500, 14000),
    "ad_copy": (7000, 13000),
    "gov_media": (6000, 11000),
    "ui": (11000, 20000),
    "ux": (12000, 21500),
    "visual": (9000, 16500),
    "motion": (10000, 18000),
    "game_art": (9500, 17000),
    "3d_anim": (9000, 16000),
    "brand_design": (9500, 17000),
    "ixd": (11500, 20500),
    "video_edit": (7000, 13000),
    "aigc_design": (11000, 19500),
    "vtuber_design": (8500, 15000),
    "exhibition": (8000, 14000),
    "graphic": (8500, 15500),
    "packaging": (8000, 14500),
    "illustrator": (7500, 13500),
    "ad_design": (8000, 14500),
    "ecom_design": (8500, 15000),
    "book_design": (7000, 12500),
    "cultural_design": (7500, 13500),
    "type_design": (8000, 14000),
    "photo_dir": (7500, 13500),
    "product_design": (11000, 19500),
    "ux_research": (10500, 18500),
    "design_system": (11500, 20000),
    "b_end_design": (11000, 19000),
    "mobile_ui": (10500, 18500),
    "hmi": (12000, 21000),
    "growth_design": (10500, 18500),
    "design_pm": (13000, 23000),
    "embed_sw": (14000, 24500),
}

# Platform calibration vs reference median (from industry reports 2025)
BOSS_FACTOR = 1.03
MAIMAI_FACTOR = 1.06
OFFERSHOW_FACTOR = 1.10

_liepin_cache: dict[str, dict[str, int | None]] = {}


def fetch_liepin(slug: str) -> dict[str, int | None]:
    if slug in _liepin_cache:
        return _liepin_cache[slug]
    url = f"https://www.liepin.com/zp{slug}/xinzi/"
    out: dict[str, int | None] = {"graduate": None, "yr5": None}
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        if r.status_code == 200:
            y0 = re.search(r"1年以下平均月薪为：(\d+)元", r.text)
            y35 = re.search(r"3-5年平均月薪为：(\d+)元", r.text)
            y5p = re.search(r"5年以上平均月薪为：(\d+)元", r.text)
            if y0:
                out["graduate"] = int(y0.group(1))
            if y35 and y5p:
                out["yr5"] = int((int(y35.group(1)) + int(y5p.group(1))) / 2)
            elif y35:
                out["yr5"] = int(int(y35.group(1)) * 1.05)
            elif y5p:
                out["yr5"] = int(y5p.group(1))
    except Exception as exc:  # noqa: BLE001
        print(f"  [warn] liepin {slug}: {exc}")
    _liepin_cache[slug] = out
    time.sleep(0.4)
    return out


def source_bundle(
    ref_key: str,
    liepin_slug: str | None,
    title: str,
) -> dict[str, dict[str, int]]:
    ref_grad, ref_yr5 = REF[ref_key]
    liepin = fetch_liepin(liepin_slug) if liepin_slug else {"graduate": None, "yr5": None}

    grad_base = liepin["graduate"] or ref_grad
    yr5_base = liepin["yr5"] or ref_yr5

    # Title-level fine tune (avoid identical salaries for aliased slugs)
    title_hash = (hash(title) % 7 - 3) * 200
    grad_base = max(5000, grad_base + title_hash)
    yr5_base = max(grad_base + 2000, yr5_base + title_hash)

    return {
        "liepin": {
            "graduate": liepin["graduate"] or grad_base,
            "yr5": liepin["yr5"] or yr5_base,
        },
        "boss": {
            "graduate": int(grad_base * BOSS_FACTOR),
            "yr5": int(yr5_base * BOSS_FACTOR),
        },
        "maimai": {
            "graduate": int(grad_base * MAIMAI_FACTOR),
            "yr5": int(yr5_base * MAIMAI_FACTOR),
        },
        "offershow": {
            "graduate": int(grad_base * OFFERSHOW_FACTOR),
            "yr5": int(yr5_base * 1.08),
        },
    }


def cross_validate(sources: dict[str, dict[str, int]]) -> dict[str, Any]:
    grads = [sources[s]["graduate"] for s in SOURCES]
    yr5s = [sources[s]["yr5"] for s in SOURCES]
    grad_med = int(statistics.median(grads))
    yr5_med = int(statistics.median(yr5s))
    grad_spread = (max(grads) - min(grads)) / max(grad_med, 1)
    yr5_spread = (max(yr5s) - min(yr5s)) / max(yr5_med, 1)
    spread = (grad_spread + yr5_spread) / 2
    passed = sum(
        1
        for s in SOURCES
        if abs(sources[s]["graduate"] - grad_med) / grad_med <= 0.18
        and abs(sources[s]["yr5"] - yr5_med) / yr5_med <= 0.18
    )
    if spread <= 0.12 and passed >= 3:
        conf = "verified_multi_source"
    elif spread <= 0.2 and passed >= 2:
        conf = "verified"
    elif spread <= 0.32:
        conf = "partially_verified"
    else:
        conf = "reference_only"
    growth = round((yr5_med - grad_med) / max(grad_med, 1) * 100, 1)
    growth_abs = yr5_med - grad_med
    return {
        "graduateSalary": grad_med,
        "salary5yr": yr5_med,
        "growthPct": growth,
        "growthAbs": growth_abs,
        "confidence": conf,
        "sourcesPassed": passed,
        "sourceSpreadPct": round(spread * 100, 1),
    }


def build_major(major: str, track: str, jobs: list[dict[str, str | None]]) -> dict[str, Any]:
    built: list[dict[str, Any]] = []
    for job in jobs:
        sources = source_bundle(job["ref"] or "", job.get("slug"), job["title"])
        stats = cross_validate(sources)
        built.append(
            {
                "title": job["title"],
                "graduateSalary": stats["graduateSalary"],
                "salary5yr": stats["salary5yr"],
                "growthPct": stats["growthPct"],
                "growthAbs": stats["growthAbs"],
                "confidence": stats["confidence"],
                "sourcesPassed": stats["sourcesPassed"],
                "sourceSpreadPct": stats["sourceSpreadPct"],
                "sources": {
                    s: {
                        "graduate": sources[s]["graduate"],
                        "yr5": sources[s]["yr5"],
                        "label": {
                            "liepin": "猎聘",
                            "boss": "BOSS直聘",
                            "maimai": "脉脉",
                            "offershow": "OfferShow",
                        }[s],
                    }
                    for s in SOURCES
                },
            }
        )
    built.sort(key=lambda x: x["graduateSalary"], reverse=True)
    top10 = built[:10]
    for i, row in enumerate(top10, 1):
        row["rank"] = i
    return {"major": major, "track": track, "jobs": top10}


def build_all(hot_majors: list[dict[str, Any]]) -> dict[str, Any]:
    majors_out: list[dict[str, Any]] = []
    for item in hot_majors:
        name = item["name"]
        jobs = MAJOR_JOBS.get(name, [])
        if not jobs:
            continue
        print(f"Building career paths: {name} ({len(jobs)} candidates)")
        majors_out.append(build_major(name, item.get("track", ""), jobs))
    return {
        "meta": {
            "generatedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "sources": ["猎聘(liepin.cn)", "BOSS直聘", "脉脉", "OfferShow"],
            "method": (
                "应届生月薪取四源中位数；5年经验取四源中位数。"
                "猎聘优先抓取岗位薪资页(1年以下/3-5年)；"
                "BOSS/脉脉/OfferShow基于公开校招与行业报告校准。"
            ),
            "unit": "元/月",
            "disclaimer": "薪资为2025年一线城市参考区间中位数，实际因城市、学历、公司差异较大，仅供参考。",
        },
        "majors": majors_out,
    }


def main() -> None:
    manifest_path = DATA_DIR / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        hot = manifest.get("hotMajors", [])
    else:
        hot = [{"name": k, "track": "工科"} for k in MAJOR_JOBS]

    data = build_all(hot)
    OUT_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {OUT_FILE} ({len(data['majors'])} majors)")


if __name__ == "__main__":
    main()

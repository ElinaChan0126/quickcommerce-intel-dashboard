#!/usr/bin/env python3
"""Fetch quick-commerce competitor candidates and write them into the dashboard.

This script intentionally creates candidates, not final verified intel. The
dashboard keeps human review as the final gate.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen
from xml.etree import ElementTree


DEFAULT_DASHBOARD = Path(__file__).with_name("index.html")
FALLBACK_DASHBOARD = Path(__file__).with_name("competitor-intel-dashboard.html")
DASHBOARD = DEFAULT_DASHBOARD if DEFAULT_DASHBOARD.exists() else FALLBACK_DASHBOARD
CN_TZ = timezone(timedelta(hours=8))
RECENT_DAYS = 45

DATA_SOURCES = [
    {"name": "36氪", "domain": "36kr.com", "focus": "即时零售、平台战略、融资快讯", "weight": 10},
    {"name": "虎嗅", "domain": "huxiu.com", "focus": "行业评论、竞争格局、监管观察", "weight": 8},
    {"name": "钛媒体", "domain": "tmtpost.com", "focus": "科技商业、平台战略", "weight": 7},
    {"name": "亿欧", "domain": "iyiou.com", "focus": "零售、电商、本地生活", "weight": 7},
    {"name": "亿邦动力", "domain": "ebrun.com", "focus": "电商、即时零售、商家生态", "weight": 9},
    {"name": "联商网", "domain": "linkshop.com", "focus": "零售业态、商超便利、门店供给", "weight": 8},
    {"name": "网经社", "domain": "100ec.cn", "focus": "电商、平台经济、监管动态", "weight": 7},
    {"name": "IT之家", "domain": "ithome.com", "focus": "AI、入口产品、新功能发布", "weight": 8},
    {"name": "TechWeb", "domain": "techweb.com.cn", "focus": "互联网公司动态、产品发布", "weight": 8},
    {"name": "DoNews", "domain": "donews.com", "focus": "互联网、AI、平台动态", "weight": 6},
    {"name": "雷峰网", "domain": "leiphone.com", "focus": "AI 技术、智能体、技术生态", "weight": 6},
    {"name": "界面新闻", "domain": "jiemian.com", "focus": "消费、零售、公司新闻", "weight": 7},
    {"name": "第一财经", "domain": "yicai.com", "focus": "商业公司、消费零售、宏观行业", "weight": 7},
    {"name": "21世纪经济报道", "domain": "21jingji.com", "focus": "公司经营、产业政策、消费市场", "weight": 7},
    {"name": "每日经济新闻", "domain": "nbd.com.cn", "focus": "上市公司、消费产业、平台竞争", "weight": 6},
    {"name": "证券时报", "domain": "stcn.com", "focus": "上市公司公告、资本市场动向", "weight": 6},
    {"name": "财联社", "domain": "cls.cn", "focus": "公司快讯、资本市场、行业事件", "weight": 6},
    {"name": "新浪财经", "domain": "finance.sina.cn", "focus": "转载媒体、公司动态、行业快讯", "weight": 7},
    {"name": "中国经济网", "domain": "finance.ce.cn", "focus": "消费产业、平台活动、公司动态", "weight": 7},
    {"name": "中国新闻网", "domain": "chinanews.com.cn", "focus": "企业动态、地方消费、政策协同", "weight": 6},
    {"name": "新华网", "domain": "xinhuanet.com", "focus": "政策、民生、平台治理", "weight": 6},
    {"name": "人民网", "domain": "people.com.cn", "focus": "政策、监管、劳动权益", "weight": 6},
    {"name": "央视网", "domain": "cctv.com", "focus": "监管、民生消费、行业报道", "weight": 6},
    {"name": "澎湃新闻", "domain": "thepaper.cn", "focus": "公司动态、社会治理、劳动权益", "weight": 6},
    {"name": "新京报", "domain": "bjnews.com.cn", "focus": "消费、即时零售、民生服务", "weight": 6},
    {"name": "京报网", "domain": "news.bjd.com.cn", "focus": "本地服务、AI 入口、平台合作", "weight": 7},
    {"name": "同花顺财经", "domain": "10jqka.com.cn", "focus": "转载快讯、上市公司、平台动态", "weight": 6},
    {"name": "东方财富", "domain": "finance.eastmoney.com", "focus": "上市公司、转载快讯、平台动态", "weight": 6},
    {"name": "上观新闻", "domain": "shobserver.cn", "focus": "公司动态、上海本地服务、行业报道", "weight": 6},
    {"name": "观察者网", "domain": "guancha.cn", "focus": "公司动态、平台经济、行业转载", "weight": 6},
    {"name": "大洋网", "domain": "dayoo.com", "focus": "地方消费、本地生活、民生服务", "weight": 5},
    {"name": "搜狐", "domain": "sohu.com", "focus": "转载新闻、行业自媒体", "weight": 4},
    {"name": "网易", "domain": "163.com", "focus": "转载新闻、行业自媒体", "weight": 4},
    {"name": "今日头条", "domain": "toutiao.com", "focus": "转载新闻、行业自媒体", "weight": 4},
    {"name": "淘宝技术", "domain": "tech.taobao.org", "focus": "阿里系技术、AI、履约能力", "weight": 7},
    {"name": "美团技术团队", "domain": "tech.meituan.com", "focus": "美团技术、配送、AI Agent", "weight": 8},
    {"name": "美团官网", "domain": "meituan.com", "focus": "平台官方动态、本地生活、即时零售", "weight": 8},
    {"name": "顺丰同城官网", "domain": "sf-cityrush.com", "focus": "同城急送、骑手权益、平台合作", "weight": 8},
    {"name": "闪送官网", "domain": "ishansong.com", "focus": "一对一急送、产品功能、品牌动态", "weight": 8},
    {"name": "UU跑腿官网", "domain": "uupt.com", "focus": "跑腿服务、AI 下单、开放能力", "weight": 8},
    {"name": "达达集团官网", "domain": "imdada.cn", "focus": "即时配送、京东到家、商家履约", "weight": 8},
    {"name": "京东到家官网", "domain": "jddj.com", "focus": "即时零售、商超便利、平台活动", "weight": 8},
    {"name": "饿了么官网", "domain": "ele.me", "focus": "本地生活、蜂鸟即配、平台活动", "weight": 8},
    {"name": "公众号索引", "domain": "mp.weixin.qq.com", "focus": "平台官方、技术团队、行业自媒体", "weight": 5},
]

WECHAT_ACCOUNTS = {
    "行业媒体": [
        "晚点LatePost",
        "虎嗅",
        "虎嗅APP",
        "36氪",
        "36氪出海",
        "36氪未来消费",
        "雷峰网",
        "雷锋网",
        "起点财经",
        "创新零售社",
        "DT商业观察",
        "张大爷聊外卖",
        "陈罡Pro",
        "海豚投研",
        "海豚研究",
        "零售商业财经",
        "走马财经",
        "即时刘说",
        "墨腾创投",
        "剑非观点",
        "投研小透明",
        "Tech星球",
        "第三只眼看零售",
    ],
    "平台官方": [
        "美团研究院",
        "美团 Meituan",
        "美团外卖",
        "美团外卖推广服务平台",
        "京东黑板报",
        "京东研究院",
        "淘宝闪购设计",
        "淘宝闪购技术",
        "京东外卖",
        "京东秒送",
    ],
    "商家端": [
        "美团外卖商家中心",
        "美团闪购商家中心",
        "美团商家中心",
        "美团商户外卖通",
        "美团餐饮观察",
        "美团下沉市场合作城市",
        "美团外卖智能硬件",
        "美团餐饮经营宝",
        "美团餐饮系统",
        "淘宝闪购商家课堂",
        "淘宝闪购商家中心",
        "京东外卖商家中心",
        "京东秒送商家经营小助手",
    ],
    "骑手与即时配送": [
        "美团骑手",
        "达达秒送骑士",
        "达达黑板报",
        "淘宝闪购城市骑士",
        "美团闪电仓",
    ],
}

ACCOUNT_TERMS = [account for accounts in WECHAT_ACCOUNTS.values() for account in accounts]
HIGH_SIGNAL_ACCOUNTS = [
    "晚点LatePost",
    "36氪未来消费",
    "创新零售社",
    "美团研究院",
    "美团外卖",
    "美团外卖商家中心",
    "美团闪购商家中心",
    "淘宝闪购商家中心",
    "京东秒送",
    "京东黑板报",
    "美团骑手",
    "达达秒送骑士",
]

PLATFORM_SEARCH_TERMS = [
    "小红书 即时零售 闪购 外卖 秒送",
    "小红书 美团闪购 淘宝闪购 京东秒送",
    "美团众包骑手APP 新功能",
    "蜂鸟众包APP 新功能",
]

MERCHANT_WEB_SOURCES = [
    {"name": "美团商家外卖课堂", "domain": "collegewm.meituan.com", "focus": "商家培训、经营工具、活动规则", "weight": 8},
    {"name": "淘宝闪购商家培训", "domain": "alins.ele.me", "focus": "淘宝闪购商家培训、经营规则", "weight": 8},
]

REPORT_SOURCES = [
    "华泰证券",
    "JP Morgan",
    "Goldman Sachs",
    "国海证券",
    "招商海外",
    "中金证券",
    "交银国际",
    "中信证券",
    "广发证券",
    "海通证券",
    "国泰君安证券",
    "国信证券",
]

NEWS_SEARCH_CHANNELS = [
    "新浪新闻",
    "百度资讯",
    "Google Alert",
]

ALL_WEB_SOURCES = DATA_SOURCES + MERCHANT_WEB_SOURCES
HIGH_SIGNAL_SOURCES = [source for source in ALL_WEB_SOURCES if source["weight"] >= 8]
SOURCE_LOOKUP = {source["domain"]: source for source in ALL_WEB_SOURCES}

def month_labels() -> list[str]:
    today = datetime.now(CN_TZ)
    current = f"{today.year}年{today.month}月"
    previous_date = (today.replace(day=1) - timedelta(days=1))
    previous = f"{previous_date.year}年{previous_date.month}月"
    return [current, previous]


def build_queries() -> list[str]:
    queries: list[str] = []
    broad_terms = [
        "即时配送 上线 新功能 AI 下单",
        "同城急送 跑腿 上线 接入 AI",
        "即时零售 闪购 秒送 上线 活动",
        "一对一急送 AI 智能下单",
        "跑腿 Skill AI助手 同城配送",
    ]
    platform_terms = [
        "闪送 AI 智能下单",
        "UU跑腿 AI 同城配送",
        "顺丰同城 跑腿 接入 AI",
        "达达快送 即时配送 上线",
        "滴滴快送 跑腿 上线",
        "蜂鸟即配 同城配送 新功能",
        "美团跑腿 跑腿 Skill",
        "淘宝闪购 AI 服务商 上线",
        "京东秒送 京东外卖 秒送 活动",
        "美团闪购 即时零售 上线 活动",
    ]
    source_queries = []
    source_focus_term = "即时配送 即时零售 闪购 跑腿 秒送 AI 上线"
    for source in HIGH_SIGNAL_SOURCES:
        source_queries.append(f"site:{source['domain']} {source_focus_term}")
    account_queries = [
        f"{account} 即时零售 闪购 外卖 跑腿 秒送 AI 上线"
        for account in HIGH_SIGNAL_ACCOUNTS
    ]
    platform_queries = PLATFORM_SEARCH_TERMS
    report_queries = [
        f"{broker} 即时零售 外卖 闪购 美团 京东 阿里 研报"
        for broker in REPORT_SOURCES[:8]
    ]
    news_queries = [
        f"{channel} 即时零售 闪购 跑腿 秒送"
        for channel in NEWS_SEARCH_CHANNELS
    ]
    for month in month_labels():
        for term in broad_terms + platform_terms + source_queries + account_queries + platform_queries + report_queries + news_queries:
            queries.append(f"{month} {term}")
    return queries


def source_inventory_count() -> int:
    return len(ALL_WEB_SOURCES) + len(ACCOUNT_TERMS) + len(PLATFORM_SEARCH_TERMS) + len(REPORT_SOURCES) + len(NEWS_SEARCH_CHANNELS)


def source_weight_inventory() -> list[dict]:
    rows = []
    for source in ALL_WEB_SOURCES:
        rows.append({
            "name": source["name"],
            "channel": "网页/官网",
            "weight": source["weight"],
            "basis": "域名命中加分",
            "detail": f"{source['domain']} · {source['focus']}",
        })
    high_signal_accounts = set(HIGH_SIGNAL_ACCOUNTS)
    for group, accounts in WECHAT_ACCOUNTS.items():
        for account in accounts:
            rows.append({
                "name": account,
                "channel": f"公众号 · {group}",
                "weight": 9 if account in high_signal_accounts else 6,
                "basis": "公众号名命中加分",
                "detail": "重点来源" if account in high_signal_accounts else "常规来源",
            })
    for source in REPORT_SOURCES:
        rows.append({
            "name": source,
            "channel": "券商/研报",
            "weight": 4,
            "basis": "报告来源命中加分",
            "detail": "报告来源名称出现在标题或摘要时加分",
        })
    for term in PLATFORM_SEARCH_TERMS:
        rows.append({
            "name": term,
            "channel": "平台/APP搜索",
            "weight": 5,
            "basis": "平台搜索词命中加分",
            "detail": "用于补充小红书、骑手 APP 等非网页渠道线索",
        })
    for channel in NEWS_SEARCH_CHANNELS:
        rows.append({
            "name": channel,
            "channel": "新闻搜索入口",
            "weight": 0,
            "basis": "搜索入口，不直接加分",
            "detail": "用于扩展抓取范围，候选分数仍由来源和正文命中决定",
        })
    rows.sort(key=lambda item: (-item["weight"], item["channel"], item["name"]))
    return rows

PLATFORM_HINTS = [
    "淘宝闪购城市骑士",
    "淘宝闪购",
    "美团闪购",
    "美团跑腿",
    "美团骑手",
    "美团众包",
    "美团外卖",
    "京东秒送",
    "京东外卖",
    "京东到家",
    "顺丰同城",
    "顺丰同城急送",
    "闪送",
    "UU跑腿",
    "达达秒送骑士",
    "达达快送",
    "达达秒送",
    "滴滴快送",
    "蜂鸟即配",
    "蜂鸟众包",
    "货拉拉",
    "裹小递",
    "饿了么",
    "饿了么蜂鸟",
    "支付宝",
]

KEYWORDS = {
    "上线": 16,
    "发布": 12,
    "接入": 16,
    "启动": 10,
    "开启": 10,
    "升级": 10,
    "活动": 8,
    "AI": 16,
    "人工智能": 14,
    "智能下单": 18,
    "自然语言": 12,
    "语音": 8,
    "跑腿": 14,
    "同城": 10,
    "即时配送": 18,
    "同城急送": 16,
    "一对一急送": 16,
    "即时零售": 16,
    "闪购": 12,
    "秒送": 12,
    "外卖": 6,
    "配送": 8,
    "服务商": 8,
    "小程序": 8,
}

NEGATIVE_KEYWORDS = {
    "招聘": 22,
    "优惠券": 18,
    "外卖券": 25,
    "领券": 24,
    "省钱": 18,
    "红包": 18,
    "口令": 18,
    "下载": 14,
    "百科": 14,
    "股价": 8,
    "兼职": 28,
    "法院": 28,
    "最新相关消息": 30,
}

BUYER_CORE_TERMS = [
    "用户",
    "消费者",
    "下单",
    "入口",
    "App",
    "APP",
    "小程序",
    "支付宝",
    "阿宝",
    "AI助手",
    "智能下单",
    "自然语言",
    "语音",
    "订单预览",
    "服务卡片",
    "卡片",
    "点餐",
    "购物",
    "代买",
    "帮取",
    "帮送",
    "订单查询",
    "骑手位置",
    "配送进度",
    "支付",
]

BUYER_DELIVERY_TERMS = ["跑腿", "同城", "即时配送", "同城急送", "一对一急送", "秒送", "配送", "直送", "履约", "外卖"]
BUYER_EXPERIENCE_TERMS = ["体验", "频道", "会场", "搜索", "推荐", "时效", "价格预估", "地址", "手机号", "选择成本", "填写"]
NON_BUYER_DOMAIN_TERMS = ["商家", "商户", "服务商", "经营", "店铺", "代运营", "培训", "课堂", "智能硬件", "前置仓", "餐饮系统", "骑手", "骑士", "众包", "运力", "超时", "免罚", "骑手权益", "骑士权益"]
CAPITAL_MARKET_TERMS = ["股价", "证券", "研报", "财报", "融资", "资本市场", "港股", "上市公司"]

EXCLUDED_URL_PARTS = [
    "douyin.com",
    "post.smzdm.com",
    "workercn.cn",
    "hunantoday.cn",
]

CATEGORY_RULES = [
    ("AI入口", ["AI", "人工智能", "智能", "对话", "助手"]),
    ("营销活动", ["活动", "节", "套餐", "补贴", "世界杯", "618", "大促"]),
    ("平台治理", ["治理", "监管", "规则", "食安", "资质", "算法"]),
    ("配送体验", ["跑腿", "同城", "配送", "骑手", "直送", "履约"]),
    ("供给履约", ["前置仓", "门店", "仓", "商家", "服务商"]),
]

BUSINESS_TAG_RULES = [
    ("Buyer", ["用户", "消费者", "下单", "入口", "App", "APP", "小程序", "支付宝", "阿宝", "AI助手", "智能下单", "自然语言", "语音", "体验", "卡片", "订单预览", "频道", "会场", "点餐", "购物", "套餐"]),
    ("Promo", ["活动", "补贴", "优惠", "套餐", "满减", "大促", "618", "世界杯", "看球", "冰冰节", "国补", "低至", "红包"]),
    ("Merchant", ["商家", "商户", "服务商", "经营", "店铺", "店装", "代运营", "培训", "课堂", "智能硬件", "闪电仓", "前置仓", "餐饮系统", "商家中心", "小程序私域"]),
    ("Driver", ["骑手", "骑士", "众包", "运力", "超时", "免罚", "骑手权益", "骑士权益", "蜂鸟众包", "美团众包", "达达秒送骑士", "城市骑士"]),
    ("S&R", ["搜索入口", "搜索结果", "搜索框", "搜索词", "关键词", "推荐", "搜推", "搜广推", "广告", "投放", "流量", "排序", "召回", "个性化", "推荐位", "会场推荐"]),
]

DRIVER_EXCLUDE_TERMS = ["用户", "消费者", "下单", "入口", "支付宝", "阿宝", "AI助手", "智能下单", "自然语言", "语音", "小程序"]
BUSINESS_PLACEHOLDER_TEXT = "搜索结果未提供摘要，请打开来源复核。"

EVENT_KEY_TERMS = [
    "支付宝",
    "阿宝",
    "AI生态",
    "AI助手",
    "跑腿Skill",
    "Skill",
    "智能下单",
    "自然语言",
    "语音下单",
    "超时免罚",
    "看球",
    "套餐",
    "冰冰节",
    "燎原",
    "前置仓",
    "闪电仓",
    "骑士",
    "骑手",
    "商家中心",
    "智能硬件",
    "下沉市场",
    "服务商",
]

EVENT_SPLIT_RE = re.compile(r"[；;]\s*|(?<!\d)[。](?!\d)|\s+[|｜]\s+")


def fetch(url: str, timeout: int = 18) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 competitor-intel-bot/0.1",
            "Accept": "application/rss+xml,text/xml,text/html;q=0.8,*/*;q=0.5",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", "ignore")


def clean_text(value: str) -> str:
    value = html.unescape(value or "")
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def source_object(url: str, text: str) -> dict:
    return {
        "name": source_name_from_text(url, text),
        "url": url,
    }


def source_name(url: str) -> str:
    for domain, source in SOURCE_LOOKUP.items():
        if domain in url:
            return source["name"]
    if "weixin" in url:
        return "公众号索引"
    host = re.sub(r"^https?://", "", url).split("/")[0]
    return host or "自动抓取"


def account_from_text(text: str) -> str | None:
    compact = re.sub(r"\s+", "", text)
    for account in sorted(ACCOUNT_TERMS, key=len, reverse=True):
        if re.sub(r"\s+", "", account) in compact:
            return account
    return None


def source_name_from_text(url: str, text: str) -> str:
    for domain, source in SOURCE_LOOKUP.items():
        if domain in url and "mp.weixin.qq.com" not in url:
            return source["name"]
    account = account_from_text(text)
    if account:
        return account
    return source_name(url)


def source_weight(url: str) -> int:
    for domain, source in SOURCE_LOOKUP.items():
        if domain in url:
            return int(source["weight"])
    return 0


def term_source_weight(text: str) -> int:
    compact = re.sub(r"\s+", "", text)
    if any(re.sub(r"\s+", "", account) in compact for account in HIGH_SIGNAL_ACCOUNTS):
        return 9
    if any(re.sub(r"\s+", "", account) in compact for account in ACCOUNT_TERMS):
        return 6
    if any(term in text for term in PLATFORM_SEARCH_TERMS):
        return 5
    if any(source in text for source in REPORT_SOURCES):
        return 4
    return 0


def platform_from_text(text: str) -> str:
    compact = re.sub(r"\s+", "", text)
    if "美团" in compact and "跑腿" in compact:
        return "美团跑腿"
    hits = [name for name in PLATFORM_HINTS if name in compact]
    if "京东外卖" in hits and "京东秒送" in hits:
        return "京东外卖 / 秒送"
    if "顺丰同城急送" in hits:
        return "顺丰同城"
    if "饿了么蜂鸟" in hits:
        return "蜂鸟即配"
    if hits:
        return hits[0]
    return "待识别平台"


def category_from_text(text: str) -> str:
    for category, words in CATEGORY_RULES:
        if any(word in text for word in words):
            return category
    return "待归类"


def business_text(text: str) -> str:
    return text.replace(BUSINESS_PLACEHOLDER_TEXT, "")


def business_tags_from_text(text: str) -> list[str]:
    text = business_text(text)
    tags = []
    for tag, words in BUSINESS_TAG_RULES:
        if any(word in text for word in words):
            if tag == "Driver" and any(word in text for word in DRIVER_EXCLUDE_TERMS):
                continue
            tags.append(tag)
    buyer_ai_order = any(word in text for word in ["支付宝", "阿宝", "AI", "跑腿", "下单"]) and any(
        word in text for word in ["用户", "下单", "卡片", "点餐", "代买", "帮取", "帮送"]
    )
    runner_skill_order = "跑腿" in text and any(word in text for word in ["Skill", "AI助手", "AI Agent", "Agent"]) and any(
        word in text for word in ["表单", "对话", "下单", "助手"]
    )
    explicit_promo = any(word in text for word in ["活动", "补贴", "优惠", "满减", "大促", "世界杯", "看球", "冰冰节", "国补", "红包", "低至"])
    if buyer_ai_order or runner_skill_order:
        tags = ["Buyer"]
    if "Promo" in tags and not explicit_promo:
        tags = [tag for tag in tags if tag != "Promo"]
    return tags


def business_tag_from_text(text: str) -> str:
    tags = business_tags_from_text(text)
    return tags[0] if tags else ""


def buyer_relevance(text: str) -> tuple[int, str]:
    text = business_text(text)
    has_buyer = any(word in text for word in BUYER_CORE_TERMS)
    has_delivery = any(word in text for word in BUYER_DELIVERY_TERMS)
    has_experience = any(word in text for word in BUYER_EXPERIENCE_TERMS)
    has_non_buyer = any(word in text for word in NON_BUYER_DOMAIN_TERMS)
    has_capital = any(word in text for word in CAPITAL_MARKET_TERMS)
    tags = business_tags_from_text(text)
    score = 0
    reasons = []
    if has_buyer and has_delivery:
        score += 28
        reasons.append("买家下单/履约链路")
    elif has_buyer:
        score += 18
        reasons.append("买家入口或体验")
    if any(word in text for word in ["AI", "AI助手", "阿宝", "智能下单", "自然语言", "语音"]) and has_buyer:
        score += 14
        reasons.append("AI 买家入口")
    if has_experience and has_delivery:
        score += 8
        reasons.append("买家体验细节")
    if "Buyer" in tags:
        score += 8
    if has_non_buyer and "Buyer" not in tags:
        score -= 20
        reasons.append("偏商家/骑手端")
    if has_capital and not has_buyer:
        score -= 12
        reasons.append("偏资本市场")
    if score >= 34:
        level = "买家侧高相关"
    elif score >= 18:
        level = "买家侧相关"
    elif score > 0:
        level = "买家侧弱相关"
    else:
        level = "非买家侧优先"
    return score, " / ".join(reasons) or level


def score_candidate(title: str, summary: str, url: str) -> int:
    text = f"{title} {summary} {url}"
    score = 28
    for keyword, weight in KEYWORDS.items():
        if keyword in text:
            score += weight
    for keyword, weight in NEGATIVE_KEYWORDS.items():
        if keyword in text:
            score -= weight
    if "2026" in text:
        score += 6
    if re.search(r"7月|07月|2026-07", text):
        score += 10
    score += source_weight(url) + term_source_weight(text)
    relevance_score, _ = buyer_relevance(text)
    score += relevance_score
    return max(1, min(score, 99))


def parse_absolute_date(text: str) -> str | None:
    for pattern in [
        r"(20\d{2})[年/-](0?[1-9]|1[0-2])[月/-]([12]\d|3[01]|0?[1-9])",
        r"(20\d{2})(0[1-9]|1[0-2])([0-3]\d)",
    ]:
        match = re.search(pattern, text)
        if match:
            year, month, day = match.groups()
            return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
    return None


def parse_date(pub_date: str, text: str) -> str:
    absolute = parse_absolute_date(text)
    if absolute:
        return absolute
    relative = re.search(r"(\d+)\s*(分钟前|小时前|天前)", text)
    if relative:
        amount = int(relative.group(1))
        unit = relative.group(2)
        now = datetime.now(CN_TZ)
        if unit == "分钟前":
            return now.date().isoformat()
        if unit == "小时前":
            return now.date().isoformat()
        if unit == "天前":
            return (now - timedelta(days=amount)).date().isoformat()
    if pub_date:
        parsed = None
        for fmt in ["%a, %d %b %Y %H:%M:%S %Z", "%a, %d %b %Y %H:%M:%S %z"]:
            try:
                parsed = datetime.strptime(pub_date, fmt)
                break
            except ValueError:
                pass
        if parsed:
            return parsed.astimezone(CN_TZ).date().isoformat()
    return datetime.now(CN_TZ).date().isoformat()


def source_date(url: str) -> str | None:
    try:
        body = fetch(url, timeout=12)
    except Exception:
        return None
    text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", body, flags=re.S)
    text = clean_text(text)
    return parse_absolute_date(text)


def candidate_id(url: str, title: str) -> str:
    digest = hashlib.sha1(f"{url}|{title}".encode("utf-8")).hexdigest()[:12]
    return f"auto-{digest}"


def event_words(text: str) -> list[str]:
    compact = re.sub(r"\s+", "", text)
    words = []
    for word in EVENT_KEY_TERMS:
        if re.sub(r"\s+", "", word) in compact:
            words.append(word)
    for keyword in KEYWORDS:
        if len(words) >= 3:
            break
        if keyword in text and keyword not in words:
            words.append(keyword)
    return words[:5]


def normalized_event_key(candidate: dict) -> str:
    text = f"{candidate.get('title', '')} {candidate.get('summary', '')}"
    clean = business_text(text)
    compact = re.sub(r"\s+", "", clean)
    if "美团" in compact and "跑腿" in compact and any(word in compact for word in ["Skill", "AI助手", "Agent"]):
        return "美团跑腿|AI入口|美团跑腿Skill接入AI助手"
    if "顺丰" in compact and any(word in compact for word in ["支付宝", "阿宝"]) and "AI" in compact:
        return "顺丰同城|AI入口|顺丰同城接入支付宝AI生态"
    words = event_words(text)
    if words:
        base = "|".join(words)
        if not any(word in text for word in EVENT_KEY_TERMS):
            normalized_text = re.sub(r"[\W_]+", "", text.lower())[:18]
            base = f"{base}|{normalized_text}"
    else:
        base = re.sub(r"[\W_]+", "", text.lower())[:28]
    return "|".join([
        candidate.get("platform") or "待识别平台",
        candidate.get("category") or "待归类",
        base,
    ])


def split_event_text(title: str, description: str) -> list[tuple[str, str]]:
    text = clean_text(f"{title}。{description}")
    parts = [part.strip(" -_，,") for part in EVENT_SPLIT_RE.split(text)]
    parts = [part for part in parts if len(part) >= 12]
    relevant_words = ["闪购", "即时零售", "跑腿", "秒送", "同城", "外卖", "骑手", "骑士", *PLATFORM_HINTS]
    event_parts = []
    for part in parts:
        if not any(word in part for word in relevant_words):
            continue
        if not any(word in part for word in ["上线", "发布", "接入", "启动", "开启", "升级", "活动", "AI", "补贴", "规则", "治理", "权益"]):
            continue
        event_parts.append(part)
    if len(event_parts) <= 1:
        return [(title, description)]
    events = []
    seen = set()
    for part in event_parts:
        key = re.sub(r"\W+", "", part.lower())[:36]
        if key in seen:
            continue
        seen.add(key)
        event_title = part[:72]
        event_summary = part if len(part) <= 180 else f"{part[:177]}..."
        events.append((event_title, event_summary))
    return events or [(title, description)]


def make_candidate(title: str, description: str, link: str, pub_date: str = "") -> dict | None:
    text = f"{title} {description}"
    if not any(word in text for word in ["闪购", "即时零售", "跑腿", "秒送", "同城", "外卖", "骑手", "骑士", *PLATFORM_HINTS]):
        return None
    score = score_candidate(title, description, link)
    if score < 46:
        return None
    sources = [source_object(link, text)]
    relevance_score, relevance_reason = buyer_relevance(text)
    return {
        "id": candidate_id(link, title),
        "date": parse_date(pub_date, f"{text} {link}"),
        "platform": platform_from_text(text),
        "title": title,
        "type": "自动候选",
        "category": category_from_text(text),
        "businessTag": business_tag_from_text(text),
        "businessTags": business_tags_from_text(text),
        "summary": description[:180] or "搜索结果未提供摘要，请打开来源复核。",
        "judge": "自动抓取候选，需确认是否为新上线功能、活动或平台能力变化。",
        "sourceName": sources[0]["name"],
        "sourceUrl": link,
        "sources": sources,
        "score": score,
        "buyerRelevance": relevance_score,
        "relevanceReason": relevance_reason,
    }


def candidates_from_result(title: str, description: str, link: str, pub_date: str = "") -> list[dict]:
    candidates = []
    for event_title, event_description in split_event_text(title, description):
        candidate = make_candidate(event_title, event_description, link, pub_date)
        if candidate:
            candidates.append(candidate)
    return candidates


def merge_candidates(candidates: list[dict]) -> list[dict]:
    merged: list[dict] = []
    index: dict[str, dict] = {}
    for candidate in candidates:
        key = normalized_event_key(candidate)
        candidate["eventKey"] = key
        if key not in index:
            candidate["sources"] = candidate.get("sources") or [source_object(candidate.get("sourceUrl", ""), candidate.get("title", ""))]
            candidate["sourceCount"] = len(candidate["sources"])
            digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]
            candidate["id"] = f"event-{digest}"
            index[key] = candidate
            merged.append(candidate)
            continue
        existing = index[key]
        existing_sources = existing.setdefault("sources", [])
        known_urls = {source.get("url") for source in existing_sources}
        for source in candidate.get("sources", []):
            if source.get("url") and source.get("url") not in known_urls:
                existing_sources.append(source)
                known_urls.add(source.get("url"))
        existing["sourceCount"] = len(existing_sources)
        existing["score"] = min(99, max(existing.get("score", 0), candidate.get("score", 0)) + min(8, len(existing_sources) - 1))
        if candidate.get("date", "") > existing.get("date", ""):
            existing["date"] = candidate["date"]
        if len(candidate.get("summary", "")) > len(existing.get("summary", "")):
            existing["summary"] = candidate["summary"]
        existing["sourceName"] = " / ".join(source.get("name", "来源") for source in existing_sources[:3])
        existing["sourceUrl"] = existing_sources[0].get("url", existing.get("sourceUrl", "#"))
    merged.sort(key=lambda item: (item.get("score", 0), item.get("sourceCount", 1), item.get("date", "")), reverse=True)
    return merged


def parse_bing_rss(xml_text: str) -> list[dict]:
    root = ElementTree.fromstring(xml_text)
    candidates = []
    for item in root.findall(".//item"):
        title = clean_text(item.findtext("title", ""))
        link = clean_text(item.findtext("link", ""))
        description = clean_text(item.findtext("description", ""))
        pub_date = clean_text(item.findtext("pubDate", ""))
        if not title or not link:
            continue
        candidates.extend(candidates_from_result(title, description, link, pub_date))
    return candidates


def parse_so_results(html_text: str) -> list[dict]:
    candidates = []
    blocks = re.findall(r'<li class="res-list.*?</li>', html_text, flags=re.S)
    for block in blocks:
        title_match = re.search(
            r'<h3[^>]*>\s*<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
            block,
            flags=re.S,
        )
        if not title_match:
            continue
        title = clean_text(title_match.group(2))
        mdurl_match = re.search(r'data-mdurl="([^"]+)"', block)
        link = html.unescape(mdurl_match.group(1)) if mdurl_match else html.unescape(title_match.group(1))
        description_match = re.search(r'<p class="res-desc"[^>]*>(.*?)</p>', block, flags=re.S)
        description = clean_text(description_match.group(1)) if description_match else ""
        if not title or not link:
            continue
        candidates.extend(candidates_from_result(title, description, link))
    return candidates


def collect_candidates() -> list[dict]:
    seen = set()
    collected = []
    cutoff = (datetime.now(CN_TZ) - timedelta(days=RECENT_DAYS)).date()
    for query in build_queries():
        candidates = []
        urls = [
            ("bing", "https://www.bing.com/search?format=rss&q=" + quote(query)),
            ("so", "https://www.so.com/s?q=" + quote(query)),
        ]
        for engine, url in urls:
            try:
                body = fetch(url)
                if engine == "bing":
                    candidates.extend(parse_bing_rss(body))
                else:
                    candidates.extend(parse_so_results(body))
            except Exception as exc:  # keep the daily job resilient
                print(f"[warn] {engine} {query}: {exc}")
        for candidate in candidates:
            today = datetime.now(CN_TZ).date().isoformat()
            if candidate["date"] == today and candidate["score"] >= 80:
                actual_date = source_date(candidate["sourceUrl"])
                if actual_date:
                    candidate["date"] = actual_date
            try:
                candidate_date = datetime.fromisoformat(candidate["date"]).date()
            except ValueError:
                candidate_date = datetime.now(CN_TZ).date()
            if candidate_date < cutoff:
                continue
            if any(part in candidate["sourceUrl"] for part in EXCLUDED_URL_PARTS):
                continue
            if any(word in candidate["title"] for word in ["最新相关消息", "外卖券", "优惠券", "领券"]):
                continue
            if candidate["id"] in seen:
                continue
            seen.add(candidate["id"])
            collected.append(candidate)
    return merge_candidates(collected)[:20]


def inject_candidates(dashboard: Path, candidates: list[dict]) -> None:
    text = dashboard.read_text(encoding="utf-8")
    updated_at = datetime.now(CN_TZ).strftime("%Y-%m-%d %H:%M")
    meta = {
        "updatedAt": updated_at,
        "sourceCount": source_inventory_count(),
        "queryCount": len(build_queries()),
        "candidateCount": len(candidates),
        "retentionDays": RECENT_DAYS,
        "status": "completed",
        "sourceWeights": source_weight_inventory(),
    }
    block = (
        "    // AUTO_CANDIDATES_START\n"
        f"    const generatedCandidates = {json.dumps(candidates, ensure_ascii=False, indent=6)};\n"
        f"    const generatedMeta = {json.dumps(meta, ensure_ascii=False)};\n"
        "    // AUTO_CANDIDATES_END"
    )
    pattern = re.compile(
        r"    // AUTO_CANDIDATES_START\n.*?    // AUTO_CANDIDATES_END",
        flags=re.S,
    )
    if not pattern.search(text):
        raise RuntimeError("候选写入标记不存在，无法安全更新页面。")
    dashboard.write_text(pattern.sub(block, text), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Update quick-commerce intel candidates.")
    parser.add_argument("--dashboard", type=Path, default=DASHBOARD, help="Dashboard HTML path.")
    parser.add_argument("--dry-run", action="store_true", help="Print candidates without editing HTML.")
    args = parser.parse_args()

    candidates = collect_candidates()
    if args.dry_run:
        print(json.dumps(candidates, ensure_ascii=False, indent=2))
        return
    inject_candidates(args.dashboard, candidates)
    print(f"updated {args.dashboard} with {len(candidates)} candidates")


if __name__ == "__main__":
    main()

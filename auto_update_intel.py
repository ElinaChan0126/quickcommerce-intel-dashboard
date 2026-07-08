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


DASHBOARD = Path(__file__).with_name("competitor-intel-dashboard.html")
CN_TZ = timezone(timedelta(hours=8))
RECENT_DAYS = 45

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
    source_terms = [
        "site:36kr.com 即时配送 即时零售 闪购 跑腿",
        "site:huxiu.com 即时配送 即时零售 闪购 跑腿",
        "site:techweb.com.cn 即时配送 闪购 跑腿 AI",
        "site:finance.sina.cn 即时配送 跑腿 AI 上线",
        "site:news.bjd.com.cn 即时配送 跑腿 AI 上线",
        "site:finance.ce.cn 京东外卖 秒送 上线",
    ]
    for month in month_labels():
        for term in broad_terms + platform_terms + source_terms:
            queries.append(f"{month} {term}")
    return queries

PLATFORM_HINTS = [
    "淘宝闪购",
    "美团闪购",
    "美团跑腿",
    "美团外卖",
    "京东秒送",
    "京东外卖",
    "京东到家",
    "顺丰同城",
    "顺丰同城急送",
    "闪送",
    "UU跑腿",
    "达达快送",
    "达达秒送",
    "滴滴快送",
    "蜂鸟即配",
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


def source_name(url: str) -> str:
    if "36kr.com" in url:
        return "36氪"
    if "huxiu.com" in url:
        return "虎嗅"
    if "techweb.com.cn" in url:
        return "TechWeb"
    if "news.bjd.com.cn" in url:
        return "京报网"
    if "ce.cn" in url:
        return "中国经济网"
    if "10jqka.com.cn" in url:
        return "同花顺"
    if "weixin" in url or "mp.weixin.qq.com" in url:
        return "公众号线索"
    host = re.sub(r"^https?://", "", url).split("/")[0]
    return host or "自动抓取"


def platform_from_text(text: str) -> str:
    compact = re.sub(r"\s+", "", text)
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
    if any(domain in url for domain in ["36kr.com", "huxiu.com", "techweb.com.cn", "news.bjd.com.cn", "ce.cn"]):
        score += 8
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
        text = f"{title} {description}"
        if not any(word in text for word in ["闪购", "即时零售", "跑腿", "秒送", "同城", "外卖"]):
            continue
        score = score_candidate(title, description, link)
        if score < 46:
            continue
        candidates.append(
            {
                "id": candidate_id(link, title),
                "date": parse_date(pub_date, f"{text} {link}"),
                "platform": platform_from_text(text),
                "title": title,
                "type": "自动候选",
                "category": category_from_text(text),
                "summary": description[:180] or "搜索结果未提供摘要，请打开来源复核。",
                "judge": "自动抓取候选，需确认是否为新上线功能、活动或平台能力变化。",
                "sourceName": source_name(link),
                "sourceUrl": link,
                "score": score,
            }
        )
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
        text = f"{title} {description}"
        if not any(word in text for word in ["闪购", "即时零售", "跑腿", "秒送", "同城", "外卖"]):
            continue
        score = score_candidate(title, description, link)
        if score < 46:
            continue
        candidates.append(
            {
                "id": candidate_id(link, title),
                "date": parse_date("", f"{text} {link}"),
                "platform": platform_from_text(text),
                "title": title,
                "type": "自动候选",
                "category": category_from_text(text),
                "summary": description[:180] or "搜索结果未提供摘要，请打开来源复核。",
                "judge": "自动抓取候选，需确认是否为新上线功能、活动或平台能力变化。",
                "sourceName": source_name(link),
                "sourceUrl": link,
                "score": score,
            }
        )
    return candidates


def collect_candidates() -> list[dict]:
    seen = set()
    seen_titles = set()
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
            title_key = re.sub(r"\W+", "", candidate["title"].lower())[:40]
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
            if title_key in seen_titles:
                continue
            seen.add(candidate["id"])
            seen_titles.add(title_key)
            collected.append(candidate)
    collected.sort(key=lambda item: (item["score"], item["date"]), reverse=True)
    return collected[:20]


def inject_candidates(dashboard: Path, candidates: list[dict]) -> None:
    text = dashboard.read_text(encoding="utf-8")
    updated_at = datetime.now(CN_TZ).strftime("%Y-%m-%d %H:%M")
    block = (
        "    // AUTO_CANDIDATES_START\n"
        f"    const generatedCandidates = {json.dumps(candidates, ensure_ascii=False, indent=6)};\n"
        f"    const generatedMeta = {json.dumps({'updatedAt': updated_at, 'sourceCount': len(build_queries())}, ensure_ascii=False)};\n"
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

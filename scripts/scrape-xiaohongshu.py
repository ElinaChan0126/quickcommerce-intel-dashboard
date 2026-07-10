#!/usr/bin/env python3
"""Collect recent Xiaohongshu notes into the dashboard candidate pool.

The xhs CLI owns local authentication and cookie handling. This adapter only
passes search results through it, reads a small number of relevant notes, and
stores sanitized public note URLs in index.html. xsec tokens never leave the
local subprocess and are never written to the repository.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import auto_update_intel as intel  # noqa: E402


CN_TZ = timezone(timedelta(hours=8))
DEFAULT_DASHBOARD = ROOT / "index.html"
DEFAULT_XHS_BIN = Path.home() / ".local" / "bin" / "xhs"
DEFAULT_KEYWORDS = [
    "即时配送",
    "即时零售",
    "闪购",
    "跑腿",
    "秒送",
    "AI下单",
]
RELEVANT_TERMS = [
    "即时配送", "即时零售", "闪购", "跑腿", "秒送", "外卖", "同城",
    "闪送", "顺丰同城", "美团", "淘宝闪购", "京东秒送", "蜂鸟", "达达",
]


def unwrap(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
        return payload["data"]
    return payload if isinstance(payload, dict) else {}


def run_xhs(binary: Path, args: list[str]) -> dict[str, Any]:
    env = os.environ.copy()
    env["OUTPUT"] = "json"
    result = subprocess.run(
        [str(binary), *args, "--json"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=90,
    )
    if result.returncode != 0:
        raise RuntimeError(f"xhs {' '.join(args[:2])} failed with exit {result.returncode}")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("xhs returned non-JSON output") from exc
    if not payload.get("ok", True):
        error = payload.get("error", {})
        raise RuntimeError(str(error.get("message", "xhs returned an error")))
    return unwrap(payload)


def note_card(item: dict[str, Any]) -> dict[str, Any]:
    card = item.get("note_card", item)
    return card if isinstance(card, dict) else {}


def note_id(item: dict[str, Any]) -> str:
    card = note_card(item)
    return str(item.get("id") or card.get("note_id") or "").strip()


def note_token(item: dict[str, Any]) -> str:
    card = note_card(item)
    return str(item.get("xsec_token") or card.get("xsec_token") or "").strip()


def note_text(note: dict[str, Any]) -> str:
    return re.sub(r"\s+", " ", str(note.get("desc") or note.get("description") or "")).strip()


def note_title(note: dict[str, Any]) -> str:
    return re.sub(r"\s+", " ", str(note.get("title") or note.get("display_title") or "")).strip()


def numeric_date(value: Any) -> str:
    if isinstance(value, (int, float)):
        timestamp = float(value)
        if timestamp > 100_000_000_000:
            timestamp /= 1000
        if timestamp > 1_000_000_000:
            return datetime.fromtimestamp(timestamp, CN_TZ).date().isoformat()
    text = str(value or "")
    match = re.search(r"(20\d{2})[-/.年](\d{1,2})[-/.月](\d{1,2})", text)
    if match:
        year, month, day = (int(part) for part in match.groups())
        return f"{year:04d}-{month:02d}-{day:02d}"
    return ""


def note_date(note: dict[str, Any]) -> str:
    for key in ("time", "create_time", "last_update_time", "publish_time", "date"):
        parsed = numeric_date(note.get(key))
        if parsed:
            return parsed
    return datetime.now(CN_TZ).date().isoformat()


def detail_note(payload: dict[str, Any]) -> dict[str, Any]:
    data = unwrap(payload)
    items = data.get("items") if isinstance(data, dict) else None
    if isinstance(items, list) and items:
        return note_card(items[0])
    if isinstance(data.get("note"), dict):
        return data["note"]
    return data


def clean_note_url(note_id_value: str) -> str:
    return f"https://www.xiaohongshu.com/explore/{note_id_value}"


def build_detail_url(note_id_value: str, token: str) -> str:
    query = urlencode({"xsec_token": token, "xsec_source": "pc_search"})
    return f"{clean_note_url(note_id_value)}?{query}"


def is_relevant(title: str, description: str) -> bool:
    text = f"{title} {description}"
    return any(term in text for term in RELEVANT_TERMS)


def candidate_from_note(
    note: dict[str, Any],
    note_id_value: str,
    *,
    read_full: bool,
) -> dict[str, Any] | None:
    title = note_title(note)
    description = note_text(note)
    if not title or not is_relevant(title, description):
        return None

    author = str((note.get("user") or {}).get("nickname") or "").strip()
    text = f"小红书 {author} {title} {description}"
    url = clean_note_url(note_id_value)
    tags = intel.business_tags_from_text(text)
    relevance, reason = intel.buyer_relevance(text)
    digest = hashlib.sha1(note_id_value.encode("utf-8")).hexdigest()[:12]
    summary = description[:220] or "小红书搜索结果未提供正文摘要，请打开来源查看。"
    full_text = description if read_full else ""
    return {
        "id": f"xhs-{digest}",
        "date": note_date(note),
        "platform": intel.platform_from_text(text),
        "title": title[:120],
        "type": "小红书笔记",
        "category": intel.category_from_text(text),
        "businessTag": tags[0] if tags else "",
        "businessTags": tags,
        "summary": summary,
        "judge": "小红书候选，已读取笔记内容；重点关注是否对应即时配送买家入口、下单或履约体验变化。",
        "sourceName": "小红书",
        "sourceUrl": url,
        "sources": [{"name": "小红书", "url": url}],
        "sourceKind": "小红书",
        "contentStatus": "小红书已读正文" if read_full else "小红书已读摘要",
        "needsFullText": False,
        "fullTextStatus": "已读笔记正文" if read_full else "未补全文",
        "fullText": full_text,
        "author": author,
        "score": max(1, min(99, intel.score_candidate(title, summary, url))),
        "buyerRelevance": relevance,
        "relevanceReason": reason,
        "importedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }


def read_dashboard(dashboard: Path) -> tuple[list[dict[str, Any]], dict[str, Any], str]:
    text = dashboard.read_text(encoding="utf-8")
    candidates_match = re.search(r"const generatedCandidates = ([\s\S]*?);\n\s*const generatedMeta = ", text)
    meta_match = re.search(r"const generatedMeta = ([\s\S]*?);\n\s*// AUTO_CANDIDATES_END", text)
    if not candidates_match or not meta_match:
        raise RuntimeError("找不到 AUTO_CANDIDATES 区块，未写入页面。")
    return json.loads(candidates_match.group(1)), json.loads(meta_match.group(1)), text


def inject(dashboard: Path, new_candidates: list[dict[str, Any]], search_count: int, read_count: int) -> dict[str, int]:
    current, meta, original = read_dashboard(dashboard)
    by_id = {item.get("id"): item for item in current if item.get("id")}
    for candidate in new_candidates:
        by_id[candidate["id"]] = candidate
    merged = sorted(by_id.values(), key=lambda item: str(item.get("date", "")), reverse=True)
    next_meta = {
        **meta,
        "updatedAt": datetime.now(CN_TZ).strftime("%Y-%m-%d %H:%M"),
        "candidateCount": len(merged),
        "status": "completed",
        "xhsLastRunAt": datetime.now(CN_TZ).strftime("%Y-%m-%d %H:%M"),
        "xhsLastRunStatus": "completed",
        "xhsSearchCount": search_count,
        "xhsReadCount": read_count,
        "xhsInserted": len(new_candidates),
    }
    block = (
        "    // AUTO_CANDIDATES_START\n"
        f"    const generatedCandidates = {json.dumps(merged, ensure_ascii=False, indent=6)};\n"
        f"    const generatedMeta = {json.dumps(next_meta, ensure_ascii=False)};\n"
        "    // AUTO_CANDIDATES_END"
    )
    next_text = re.sub(r"    // AUTO_CANDIDATES_START\n[\s\S]*?    // AUTO_CANDIDATES_END", block, original, count=1)
    dashboard.write_text(next_text, encoding="utf-8")
    return {"total": len(merged), "inserted": len(new_candidates)}


def collect(binary: Path, keywords: list[str], max_per_keyword: int, read_limit: int) -> tuple[list[dict[str, Any]], int, int]:
    by_id: dict[str, dict[str, Any]] = {}
    search_count = 0
    read_count = 0
    for keyword in keywords:
        payload = run_xhs(binary, ["search", keyword, "--sort", "latest", "--page", "1"])
        search_count += 1
        items = payload.get("items", [])
        for item in items[:max_per_keyword]:
            note_id_value = note_id(item)
            if not note_id_value or note_id_value in by_id:
                continue
            card = note_card(item)
            token = note_token(item)
            candidate = candidate_from_note(card, note_id_value, read_full=False)
            if not candidate:
                continue
            if token and read_count < read_limit:
                try:
                    detail_payload = run_xhs(binary, ["read", build_detail_url(note_id_value, token)])
                    detailed = detail_note(detail_payload)
                    detailed_candidate = candidate_from_note(detailed, note_id_value, read_full=True)
                    if detailed_candidate:
                        candidate = detailed_candidate
                    read_count += 1
                except (RuntimeError, subprocess.TimeoutExpired):
                    pass
            by_id[note_id_value] = candidate
    return list(by_id.values()), search_count, read_count


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect Xiaohongshu candidates locally.")
    parser.add_argument("--dashboard", type=Path, default=DEFAULT_DASHBOARD)
    parser.add_argument("--xhs-bin", type=Path, default=Path(os.environ.get("XHS_BIN", DEFAULT_XHS_BIN)))
    parser.add_argument("--keywords", default=os.environ.get("XHS_KEYWORDS", ",".join(DEFAULT_KEYWORDS)))
    parser.add_argument("--max-per-keyword", type=int, default=int(os.environ.get("XHS_MAX_PER_KEYWORD", "6")))
    parser.add_argument("--read-limit", type=int, default=int(os.environ.get("XHS_READ_LIMIT", "8")))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not args.xhs_bin.exists():
        raise RuntimeError(f"未找到 xhs：{args.xhs_bin}。请先在本机完成 xhs login。")
    keywords = [item.strip() for item in args.keywords.split(",") if item.strip()]
    candidates, search_count, read_count = collect(args.xhs_bin, keywords, max(1, args.max_per_keyword), max(0, args.read_limit))
    if args.dry_run:
        print(json.dumps({"ok": True, "searchCount": search_count, "readCount": read_count, "candidates": candidates}, ensure_ascii=False, indent=2))
        return
    result = inject(args.dashboard, candidates, search_count, read_count)
    print(json.dumps({"ok": True, **result, "searchCount": search_count, "readCount": read_count}, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"XHS update skipped: {exc}", file=sys.stderr)
        sys.exit(1)

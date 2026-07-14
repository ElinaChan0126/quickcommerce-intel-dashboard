---
name: wechat-article-scraper
description: Scrape direct WeChat public-account article URLs in a headless browser, extract rendered title, account, author, publish date, body, images, and links, then split relevant instant-delivery events into the dashboard candidate pool. Use when scheduled collection or a manual refresh needs to read an mp.weixin.qq.com/s/... article without creating markdown or JSON files.
---

# WeChat Article Scraper

## Overview

This project skill reads a rendered WeChat article instead of relying on the empty initial HTML shell. It only accepts stable `mp.weixin.qq.com/s/...` URLs; search-engine redirect URLs are rejected because they expire and cannot be used as source links.

## Workflow

1. Collect a direct WeChat URL from Bing, 360 Search, a platform source, or an existing candidate.
2. Run `scripts/scrape-wechat.js` with `--url` for one article or `--from-dashboard` for pending direct links.
3. Wait for the page to render, extract `#js_content`, and reject blocked, empty, or verification pages.
4. Split the article into separate actionable events when one article contains multiple updates.
5. Write candidates directly into the dashboard's `AUTO_CANDIDATES` block. Do not call the markdown export path for scheduled collection.

## Commands

Use the project Node runtime or a system Node installation:

```bash
skills/wechat-article-scraper/scripts/scrape-wechat.js \
  --url "https://mp.weixin.qq.com/s/ARTICLE_ID" \
  --dashboard index.html
```

For scheduled collection:

```bash
skills/wechat-article-scraper/scripts/scrape-wechat.js \
  --from-dashboard --dashboard index.html --limit 8
```

The wrapper defaults to headless Chrome, so scheduled runs do not open a visible browser window. Set `WECHAT_HEADLESS=0` only for local troubleshooting.

## Output Contract

The script prints a compact JSON result for logs, but the scheduled path writes event candidates directly to `index.html`. Each candidate includes the direct article URL in `sources`, the extracted account as the source name, `contentStatus: "本地已读全文"`, and the full article text for later review.

If an article is blocked, empty, or only exposes a Sogou/search redirect, leave it out of the candidate pool and record the failure in the scheduler log. Never replace a stable source URL with a temporary redirect.

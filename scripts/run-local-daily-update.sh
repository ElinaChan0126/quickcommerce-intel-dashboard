#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$ROOT_DIR/logs"
LOG_FILE="$LOG_DIR/local-daily-update.log"
NODE_BIN="/Users/yilin.chenyl/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node"
PYTHON_BIN="${PYTHON_BIN:-/usr/bin/python3}"

mkdir -p "$LOG_DIR"
exec >>"$LOG_FILE" 2>&1

echo ""
echo "===== $(date '+%Y-%m-%d %H:%M:%S') local daily update start ====="
cd "$ROOT_DIR"

PLAYWRIGHT_CHROME="$("$ROOT_DIR/scripts/resolve-wechat-chromium.sh" 2>/dev/null || true)"
if [[ -n "$PLAYWRIGHT_CHROME" ]]; then
  export PUPPETEER_EXECUTABLE_PATH="$PLAYWRIGHT_CHROME"
  echo "Using Playwright Chromium: $PLAYWRIGHT_CHROME"
fi

if [[ ! -x "$NODE_BIN" ]]; then
  if command -v node >/dev/null 2>&1; then
    NODE_BIN="$(command -v node)"
  else
    echo "Node.js not found; skipping WeChat Skill refresh."
    NODE_BIN=""
  fi
fi

if command -v git >/dev/null 2>&1; then
  if git diff --quiet && git diff --cached --quiet; then
    git pull --rebase origin main || echo "git pull skipped or failed; continuing with local copy."
  else
    echo "Local changes exist; skip git pull to avoid overwriting work."
  fi
fi

"$PYTHON_BIN" auto_update_intel.py --dashboard index.html || echo "Web search process failed; keeping existing candidates and continuing with WeChat refresh."
WECHAT_SKILL="$ROOT_DIR/skills/wechat-article-scraper/scripts/scrape-wechat.js"
if [[ -f "$WECHAT_SKILL" && -n "$NODE_BIN" ]]; then
  "$NODE_BIN" "$WECHAT_SKILL" --from-dashboard --dashboard index.html --limit "${WECHAT_LIMIT:-8}" || echo "Some WeChat full-text fetches failed; keeping successful candidates."
else
  echo "Project WeChat Skill is missing; skipping WeChat refresh."
fi

if git diff --quiet -- index.html; then
  echo "No dashboard changes to commit."
else
  git config user.name "local-intel-bot"
  git config user.email "local-intel-bot@example.local"
  git add index.html
  git commit -m "chore: local daily intel update"
  git push origin main
fi

echo "===== $(date '+%Y-%m-%d %H:%M:%S') local daily update end ====="

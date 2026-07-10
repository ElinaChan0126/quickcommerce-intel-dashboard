#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$ROOT_DIR/logs"
LOG_FILE="$LOG_DIR/local-daily-update.log"
NODE_BIN="/Users/yilin.chenyl/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node"
PYTHON_BIN="${PYTHON_BIN:-/usr/bin/python3}"
XHS_BIN="${XHS_BIN:-$HOME/.local/bin/xhs}"

mkdir -p "$LOG_DIR"
exec >>"$LOG_FILE" 2>&1

echo ""
echo "===== $(date '+%Y-%m-%d %H:%M:%S') local daily update start ====="
cd "$ROOT_DIR"

if [[ ! -x "$NODE_BIN" ]]; then
  if command -v node >/dev/null 2>&1; then
    NODE_BIN="$(command -v node)"
  else
    echo "Node.js not found."
    exit 1
  fi
fi

if command -v git >/dev/null 2>&1; then
  if git diff --quiet && git diff --cached --quiet; then
    git pull --rebase origin main || echo "git pull skipped or failed; continuing with local copy."
  else
    echo "Local changes exist; skip git pull to avoid overwriting work."
  fi
fi

"$PYTHON_BIN" auto_update_intel.py --dashboard index.html
if [[ -x "$XHS_BIN" ]]; then
  "$PYTHON_BIN" scripts/scrape-xiaohongshu.py --dashboard index.html || echo "XHS collection failed; keeping web candidates."
else
  echo "xhs CLI not found at $XHS_BIN; skipping Xiaohongshu collection."
fi
"$NODE_BIN" scripts/scrape-wechat-chrome.cjs --from-dashboard --dashboard index.html --limit "${WECHAT_LIMIT:-8}" || echo "Some WeChat full-text fetches failed; keeping successful candidates."

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

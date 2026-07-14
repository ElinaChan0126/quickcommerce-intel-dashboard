#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$ROOT_DIR/logs"
LOG_FILE="$LOG_DIR/local-daily-update.log"
PYTHON_BIN="${PYTHON_BIN:-/usr/bin/python3}"

mkdir -p "$LOG_DIR"
exec >>"$LOG_FILE" 2>&1

echo ""
echo "===== $(date '+%Y-%m-%d %H:%M:%S') local daily update start ====="
cd "$ROOT_DIR"

if command -v git >/dev/null 2>&1; then
  if git diff --quiet && git diff --cached --quiet; then
    git pull --rebase origin main || echo "git pull skipped or failed; continuing with local copy."
  else
    echo "Local changes exist; skip git pull to avoid overwriting work."
  fi
fi

"$PYTHON_BIN" auto_update_intel.py --dashboard index.html || echo "Web search failed; keeping existing candidates and skipping browser-based WeChat refresh."
if [[ -n "${WECHAT_SKILL_DIR:-}" && -f "${WECHAT_SKILL_DIR}/SKILL.md" && -f "${WECHAT_SKILL_DIR}/scripts/scrape-wechat.js" ]]; then
  echo "WeChat Skill detected at ${WECHAT_SKILL_DIR}, but its adapter is not configured yet; skipping browser refresh."
else
  echo "WeChat Skill is not installed; skipping WeChat refresh. No Chrome or Sogou process will be started."
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

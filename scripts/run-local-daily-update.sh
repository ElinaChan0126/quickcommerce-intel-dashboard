#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$ROOT_DIR/logs"
LOG_FILE="$LOG_DIR/local-daily-update.log"
PYTHON_BIN="${PYTHON_BIN:-/usr/bin/python3}"
LOOKBACK_DAYS="${LOOKBACK_DAYS:-3}"

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

AUDIT_MARKER="$LOG_DIR/monthly-backfill-$(date '+%G-%V').done"
if [[ "$(date '+%u')" == "1" && ! -f "$AUDIT_MARKER" ]]; then
  # The first run each Monday re-checks the current month. The marker also
  # makes this work when a sleeping Mac resumes after 09:45.
  AUDIT_MONTH="$(date '+%Y-%m')"
  echo "Running weekly monthly backfill for $AUDIT_MONTH"
  if "$PYTHON_BIN" auto_update_intel.py --dashboard index.html --month "$AUDIT_MONTH" --lookback-days "$LOOKBACK_DAYS"; then
    touch "$AUDIT_MARKER"
  else
    echo "Monthly backfill failed; keeping existing candidates."
  fi
else
  "$PYTHON_BIN" auto_update_intel.py --dashboard index.html --lookback-days "$LOOKBACK_DAYS" || echo "Web search process failed; keeping existing candidates."
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

#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$ROOT_DIR/logs"
LOG_FILE="$LOG_DIR/intel-publisher.log"

mkdir -p "$LOG_DIR"
exec >>"$LOG_FILE" 2>&1

echo ""
echo "===== $(date '+%Y-%m-%d %H:%M:%S') intel publisher start ====="
cd "$ROOT_DIR"

# Do not publish over local work or a remote branch that changed independently.
if [[ -n "$(git status --porcelain)" ]]; then
  echo "Working tree is not clean; skip publishing."
  exit 0
fi

if ! git fetch origin main; then
  echo "Unable to fetch origin/main; retry at the next scheduled run."
  exit 0
fi

read -r remote_ahead local_ahead < <(git rev-list --left-right --count origin/main...HEAD)
if [[ "$remote_ahead" != "0" ]]; then
  echo "origin/main has commits not present locally; skip publishing to avoid a non-fast-forward push."
  exit 0
fi

if [[ "$local_ahead" == "0" ]]; then
  echo "No unpublished commits."
  exit 0
fi

# This helper is deliberately narrow: only Codex-generated intel commits are
# eligible. Ordinary commits remain under the user's normal GitHub workflow.
if git log --format='%s' origin/main..HEAD | grep -qv '^intel: '; then
  echo "Pending commits include non-intel work; skip publishing."
  exit 0
fi

for attempt in 1 2 3; do
  if git push origin HEAD:main; then
    echo "Published $local_ahead pending intel commit(s)."
    exit 0
  fi
  echo "Push attempt $attempt failed; retrying shortly."
  sleep "$((attempt * 10))"
done

echo "Publishing failed after three attempts; committed intel remains local."
exit 1

#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
URL="${1:-}"

if [[ -z "$URL" ]]; then
  echo "Usage: scripts/run-wechat-scrape.sh https://mp.weixin.qq.com/s/xxxx"
  exit 1
fi

if command -v node >/dev/null 2>&1; then
  NODE_BIN="$(command -v node)"
else
  NODE_BIN="/Users/yilin.chenyl/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node"
fi

if [[ ! -x "$NODE_BIN" ]]; then
  echo "Node.js not found. Please install Node.js or run this from Codex's prepared environment."
  exit 1
fi

cd "$ROOT_DIR"
"$NODE_BIN" scripts/scrape-wechat-chrome.cjs --url "$URL"

#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NODE_BIN="${NODE_BIN:-/Users/yilin.chenyl/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node}"
RUNTIME_PACKAGE="$ROOT_DIR/tools/playwright-runtime/node_modules/playwright"

if [[ ! -x "$NODE_BIN" ]]; then
  NODE_BIN="$(command -v node 2>/dev/null || true)"
fi
if [[ -z "$NODE_BIN" || ! -f "$RUNTIME_PACKAGE/package.json" ]]; then
  exit 1
fi

CHROMIUM_PATH="$("$NODE_BIN" -e 'const { chromium } = require(process.argv[1]); process.stdout.write(chromium.executablePath())' "$RUNTIME_PACKAGE" 2>/dev/null || true)"
if [[ -n "$CHROMIUM_PATH" && -x "$CHROMIUM_PATH" ]]; then
  printf '%s\n' "$CHROMIUM_PATH"
  exit 0
fi
exit 1

#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NODE_BIN="${NODE_BIN:-/Users/yilin.chenyl/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node}"
NPM_BIN="${NPM_BIN:-$(dirname "$NODE_BIN")/npm}"
PNPM_BIN="${PNPM_BIN:-/Users/yilin.chenyl/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/fallback/pnpm}"
RUNTIME_DIR="$ROOT_DIR/tools/playwright-runtime"

if [[ ! -x "$NODE_BIN" ]]; then
  NODE_BIN="$(command -v node 2>/dev/null || true)"
fi
if [[ ! -x "$NPM_BIN" ]]; then
  NPM_BIN="$(command -v npm 2>/dev/null || true)"
fi
if [[ ! -x "$PNPM_BIN" ]]; then
  PNPM_BIN="$(command -v pnpm 2>/dev/null || true)"
fi
if [[ -z "$NODE_BIN" ]]; then
  echo "找不到 Node.js：$NODE_BIN" >&2
  exit 1
fi
if [[ -z "$NPM_BIN" && -z "$PNPM_BIN" ]]; then
  echo "找不到 npm 或 pnpm，无法安装 Playwright。" >&2
  exit 1
fi

mkdir -p "$RUNTIME_DIR"
if [[ ! -f "$RUNTIME_DIR/package.json" ]]; then
  printf '%s\n' '{"name":"wechat-playwright-runtime","private":true,"version":"1.0.0"}' > "$RUNTIME_DIR/package.json"
fi

if [[ -n "$NPM_BIN" ]]; then
  "$NPM_BIN" --prefix "$RUNTIME_DIR" install --no-fund --no-audit playwright
else
  "$PNPM_BIN" --dir "$RUNTIME_DIR" add --ignore-workspace playwright
fi

"$NODE_BIN" "$RUNTIME_DIR/node_modules/playwright/cli.js" install chromium
CHROMIUM_PATH="$("$ROOT_DIR/scripts/resolve-wechat-chromium.sh")"
echo "独立 Chromium 已安装：$CHROMIUM_PATH"
echo "公众号抓取将优先使用该 Chromium，不再依赖日常 Google Chrome。"

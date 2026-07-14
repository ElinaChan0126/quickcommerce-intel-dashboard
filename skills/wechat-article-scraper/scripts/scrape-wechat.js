#!/usr/bin/env node

import path from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

const here = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(here, "../../..");
const scraper = path.join(repoRoot, "scripts", "scrape-wechat-chrome.cjs");
const result = spawnSync(process.execPath, [scraper, ...process.argv.slice(2)], {
  cwd: repoRoot,
  env: {
    ...process.env,
    WECHAT_HEADLESS: process.env.WECHAT_HEADLESS || "1",
  },
  stdio: "inherit",
});

if (result.error) {
  console.error(result.error.message);
  process.exit(1);
}
process.exit(result.status ?? 1);

#!/usr/bin/env node

const fs = require("fs");
const http = require("http");
const path = require("path");
const { spawn } = require("child_process");

const DEFAULT_CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";

function argValue(name, fallback = "") {
  const index = process.argv.indexOf(name);
  if (index >= 0 && process.argv[index + 1]) return process.argv[index + 1];
  return fallback;
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function requestJson(url, method = "GET") {
  return new Promise((resolve, reject) => {
    const req = http.request(url, { method }, res => {
      let body = "";
      res.setEncoding("utf8");
      res.on("data", chunk => body += chunk);
      res.on("end", () => {
        try {
          resolve(JSON.parse(body));
        } catch (error) {
          reject(new Error(`Invalid JSON from ${url}: ${body.slice(0, 120)}`));
        }
      });
    });
    req.on("error", reject);
    req.end();
  });
}

async function waitForDebugger(port, timeoutMs = 12000) {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    try {
      return await requestJson(`http://127.0.0.1:${port}/json/version`);
    } catch {
      await sleep(250);
    }
  }
  throw new Error("Chrome remote debugging port did not become ready.");
}

function connectWebSocket(url) {
  return new Promise((resolve, reject) => {
    const socket = new WebSocket(url);
    socket.addEventListener("open", () => resolve(socket), { once: true });
    socket.addEventListener("error", event => reject(event.error || new Error("WebSocket error")), { once: true });
  });
}

function createCdpClient(socket) {
  let id = 0;
  const pending = new Map();
  socket.addEventListener("message", event => {
    const message = JSON.parse(event.data);
    if (!message.id || !pending.has(message.id)) return;
    const { resolve, reject } = pending.get(message.id);
    pending.delete(message.id);
    if (message.error) reject(new Error(message.error.message || JSON.stringify(message.error)));
    else resolve(message.result || {});
  });
  return {
    send(method, params = {}) {
      const nextId = ++id;
      socket.send(JSON.stringify({ id: nextId, method, params }));
      return new Promise((resolve, reject) => pending.set(nextId, { resolve, reject }));
    },
    close() {
      socket.close();
    },
  };
}

function sanitizeName(value) {
  return String(value || "wechat-article")
    .replace(/[\\/:*?"<>|#%&{}$!'@+`=]/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 48) || "wechat-article";
}

function markdownEscape(value) {
  return String(value || "").replace(/\r/g, "");
}

function toMarkdown(article) {
  const lines = [
    `# ${markdownEscape(article.title || "未命名公众号文章")}`,
    "",
    `- 公众号：${markdownEscape(article.account || "未识别")}`,
    `- 作者：${markdownEscape(article.author || "未识别")}`,
    `- 发布时间：${markdownEscape(article.publishTime || "未识别")}`,
    `- 链接：${markdownEscape(article.url)}`,
    "",
    markdownEscape(article.text || ""),
    "",
  ];
  return lines.join("\n");
}

async function main() {
  const url = argValue("--url", process.argv[2] || "");
  const outDir = argValue("--out", "wechat-articles");
  const chromePath = process.env.PUPPETEER_EXECUTABLE_PATH || argValue("--chrome", DEFAULT_CHROME);
  const port = Number(argValue("--port", "9227"));
  if (!url || !url.includes("mp.weixin.qq.com")) {
    throw new Error("Usage: node scripts/scrape-wechat-chrome.cjs --url https://mp.weixin.qq.com/s/...");
  }
  if (!fs.existsSync(chromePath)) {
    throw new Error(`Chrome not found: ${chromePath}`);
  }
  fs.mkdirSync(outDir, { recursive: true });
  const userDataDir = path.join("/private/tmp", `wechat-chrome-${Date.now()}`);
  const chrome = spawn(chromePath, [
    `--remote-debugging-port=${port}`,
    `--user-data-dir=${userDataDir}`,
    "--no-first-run",
    "--disable-popup-blocking",
    "--disable-background-networking",
    "--disable-breakpad",
    "--disable-crash-reporter",
    "--disable-crashpad",
    "--disable-sync",
    "--window-size=1280,1600",
    "about:blank",
  ], { stdio: ["ignore", "ignore", "pipe"] });
  let stderr = "";
  chrome.stderr.on("data", chunk => stderr += chunk.toString());
  try {
    await waitForDebugger(port);
    const target = await requestJson(`http://127.0.0.1:${port}/json/new?${encodeURIComponent(url)}`, "PUT");
    const socket = await connectWebSocket(target.webSocketDebuggerUrl);
    const cdp = createCdpClient(socket);
    await cdp.send("Page.enable");
    await cdp.send("Runtime.enable");
    await sleep(6500);
    const result = await cdp.send("Runtime.evaluate", {
      returnByValue: true,
      awaitPromise: true,
      expression: `(() => {
        const text = selector => document.querySelector(selector)?.textContent?.trim().replace(/\\s+/g, " ") || "";
        const attr = (selector, name) => document.querySelector(selector)?.getAttribute(name) || "";
        const content = document.querySelector("#js_content");
        const links = [...(content?.querySelectorAll("a[href]") || [])].map(a => ({ text: a.textContent.trim(), href: a.href })).filter(x => x.href);
        const images = [...(content?.querySelectorAll("img") || [])].map(img => img.dataset.src || img.src).filter(Boolean);
        return {
          url: location.href,
          title: text("#activity-name") || document.title,
          account: text("#js_name"),
          author: text("#js_author_name"),
          publishTime: text("#publish_time"),
          digest: attr('meta[property="og:description"]', "content") || attr('meta[name="description"]', "content"),
          text: content?.innerText?.trim() || "",
          html: content?.innerHTML || "",
          images,
          links,
          blockedText: document.body.innerText.slice(0, 300),
        };
      })()`,
    });
    cdp.close();
    const article = result.result.value;
    const ok = article.title && article.text && article.text.length > 30 && !/环境异常|访问过于频繁|请在微信客户端打开|验证码/.test(article.blockedText || "");
    article.ok = Boolean(ok);
    article.fetchedAt = new Date().toISOString();
    const base = `${new Date().toISOString().slice(0, 10)}_${sanitizeName(article.title)}`;
    const jsonPath = path.join(outDir, `${base}.json`);
    const markdownPath = path.join(outDir, `${base}.md`);
    fs.writeFileSync(jsonPath, JSON.stringify(article, null, 2), "utf8");
    fs.writeFileSync(markdownPath, toMarkdown(article), "utf8");
    console.log(JSON.stringify({ ok: article.ok, title: article.title, account: article.account, jsonPath, markdownPath }, null, 2));
    if (!article.ok) process.exitCode = 2;
  } finally {
    chrome.kill("SIGTERM");
    await sleep(300);
    if (!chrome.killed) chrome.kill("SIGKILL");
    if (stderr && process.env.DEBUG_WECHAT_CHROME) console.error(stderr);
  }
}

main().catch(error => {
  console.error(error.message);
  process.exit(1);
});

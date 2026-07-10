#!/usr/bin/env node

const fs = require("fs");
const http = require("http");
const path = require("path");
const crypto = require("crypto");
const { spawn } = require("child_process");

const DEFAULT_CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";

function argValue(name, fallback = "") {
  const index = process.argv.indexOf(name);
  if (index >= 0 && process.argv[index + 1]) return process.argv[index + 1];
  return fallback;
}

function hasFlag(name) {
  return process.argv.includes(name);
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

function localDateISO() {
  const formatter = new Intl.DateTimeFormat("sv-SE", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
  return formatter.format(new Date());
}

function normalizeDate(value) {
  const text = String(value || "");
  const match = text.match(/20\d{2}[-/.年]\d{1,2}[-/.月]\d{1,2}/);
  if (!match) return localDateISO();
  const parts = match[0].match(/\d+/g).map(Number);
  if (parts.length < 3) return localDateISO();
  return `${parts[0]}-${String(parts[1]).padStart(2, "0")}-${String(parts[2]).padStart(2, "0")}`;
}

function compactText(value) {
  return String(value || "")
    .replace(/\r/g, "\n")
    .replace(/[ \t]+/g, " ")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function candidateHash(...parts) {
  return crypto.createHash("sha1").update(parts.filter(Boolean).join("|")).digest("hex").slice(0, 12);
}

function platformFromText(text) {
  const rules = [
    ["淘宝闪购", ["淘宝闪购", "淘宝买菜", "饿了么"]],
    ["京东秒送", ["京东秒送", "京东外卖", "京东到家", "达达"]],
    ["美团闪购", ["美团闪购", "美团外卖", "美团跑腿", "美团"]],
    ["顺丰同城", ["顺丰同城", "顺丰", "丰巢"]],
    ["闪送", ["闪送"]],
    ["UU跑腿", ["UU跑腿"]],
    ["盒马", ["盒马"]],
  ];
  return rules.find(([, words]) => words.some(word => text.includes(word)))?.[0] || "待识别平台";
}

function categoryFromText(text) {
  const rules = [
    ["AI入口", ["AI", "智能体", "Agent", "助手", "阿宝", "自然语言", "语音", "Skill"]],
    ["活动营销", ["活动", "补贴", "优惠", "满减", "红包", "大促", "会场", "低至", "618"]],
    ["供给履约", ["前置仓", "便利店", "商超", "供给", "履约", "配送", "运力", "时效", "即时配送"]],
    ["平台治理", ["规则", "治理", "权益", "免罚", "超时", "处罚", "安全"]],
    ["商家工具", ["商家", "商户", "经营", "服务商", "代运营", "店铺", "培训", "课堂"]],
  ];
  return rules.find(([, words]) => words.some(word => text.includes(word)))?.[0] || "待归类";
}

function businessTagsFromText(text) {
  const tags = [];
  const hasAny = words => words.some(word => text.includes(word));
  if (hasAny(["用户", "消费者", "买家", "下单", "点餐", "代买", "跑腿单", "小程序", "支付宝", "阿宝", "入口", "体验"])) tags.push("Buyer");
  if (hasAny(["活动", "补贴", "优惠", "满减", "红包", "大促", "会场", "营销"])) tags.push("Promo");
  if (hasAny(["商家", "商户", "门店", "经营", "服务商", "培训", "课堂", "前置仓", "便利店", "供给"])) tags.push("Merchant");
  if (hasAny(["骑手", "骑士", "众包", "配送员", "运力", "超时", "免罚", "接单"])) tags.push("Driver");
  if (hasAny(["搜索", "推荐", "广告", "投放", "排序", "召回", "流量分发", "个性化"])) tags.push("S&R");
  return tags.length ? tags : ["Buyer"];
}

function typeFromText(text, category) {
  if (category === "AI入口") return "AI 对话入口";
  if (category === "活动营销") return "活动营销";
  if (category === "平台治理") return "规则/权益";
  if (category === "供给履约") return "供给履约";
  if (category === "商家工具") return "商家工具";
  return "公众号解析";
}

function scoreFromText(text, tags, sourceName) {
  let score = 58;
  if (tags.includes("Buyer")) score += 18;
  if (["上线", "发布", "接入", "启动", "升级", "开启", "新增"].some(word => text.includes(word))) score += 10;
  if (["AI", "下单", "跑腿", "闪购", "秒送", "即时配送"].some(word => text.includes(word))) score += 8;
  if (sourceName && sourceName !== "公众号") score += 5;
  return Math.max(1, Math.min(99, score));
}

function sentenceList(text) {
  return compactText(text)
    .split(/(?<=[。！？!?；;])|\n+/)
    .map(sentence => sentence.trim())
    .filter(sentence => sentence.length >= 12 && !["点击", "阅读原文", "微信扫一扫", "分享", "点赞", "在看"].some(word => sentence.includes(word)));
}

function splitArticleEvents(article) {
  const whole = `${article.title || ""}。${article.digest || ""}。${article.text || ""}`;
  const relevantWords = ["闪购", "即时零售", "跑腿", "秒送", "同城", "外卖", "骑手", "骑士", "配送", "下单", "AI"];
  const actionWords = ["上线", "发布", "接入", "启动", "开启", "升级", "活动", "补贴", "规则", "治理", "权益", "新增"];
  const signatureWords = ["美团", "淘宝", "饿了么", "京东", "达达", "顺丰", "闪送", "UU跑腿", "支付宝", "阿宝", "AI", "接入", "上线", "发布", "升级", "启动", "跑腿", "下单", "代买", "点餐", "闪购", "秒送", "外卖", "即时零售", "骑手", "商家", "活动", "补贴", "规则"];
  const events = [];
  const seen = new Set();
  const seenSignatures = [];
  for (const sentence of sentenceList(whole)) {
    if (!relevantWords.some(word => sentence.includes(word))) continue;
    if (!actionWords.some(word => sentence.includes(word))) continue;
    const normalized = sentence.replace(/[^\u4e00-\u9fa5a-zA-Z0-9]/g, "");
    const key = normalized.slice(0, 48);
    const signature = signatureWords.filter(word => sentence.includes(word));
    const isDuplicate = [...seen].some(existing =>
      existing.includes(normalized.slice(0, 24)) || normalized.includes(existing.slice(0, 24))
    ) || seenSignatures.some(existing => {
      const common = signature.filter(word => existing.includes(word)).length;
      return common >= 3 && common / Math.min(existing.length, signature.length || 1) >= 0.75;
    });
    if (!key || seen.has(key) || isDuplicate) continue;
    seen.add(normalized);
    if (signature.length) seenSignatures.push(signature);
    events.push({
      title: sentence.length <= 72 ? sentence : `${sentence.slice(0, 69)}...`,
      summary: sentence.length <= 220 ? sentence : `${sentence.slice(0, 217)}...`,
    });
    if (events.length >= 5) break;
  }
  if (events.length) return events;
  const fallbackSummary = article.digest || sentenceList(article.text || "").slice(0, 2).join("") || "公众号正文已读取，请复核是否为有效情报。";
  return [{
    title: article.title || "未命名公众号文章",
    summary: fallbackSummary.slice(0, 220),
  }];
}

function articleToCandidates(article) {
  const sourceName = article.account || "公众号";
  const date = normalizeDate(article.publishTime);
  return splitArticleEvents(article).map((event, index) => {
    const text = `${sourceName} ${article.title || ""} ${event.title} ${event.summary} ${article.text || ""}`;
    const category = categoryFromText(text);
    const tags = businessTagsFromText(text);
    const score = scoreFromText(text, tags, sourceName);
    const id = `wechat-${candidateHash(article.url, event.title, String(index))}`;
    return {
      id,
      date,
      platform: platformFromText(text),
      title: event.title,
      type: typeFromText(text, category),
      category,
      businessTag: tags[0] || "",
      businessTags: tags,
      summary: event.summary,
      judge: tags.includes("Buyer")
        ? "本地 Chrome 已读取公众号正文，候选与买家入口、下单或履约体验相关，建议复核功能形态、上线范围和业务影响。"
        : "本地 Chrome 已读取公众号正文，建议复核是否会间接影响买家侧体验。",
      sourceName,
      sourceUrl: article.url,
      sources: [{ name: sourceName, url: article.url }],
      sourceKind: "公众号",
      contentStatus: "本地已读全文",
      needsFullText: false,
      fullTextStatus: "已补全文",
      fullText: article.text || "",
      score,
      buyerRelevance: tags.includes("Buyer") ? 30 : 8,
      relevanceReason: tags.includes("Buyer") ? "公众号正文命中买家入口/下单链路" : "公众号正文已读取，需人工判断买家侧影响",
      importedAt: new Date().toISOString(),
    };
  });
}

function injectCandidatesIntoDashboard(dashboardPath, newCandidates) {
  const original = fs.readFileSync(dashboardPath, "utf8");
  const candidatesMatch = original.match(/const generatedCandidates = ([\s\S]*?);\n\s*const generatedMeta = /);
  const metaMatch = original.match(/const generatedMeta = ([\s\S]*?);\n\s*\/\/ AUTO_CANDIDATES_END/);
  if (!candidatesMatch || !metaMatch) {
    throw new Error(`Could not find AUTO_CANDIDATES block in ${dashboardPath}`);
  }
  const currentCandidates = JSON.parse(candidatesMatch[1]);
  const currentMeta = JSON.parse(metaMatch[1]);
  const byId = new Map(currentCandidates.map(item => [item.id, item]));
  for (const candidate of newCandidates) byId.set(candidate.id, candidate);
  const merged = [...byId.values()].sort((a, b) => String(b.date || "").localeCompare(String(a.date || "")));
  const nextMeta = {
    ...currentMeta,
    updatedAt: new Intl.DateTimeFormat("sv-SE", {
      timeZone: "Asia/Shanghai",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    }).format(new Date()),
    candidateCount: merged.length,
    status: "completed",
  };
  const block = [
    "    // AUTO_CANDIDATES_START",
    `    const generatedCandidates = ${JSON.stringify(merged, null, 6)};`,
    `    const generatedMeta = ${JSON.stringify(nextMeta)};`,
    "    // AUTO_CANDIDATES_END",
  ].join("\n");
  const next = original.replace(/    \/\/ AUTO_CANDIDATES_START\n[\s\S]*?    \/\/ AUTO_CANDIDATES_END/, block);
  fs.writeFileSync(dashboardPath, next, "utf8");
  return { total: merged.length, inserted: newCandidates.length };
}

async function main() {
  const url = argValue("--url", process.argv[2] || "");
  const outDir = argValue("--out", "wechat-articles");
  const dashboardPath = path.resolve(argValue("--dashboard", "index.html"));
  const chromePath = process.env.PUPPETEER_EXECUTABLE_PATH || argValue("--chrome", DEFAULT_CHROME);
  const port = Number(argValue("--port", "9227"));
  const shouldSaveFiles = hasFlag("--save-files");
  const shouldInject = !hasFlag("--no-inject");
  if (!url || !url.includes("mp.weixin.qq.com")) {
    throw new Error("Usage: node scripts/scrape-wechat-chrome.cjs --url https://mp.weixin.qq.com/s/...");
  }
  if (!fs.existsSync(chromePath)) {
    throw new Error(`Chrome not found: ${chromePath}`);
  }
  if (shouldSaveFiles) fs.mkdirSync(outDir, { recursive: true });
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
    const candidates = article.ok ? articleToCandidates(article) : [];
    let injected = null;
    if (article.ok && shouldInject) {
      injected = injectCandidatesIntoDashboard(dashboardPath, candidates);
    }
    let saved = null;
    if (shouldSaveFiles) {
      const base = `${new Date().toISOString().slice(0, 10)}_${sanitizeName(article.title)}`;
      const jsonPath = path.join(outDir, `${base}.json`);
      const markdownPath = path.join(outDir, `${base}.md`);
      fs.writeFileSync(jsonPath, JSON.stringify(article, null, 2), "utf8");
      fs.writeFileSync(markdownPath, toMarkdown(article), "utf8");
      saved = { jsonPath, markdownPath };
    }
    console.log(JSON.stringify({
      ok: article.ok,
      title: article.title,
      account: article.account,
      candidateCount: candidates.length,
      injected,
      saved,
      dashboardPath: shouldInject ? dashboardPath : null,
    }, null, 2));
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

# 即时配送竞品情报看板

这是一个用于跟踪闪购、即时零售、同城跑腿、即时配送平台动态的情报看板。

## 页面

- `index.html`：公开访问的网站首页。
- `auto_update_intel.py`：每日抓取候选线索，并写入页面的自动候选池。
- `.github/workflows/daily-update.yml`：每天 09:30（北京时间）自动运行抓取脚本。

## 使用方式

1. 在 GitHub 仓库中开启 Pages。
2. 选择从 `main` 分支的根目录发布。
3. 页面发布后，访问 GitHub Pages 给出的公开网址。

## 日常维护

- 页面 UI 优化：修改 `index.html`。
- 抓取范围优化：修改 `auto_update_intel.py` 里的平台词、关键词、`DATA_SOURCES` 数据源池。
- 自动更新时间调整：修改 `.github/workflows/daily-update.yml` 的 `cron` 配置。
- 本地抓取单篇公众号：在 macOS 终端运行 `scripts/run-wechat-scrape.sh <公众号文章链接>`。脚本会调用本机 Google Chrome，输出 JSON 和 Markdown 到 `wechat-articles/`。

自动抓取只进入“候选池”，仍建议由产品经理人工确认后再入库。

## 公众号抓取说明

公众号文章抓取分两层：

- GitHub Actions 自动抓取：使用 Bing、360 和搜狗微信公开搜索发现公众号文章标题、链接和摘要；对能直接访问的 `mp.weixin.qq.com` 链接尝试提取元信息。
- 本地 Chrome 抓取：`scripts/scrape-wechat-chrome.cjs` 会启动你电脑上的 Google Chrome，等待页面渲染后读取 `#js_content`。这更接近人工打开微信文章，成功率通常高于云端请求，但仍可能遇到微信访问限制。

示例：

```bash
cd /Users/yilin.chenyl/Documents/Codex/2026-07-07/wo/github-site
scripts/run-wechat-scrape.sh https://mp.weixin.qq.com/s/xxxx
```

如果 Chrome 不在默认位置，可以指定：

```bash
PUPPETEER_EXECUTABLE_PATH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" scripts/run-wechat-scrape.sh https://mp.weixin.qq.com/s/xxxx
```

如果在 Codex 内运行时报 `Chrome remote debugging port did not become ready`，通常是桌面沙箱拦截了 Chrome 的本地权限。可以打开 macOS 自带“终端”，进入仓库目录后运行同一条命令。

## 候选去重与合并

自动更新脚本会先把搜索结果拆成事件级候选，再按平台、类型和事件关键词生成指纹。同一事件被多个网站报道时，会合并成一条候选，并在 `sources` 中保留多个可点击来源。

如果一篇文章里同时包含多个动作，例如“平台规则更新；某跑腿平台上线 AI 下单”，脚本会按分号、句号和标题分隔符尝试拆成多条事件候选，避免把不同事件混成一条。

## 业务标签

情报会自动打上一个或多个业务标签，便于按产品域筛选：

- `Buyer`：主要发生在用户端的入口、下单体验、AI 助手、小程序、消费体验。例如“顺丰接入支付宝 AI，用户可在阿宝里下跑腿单”应归为 Buyer。
- `Promo`：活动、补贴、套餐、大促、赛事/季节营销。
- `Merchant`：商家端、经营工具、服务商、培训、闪电仓、前置仓。
- `Driver`：明确影响骑手/骑士/众包 App、运力管理、骑手权益或处罚规则的动作。仅出现“配送/履约”不自动归为 Driver。
- `S&R`：Search & Recommendation，搜索/推荐相关能力，例如搜索结果、搜索框/搜索词、推荐位、排序召回、个性化推荐、广告投放和流量分发。普通文案里提到“从搜索入口迁移到 AI 入口”不算 S&R。

自动候选由 `auto_update_intel.py` 的 `BUSINESS_TAG_RULES` 识别；跨端功能会保留多个标签。手动录入时可以在页面上多选业务标签。

## 数据源池

当前脚本已覆盖 116 个来源入口，分为：

- 网页来源：36氪、虎嗅、亿邦动力、美团新闻中心、美团商家外卖课堂、淘宝闪购商家培训等。
- 行业公众号：晚点 LatePost、36氪未来消费、创新零售社、DT商业观察、张大爷聊外卖、陈罡Pro、海豚投研、即时刘说等。
- 平台官方公众号：美团研究院、美团 Meituan、美团外卖、京东黑板报、淘宝闪购设计、淘宝闪购技术、京东外卖、京东秒送等。
- 商家端公众号：美团外卖商家中心、美团闪购商家中心、美团餐饮观察、淘宝闪购商家课堂、京东外卖商家中心等。
- 骑手与即时配送：美团骑手、达达秒送骑士、淘宝闪购城市骑士、美团闪电仓、美团众包骑手 APP、蜂鸟众包 APP。
- 报告与平台搜索：华泰、中金、中信、广发等券商报告，小红书关键词搜索，新浪新闻、百度资讯、Google Alert。

在 `DATA_SOURCES` 中新增网页来源时，建议补齐 `name`、`domain`、`focus` 和 `weight`。公众号、APP、研报和平台搜索入口分别维护在 `WECHAT_ACCOUNTS`、`PLATFORM_SEARCH_TERMS`、`REPORT_SOURCES` 和 `NEWS_SEARCH_CHANNELS`。`weight` 和账号命中会影响候选相关度评分，越高越容易排在前面。

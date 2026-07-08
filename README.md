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
- 抓取范围优化：修改 `auto_update_intel.py` 里的平台词、关键词、来源站点。
- 自动更新时间调整：修改 `.github/workflows/daily-update.yml` 的 `cron` 配置。

自动抓取只进入“候选池”，仍建议由产品经理人工确认后再入库。

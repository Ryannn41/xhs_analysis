# xhs_analysis

基于 FastAPI + Playwright + React 的小红书账号分析工具。

## 功能概览

- 使用 Playwright 保存并复用小红书浏览器登录态。
- 支持输入昵称、`user_id` 或小红书用户主页 URL 查询账号。
- 支持上传 Excel 批量查询账号，前端会展示读取预览和逐个账号的抓取进度。
- 支持按日期范围统计账号笔记数据，默认统计最近 30 天。
- 支持缓存查询结果；需要最新数据时可勾选“跳过缓存”实时抓取。
- 支持将成功查询的结果下载为 Excel，包含账号汇总和笔记明细两个工作表。

## 目录结构

```text
xhs_analysis/
├── backend/
│   ├── app.py
│   ├── config.py
│   ├── save_xhs_state.py
│   ├── requirements.txt
│   ├── services/
│   │   ├── xhs_browser.py
│   │   ├── xhs_scraper.py
│   │   ├── xhs_session.py
│   │   ├── account_resolver.py
│   │   └── cache.py
│   ├── data/
│   │   ├── accounts.json
│   │   └── cache/
│   └── storage/
│       └── xhs_state.json
└── frontend/
    ├── package.json
    └── src/
```

`backend/storage/xhs_state.json` 是 Playwright 登录态文件，已经被 `.gitignore` 忽略。

## 启动后端

```bash
python -m venv backend/.venv
source backend/.venv/bin/activate
pip install -r backend/requirements.txt
playwright install chromium
uvicorn backend.app:app --reload --host 0.0.0.0 --port 8000
```

如果抓取小红书页面出现 `Page.goto: net::ERR_TIMED_OUT`，建议本地开发时在 `.env` 中使用可视化浏览器并延长超时：

```env
BROWSER_HEADLESS=false
BROWSER_TIMEOUT_MS=90000
```

## 准备登录态

后端默认读取 `backend/storage/xhs_state.json`。启动前端后，可以在页面顶部点击“重新登录”打开可视化浏览器，登录完成并确认小红书首页/个人入口已显示登录状态后，再点击“保存登录态”。

也可以用命令行脚本生成或刷新登录态：

```bash
python -m backend.save_xhs_state
```

浏览器打开后完成登录，确认页面已显示登录状态，再回到终端按回车保存。保存成功后，后端后续抓取会使用新的登录态。

登录态没有固定的项目内过期时间，实际可用时长由小红书下发的 Cookie 和服务端风控状态决定。若页面重新出现登录墙、验证或抓取失败，重新保存登录态即可。

## 启动前端

```bash
cd frontend
npm install
npm run dev
```

前端默认请求 `http://127.0.0.1:8000`。如需修改：

```bash
VITE_API_BASE_URL=http://127.0.0.1:8000 npm run dev
```

## 账号解析

前端可以输入：

- `backend/data/accounts.json` 里维护过的昵称
- 小红书 `user_id`
- 小红书用户主页 URL
- 包含 `name`、`id` 两列的 Excel 文件，用于批量查询账号

昵称不唯一，所以未维护在 `accounts.json` 的昵称不会自动搜索解析。

## Excel 上传

前端支持上传 `.xlsx` 或 `.xls` 文件进行批量查询。默认读取第一个工作表，表头需要包含：

- `name`：账号名称，可为空，主要用于展示和结果识别。
- `id`：必填，支持纯 `user_id` 或小红书用户主页 URL。

上传后页面会展示数据预览。若 Excel 为空、缺少可读取数据、没有有效账号，或某一行缺少 `id`，前端会直接提示错误并停止查询。

示例：

```text
name,id
示例账号,https://www.xiaohongshu.com/user/profile/xxxxxxxxxxxxxxxxxxxxxxxx
另一个账号,xxxxxxxxxxxxxxxxxxxxxxxx
```

## 查询与下载

查询区域可以选择开始日期、结束日期和是否“跳过缓存”。不勾选“跳过缓存”时，后端会优先读取 `backend/data/cache/` 中的缓存结果；缓存默认有效期由 `CACHE_TTL_SECONDS` 控制，当前默认值为 900 秒。

批量查询会按账号顺序逐个抓取，部分账号失败时，成功结果仍会展示在页面下方。只要存在成功结果，页面会出现“下载 Excel”按钮，导出的文件名形如 `小红书账号统计_YYYY-MM-DD.xlsx`，包含：

- `账号汇总`：账号名称、账号 ID、小红书号、主页链接、粉丝量、统计区间互动汇总、抓取时间和数据来源。
- `笔记明细`：每篇笔记的标题、发布时间、类型、链接、点赞、收藏、评论、转发和封面链接。

## 使用提醒

本工具会使用浏览器登录态访问账号主页和笔记详情页。短时间批量查询大量账号、频繁跳过缓存实时抓取，可能触发小红书登录验证、访问限制或数据读取失败。建议优先使用缓存，批量账号分批执行。

# 本地桌面软件方案记录

## 方向结论

本项目后续不再优先考虑阿里云公网部署，改为面向用户本机运行的本地桌面软件。

原因：

- 项目依赖 Playwright 操作真实浏览器，登录、扫码、风控和 Cookie 都更适合在用户本机完成。
- 云端部署会遇到 X server、扫码可视化、用户登录态隔离、共享服务器 IP 风控、图片防盗链和任务队列等复杂问题。
- 本地软件可以直接弹出 Playwright 浏览器，用户能看到登录/验证页面，登录态和导出文件也都保存在本机。

目标用户体验：

```text
用户双击软件
  -> 软件自动启动本地后端
  -> 打开桌面窗口或本地前端页面
  -> 用户点击“重新登录”
  -> Playwright 弹出本机 Chromium 浏览器
  -> 用户用小红书 App 扫码登录
  -> 点击“保存登录态”
  -> 查询账号、批量抓取、导出 Excel
```

## 当前项目形态

现有代码仍保持：

- 后端：`FastAPI + Playwright`
- 前端：`React + Vite`
- 登录态：`backend/storage/xhs_state.json`
- 导出：前端生成 Excel

本地软件方向下，现有业务逻辑不需要重写。主要工作是把“启动前端、启动后端、管理依赖、打包发布”做成用户可双击使用的桌面应用。

## 登录设计

采用本地可视化浏览器登录：

- 前端点击“重新登录”。
- 后端启动 `XhsLoginSession`。
- Playwright 以 `headless=False` 打开 Chromium。
- 用户在弹出的浏览器里扫码登录。
- 用户回到前端点击“保存登录态”。
- 后端保存 `storage_state`，后续抓取复用。

不再使用云端扫码截图方案：

- 不需要 `/api/xhs/session/login/screenshot`。
- 不需要前端展示登录截图。
- 不需要 Xvfb/noVNC。
- 不需要把二维码从云服务器传给前端。

## 抓取设计

抓取阶段仍由后端 Playwright 自动完成。

默认建议：

- 登录浏览器：可视化，方便用户扫码和处理验证。
- 抓取浏览器：可以继续由 `.env` 的 `BROWSER_HEADLESS` 控制。

如果希望用户看到抓取过程，可以设置：

```env
BROWSER_HEADLESS=false
```

如果希望抓取安静执行，可以设置：

```env
BROWSER_HEADLESS=true
```

## 推荐打包路线

推荐最终形态：

```text
Electron 桌面壳
  + React 前端构建产物 frontend/dist
  + PyInstaller/Nuitka 打包出来的 Python 后端可执行文件
  + Playwright Chromium 浏览器文件
  + 本地数据目录和登录态目录
```

开发阶段可以分两步走。

### 阶段 1：本地一键启动版

目标：先让开发者/内部用户可以一键启动。

可做内容：

- 编写启动脚本，同时启动 FastAPI 后端和 Vite 前端。
- 确认登录、抓取、导出 Excel 在本机稳定运行。
- README 补充 conda/venv 两种启动方式。

这一阶段用户可能仍需要本机环境，不作为正式分发版。

### 阶段 2：Electron 开发版

目标：用 Electron 打开应用窗口，并自动启动本地后端。

可做内容：

- 新增 Electron 主进程。
- Electron 启动时拉起本地后端。
- Electron 窗口加载前端页面。
- 关闭窗口时停止后端进程。

开发阶段可以先让 Electron 调用本机已有的 Python/uvicorn。

### 阶段 3：正式安装包

目标：普通用户无需安装 Node、Python、pip 依赖。

可做内容：

- 使用 PyInstaller 或 Nuitka 打包后端为 `backend.exe`。
- 将 Playwright Chromium 一起随包分发。
- Electron 调用打包后的后端可执行文件。
- 使用 electron-builder 生成 Windows 安装包。
- 数据目录、缓存目录、登录态文件放到用户本机应用数据目录。

最终用户只需要双击安装或打开软件。

## Windows 打包注意事项

如果目标用户是 Windows 用户，最终建议在 Windows 原生环境打包，而不是只在 WSL 里打包。

原因：

- WSL 里通常产出 Linux 可执行文件，不是 Windows `.exe`。
- Playwright 浏览器、PyInstaller 产物、Electron 安装包都和目标系统强相关。
- Windows 用户需要的是 Windows 原生安装包或 `.exe`。

推荐打包环境：

```text
Windows Node/Electron
Windows Python
Windows Playwright Chromium
PyInstaller 生成 backend.exe
electron-builder 生成安装包
```

WSL 可以继续用于日常开发和验证业务逻辑。

## 后续任务清单

- 确认当前本地浏览器登录流程稳定。
- 确认 `.env` 中 `BROWSER_HEADLESS` 对抓取浏览器生效。
- 整理本地运行 README，弱化云端部署说明。
- 增加本地一键启动脚本。
- 评估 Electron 与 Tauri，优先 Electron，因为生态成熟且适合包装现有 React 前端。
- 新增 Electron 主进程，自动启动/停止后端。
- 研究 PyInstaller 打包 FastAPI + Playwright 的方式。
- 确定用户数据目录，例如登录态、缓存和导出文件保存位置。
- 打包 Windows 测试版。

## 暂不处理的问题

这些问题在本地单用户软件阶段可以暂时不做：

- 多用户账号体系。
- 云端登录态隔离。
- 云端任务队列。
- 云端图片代理。
- 公网 CORS/域名/Nginx 部署。
- 服务器 X server 或 noVNC。

## 当前决策

短期目标是把项目稳定成“本地可运行工具”。

中期目标是包装成“用户双击可用的 Windows 桌面软件”。

云端部署路线暂停。

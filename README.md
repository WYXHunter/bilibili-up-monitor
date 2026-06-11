# B站 UP主 动态监控

[![Release](https://img.shields.io/github/v/release/WYXHunter/bilibili-up-monitor)](https://github.com/WYXHunter/bilibili-up-monitor/releases)
[![License](https://img.shields.io/github/license/WYXHunter/bilibili-up-monitor)](LICENSE)

监控 Bilibili UP 主动态更新，通过钉钉机器人实时推送通知。提供 Web 管理面板，打包为单个 EXE 开箱即用。

## ✨ 功能

- 🔍 通过 UID 添加 B站 UP主，自动获取昵称和头像
- ⏱️ 定时轮询检查（可配置 1-30 分钟间隔）
- 🔔 钉钉群机器人推送，支持加签安全模式（HMAC-SHA256）
- 🌐 Web 管理面板，查看动态时间线、统计数据
- 🖼️ 支持图文、视频、专栏、直播等全部动态类型的内容提取
- 📦 打包为单个 EXE，无需安装 Python 或任何依赖
- 🚀 首次运行自动弹出浏览器配置引导页

## 📥 下载

前往 [Releases](https://github.com/WYXHunter/bilibili-up-monitor/releases) 页面下载最新版 `Bilibili-UP-Monitor.exe`。

## 🚀 使用

1. 双击运行 `Bilibili-UP-Monitor.exe`
2. 浏览器自动打开配置引导页
3. 填写钉钉 Webhook 地址、加签密钥、B站 Cookie
4. 添加要监控的 UP主 UID（在 B站空间 URL 中可找到，如 `space.bilibili.com/25470223`）
5. 开始接收钉钉推送通知

## 🔧 从源码运行

```bash
git clone https://github.com/WYXHunter/bilibili-up-monitor.git
cd bilibili-up-monitor
pip install -r requirements.txt
python app.py
```

浏览器访问 `http://127.0.0.1:5000`。

## ⚙️ 配置说明

| 配置项 | 说明 | 必需 |
|--------|------|------|
| 钉钉 Webhook | 钉钉群 → 群设置 → 机器人 → Webhook 地址 | ✅ |
| 加签密钥 | 机器人安全设置中的 SEC 密钥（推荐开启） | 推荐 |
| B站 Cookie | 浏览器登录 B站后 F12 → Application → Cookies 复制 | ✅ |
| 检查间隔 | 1-30 分钟，默认 5 分钟 | - |

### 如何获取 B站 Cookie

1. 浏览器打开 [bilibili.com](https://www.bilibili.com) 并登录
2. 按 `F12` 打开开发者工具 → `Application` → `Cookies` → `bilibili.com`
3. 复制 `buvid3` 的值即可（仅需此项即可正常使用）
4. 将完整 Cookie 字符串粘贴到设置中

## 🏗️ 构建

```bash
pyinstaller --onefile --noconsole --name "B站UP主监控" --add-data "templates;templates" --add-data "static;static" app.py
```

EXE 输出在 `dist/` 目录。

## 📁 项目结构

```
├── app.py              # Flask 应用入口 + Web 路由
├── bilibili.py         # B站 API 客户端（WBI 签名）
├── config.py           # 配置管理
├── database.py         # SQLite 数据层
├── monitor.py          # 后台监控引擎
├── notifier.py         # 钉钉机器人通知
├── templates/          # Web 页面模板
│   ├── index.html      # 管理面板
│   └── wizard.html     # 首次配置引导
├── static/             # 前端资源
│   ├── app.js
│   └── style.css
└── requirements.txt
```

## 🛠️ 技术栈

- **后端**: Flask
- **数据库**: SQLite
- **定时调度**: APScheduler
- **B站 API**: WBI 签名鉴权
- **钉钉通知**: Webhook + HMAC-SHA256 加签
- **打包**: PyInstaller

## 📄 License

MIT License - 详见 [LICENSE](LICENSE) 文件。

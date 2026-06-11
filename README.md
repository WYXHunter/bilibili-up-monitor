# B站 UP主 动态监控

监控 Bilibili UP 主动态更新，通过钉钉机器人实时推送。

## 功能

- 🔍 通过 UID 添加 B站 UP主，自动获取昵称头像
- ⏱️ 定时轮询（可配置 1-30 分钟间隔）
- 🔔 钉钉群机器人推送，支持加签安全模式
- 🌐 Web 管理面板，查看动态时间线
- 📦 打包为单个 EXE，无需安装 Python

## 启动

```bash
pip install -r requirements.txt
python app.py
```

浏览器自动打开 `http://127.0.0.1:5000`，首次运行会进入配置引导页。

## 配置

| 配置项 | 说明 |
|--------|------|
| 钉钉 Webhook | 钉钉群 → 机器人 → Webhook 地址 |
| 钉钉加签密钥 | 可选，机器人安全设置中的 SEC 密钥 |
| B站 Cookie | 浏览器登录 B站后 F12 复制，至少需要 buvid3 |
| 检查间隔 | 1-30 分钟可调 |

## 打包

```bash
pyinstaller --onefile --noconsole --name "B站UP主监控" --add-data "templates;templates" --add-data "static;static" app.py
```

## 技术栈

- Flask + SQLite + APScheduler
- B站 API (WBI 签名)
- 钉钉机器人 Webhook (HMAC-SHA256 加签)

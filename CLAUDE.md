# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Common commands

```bash
# Run in development mode
python app.py

# Build single EXE
pyinstaller --onefile --noconsole --name "B站UP主监控" --add-data "templates;templates" --add-data "static;static" app.py

# Create GitHub release (requires gh CLI logged in)
gh release create v<VERSION> "dist/Bilibili-UP-Monitor.exe" --title "标题" --notes "说明"

# Clean build artifacts
rm -rf dist/ build/ *.spec
```

## Architecture

**Data flow:** B站 API → `bilibili.py` (fetch + WBI sign) → `monitor.py` (detect new vs stored) → `notifier.py` (DingTalk push) & `database.py` (SQLite persistence)

**Two config sources — only `config.py` (JSON) is actively used.** `database.py` has a `settings` table but it's vestigial; the app reads/writes `data/config.json` exclusively. Writable data (`data/`, `*.db`) lives next to the EXE when frozen, or next to `__file__` in dev.

### Key modules

| Module | Role |
|--------|------|
| `app.py` | Flask app entry point, serves REST API + templates, starts scheduler on boot, opens browser |
| `bilibili.py` | B站 API client: WBI signing, UP主 info (dual-method), dynamics fetching with content extraction |
| `monitor.py` | APScheduler background loop, per-UP主 delta detection, first-check notification suppression |
| `notifier.py` | DingTalk webhook push with HMAC-SHA256 signing |
| `database.py` | SQLite CRUD for `up_users`, `dynamics`, `settings` tables |
| `config.py` | JSON file read/write for dingtalk_webhook, dingtalk_secret, bilibili_cookie, check_interval_minutes, first_run, port |

### WBI signing flow

1. `_get_mixin_key()` fetches `https://api.bilibili.com/x/web-interface/nav`, extracts `wbi_img.img_url` and `sub_url`
2. Regex extracts hex keys from image URLs → concat → first 32 chars = mixin_key (cached 1 hour)
3. `_sign_params()` sorts params alphabetically, appends mixin_key, MD5 hashes → `w_rid`, adds `wts` (unix timestamp)

### B站 API critical details

- **The `features` param is mandatory.** Without `'features': 'itemOpusStyle,listOnlyfans,opusBigCover'` and `'platform': 'web'` in the dynamics feed request, B站 returns 0 items.
- `get_up_info()` tries `acc/info` first (may fail with -352 if cookie lacks SESSDATA), then falls back to extracting author info from the dynamics feed response.
- Rate limiting: 0.6s delay between pages, 1.0s delay between UP主 checks.

### First-check suppression

`check_up_user()` in `monitor.py` detects first check via `db.get_latest_dynamic_id(uid) is None`. On first check, dynamics are stored but no DingTalk notification is sent — prevents spam when adding a new UP主.

### Image proxy

B站 CDN blocks hotlinking via referrer check. The `/proxy/image` route fetches images server-side with a B站 referer header. Frontend JS wraps all avatar/src URLs through `proxyImage()`.

### PyInstaller notes

- `--noconsole` means no terminal window; stdout/stderr are redirected to `data/app.log` via `_setup_logging()`
- `sys._MEIPASS` for read-only bundled assets (templates, static); `sys.executable` directory for writable data
- `.gitignore` excludes `data/`, `dist/`, `build/`, `*.spec`, `__pycache__/`, `*.db`, `app.log`

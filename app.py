"""
Flask web application for B站 UP主 dynamic monitor.
Provides REST API and serves the web dashboard.
"""

import os
import sys
import json
import logging
import threading
import webbrowser

from flask import Flask, request, jsonify, render_template, send_from_directory

import config as cfg
import database as db

# ── File logging (for --noconsole builds) ──────────────────

def _setup_logging():
    """Redirect stdout/stderr to a log file so errors are captured."""
    log_dir = os.path.join(os.path.dirname(sys.executable) if getattr(sys, 'frozen', False)
                           else os.path.dirname(os.path.abspath(__file__)), 'data')
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, 'app.log')

    # Truncate old log
    with open(log_path, 'w', encoding='utf-8') as f:
        f.write(f'[App] Log started\n')

    class _LogWriter:
        def __init__(self, path):
            self._f = open(path, 'a', encoding='utf-8')
        def write(self, s):
            self._f.write(s)
            self._f.flush()
        def flush(self):
            self._f.flush()
        def fileno(self):
            return self._f.fileno()

    writer = _LogWriter(log_path)
    sys.stdout = writer
    sys.stderr = writer
    logging.basicConfig(stream=writer, level=logging.INFO, format='%(asctime)s %(message)s')
from monitor import start_scheduler, stop_scheduler, check_all, check_up_user
from notifier import send_test


def get_base_dir():
    """Get the base directory, works both in dev and PyInstaller bundle."""
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


BASE_DIR = get_base_dir()

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, 'templates'),
    static_folder=os.path.join(BASE_DIR, 'static'),
)


# ── Page Routes ────────────────────────────────────────────

@app.route('/')
def index():
    """Main dashboard page."""
    is_first_run = cfg.get('first_run', True)
    if is_first_run:
        return render_template('wizard.html')
    return render_template('index.html')


@app.route('/wizard')
def wizard():
    """Setup wizard page."""
    return render_template('wizard.html')


# ── API: Stats ─────────────────────────────────────────────

@app.route('/api/stats')
def api_stats():
    up_count = len(db.get_up_users(active_only=True))
    total_dynamics = len(db.get_dynamics(limit=9999))
    today_count = db.get_today_dynamic_count()
    return jsonify({
        'up_count': up_count,
        'total_dynamics': total_dynamics,
        'today_dynamics': today_count,
    })


# ── API: UP Users ──────────────────────────────────────────

@app.route('/api/up_users', methods=['GET'])
def api_get_up_users():
    users = db.get_up_users(active_only=True)
    return jsonify(users)


@app.route('/api/up_users', methods=['POST'])
def api_add_up_user():
    data = request.get_json()
    uid = data.get('uid', '').strip()
    if not uid:
        return jsonify({'error': 'UID is required'}), 400

    # Validate UID is numeric
    if not uid.isdigit():
        return jsonify({'error': 'UID 必须是纯数字'}), 400

    # Try to get UP主 info
    cookie = cfg.get('bilibili_cookie', '')
    from bilibili import get_up_info
    info = get_up_info(uid, cookie=cookie)

    row_id, created = db.add_up_user(uid, name=info.get('name', ''), avatar=info.get('avatar', ''))
    if not created:
        return jsonify({'error': '该 UP主 已在追踪列表中'}), 409

    # Immediately fetch dynamics (first check — no notifications)
    threading.Thread(target=check_up_user, args=(uid,), daemon=True).start()

    return jsonify({
        'id': row_id,
        'uid': uid,
        'name': info.get('name', ''),
        'avatar': info.get('avatar', ''),
    })


@app.route('/api/up_users/<uid>', methods=['DELETE'])
def api_remove_up_user(uid):
    db.remove_up_user(uid)
    return jsonify({'ok': True})


# ── API: Dynamics ──────────────────────────────────────────

@app.route('/api/dynamics', methods=['GET'])
def api_get_dynamics():
    up_uid = request.args.get('up_uid', '')
    limit = int(request.args.get('limit', 50))
    offset = int(request.args.get('offset', 0))

    dynamics = db.get_dynamics(up_uid=up_uid or None, limit=limit, offset=offset)

    # Attach UP主 name
    users = {u['uid']: u for u in db.get_up_users(active_only=False)}
    for dyn in dynamics:
        u = users.get(dyn['up_uid'], {})
        dyn['up_name'] = u.get('name', dyn['up_uid'])
        dyn['up_avatar'] = u.get('avatar', '')
        dyn['detail_url'] = f'https://t.bilibili.com/{dyn["dynamic_id"]}'

    return jsonify(dynamics)


# ── API: Check Now ─────────────────────────────────────────

@app.route('/api/check_now', methods=['POST'])
def api_check_now():
    """Manually trigger a full check."""
    threading.Thread(target=check_all, daemon=True).start()
    return jsonify({'ok': True, 'message': '检查已开始'})


# ── API: Settings ──────────────────────────────────────────

@app.route('/api/settings', methods=['GET'])
def api_get_settings():
    return jsonify(cfg.load_config())


@app.route('/api/settings', methods=['POST'])
def api_save_settings():
    data = request.get_json()
    if data is None:
        return jsonify({'error': 'Invalid JSON'}), 400

    current = cfg.load_config()

    # Update allowed keys
    allowed_keys = [
        'dingtalk_webhook', 'dingtalk_secret',
        'check_interval_minutes', 'bilibili_cookie', 'first_run',
    ]
    for k in allowed_keys:
        if k in data:
            current[k] = data[k]

    cfg.save_config(current)

    # Restart scheduler if interval changed
    from monitor import get_scheduler, stop_scheduler, start_scheduler
    sched = get_scheduler()
    if sched:
        job = sched.get_job('check_all')
        new_interval = int(data.get('check_interval_minutes',
                                    current.get('check_interval_minutes', 5)))
        if job and job.trigger.interval != new_interval:
            stop_scheduler()
            start_scheduler()

    return jsonify({'ok': True})


@app.route('/proxy/image')
def proxy_image():
    """Proxy B站 images to bypass referrer blocking."""
    import requests as req
    url = request.args.get('url', '')
    if not url or not url.startswith(('https://i', 'http://i')):
        return '', 400
    try:
        resp = req.get(url, headers={
            'Referer': 'https://www.bilibili.com/',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        }, timeout=10)
        return resp.content, resp.status_code, {'Content-Type': resp.headers.get('Content-Type', 'image/jpeg')}
    except Exception:
        return '', 404


@app.route('/api/shutdown', methods=['POST'])
def api_shutdown():
    """Shutdown the application gracefully."""
    from monitor import stop_scheduler
    stop_scheduler()
    print('[App] Shutdown requested via API')
    # Schedule actual shutdown after response is sent
    threading.Timer(1.0, lambda: os._exit(0)).start()
    return jsonify({'ok': True})


@app.route('/api/test_notify', methods=['POST'])
def api_test_notify():
    webhook = cfg.get('dingtalk_webhook', '')
    secret = cfg.get('dingtalk_secret', '')
    if not webhook:
        return jsonify({'error': '请先配置钉钉 Webhook 地址'}), 400
    success = send_test(webhook, secret)
    return jsonify({'ok': success, 'message': '测试成功' if success else '测试失败，请检查配置'})


# ── Startup ────────────────────────────────────────────────

def open_browser():
    """Open browser after a short delay."""
    port = cfg.get('port', 5000)
    webbrowser.open(f'http://127.0.0.1:{port}')


def main():
    # Setup file logging (important for --noconsole builds)
    _setup_logging()

    # Initialize
    db.init_db()

    # Ensure first_run flag exists
    is_first = cfg.get('first_run', True)

    # Start background monitor
    start_scheduler()

    # Start Flask
    port = cfg.get('port', 5000)
    print(f'[App] Dashboard running at http://127.0.0.1:{port}')

    # Open browser in background thread
    threading.Timer(1.0, open_browser).start()

    try:
        app.run(host='127.0.0.1', port=int(port), debug=False, use_reloader=False)
    except KeyboardInterrupt:
        pass
    finally:
        stop_scheduler()
        print('[App] Shutdown complete')


if __name__ == '__main__':
    main()

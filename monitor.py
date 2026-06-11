"""
Monitor engine — periodic B站 dynamics checker.
Uses APScheduler for scheduling, detects new dynamics vs stored ones.
"""

import time
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler

import config as cfg
import database as db
from bilibili import fetch_dynamics, get_up_info
from notifier import send_dynamic


# Global scheduler instance
_scheduler = None


def get_scheduler():
    global _scheduler
    return _scheduler


def check_up_user(uid):
    """
    Check a single UP主 for new dynamics.
    - First check: only store the latest dynamic, don't notify
    - Subsequent checks: notify on all new dynamics
    Uses a set-based comparison to avoid missing dynamics due to CDN ordering issues.
    """
    start_time = time.time()
    cookie = cfg.get('bilibili_cookie', '')
    webhook = cfg.get('dingtalk_webhook', '')
    dingtalk_secret = cfg.get('dingtalk_secret', '')
    latest_stored = db.get_latest_dynamic_id(uid)
    is_first_check = (latest_stored is None)

    # Fetch dynamics
    dynamics = fetch_dynamics(uid, cookie=cookie)
    if not dynamics:
        print(f'[Monitor] No dynamics fetched for {uid}')
        return

    # Update UP主 info every check (name/avatar may change)
    info = get_up_info(uid, cookie=cookie)
    if info['name']:
        db.update_up_user(uid, name=info['name'], avatar=info['avatar'])

    # Update last check time
    db.update_up_user(uid, last_check_at=datetime.now().isoformat())

    # Get all existing dynamic IDs for this UP主 (set for O(1) lookup)
    existing_ids = set()
    for dyn in db.get_dynamics(up_uid=uid, limit=200):
        existing_ids.add(str(dyn['dynamic_id']))

    # Collect genuinely new dynamics (don't break on first existing — CDN may reorder)
    new_dynamics = []
    skipped = 0
    for dyn in dynamics:
        dyn_id = str(dyn['dynamic_id'])
        if dyn_id in existing_ids:
            skipped += 1
            continue
        if db.insert_dynamic(
            dyn['dynamic_id'], uid,
            dyn_type=dyn['type'],
            content=dyn['content'],
            raw_json=dyn['raw_json'],
            pub_time=dyn['pub_time']
        ):
            new_dynamics.append(dyn)
            existing_ids.add(dyn_id)

    elapsed = time.time() - start_time
    if new_dynamics:
        print(f'[Monitor] Found {len(new_dynamics)} new dynamics for {uid} ({skipped} skipped, {elapsed:.1f}s)')
    else:
        print(f'[Monitor] No new dynamics for {uid} ({skipped} existing, {elapsed:.1f}s)')

    # Don't notify on first check (initial sync)
    if is_first_check:
        print(f'[Monitor] First check for {uid}, skipping notifications')
        return

    # Send notifications for new dynamics (newest first)
    up_users = db.get_up_users()
    up_info = next((u for u in up_users if str(u['uid']) == str(uid)), {})
    up_name = up_info.get('name', f'UID:{uid}')

    for dyn in reversed(new_dynamics):
        send_dynamic(
            webhook_url=webhook,
            up_name=up_name,
            up_uid=uid,
            dynamic_id=dyn['dynamic_id'],
            dyn_type=dyn['type'],
            content=dyn['content'],
            pub_time=dyn['pub_time'],
            secret=dingtalk_secret,
        )
        time.sleep(0.3)  # small delay between notifications


def check_all():
    """Check all active UP主 for new dynamics."""
    start_time = time.time()
    print(f'[Monitor] === Check cycle started at {datetime.now().strftime("%H:%M:%S")} ===')
    up_users = db.get_up_users(active_only=True)
    if not up_users:
        print('[Monitor] No UP主 to check')
        return

    for user in up_users:
        uid = user['uid']
        try:
            check_up_user(uid)
        except Exception as e:
            print(f'[Monitor] Error checking {uid}: {e}')
        time.sleep(0.5)  # delay between UP主 checks (reduced from 1.0s)

    elapsed = time.time() - start_time
    print(f'[Monitor] === Check cycle complete ({elapsed:.1f}s) at {datetime.now().strftime("%H:%M:%S")} ===')


def start_scheduler():
    """Start the background scheduler for periodic checking."""
    global _scheduler
    interval = int(cfg.get('check_interval_minutes', 5))

    _scheduler = BackgroundScheduler()
    # misfire_grace_time=30 allows the job to run even if slightly delayed
    _scheduler.add_job(
        check_all, 'interval', minutes=interval, id='check_all',
        misfire_grace_time=30,
        coalesce=True,  # skip overlapping runs if previous is still running
    )
    _scheduler.start()
    print(f'[Monitor] Scheduler started, interval: {interval} minutes')


def stop_scheduler():
    """Stop the scheduler."""
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        print('[Monitor] Scheduler stopped')

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
    """
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

    # Find new dynamics (not yet in DB)
    new_dynamics = []
    for dyn in dynamics:
        if not db.insert_dynamic(
            dyn['dynamic_id'], uid,
            dyn_type=dyn['type'],
            content=dyn['content'],
            raw_json=dyn['raw_json'],
            pub_time=dyn['pub_time']
        ):
            # Already stored — stop here since older ones should be stored too
            break
        new_dynamics.append(dyn)

    if not new_dynamics:
        print(f'[Monitor] No new dynamics for {uid}')
        return

    print(f'[Monitor] Found {len(new_dynamics)} new dynamics for {uid}')

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
    print(f'[Monitor] Starting check cycle at {datetime.now()}')
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
        time.sleep(1.0)  # delay between UP主 checks

    print(f'[Monitor] Check cycle complete at {datetime.now()}')


def start_scheduler():
    """Start the background scheduler for periodic checking."""
    global _scheduler
    interval = int(cfg.get('check_interval_minutes', 5))

    _scheduler = BackgroundScheduler()
    _scheduler.add_job(check_all, 'interval', minutes=interval, id='check_all')
    _scheduler.start()
    print(f'[Monitor] Scheduler started, interval: {interval} minutes')


def stop_scheduler():
    """Stop the scheduler."""
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        print('[Monitor] Scheduler stopped')

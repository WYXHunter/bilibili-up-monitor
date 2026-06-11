"""
SQLite database layer for B站 UP主 monitor.
Stores UP主 info, dynamics history, and application settings.
"""

import sqlite3
import os
import sys
from datetime import datetime

# When frozen (PyInstaller), put data next to the EXE, not in temp
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_DIR = os.path.join(BASE_DIR, 'data')
DB_PATH = os.path.join(DB_DIR, 'monitor.db')


def get_connection():
    """Get a database connection with row factory enabled."""
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    """Initialize database tables."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.executescript('''
        CREATE TABLE IF NOT EXISTS up_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uid TEXT UNIQUE NOT NULL,
            name TEXT DEFAULT '',
            avatar TEXT DEFAULT '',
            is_active INTEGER DEFAULT 1,
            last_check_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS dynamics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dynamic_id TEXT UNIQUE NOT NULL,
            up_uid TEXT NOT NULL,
            type TEXT DEFAULT '',
            content TEXT DEFAULT '',
            raw_json TEXT DEFAULT '',
            pub_time TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_dynamics_up_uid ON dynamics(up_uid);
        CREATE INDEX IF NOT EXISTS idx_dynamics_created_at ON dynamics(created_at);

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT DEFAULT ''
        );
    ''')

    conn.commit()
    conn.close()


# ── UP主 CRUD ──────────────────────────────────────────────

def add_up_user(uid, name='', avatar=''):
    """Add a new UP主 to track. Returns (id, created)."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            'INSERT INTO up_users (uid, name, avatar) VALUES (?, ?, ?)',
            (str(uid), name, avatar)
        )
        conn.commit()
        return cursor.lastrowid, True
    except sqlite3.IntegrityError:
        return None, False  # already exists
    finally:
        conn.close()


def remove_up_user(uid):
    """Remove a UP主 and their dynamics."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM up_users WHERE uid = ?', (str(uid),))
    cursor.execute('DELETE FROM dynamics WHERE up_uid = ?', (str(uid),))
    conn.commit()
    conn.close()


def get_up_users(active_only=True):
    """Get all tracked UP主."""
    conn = get_connection()
    cursor = conn.cursor()
    if active_only:
        cursor.execute('SELECT * FROM up_users WHERE is_active = 1 ORDER BY created_at DESC')
    else:
        cursor.execute('SELECT * FROM up_users ORDER BY created_at DESC')
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def update_up_user(uid, **kwargs):
    """Update UP主 fields."""
    allowed = {'name', 'avatar', 'is_active', 'last_check_at'}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return
    conn = get_connection()
    cursor = conn.cursor()
    sets = ', '.join(f'{k} = ?' for k in updates)
    values = list(updates.values()) + [str(uid)]
    cursor.execute(f'UPDATE up_users SET {sets} WHERE uid = ?', values)
    conn.commit()
    conn.close()


# ── Dynamics CRUD ──────────────────────────────────────────

def insert_dynamic(dynamic_id, up_uid, dyn_type='', content='', raw_json='', pub_time=None):
    """Insert a new dynamic. Returns True if inserted, False if already exists."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            'INSERT INTO dynamics (dynamic_id, up_uid, type, content, raw_json, pub_time) '
            'VALUES (?, ?, ?, ?, ?, ?)',
            (str(dynamic_id), str(up_uid), dyn_type, content, raw_json, pub_time)
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def get_latest_dynamic_id(up_uid):
    """Get the most recent dynamic_id for a UP主."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        'SELECT dynamic_id FROM dynamics WHERE up_uid = ? ORDER BY id DESC LIMIT 1',
        (str(up_uid),)
    )
    row = cursor.fetchone()
    conn.close()
    return row['dynamic_id'] if row else None


def get_dynamics(up_uid=None, limit=50, offset=0):
    """Get dynamics, optionally filtered by UP主."""
    conn = get_connection()
    cursor = conn.cursor()
    if up_uid:
        cursor.execute(
            'SELECT * FROM dynamics WHERE up_uid = ? ORDER BY pub_time DESC LIMIT ? OFFSET ?',
            (str(up_uid), limit, offset)
        )
    else:
        cursor.execute(
            'SELECT * FROM dynamics ORDER BY pub_time DESC LIMIT ? OFFSET ?',
            (limit, offset)
        )
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def get_today_dynamic_count():
    """Count dynamics fetched today."""
    conn = get_connection()
    cursor = conn.cursor()
    today = datetime.now().strftime('%Y-%m-%d')
    cursor.execute(
        "SELECT COUNT(*) as cnt FROM dynamics WHERE date(created_at) = ?",
        (today,)
    )
    row = cursor.fetchone()
    conn.close()
    return row['cnt'] if row else 0


# ── Settings CRUD ──────────────────────────────────────────

def get_setting(key, default=''):
    """Get a setting value."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT value FROM settings WHERE key = ?', (key,))
    row = cursor.fetchone()
    conn.close()
    return row['value'] if row else default


def set_setting(key, value):
    """Set a setting value."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        'INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)',
        (key, str(value))
    )
    conn.commit()
    conn.close()


def get_all_settings():
    """Get all settings as a dict."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT key, value FROM settings')
    rows = {r['key']: r['value'] for r in cursor.fetchall()}
    conn.close()
    return rows

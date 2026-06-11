"""
Configuration management using JSON file.
Stores: dingtalk webhook, bilibili cookies, check interval, etc.
"""

import json
import os
import sys

# When frozen (PyInstaller), put data next to the EXE, not in temp
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_DIR = os.path.join(BASE_DIR, 'data')
CONFIG_PATH = os.path.join(CONFIG_DIR, 'config.json')

DEFAULT_CONFIG = {
    'dingtalk_webhook': '',
    'dingtalk_secret': '',
    'check_interval_minutes': 5,
    'bilibili_cookie': '',
    'first_run': True,
    'port': 5000,
}


def load_config():
    """Load config from file, creating with defaults if missing."""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    if not os.path.exists(CONFIG_PATH):
        save_config(DEFAULT_CONFIG)
        return dict(DEFAULT_CONFIG)
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
        for k, v in DEFAULT_CONFIG.items():
            if k not in cfg:
                cfg[k] = v
        return cfg
    except (json.JSONDecodeError, IOError):
        save_config(DEFAULT_CONFIG)
        return dict(DEFAULT_CONFIG)


def save_config(cfg):
    """Save config dict to file."""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def get(key, default=None):
    """Get a single config value."""
    cfg = load_config()
    return cfg.get(key, default)


def set_(key, value):
    """Set a single config value."""
    cfg = load_config()
    cfg[key] = value
    save_config(cfg)

"""
DingTalk robot notification sender.
Sends markdown messages via webhook.
Supports both simple and signed (HMAC-SHA256) modes.
"""

import base64
import hashlib
import hmac
import time
import requests
from urllib.parse import quote_plus


def _build_url(webhook_url, secret=''):
    """If secret is provided, append timestamp and sign for DingTalk security."""
    if not secret:
        return webhook_url

    timestamp = str(round(time.time() * 1000))
    string_to_sign = f'{timestamp}\n{secret}'
    hmac_code = hmac.new(
        secret.encode('utf-8'),
        string_to_sign.encode('utf-8'),
        digestmod=hashlib.sha256
    ).digest()
    sign = quote_plus(base64.b64encode(hmac_code).decode('utf-8'))

    # Remove trailing access_token if present, re-add with params
    return f'{webhook_url}&timestamp={timestamp}&sign={sign}'


def send_dynamic(webhook_url, up_name, up_uid, dynamic_id, dyn_type, content,
                 pub_time, secret=''):
    """
    Send a dynamic update notification to DingTalk.

    Args:
        webhook_url: DingTalk robot webhook URL
        up_name: UP主 display name
        up_uid: UP主 UID
        dynamic_id: Bilibili dynamic ID string
        dyn_type: Dynamic type (e.g. 'MAJOR_TYPE_DRAW', 'MAJOR_TYPE_ARCHIVE')
        content: Extracted text content
        pub_time: ISO format publish time
        secret: Optional HMAC-SHA256 signing secret
    """
    if not webhook_url:
        print('[Notifier] No webhook configured, skipping notification')
        return False

    # Friendly type name
    type_map = {
        'MAJOR_TYPE_DRAW': '图文动态',
        'MAJOR_TYPE_ARCHIVE': '视频投稿',
        'MAJOR_TYPE_OPUS': '图文动态',
        'MAJOR_TYPE_COMMON': '普通动态',
        'MAJOR_TYPE_ARTICLE': '专栏文章',
        'MAJOR_TYPE_LIVE': '直播',
        'MAJOR_TYPE_LIVE_RCMD': '直播回放',
    }
    cn_type = type_map.get(dyn_type, dyn_type)

    # Dynamic detail link
    detail_url = f'https://t.bilibili.com/{dynamic_id}'
    space_url = f'https://space.bilibili.com/{up_uid}/dynamic'

    # Build markdown message
    pub_display = pub_time[:16].replace('T', ' ') if pub_time else '未知时间'

    markdown_text = (
        f'## {up_name} 发布了新动态\n\n'
        f'> 类型：{cn_type}\n\n'
        f'> 时间：{pub_display}\n\n'
        f'{content}\n\n'
        f'---\n\n'
        f'[查看动态]({detail_url})  |  [UP主空间]({space_url})'
    )

    payload = {
        'msgtype': 'markdown',
        'markdown': {
            'title': f'{up_name} 发布了新动态',
            'text': markdown_text,
        },
    }

    try:
        url = _build_url(webhook_url, secret)
        resp = requests.post(url, json=payload, timeout=10)
        result = resp.json()
        if result.get('errcode') == 0:
            print(f'[Notifier] Sent: {up_name} - {content[:50]}')
            return True
        else:
            print(f'[Notifier] DingTalk error: {result}')
            return False
    except Exception as e:
        print(f'[Notifier] Send failed: {e}')
        return False


def send_test(webhook_url, secret=''):
    """Send a test message to verify webhook config."""
    payload = {
        'msgtype': 'markdown',
        'markdown': {
            'title': 'B站监控测试',
            'text': '## B站 UP主 动态监控\n\n配置测试成功！\n\n> 开始监控你关注的 UP主吧~',
        },
    }
    try:
        url = _build_url(webhook_url, secret)
        resp = requests.post(url, json=payload, timeout=10)
        result = resp.json()
        return result.get('errcode') == 0
    except Exception as e:
        print(f'[Notifier] Test failed: {e}')
        return False

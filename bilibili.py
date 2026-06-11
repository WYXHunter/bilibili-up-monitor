"""
Bilibili API client with WBI signing.
Handles fetching UP主 info and space dynamics.
"""

import hashlib
import re
import time
import datetime
import requests
from urllib.parse import urlencode

# ── Common headers ─────────────────────────────────────────

_BASE_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                   'AppleWebKit/537.36 (KHTML, like Gecko) '
                   'Chrome/125.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Origin': 'https://www.bilibili.com',
}


def _make_headers(cookie='', referer='https://www.bilibili.com/'):
    """Build request headers with optional cookie and referer."""
    headers = dict(_BASE_HEADERS)
    headers['Referer'] = referer
    if cookie:
        headers['Cookie'] = cookie
    return headers


# ── WBI Signing ────────────────────────────────────────────

# Cached mixin key and its expiry
_wbi_mixin_key = None
_wbi_key_ts = 0
_WBI_KEY_TTL = 3600  # refresh mixin key every hour


def _extract_key_from_url(url):
    """Extract the wbi key from an image URL path.
    e.g. https://i0.hdslb.com/bfs/wbi/7cd084941338484aae1ad9425b84077a.png
    → 7cd084941338484aae1ad9425b84077a
    """
    match = re.search(r'/wbi/([a-f0-9]+)\.(?:png|jpg)', url)
    return match.group(1) if match else ''


def _get_mixin_key(cookie=''):
    """Fetch and compute the WBI mixin key. Cached for 1 hour."""
    global _wbi_mixin_key, _wbi_key_ts
    now = time.time()
    if _wbi_mixin_key and (now - _wbi_key_ts) < _WBI_KEY_TTL:
        return _wbi_mixin_key

    headers = _make_headers(cookie=cookie, referer='https://www.bilibili.com/')

    try:
        resp = requests.get(
            'https://api.bilibili.com/x/web-interface/nav',
            headers=headers, timeout=10
        )
        data = resp.json()
        wbi_img = data.get('data', {}).get('wbi_img', {})
        img_url = wbi_img.get('img_url', '')
        sub_url = wbi_img.get('sub_url', '')

        img_key = _extract_key_from_url(img_url)
        sub_key = _extract_key_from_url(sub_url)

        mixin = img_key + sub_key
        _wbi_mixin_key = mixin[:32]
        _wbi_key_ts = now
        return _wbi_mixin_key
    except Exception as e:
        print(f'[Bilibili] WBI key fetch failed: {e}')
        return _wbi_mixin_key or ''


def _sign_params(params, cookie=''):
    """Add w_rid and wts to params dict (mutates in-place)."""
    mixin_key = _get_mixin_key(cookie)
    if not mixin_key:
        return  # can't sign, proceed without signing

    params['wts'] = int(time.time())
    # Sort by key
    sorted_params = sorted(params.items(), key=lambda x: x[0])
    query = urlencode(sorted_params)
    sign_str = query + mixin_key
    params['w_rid'] = hashlib.md5(sign_str.encode()).hexdigest()


# ── UP主 Info ──────────────────────────────────────────────

def get_up_info(uid, cookie=''):
    """Get UP主 basic info: name and avatar.
    Tries acc/info first, falls back to extracting from dynamics feed.
    """
    headers = _make_headers(cookie=cookie, referer=f'https://space.bilibili.com/{uid}/')

    # Method 1: Try acc/info (requires login, may fail with -352)
    params = {'mid': str(uid)}
    _sign_params(params, cookie)
    try:
        resp = requests.get(
            'https://api.bilibili.com/x/space/wbi/acc/info',
            params=params, headers=headers, timeout=10
        )
        data = resp.json()
        if data.get('code') == 0:
            info = data['data']
            return {
                'name': info.get('name', ''),
                'avatar': info.get('face', ''),
            }
    except Exception:
        pass

    # Method 2: Extract from dynamics feed (works without login)
    return _get_up_info_from_dynamics(uid, cookie)


def _get_up_info_from_dynamics(uid, cookie=''):
    """Extract UP主 name and avatar from the dynamics feed API."""
    headers = _make_headers(
        cookie=cookie,
        referer=f'https://space.bilibili.com/{uid}/dynamic',
    )
    params = {'host_mid': str(uid), 'offset': ''}
    _sign_params(params, cookie)

    try:
        resp = requests.get(
            'https://api.bilibili.com/x/polymer/web-dynamic/v1/feed/space',
            params=params, headers=headers, timeout=15
        )
        if resp.status_code != 200:
            return {'name': '', 'avatar': ''}

        data = resp.json()
        if data.get('code') != 0:
            return {'name': '', 'avatar': ''}

        items = data.get('data', {}).get('items', [])
        for item in items:
            author = item.get('modules', {}).get('module_author', {})
            name = author.get('name', '')
            face = author.get('face', '')
            if name:
                return {'name': name, 'avatar': face}

    except Exception as e:
        print(f'[Bilibili] Dynamics info fallback failed for {uid}: {e}')

    return {'name': '', 'avatar': ''}


# ── Dynamics ───────────────────────────────────────────────

def _extract_dynamic_content(item):
    """Extract human-readable content from a dynamic item.
    Walks through the messy B站 API structure to find actual text.
    """
    modules = item.get('modules', {})
    desc_module = modules.get('module_dynamic', {})
    major = desc_module.get('major', {})
    dyn_type = major.get('type', 'UNKNOWN')

    text_parts = []

    # 1) Try desc.text (may be null, str, or dict)
    desc = desc_module.get('desc')
    if desc:
        if isinstance(desc, dict):
            t = desc.get('text', '')
            if t:
                text_parts.append(t)
        elif isinstance(desc, str) and desc.strip():
            text_parts.append(desc.strip())

    # 2) Type-specific extraction
    if dyn_type == 'MAJOR_TYPE_OPUS':
        opus = major.get('opus', {})
        if opus:
            title = opus.get('title', '')
            if title:
                text_parts.append(title)
            summary = opus.get('summary', {})
            if isinstance(summary, dict) and summary.get('text'):
                text_parts.append(summary['text'])
            # Also check paragraphs (rich text)
            paragraphs = opus.get('paragraphs', [])
            for p in paragraphs:
                if isinstance(p, dict):
                    pt = p.get('text', '')
                    if pt:
                        text_parts.append(pt)

    elif dyn_type == 'MAJOR_TYPE_ARCHIVE':
        archive = major.get('archive', {})
        if archive:
            title = archive.get('title', '')
            if title:
                text_parts.append(title)
            # Include video stats
            play = archive.get('play', '')
            danmaku = archive.get('danmaku', '')
            duration = archive.get('duration_text', '')
            stats_parts = []
            if duration:
                stats_parts.append(f'时长 {duration}')
            if play:
                stats_parts.append(f'播放 {play}')
            if danmaku:
                stats_parts.append(f'弹幕 {danmaku}')
            if stats_parts:
                text_parts.append('  |  '.join(stats_parts))

    elif dyn_type == 'MAJOR_TYPE_DRAW':
        draw = major.get('draw', {})
        items = draw.get('items', []) if draw else []
        img_count = len(items)
        # Sometimes draw has a description field
        draw_desc = draw.get('description', '') if draw else ''
        if draw_desc:
            text_parts.append(draw_desc)
        if img_count > 0:
            text_parts.append(f'[共{img_count}张图片]')

    elif dyn_type == 'MAJOR_TYPE_COMMON':
        common = major.get('common', {})
        if common:
            common_desc = common.get('desc', '') or common.get('title', '')
            if common_desc:
                text_parts.append(common_desc)

    elif dyn_type == 'MAJOR_TYPE_ARTICLE':
        article = major.get('article', {})
        if article:
            art_title = article.get('title', '')
            art_desc = article.get('desc', '')
            if art_title:
                text_parts.append(art_title)
            if art_desc:
                text_parts.append(art_desc)

    elif dyn_type == 'MAJOR_TYPE_LIVE' or dyn_type == 'MAJOR_TYPE_LIVE_RCMD':
        live = major.get('live', {}) or major.get('live_rcmd', {})
        if live:
            live_title = live.get('title', '')
            if live_title:
                text_parts.append(f'[直播] {live_title}')

    # 3) If still nothing, provide a meaningful fallback
    if not text_parts:
        type_labels = {
            'MAJOR_TYPE_DRAW': '[图片动态]',
            'MAJOR_TYPE_ARCHIVE': '[视频投稿]',
            'MAJOR_TYPE_OPUS': '[图文动态]',
            'MAJOR_TYPE_COMMON': '[普通动态]',
            'MAJOR_TYPE_ARTICLE': '[专栏文章]',
            'MAJOR_TYPE_LIVE': '[直播]',
            'MAJOR_TYPE_LIVE_RCMD': '[直播回放]',
        }
        text_parts.append(type_labels.get(dyn_type, f'[{dyn_type}]'))

    # Join and clean
    text = '\n'.join(text_parts)
    text = re.sub(r'<[^>]+>', '', text)
    if len(text) > 500:
        text = text[:500] + '...'

    return dyn_type, text.strip()


def fetch_dynamics(uid, cookie='', max_pages=3):
    """
    Fetch dynamics for a UP主. Returns list of dynamic dicts.
    Each dict: {dynamic_id, type, content, pub_time, raw_json}
    """
    headers = _make_headers(
        cookie=cookie,
        referer=f'https://space.bilibili.com/{uid}/dynamic',
    )

    all_dynamics = []
    offset = ''
    pages = 0

    while pages < max_pages:
        # Build params
        params = {
            'host_mid': str(uid),
            'offset': offset,
            'features': 'itemOpusStyle,listOnlyfans,opusBigCover',
            'platform': 'web',
        }
        _sign_params(params, cookie)

        try:
            resp = requests.get(
                'https://api.bilibili.com/x/polymer/web-dynamic/v1/feed/space',
                params=params, headers=headers, timeout=15
            )

            if resp.status_code != 200:
                print(f'[Bilibili] HTTP {resp.status_code} for {uid}')
                break

            data = resp.json()

            if data.get('code') != 0:
                print(f'[Bilibili] API error for {uid}: code={data.get("code")} msg={data.get("message")}')
                break

            items = data.get('data', {}).get('items', [])
            for item in items:
                if not item or not isinstance(item, dict):
                    continue  # skip null/empty items
                try:
                    id_str = item.get('id_str') or str(item.get('id', ''))
                    dyn_type, content = _extract_dynamic_content(item)

                    # Parse publish time using timestamp in seconds
                    pub_ts = 0
                    modules = item.get('modules') or {}
                    author_module = modules.get('module_author') or {}
                    pub_ts_val = author_module.get('pub_ts')
                    if pub_ts_val:
                        try:
                            pub_ts = int(pub_ts_val)
                        except (ValueError, TypeError):
                            pass

                    pub_time = None
                    if pub_ts:
                        pub_time = datetime.datetime.fromtimestamp(pub_ts).isoformat()

                    all_dynamics.append({
                        'dynamic_id': id_str,
                        'type': dyn_type,
                        'content': content,
                        'pub_time': pub_time,
                        'raw_json': '',
                    })
                except Exception as e:
                    print(f'[Bilibili] Error processing item: {e}')
                    continue

            # Pagination
            has_more = data.get('data', {}).get('has_more', False)
            new_offset = data.get('data', {}).get('offset', '')
            if not has_more or not new_offset or new_offset == offset:
                break
            offset = new_offset
            pages += 1
            time.sleep(0.6)  # rate limiting

        except requests.exceptions.JSONDecodeError:
            print(f'[Bilibili] Non-JSON response for {uid} (status={resp.status_code})')
            break
        except Exception as e:
            print(f'[Bilibili] Error fetching dynamics for {uid}: {e}')
            break

    return all_dynamics

/**
 * B站 UP主 动态监控 — Frontend App
 */

// ── Toast ──────────────────────────────────────────────────

function showToast(msg, type) {
    var el = document.getElementById('toast');
    el.textContent = msg;
    el.className = 'toast ' + (type || 'info') + ' show';
    setTimeout(function () { el.className = 'toast'; }, 2500);
}

// ── API Helpers ────────────────────────────────────────────

function api(method, url, data) {
    var opts = { method: method, headers: { 'Content-Type': 'application/json' } };
    if (data) opts.body = JSON.stringify(data);
    return fetch(url, opts).then(function (r) {
        if (!r.ok) return r.json().then(function (e) { throw new Error(e.error || 'Request failed'); });
        return r.json();
    });
}

// ── Navigation ─────────────────────────────────────────────

(function initNav() {
    var items = document.querySelectorAll('.nav-item');
    items.forEach(function (item) {
        item.addEventListener('click', function (e) {
            e.preventDefault();
            var page = this.getAttribute('data-page');
            switchPage(page);
        });
    });
})();

function switchPage(name) {
    document.querySelectorAll('.nav-item').forEach(function (n) { n.classList.remove('active'); });
    var nav = document.querySelector('[data-page="' + name + '"]');
    if (nav) nav.classList.add('active');

    document.querySelectorAll('.page').forEach(function (p) { p.classList.remove('active'); });
    var page = document.getElementById('page-' + name);
    if (page) page.classList.add('active');

    if (name === 'dashboard') loadDashboard();
    if (name === 'up_users') loadUpUsers();
    if (name === 'settings') loadSettings();
}

// ── Dashboard ──────────────────────────────────────────────

function loadDashboard() {
    api('GET', '/api/stats').then(function (s) {
        document.getElementById('stat-up-count').textContent = s.up_count;
        document.getElementById('stat-total').textContent = s.total_dynamics;
        document.getElementById('stat-today').textContent = s.today_dynamics;
    }).catch(function () {});

    api('GET', '/api/dynamics?limit=30').then(function (list) {
        var container = document.getElementById('dynamics-list');
        if (!list.length) {
            container.innerHTML = '<p class="empty-hint">暂无动态，请先添加 UP主</p>';
            return;
        }
        container.innerHTML = list.map(renderDynamic).join('');
    }).catch(function () {});
}

function renderDynamic(d) {
    var typeClass = d.type ? d.type.replace(/^MAJOR_TYPE_/, '').toLowerCase() : '';
    var typeLabel = d.type || '';
    var typeMap = {
        'MAJOR_TYPE_DRAW': '图文', 'MAJOR_TYPE_ARCHIVE': '视频',
        'MAJOR_TYPE_OPUS': '图文', 'MAJOR_TYPE_COMMON': '动态',
        'MAJOR_TYPE_ARTICLE': '专栏', 'MAJOR_TYPE_LIVE': '直播',
        'MAJOR_TYPE_LIVE_RCMD': '直播回放',
    };
    typeLabel = typeMap[d.type] || typeLabel;

    var pubText = d.pub_time ? d.pub_time.slice(0, 16).replace('T', ' ') : '';
    var avatarHtml = d.up_avatar
        ? '<img class="dyn-avatar" src="' + proxyImage(d.up_avatar) + '" alt="" referrerpolicy="no-referrer">'
        : '';

    return '<div class="dynamic-card">'
        + '<div class="dyn-header">'
        + avatarHtml
        + '<span class="dyn-up-name">' + escapeHtml(d.up_name) + '</span>'
        + '<span class="dyn-type">' + escapeHtml(typeLabel) + '</span>'
        + '</div>'
        + '<div class="dyn-content">' + escapeHtml(d.content) + '</div>'
        + '<div class="dyn-footer">'
        + '<span>' + pubText + '</span>'
        + '<a class="dyn-link" href="' + escapeHtml(d.detail_url) + '" target="_blank">查看详情 →</a>'
        + '</div>'
        + '</div>';
}

function checkNow() {
    var btn = event.target;
    btn.disabled = true;
    btn.textContent = '检查中...';
    api('POST', '/api/check_now').then(function () {
        showToast('检查已触发，请稍后刷新页面查看结果', 'info');
        btn.disabled = false;
        btn.textContent = '🔄 立即检查';
        // Reload after a short delay
        setTimeout(loadDashboard, 3000);
    }).catch(function () {
        btn.disabled = false;
        btn.textContent = '🔄 立即检查';
        showToast('触发失败', 'error');
    });
}

// ── UP Users ───────────────────────────────────────────────

function loadUpUsers() {
    api('GET', '/api/up_users').then(function (users) {
        var container = document.getElementById('up-list');
        if (!users.length) {
            container.innerHTML = '<p class="empty-hint">还没有添加任何 UP主</p>';
            return;
        }
        container.innerHTML = users.map(function (u) {
            return '<div class="up-card">'
                + (u.avatar ? '<img src="' + proxyImage(u.avatar) + '" alt="" referrerpolicy="no-referrer">' : '<div style="width:44px;height:44px;border-radius:50%;background:#eee;"></div>')
                + '<div class="up-info">'
                + '<div class="up-name">' + (u.name || '加载中...') + '</div>'
                + '<div class="up-uid">UID: ' + escapeHtml(u.uid) + '</div>'
                + '</div>'
                + '<div class="up-actions">'
                + '<a class="btn btn-sm" href="https://space.bilibili.com/' + escapeHtml(u.uid) + '/dynamic" target="_blank">B站空间</a>'
                + '<button class="btn btn-sm btn-danger" onclick="removeUpUser(\'' + escapeHtml(u.uid) + '\')">移除</button>'
                + '</div>'
                + '</div>';
        }).join('');
    }).catch(function (e) {
        showToast('加载 UP主 列表失败', 'error');
    });
}

function addUpUser() {
    var input = document.getElementById('add-uid');
    var uid = input.value.trim();
    if (!uid) { showToast('请输入 UP主 UID', 'error'); return; }

    api('POST', '/api/up_users', { uid: uid }).then(function (data) {
        input.value = '';
        showToast('已添加 ' + (data.name || uid), 'success');
        loadUpUsers();
        loadDashboard();
    }).catch(function (e) {
        showToast(e.message, 'error');
    });
}

function removeUpUser(uid) {
    if (!confirm('确定要移除该 UP主 及其所有动态记录吗？')) return;
    api('DELETE', '/api/up_users/' + uid).then(function () {
        showToast('已移除', 'success');
        loadUpUsers();
        loadDashboard();
    }).catch(function (e) {
        showToast('移除失败', 'error');
    });
}

// ── Settings ───────────────────────────────────────────────

function loadSettings() {
    api('GET', '/api/settings').then(function (s) {
        document.getElementById('set-webhook').value = s.dingtalk_webhook || '';
        document.getElementById('set-secret').value = s.dingtalk_secret || '';
        document.getElementById('set-cookie').value = s.bilibili_cookie || '';
        document.getElementById('set-interval').value = s.check_interval_minutes || 5;
    }).catch(function () {});
}

document.addEventListener('DOMContentLoaded', function () {
    var form = document.getElementById('settings-form');
    if (form) {
        form.addEventListener('submit', function (e) {
            e.preventDefault();
            var data = {
                dingtalk_webhook: document.getElementById('set-webhook').value.trim(),
                dingtalk_secret: document.getElementById('set-secret').value.trim(),
                bilibili_cookie: document.getElementById('set-cookie').value.trim(),
                check_interval_minutes: parseInt(document.getElementById('set-interval').value),
            };
            api('POST', '/api/settings', data).then(function () {
                showToast('设置已保存', 'success');
            }).catch(function (e) {
                showToast('保存失败: ' + e.message, 'error');
            });
        });
    }
});

function testNotify() {
    var webhook = document.getElementById('set-webhook').value.trim();
    if (!webhook) { showToast('请先填写 Webhook 地址', 'error'); return; }
    api('POST', '/api/test_notify', {}).then(function (r) {
        showToast(r.message, r.ok ? 'success' : 'error');
    }).catch(function (e) {
        showToast('测试失败: ' + e.message, 'error');
    });
}

// ── Wizard ─────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', function () {
    var wizardForm = document.getElementById('wizard-form');
    if (wizardForm) {
        wizardForm.addEventListener('submit', function (e) {
            e.preventDefault();
            var statusEl = document.getElementById('wizard-status');
            statusEl.textContent = '保存配置中...';
            statusEl.style.color = '#6b7280';

            var data = {
                dingtalk_webhook: document.getElementById('webhook').value.trim(),
                dingtalk_secret: document.getElementById('secret').value.trim(),
                bilibili_cookie: document.getElementById('cookie').value.trim(),
                check_interval_minutes: parseInt(document.getElementById('interval').value),
                first_run: false,
            };

            api('POST', '/api/settings', data).then(function () {
                statusEl.textContent = '配置完成！正在跳转...';
                statusEl.style.color = '#10b981';
                setTimeout(function () { window.location.href = '/'; }, 800);
            }).catch(function (e) {
                statusEl.textContent = '保存失败: ' + e.message;
                statusEl.style.color = '#ef4444';
            });
        });
    }
});

function shutdown() {
    if (!confirm('确定要退出 B站监控程序吗？')) return;
    api('POST', '/api/shutdown').then(function () {
        showToast('程序已退出', 'info');
        setTimeout(function () { window.close(); }, 1000);
    }).catch(function () {});
}

// ── Utilities ──────────────────────────────────────────────

function proxyImage(url) {
    if (!url) return '';
    return '/proxy/image?url=' + encodeURIComponent(url);
}

function escapeHtml(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

// ── Auto-refresh dashboard every 60s ──────────────────────
setInterval(function () {
    var dashPage = document.getElementById('page-dashboard');
    if (dashPage && dashPage.classList.contains('active')) {
        loadDashboard();
    }
}, 60000);

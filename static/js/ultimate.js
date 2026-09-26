/* ALOO PANEL ULTIMATE v3.0 — command palette + password meter (Phase 1) */
(() => {
  const $ = (id) => document.getElementById(id);

  // ---------- audit-action labels (Phase 4: translatable, fallback = code) ----------
  const ACTION_KEYS = {
    login: 'audit_login', update_settings: 'audit_settings', create_user: 'audit_create_user',
    update_user: 'audit_update_user', delete_user: 'audit_delete_user', toggle: 'audit_toggle',
    clone: 'audit_clone', extend: 'audit_extend', adjust_traffic: 'audit_adjust',
    regenerate: 'audit_regenerate', regen_sub: 'audit_regen_sub', sub_toggle: 'audit_sub_toggle',
    bulk_create: 'audit_bulk', reset_all: 'audit_reset_all', cleanup: 'audit_cleanup',
    plan_create: 'audit_plan_create', plan_update: 'audit_plan_update', plan_delete: 'audit_plan_delete',
    apply_plan: 'audit_apply_plan', telegram_save: 'audit_tg_save', telegram_test: 'audit_tg_test',
    token_create: 'audit_token_create', token_revoke: 'audit_token_revoke',
    backup_export: 'audit_bk_export', backup_import: 'audit_bk_import',
    xray_restart: 'audit_xray_restart', server_add: 'audit_srv_add', server_update: 'audit_srv_update',
    server_delete: 'audit_srv_delete', server_test: 'audit_srv_test',
    server_online: 'audit_srv_online', server_offline: 'audit_srv_offline',
    password_change: 'audit_password_change', admin_create: 'audit_admin_create',
    admin_update: 'audit_admin_update', admin_delete: 'audit_admin_delete',
    '2fa_setup': 'audit_2fa_setup', '2fa_enable': 'audit_2fa_enable',
    '2fa_disable': 'audit_2fa_disable', login_failed: 'audit_login_failed',
    ip_unblock: 'audit_ip_unblock', sessions_revoke: 'audit_sessions_revoke',
    backup_create: 'audit_backup_create', backup_restore: 'audit_backup_restore',
    backup_delete: 'audit_backup_delete', diagnostics_run: 'audit_diagnostics_run',
    shop_balance: 'audit_shop_balance', shop_topup: 'audit_shop_topup',
    plugin_toggle: 'audit_plugin_toggle', role_update: 'audit_role_update',
    xray_start: 'audit_xray_start', xray_stop: 'audit_xray_stop',
    group_create: 'audit_group_create', group_update: 'audit_group_update',
    group_delete: 'audit_group_delete', group_members: 'audit_group_members',
    assign_create: 'audit_assign_create', failover: 'audit_failover',
    alert_open: 'audit_alert_open', alert_resolved: 'audit_alert_resolved',
  };
  window.ALOO_ACTION = (code) => {
    const k = ACTION_KEYS[code || ''];
    if (!k) return (code || '').replace(/_/g, ' ');
    const t = window.STANNG.t(k);
    return t === k ? (code || '').replace(/_/g, ' ') : t;
  };

  // ---------- password strength (mirrors core/security.py) ----------
  function scorePassword(pw) {
    pw = pw || '';
    let s = 0;
    if (pw.length >= 8) s++;
    if (pw.length >= 12) s++;
    if (/[a-z]/.test(pw) && /[A-Z]/.test(pw)) s++;
    if (/\d/.test(pw) && /[^a-zA-Z0-9]/.test(pw)) s++;
    if (['password', '12345678', 'qwerty123', 'admin123', 'aloo1234'].includes(pw.toLowerCase())) s = 0;
    return Math.max(0, Math.min(4, s));
  }
  const PW_LABELS = ['pw_very_weak', 'pw_weak', 'pw_ok', 'pw_strong', 'pw_very_strong'];

  function attachMeter(inputId) {
    const input = $(inputId);
    if (!input || input.dataset.meterBound) return;
    input.dataset.meterBound = '1';
    const meter = document.createElement('div');
    meter.className = 'pw-meter';
    meter.innerHTML = '<i></i><i></i><i></i><i></i>';
    const label = document.createElement('div');
    label.className = 'pw-label';
    input.closest('.field').appendChild(meter);
    input.closest('.field').appendChild(label);
    input.addEventListener('input', () => {
      const s = scorePassword(input.value);
      meter.className = 'pw-meter s' + s;
      label.textContent = input.value ? window.STANNG.t(PW_LABELS[s]) : '';
    });
  }

  // ---------- command palette ----------
  const PAGES = [
    ['dashboard', 'nav_dashboard', 'icon-dashboard'], ['inbounds', 'nav_inbounds', 'icon-users'],
    ['traffic', 'nav_traffic', 'icon-traffic'], ['plans', 'nav_plans', 'icon-crown'],
    ['servers', 'nav_servers', 'icon-globe'], ['analytics', 'nav_analytics', 'icon-traffic'],
    ['live', 'nav_live', 'icon-bolt'], ['notifications', 'nav_notifications', 'icon-info'],
    ['shop', 'nav_shop', 'icon-crown'], ['ai', 'nav_ai', 'icon-sparkles'],
    ['extensions', 'nav_extensions', 'icon-puzzle'],
    ['alerts', 'nav_alerts', 'icon-bolt'], ['map', 'nav_map', 'icon-globe'],
    ['compare', 'nav_compare', 'icon-traffic'],
    ['diagnostics', 'nav_diagnostics', 'icon-info'],
    ['xray', 'nav_xray', 'icon-server'],
    ['telegram', 'nav_telegram', 'icon-telegram'],
    ['api', 'nav_api', 'icon-terminal'], ['backup', 'nav_backup', 'icon-database'],
    ['logs', 'nav_logs', 'icon-clock'], ['security', 'nav_security', 'icon-shield'],
    ['settings', 'nav_settings', 'icon-settings'],
  ];

  function gotoView(name) {
    const nav = document.querySelector(`.nav-item[data-view="${name}"]`);
    if (nav) nav.click();
  }

  function collectCommands() {
    const T = (k) => window.STANNG.t(k);
    return [
      { label: T('inb_add'), icon: 'icon-plus', run: () => { gotoView('inbounds'); const b = $('addInboundBtn'); if (b) b.click(); } },
      { label: T('bulk_add'), icon: 'icon-users', run: () => { gotoView('inbounds'); const m = $('bulkModal'); if (m) m.classList.add('open'); } },
      { label: T('bk_export'), icon: 'icon-download', run: async () => {
        const r = await window.STANNG.api('/api/backup/export');
        const blob = new Blob([JSON.stringify(r, null, 2)], { type: 'application/json' });
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = `aloo-backup-${new Date().toISOString().slice(0, 10)}.json`;
        a.click();
      } },
      { label: T('tg_test'), icon: 'icon-telegram', run: () => gotoView('telegram') },
      { label: T('ops_export'), icon: 'icon-download', run: () => { gotoView('dashboard'); if (window.PREMIUM) window.PREMIUM.exportTelemetry(); } },
      { label: T('ops_title'), icon: 'icon-bolt', run: () => { gotoView('dashboard'); if (window.PREMIUM) window.PREMIUM.refreshTelemetry(true); } },
      { label: T('nav_logout'), icon: 'icon-logout', run: async () => { await window.STANNG.api('/api/logout', { method: 'POST' }); window.location.href = '/login'; } },
    ];
  }

  function openPalette() { const o = $('paletteOverlay'); if (!o) return; o.classList.add('open'); const i = $('paletteInput'); i.value = ''; renderPalette(''); setTimeout(() => i.focus(), 30); }
  function closePalette() { const o = $('paletteOverlay'); if (o) o.classList.remove('open'); }

  let selIndex = 0;
  let currentItems = [];

  function renderPalette(q) {
    const box = $('paletteResults');
    if (!box) return;
    q = (q || '').trim().toLowerCase();
    const T = (k) => window.STANNG.t(k);
    currentItems = [];
    let html = '';

    const pages = PAGES.filter(p => !q || T(p[1]).toLowerCase().includes(q) || p[0].includes(q));
    if (pages.length) {
      html += `<div class="small muted" style="padding:8px 12px 2px;">${T('palette_pages')}</div>`;
      pages.forEach(p => {
        currentItems.push({ label: T(p[1]), icon: p[2], run: () => gotoView(p[0]) });
        html += `<button class="palette-item" data-idx="${currentItems.length - 1}"><svg><use href="#${p[2]}"/></svg>${T(p[1])}<span class="k">${p[0]}</span></button>`;
      });
    }
    const cmds = collectCommands().filter(c => !q || c.label.toLowerCase().includes(q));
    if (cmds.length) {
      html += `<div class="small muted" style="padding:8px 12px 2px;">${T('palette_commands')}</div>`;
      cmds.forEach(c => {
        currentItems.push(c);
        html += `<button class="palette-item" data-idx="${currentItems.length - 1}"><svg><use href="#${c.icon}"/></svg>${c.label}</button>`;
      });
    }
    if (window.STANNG_INBOUNDS && q.length >= 2) {
      const users = window.STANNG_INBOUNDS.get().filter(u => (u.name || '').toLowerCase().includes(q)).slice(0, 8);
      if (users.length) {
        html += `<div class="small muted" style="padding:8px 12px 2px;">${T('palette_users')}</div>`;
        users.forEach(u => {
          currentItems.push({ label: u.name, icon: 'icon-user-circle', run: () => {
            gotoView('inbounds');
            const s = $('inboundSearch');
            if (s) { s.value = u.name; s.dispatchEvent(new Event('input')); }
          } });
          html += `<button class="palette-item" data-idx="${currentItems.length - 1}"><svg><use href="#icon-user-circle"/></svg>${u.name.replace(/[&<>"']/g, m => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m]))}</button>`;
        });
      }
    }
    if (!currentItems.length) html = `<div class="muted small" style="padding:16px;">${T('palette_no_result')}</div>`;
    selIndex = 0;
    box.innerHTML = html;
    paintSel();
    box.querySelectorAll('.palette-item').forEach(b => b.addEventListener('click', () => { const it = currentItems[+b.dataset.idx]; closePalette(); if (it) it.run(); }));
  }

  function paintSel() {
    document.querySelectorAll('#paletteResults .palette-item').forEach((b, i) => b.classList.toggle('sel', i === selIndex));
  }

  document.addEventListener('DOMContentLoaded', () => {
    attachMeter('password');
    attachMeter('newPassword');
    const ov = $('paletteOverlay');
    if (ov) {
      ov.addEventListener('click', (e) => { if (e.target === ov) closePalette(); });
      $('paletteInput').addEventListener('input', (e) => renderPalette(e.target.value));
      $('paletteInput').addEventListener('keydown', (e) => {
        if (e.key === 'ArrowDown') { e.preventDefault(); selIndex = Math.min(currentItems.length - 1, selIndex + 1); paintSel(); }
        else if (e.key === 'ArrowUp') { e.preventDefault(); selIndex = Math.max(0, selIndex - 1); paintSel(); }
        else if (e.key === 'Enter') { const it = currentItems[selIndex]; closePalette(); if (it) it.run(); }
      });
    }
  });

  document.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); const o = $('paletteOverlay'); if (o) (o.classList.contains('open') ? closePalette() : openPalette()); }
    else if (e.key === 'Escape') closePalette();
    else if (e.key === '/' && !/INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName)) {
      const s = $('inboundSearch');
      if (s && document.getElementById('view-inbounds').classList.contains('active')) { e.preventDefault(); s.focus(); }
    }
  });
})();

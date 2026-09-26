/* SsPanel v2.0 — premium features controller (telegram, tokens, backup, audit, bulk, online) */
(() => {
  const $ = (id) => document.getElementById(id);
  const api = (p, o) => window.STANNG.api(p, o);

  function fmtTime(ts) {
    if (!ts) return window.STANNG.t('never');
    const d = new Date(ts * 1000);
    return d.toLocaleString(window.STANNG.getLang() === 'fa' ? 'fa-IR' : 'en-US');
  }

  // ---------- TELEGRAM ----------
  async function loadTelegram() {
    try {
      const r = await api('/api/telegram/status');
      if ($('tgChatId') && !$('tgChatId').value) $('tgChatId').value = r.chat_id || '';
      const _env = $('tgEnvNote');
      if (_env) _env.style.display = r.token_source === 'env' ? '' : 'none';
      if ($('tgEnabled')) $('tgEnabled').checked = !!r.enabled;
      if ($('tgNNew')) $('tgNNew').checked = r.notify_new_user !== false;
      if ($('tgNQuota')) $('tgNQuota').checked = r.notify_quota !== false;
      if ($('tgNExpiry')) $('tgNExpiry').checked = r.notify_expiry !== false;
      if ($('tgNLogin')) $('tgNLogin').checked = !!r.notify_login;
      if ($('tgNServer')) $('tgNServer').checked = r.notify_server !== false;
      // shop settings live in the same status payload
      const sh = r.shop || {};
      if ($('shopEnabled')) $('shopEnabled').checked = sh.enabled !== false;
      if ($('shopSupport')) $('shopSupport').value = sh.support_username || '';
      if ($('shopBonus')) $('shopBonus').value = sh.referral_bonus || 0;
      if ($('shopTestGb')) $('shopTestGb').value = sh.test_gb || 0;
      if ($('shopTestDays')) $('shopTestDays').value = sh.test_days || 0;
      const sp = $('shopPill');
      if (sp) {
        sp.textContent = (sh.enabled !== false ? '● ' : '○ ') + window.STANNG.t('shop_title');
        sp.className = 'pill ' + (sh.enabled !== false ? 'pill-on' : 'pill-off');
      }
      try {
        const ov = await api('/api/shop/overview');
        const ss = $('shopStats');
        if (ss) ss.textContent = `${window.STANNG.t('shop_customers')}: ${ov.customers} · ${window.STANNG.t('shop_pending')}: ${ov.pending_topups} · ${window.STANNG.t('shop_revenue')}: ${Number(ov.approved_total || 0).toLocaleString()}`;
      } catch (e) { /* perm-gated */ }
      const poll = r.poll || {};
      const ps = $('tgPollState');
      if (ps) {
        if (poll.fresh && poll.last_ok) ps.innerHTML = '<span style="color:var(--emerald)">● live</span>';
        else if (poll.last_ts && !poll.last_ok) ps.innerHTML = `<span style="color:var(--crimson)">● ${escapeHtml(poll.error || 'error')}</span>`;
        else ps.innerHTML = `<span class="muted">${window.STANNG.t(poll.last_ts ? 'tg_poll_idle' : 'tg_poll_waiting')}</span>`;
      }
      const pill = $('tgStatusPill');
      if (pill) {
        const ok = r.enabled && r.has_token && r.chat_id;
        pill.textContent = ok ? '● ' + window.STANNG.t('tg_connected') : '○ ' + window.STANNG.t('tg_disconnected');
        pill.className = 'pill ' + (ok ? 'pill-on' : 'pill-off');
      }
      const badge = $('navTgBadge');
      if (badge) badge.style.display = (r.enabled && r.has_token) ? '' : 'none';
      const card = $('tgStatusCard');
      if (card) { card.classList.toggle('tg-connected', !!(r.enabled && r.has_token)); card.classList.toggle('tg-disconnected', !(r.enabled && r.has_token)); }
    } catch (e) { /* ignore */ }
  }

  async function saveTelegram(btn) {
    window.STANNG.setLoading(btn, true);
    try {
      const payload = {
        bot_token: $('tgToken').value.trim(),
        chat_id: $('tgChatId').value.trim(),
        telegram_enabled: $('tgEnabled').checked,
        notify_new_user: $('tgNNew').checked,
        notify_quota: $('tgNQuota').checked,
        notify_expiry: $('tgNExpiry').checked,
        notify_login: $('tgNLogin').checked,
        notify_server: $('tgNServer').checked,
      };
      // don't overwrite token with empty (keep old)
      if (!payload.bot_token) delete payload.bot_token;
      const r = await api('/api/telegram/save', { method: 'POST', body: payload });
      $('tgResult').innerHTML = '<span style="color:var(--emerald)">✔ ' + (r.bot_username ? '@' + r.bot_username : 'saved') + '</span>';
      window.STANNG.toast(window.STANNG.t('settings_saved'), 'success');
      $('tgToken').value = '';
      loadTelegram();
    } catch (e) {
      $('tgResult').innerHTML = '<span style="color:var(--crimson)">✖ ' + (e.detail || 'error') + '</span>';
      window.STANNG.toast(e.detail || 'error', 'error');
    } finally { window.STANNG.setLoading(btn, false); }
  }

  // ---------- TOKENS ----------
  async function loadTokens() {
    try {
      const r = await api('/api/tokens');
      const tb = $('tokensTableBody');
      if (!tb) return;
      tb.innerHTML = '';
      (r.tokens || []).forEach(t => {
        const tr = document.createElement('tr');
        tr.innerHTML = `<td><b>${escapeHtml(t.name)}</b><div class="small muted">${t.id}</div></td>
          <td style="direction:ltr;"><code>${escapeHtml(t.prefix)}</code></td>
          <td class="small">${t.last_used ? fmtTime(t.last_used) : window.STANNG.t('never')}</td>
          <td><button class="icon-btn btn-sm" data-tid="${t.id}" style="color:var(--crimson)"><svg width="15" height="15"><use href="#icon-trash"/></svg></button></td>`;
        tb.appendChild(tr);
      });
      if (!(r.tokens || []).length) tb.innerHTML = `<tr><td colspan="4" class="muted small" style="text-align:center;">—</td></tr>`;
      tb.querySelectorAll('button[data-tid]').forEach(b => b.addEventListener('click', async () => {
        if (!confirm(window.STANNG.t('api_revoke_confirm'))) return;
        await api(`/api/tokens/${b.dataset.tid}`, { method: 'DELETE' });
        loadTokens();
      }));
    } catch (e) { window.STANNG.toast(e.detail || 'error', 'error'); }
  }

  // ---------- AUDIT ----------
  async function loadAudit() {
    const box = $('auditBox');
    if (!box) return;
    try {
      const filter = $('auditActionFilter') ? $('auditActionFilter').value : '';
      const r = await api('/api/audit' + (filter ? '?action=' + encodeURIComponent(filter) : ''));
      const sel = $('auditActionFilter');
      if (sel && (r.actions || []).length) {
        const cur = sel.value;
        sel.innerHTML = '<option value="">—</option>' + r.actions.map(a =>
          `<option value="${escapeHtml(a)}">${escapeHtml(window.ALOO_ACTION ? window.ALOO_ACTION(a) : a)}</option>`).join('');
        sel.value = cur;
      }
      if (!(r.logs || []).length) { box.innerHTML = '<div class="muted small">—</div>'; return; }
      box.innerHTML = r.logs.map(l =>
        `<div class="audit-item"><span class="audit-time">${fmtTime(l.ts)}</span><b>${escapeHtml(l.actor)}</b><span class="pill" style="font-size:.62rem;">${escapeHtml(window.ALOO_ACTION ? window.ALOO_ACTION(l.action) : (l.action || ''))}</span><span class="muted">${escapeHtml(l.detail || '')}</span>${l.ip ? `<code class="small" style="direction:ltr;">${escapeHtml(l.ip)}</code>` : ''}</div>`
      ).join('');
    } catch (e) { box.innerHTML = '<div class="muted small">—</div>'; }
  }

  // ---------- SYSTEM / ONLINE ----------
  let telemetryTimer = null;
  let telemetryPaused = false;
  let lastTelemetry = null;
  let previousTelemetry = null;

  const clampPct = (v) => Math.max(0, Math.min(100, Number(v) || 0));
  const setText = (id, value) => { const el = $(id); if (el) el.textContent = value; };
  const setWidth = (id, value) => { const el = $(id); if (el) el.style.width = clampPct(value) + '%'; };

  function networkRate(current, previous) {
    if (!previous || !current.network || !previous.network) return { up: 0, down: 0 };
    const seconds = Math.max(.1, Number(current.sampled_at) - Number(previous.sampled_at));
    return {
      up: Math.max(0, (Number(current.network.bytes_sent) - Number(previous.network.bytes_sent)) / seconds),
      down: Math.max(0, (Number(current.network.bytes_recv) - Number(previous.network.bytes_recv)) / seconds),
    };
  }

  function renderTelemetry(t) {
    const n = t.network || {}, m = t.memory || {}, d = t.disk || {}, p = t.process || {}, db = t.database || {}, cpu = t.cpu || {};
    const rate = networkRate(t, previousTelemetry);
    setText('opsHealth', Math.round(t.health_score || 0) + '%');
    const ring = $('opsHealthRing'); if (ring) ring.style.setProperty('--pct', clampPct(t.health_score));
    setText('opsCpu', (Number(cpu.percent) || 0).toFixed(1) + '%');
    setWidth('opsCpuBar', cpu.percent);
    setText('opsCpuMeta', `${cpu.physical_cores || '—'} physical / ${cpu.logical_cores || '—'} logical`);
    setText('opsMemory', (Number(m.percent) || 0).toFixed(1) + '%');
    setWidth('opsMemoryBar', m.percent);
    setText('opsMemoryMeta', `${window.STANNG.fmtBytes(m.used_bytes)} / ${window.STANNG.fmtBytes(m.total_bytes)} · swap ${Number(m.swap_percent || 0).toFixed(1)}%`);
    setText('opsDisk', (Number(d.percent) || 0).toFixed(1) + '%');
    setWidth('opsDiskBar', d.percent);
    setText('opsDiskMeta', `${window.STANNG.fmtBytes(d.free_bytes)} free / ${window.STANNG.fmtBytes(d.total_bytes)}`);
    setText('opsNetwork', `↑ ${window.STANNG.fmtBytes(rate.up)}/s · ↓ ${window.STANNG.fmtBytes(rate.down)}/s`);
    setText('opsNetworkMeta', `${window.STANNG.fmtBytes(n.bytes_sent)} sent · ${window.STANNG.fmtBytes(n.bytes_recv)} received · ${Number(n.errin || 0) + Number(n.errout || 0)} errors`);
    setText('opsProcess', `PID ${p.pid || '—'} · ${window.STANNG.fmtBytes(p.rss_bytes)}`);
    setText('opsProcessMeta', `${p.threads || 0} threads · ${p.open_files || 0} open files · ${window.STANNG.fmtDuration(p.uptime_seconds || 0)}`);
    setText('opsDatabase', `${db.users || 0} users · ${window.STANNG.fmtBytes(db.size_bytes)}`);
    setText('opsDatabaseMeta', `${db.plans || 0} plans · ${db.servers || 0} servers · ${db.audit_entries || 0} audit events`);
    setText('opsFreshness', new Date(t.sampled_at * 1000).toLocaleTimeString(window.STANNG.getLang() === 'fa' ? 'fa-IR' : 'en-US'));
    const badge = $('opsRealBadge');
    if (badge) { badge.classList.toggle('pill-on', t.synthetic === false); badge.title = t.source || ''; }
  }

  async function refreshTelemetry(force = false) {
    if (telemetryPaused && !force) return;
    try {
      const t = await api('/api/system/telemetry');
      previousTelemetry = lastTelemetry;
      lastTelemetry = t;
      renderTelemetry(t);
    } catch (e) {
      setText('opsFreshness', e.detail || 'offline');
    }
  }

  function startTelemetry() {
    if (telemetryTimer) clearInterval(telemetryTimer);
    refreshTelemetry();
    telemetryTimer = setInterval(refreshTelemetry, 4000);
  }

  function exportTelemetry() {
    if (!lastTelemetry) return;
    const payload = Object.assign({ exported_at: new Date().toISOString(), panel_url: window.location.origin }, lastTelemetry);
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `aloo-live-snapshot-${new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19)}.json`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
    window.STANNG.toast(window.STANNG.t('ops_exported'), 'success');
  }

  async function loadSystem() {
    try {
      const [sys, on] = await Promise.all([api('/api/system'), api('/api/online')]);
      const box = $('systemInfoBox');
      const disk = sys.disk || {};
      if (box) box.innerHTML =
        `<div>🖥️ CPU: <b>${sys.cpu_count}</b> cores ${sys.load_avg && sys.load_avg.length ? '(' + sys.load_avg.map(x => x.toFixed(2)).join(' / ') + ')' : ''}</div>
         <div>💾 Disk: <b>${disk.used_gb ?? '?'} / ${disk.total_gb ?? '?'} GB</b> (${disk.percent ?? '?'}%)</div>
         <div>🐍 Python <b>${sys.python}</b> · Panel <b>v${sys.version}</b></div>
         <div>🔑 API tokens: <b>${sys.tokens}</b> · 👥 Users: <b>${sys.users}</b></div>`;
      const ot = $('onlineTableBody');
      if (ot) {
        ot.innerHTML = '';
        $('onlineCount').textContent = on.count || 0;
        $('onlineEmpty').style.display = (on.count ? 'none' : 'block');
        (on.online || []).forEach(u => {
          const tr = document.createElement('tr');
          const ago = window.STANNG.t('time_ago_s').replace('{n}', u.last_seen_ago);
          tr.innerHTML = `<td><span class="online-dot"></span> <b>${escapeHtml(u.name)}</b></td><td class="small muted">${ago}</td>`;
          ot.appendChild(tr);
        });
      }
    } catch (e) { /* ignore */ }
  }

  function escapeHtml(s) {
    return (s || '').replace(/[&<>"']/g, m => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m]));
  }

  // ---------- PLANS ----------
  async function loadPlans() {
    try {
      const r = await api('/api/plans');
      const tb = $('plansTableBody');
      if (!tb) return;
      tb.innerHTML = '';
      const plans = r.plans || [];
      $('plansEmpty').style.display = plans.length ? 'none' : 'block';
      plans.forEach(p => {
        const tr = document.createElement('tr');
        tr.innerHTML = `<td><b>${escapeHtml(p.name)}</b><div class="small muted">${escapeHtml(p.description || '')}</div></td>
          <td>${p.traffic_gb} GB</td><td>${p.duration_days} ${window.STANNG.t('inb_days_left')}</td><td>${p.device_limit || '∞'}</td>
          <td>${Number(p.price || 0).toLocaleString()}</td>
          <td>${p.enabled ? `<span class="pill pill-on"><span class="pill-dot"></span>${window.STANNG.t('active')}</span>` : `<span class="pill pill-off"><span class="pill-dot"></span>${window.STANNG.t('inactive')}</span>`}</td>
          <td><div class="row-actions">
            <button class="icon-btn btn-sm" data-pact="edit" data-pid="${p.id}"><svg width="15" height="15"><use href="#icon-edit"/></svg></button>
            <button class="icon-btn btn-sm" data-pact="toggle" data-pid="${p.id}"><svg width="15" height="15"><use href="#icon-bolt"/></svg></button>
            <button class="icon-btn btn-sm" data-pact="del" data-pid="${p.id}" style="color:var(--crimson)"><svg width="15" height="15"><use href="#icon-trash"/></svg></button>
          </div></td>`;
        tb.appendChild(tr);
      });
      tb.querySelectorAll('button[data-pact]').forEach(b => b.addEventListener('click', () => planAction(b.dataset.pact, b.dataset.pid)));
    } catch (e) { window.STANNG.toast(e.detail || 'error', 'error'); }
  }

  async function planAction(act, pid) {
    try {
      if (act === 'del') {
        if (!confirm(window.STANNG.t('plan_delete_confirm'))) return;
        await api(`/api/plans/${pid}`, { method: 'DELETE' });
      } else if (act === 'toggle') {
        const r = await api('/api/plans');
        const p = (r.plans || []).find(x => x.id === pid);
        await api(`/api/plans/${pid}`, { method: 'PATCH', body: { enabled: !(p && p.enabled) } });
      } else if (act === 'edit') {
        const r = await api('/api/plans');
        const p = (r.plans || []).find(x => x.id === pid);
        if (!p) return;
        $('planId').value = p.id; $('pName').value = p.name; $('pTraffic').value = p.traffic_gb;
        $('pDuration').value = p.duration_days; $('pDevices').value = p.device_limit;
        $('pPrice').value = p.price || 0;
        $('pDesc').value = p.description || ''; $('pEnabled').checked = !!p.enabled;
        $('planModal').classList.add('open');
        return;
      }
      loadPlans();
    } catch (e) { window.STANNG.toast(e.detail || 'error', 'error'); }
  }

  async function openAssign(uid, name) {
    $('assignUid').value = uid;
    $('assignUserName').textContent = name || '';
    try {
      const r = await api('/api/plans');
      const sel = $('assignPlanSelect');
      sel.innerHTML = (r.plans || []).filter(p => p.enabled).map(p =>
        `<option value="${p.id}">${escapeHtml(p.name)} · ${p.traffic_gb}GB · ${p.duration_days}d · ${Number(p.price || 0).toLocaleString()}</option>`).join('')
        || '<option value="">—</option>';
    } catch (e) { $('assignPlanSelect').innerHTML = '<option value="">—</option>'; }
    $('assignPlanModal').classList.add('open');
  }

  // ---------- XRAY ----------
  async function loadXray() {
    try {
      const r = await api('/api/xray/status');
      const pill = $('xrayPill');
      if (pill) {
        pill.textContent = '● ' + (r.status === 'online' ? window.STANNG.t('svc_online') : (r.status === 'mock' ? window.STANNG.t('svc_mock') : window.STANNG.t('svc_offline')));
        pill.className = 'pill ' + (r.status === 'online' ? 'pill-on' : (r.status === 'mock' ? 'pill-warn' : 'pill-off'));
      }
      const box = $('xrayBox');
      if (box) box.innerHTML = `
        <div class="svc-row"><span class="svc-name">${window.STANNG.t('svc_xray')}</span><span class="small muted" style="direction:ltr;">${escapeHtml(r.version || '—')}</span></div>
        <div class="svc-row"><span class="svc-name">Panel</span><span class="small muted" style="direction:ltr;">127.0.0.1:${r.ports.panel}</span></div>
        <div class="svc-row"><span class="svc-name">VLESS WS</span><span class="small muted" style="direction:ltr;">127.0.0.1:${r.ports.vless_ws} · /vl-ws</span></div>
        <div class="svc-row"><span class="svc-name">VMess WS</span><span class="small muted" style="direction:ltr;">127.0.0.1:${r.ports.vmess_ws} · /vm-ws</span></div>
        <div class="svc-row"><span class="svc-name">VLESS XHTTP</span><span class="small muted" style="direction:ltr;">127.0.0.1:${r.ports.vless_xhttp} · /vl-xhttp</span></div>
        <div class="svc-row"><span class="svc-name">${window.STANNG.t('nav_inbounds')}</span><span class="small muted">${r.tracked_clients == null ? '—' : r.tracked_clients}</span></div>`;
      const sel = $('xrayLogLevel');
      if (sel) sel.value = r.log_level || 'warning';
      fetch('/api/xray/config', { credentials: 'same-origin' }).then(res => res.text()).then(t => {
        const pre = $('xrayConfigPre');
        if (pre) pre.textContent = t.slice(0, 6000);
      }).catch(() => {});
    } catch (e) { window.STANNG.toast(e.detail || 'error', 'error'); }
  }

  // ---------- wire up ----------
  document.addEventListener('DOMContentLoaded', () => {
    startTelemetry();
    if ($('opsPauseBtn')) $('opsPauseBtn').addEventListener('click', (e) => {
      telemetryPaused = !telemetryPaused;
      const center = document.querySelector('.ops-center');
      if (center) center.classList.toggle('paused', telemetryPaused);
      e.currentTarget.textContent = window.STANNG.t(telemetryPaused ? 'ops_resume' : 'ops_pause');
      if (!telemetryPaused) refreshTelemetry(true);
      else setText('opsFreshness', window.STANNG.t('ops_paused'));
    });
    if ($('opsExportBtn')) $('opsExportBtn').addEventListener('click', exportTelemetry);
    if ($('tgSaveBtn')) $('tgSaveBtn').addEventListener('click', (e) => saveTelegram(e.currentTarget));
    if ($('tgTestBtn')) $('tgTestBtn').addEventListener('click', async (e) => {
      window.STANNG.setLoading(e.currentTarget, true);
      try { await api('/api/telegram/test', { method: 'POST', body: {} }); window.STANNG.toast(window.STANNG.t('tg_sent'), 'success'); }
      catch (err) { window.STANNG.toast(err.detail || 'error', 'error'); }
      finally { window.STANNG.setLoading(e.currentTarget, false); }
    });
    if ($('newTokenBtn')) $('newTokenBtn').addEventListener('click', async () => {
      const name = prompt('Token name (e.g. my-bot):', 'my-bot') || 'bot';
      try {
        const r = await api('/api/tokens', { method: 'POST', body: { name } });
        $('newTokenBox').style.display = '';
        $('newTokenSecret').textContent = r.token;
        window.STANNG.toast(window.STANNG.t('copied') + ': ' + window.STANNG.t('api_once'), 'success', 6000);
        loadTokens();
      } catch (e) { window.STANNG.toast(e.detail || 'error', 'error'); }
    });
    if ($('reloadLogsBtn')) $('reloadLogsBtn').addEventListener('click', loadAudit);
    const _aaf = $('auditActionFilter');
    if (_aaf) _aaf.addEventListener('change', loadAudit);
    if ($('bulkAddBtn')) $('bulkAddBtn').addEventListener('click', () => $('bulkModal').classList.add('open'));
    if ($('bulkSaveBtn')) $('bulkSaveBtn').addEventListener('click', async (e) => {
      window.STANNG.setLoading(e.currentTarget, true);
      try {
        await api('/api/inbounds/bulk', { method: 'POST', body: {
          count: parseInt($('bCount').value || 5), name_prefix: $('bPrefix').value || 'User',
          quota_gb: parseFloat($('bQuota').value || 0), expire_days: parseInt($('bExpire').value || 0) } });
        $('bulkModal').classList.remove('open');
        window.STANNG.toast(window.STANNG.t('bulk_created'), 'success');
        if (window.STANNG_INBOUNDS) window.STANNG_INBOUNDS.reload();
      } catch (err) { window.STANNG.toast(err.detail || 'error', 'error'); }
      finally { window.STANNG.setLoading(e.currentTarget, false); }
    });
    if ($('extendSaveBtn')) $('extendSaveBtn').addEventListener('click', async (e) => {
      window.STANNG.setLoading(e.currentTarget, true);
      try {
        await api(`/api/inbounds/${$('extendUid').value}/extend`, { method: 'POST', body: {
          days: parseInt($('eDays').value || 0), add_gb: parseFloat($('eGb').value || 0) } });
        $('extendModal').classList.remove('open');
        if (window.STANNG_INBOUNDS) window.STANNG_INBOUNDS.reload();
      } catch (err) { window.STANNG.toast(err.detail || 'error', 'error'); }
      finally { window.STANNG.setLoading(e.currentTarget, false); }
    });
    if ($('resetAllBtn')) $('resetAllBtn').addEventListener('click', async () => {
      if (!confirm(window.STANNG.t('reset_all_confirm'))) return;
      await api('/api/inbounds/reset-all-usage', { method: 'POST' });
      if (window.STANNG_INBOUNDS) window.STANNG_INBOUNDS.reload();
    });
    if ($('cleanupBtn')) $('cleanupBtn').addEventListener('click', async () => {
      if (!confirm(window.STANNG.t('cleanup_confirm'))) return;
      const r = await api('/api/inbounds/cleanup', { method: 'POST', body: { mode: 'both' } });
      window.STANNG.toast(window.STANNG.t('cleanup_done').replace('{n}', r.removed), 'success');
      if (window.STANNG_INBOUNDS) window.STANNG_INBOUNDS.reload();
    });
    if ($('exportBtn')) $('exportBtn').addEventListener('click', async () => {
      const r = await api('/api/backup/export');
      const blob = new Blob([JSON.stringify(r, null, 2)], { type: 'application/json' });
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = `sspanel-backup-${new Date().toISOString().slice(0, 10)}.json`;
      a.click();
    });
    async function doImport(mode) {
      const f = $('importFile').files[0];
      if (!f) { window.STANNG.toast(window.STANNG.t('bk_select_file'), 'error'); return; }
      const text = await f.text();
      const data = JSON.parse(text);
      await api('/api/backup/import', { method: 'POST', body: { db: data.db || data, mode } });
      window.STANNG.toast(window.STANNG.t('bk_imported'), 'success');
      if (window.STANNG_INBOUNDS) window.STANNG_INBOUNDS.reload();
    }
    if ($('importMergeBtn')) $('importMergeBtn').addEventListener('click', () => doImport('merge').catch(e => window.STANNG.toast(e.detail || 'error', 'error')));
    if ($('importReplaceBtn')) $('importReplaceBtn').addEventListener('click', () => { if (confirm(window.STANNG.t('bk_replace_confirm'))) doImport('replace').catch(e => window.STANNG.toast(e.detail || 'error', 'error')); });
    if ($('saveExtrasBtn')) $('saveExtrasBtn').addEventListener('click', async (e) => {
      window.STANNG.setLoading(e.currentTarget, true);
      try {
        await api('/api/settings', { method: 'POST', body: {
          sub_remark_prefix: $('settingPrefix').value.trim() || 'SsPanel',
          auto_disable_exhausted: $('settingAutoDisable').checked,
          quota_warn_percent: parseFloat($('settingWarnPct').value || 80),
          expiry_warn_days: parseInt($('settingWarnDays').value || 3) } });
        window.STANNG.toast(window.STANNG.t('settings_saved'), 'success');
      } catch (err) { window.STANNG.toast(err.detail || 'error', 'error'); }
      finally { window.STANNG.setLoading(e.currentTarget, false); }
    });

    if ($('newPlanBtn')) $('newPlanBtn').addEventListener('click', () => {
      $('planId').value = ''; $('pName').value = ''; $('pTraffic').value = 50;
      $('pDuration').value = 30; $('pDevices').value = 1; $('pPrice').value = 0; $('pDesc').value = ''; $('pEnabled').checked = true;
      $('planModal').classList.add('open');
    });
    if ($('planSaveBtn')) $('planSaveBtn').addEventListener('click', async (e) => {
      window.STANNG.setLoading(e.currentTarget, true);
      try {
        const body = { name: $('pName').value.trim(), traffic_gb: parseFloat($('pTraffic').value || 0),
          duration_days: parseInt($('pDuration').value || 0), device_limit: parseInt($('pDevices').value || 0),
          price: parseFloat($('pPrice').value || 0),
          description: $('pDesc').value.trim(), enabled: $('pEnabled').checked };
        const pid = $('planId').value;
        if (pid) await api(`/api/plans/${pid}`, { method: 'PATCH', body });
        else await api('/api/plans', { method: 'POST', body });
        $('planModal').classList.remove('open');
        window.STANNG.toast(window.STANNG.t('settings_saved'), 'success');
        loadPlans();
      } catch (err) { window.STANNG.toast(err.detail || 'error', 'error'); }
      finally { window.STANNG.setLoading(e.currentTarget, false); }
    });
    if ($('assignPlanBtn')) $('assignPlanBtn').addEventListener('click', async (e) => {
      window.STANNG.setLoading(e.currentTarget, true);
      try {
        await api(`/api/inbounds/${$('assignUid').value}/apply-plan`, { method: 'POST', body: { plan_id: $('assignPlanSelect').value } });
        $('assignPlanModal').classList.remove('open');
        window.STANNG.toast(window.STANNG.t('settings_saved'), 'success');
        if (window.STANNG_INBOUNDS) window.STANNG_INBOUNDS.reload();
      } catch (err) { window.STANNG.toast(err.detail || 'error', 'error'); }
      finally { window.STANNG.setLoading(e.currentTarget, false); }
    });
    // ---- subscription management inside links modal ----
    async function refreshLinks() {
      const uid = window._lastUid;
      if (!uid) return;
      try {
        const r = await api(`/api/inbounds/${uid}/links`);
        window._lastLinks = r;
        $('linkSub').textContent = r.sub_url || '';
        const stLine = $('subStateLine');
        if (stLine) stLine.innerHTML = r.sub_enabled === false
          ? `<span style="color:var(--crimson)">● ${window.STANNG.t('sub_disabled')}</span>`
          : `<span style="color:var(--emerald)">● ${window.STANNG.t('sub_active')}</span>`;
      } catch (err) { window.STANNG.toast(err.detail || 'error', 'error'); }
    }
    if ($('subQrBtn')) $('subQrBtn').addEventListener('click', () => {
      const uid = window._lastUid;
      if (uid) $('qrImg').src = `/api/inbounds/${uid}/qr?link=sub&t=${Date.now()}`;
    });
    if ($('subRegenBtn')) $('subRegenBtn').addEventListener('click', async () => {
      const uid = window._lastUid;
      if (!uid || !confirm(window.STANNG.t('sub_regen_confirm'))) return;
      await api(`/api/inbounds/${uid}/regen-sub`, { method: 'POST' });
      window.STANNG.toast(window.STANNG.t('done'), 'success');
      refreshLinks();
    });
    if ($('subToggleBtn')) $('subToggleBtn').addEventListener('click', async () => {
      const uid = window._lastUid;
      if (!uid) return;
      await api(`/api/inbounds/${uid}/sub-toggle`, { method: 'POST' });
      refreshLinks();
    });
    if ($('configDlBtn')) $('configDlBtn').addEventListener('click', () => {
      const uid = window._lastUid;
      if (!uid) return;
      const a = document.createElement('a');
      a.href = `/api/inbounds/${uid}/config-file`;
      a.click();
    });
    if ($('xraySaveBtn')) $('xraySaveBtn').addEventListener('click', async (e) => {
      window.STANNG.setLoading(e.currentTarget, true);
      try {
        await api('/api/settings', { method: 'POST', body: { xray_log_level: $('xrayLogLevel').value } });
        await api('/api/xray/restart', { method: 'POST' });
        window.STANNG.toast(window.STANNG.t('settings_saved'), 'success');
        loadXray();
      } catch (err) { window.STANNG.toast(err.detail || 'error', 'error'); }
      finally { window.STANNG.setLoading(e.currentTarget, false); }
    });
    if ($('xrayRestartBtn')) $('xrayRestartBtn').addEventListener('click', async (e) => {
      window.STANNG.setLoading(e.currentTarget, true);
      try {
        await api('/api/xray/restart', { method: 'POST' });
        window.STANNG.toast(window.STANNG.t('done'), 'success');
        loadXray();
      } catch (err) { window.STANNG.toast(err.detail || 'error', 'error'); }
      finally { window.STANNG.setLoading(e.currentTarget, false); }
    });
    async function xrayOp(url, btn) {
      window.STANNG.setLoading(btn, true);
      try {
        const r = await api(url, { method: 'POST' });
        const el = $('xrayOpResult');
        if (el) el.innerHTML = `<span style="color:var(--emerald)">● ${escapeHtml(JSON.stringify(r.status || r))}</span>`;
        loadXray();
      } catch (err) {
        const el = $('xrayOpResult');
        if (el) el.innerHTML = `<span style="color:var(--crimson)">✖ ${escapeHtml(err.detail || 'error')}</span>`;
      }
      finally { window.STANNG.setLoading(btn, false); }
    }
    if ($('xrayStartBtn')) $('xrayStartBtn').addEventListener('click', (e) => xrayOp('/api/xray/start', e.currentTarget));
    if ($('xrayStopBtn')) $('xrayStopBtn').addEventListener('click', (e) => xrayOp('/api/xray/stop', e.currentTarget));
    if ($('xrayValidateBtn')) $('xrayValidateBtn').addEventListener('click', async (e) => {
      window.STANNG.setLoading(e.currentTarget, true);
      try {
        const r = await api('/api/xray/validate');
        const el = $('xrayOpResult');
        if (el) el.innerHTML = r.ok
          ? `<span style="color:var(--emerald)">● OK — ${r.inbounds} inbounds, ${r.clients} clients</span>`
          : `<span style="color:var(--crimson)">✖ ${(r.errors || []).map(escapeHtml).join('<br>')}</span>`;
      } catch (err) { window.STANNG.toast(err.detail || 'error', 'error'); }
      finally { window.STANNG.setLoading(e.currentTarget, false); }
    });

    // ---- phase 6 wiring: backups / diagnostics / shop ----
    if ($('snapBtn')) $('snapBtn').addEventListener('click', async (e) => {
      window.STANNG.setLoading(e.currentTarget, true);
      try {
        await api('/api/backups', { method: 'POST' });
        window.STANNG.toast(window.STANNG.t('done'), 'success');
        loadBackups();
      } catch (err) { window.STANNG.toast(err.detail || 'error', 'error'); }
      finally { window.STANNG.setLoading(e.currentTarget, false); }
    });
    if ($('bkSchedSave')) $('bkSchedSave').addEventListener('click', async (e) => {
      window.STANNG.setLoading(e.currentTarget, true);
      try {
        await api('/api/settings', { method: 'POST', body: {
          backup_enabled: $('bkEnabled').checked,
          backup_hour: parseInt($('bkHour').value || 4),
          backup_minute: parseInt($('bkMin').value || 0),
          backup_keep: parseInt($('bkKeep').value || 7),
          backup_send_telegram: $('bkTg').checked } });
        window.STANNG.toast(window.STANNG.t('settings_saved'), 'success');
      } catch (err) { window.STANNG.toast(err.detail || 'error', 'error'); }
      finally { window.STANNG.setLoading(e.currentTarget, false); }
    });
    const _dg = $('dgRunBtn');
    if (_dg) _dg.addEventListener('click', () => runDiagnostics(_dg));
    if ($('shopSaveBtn')) $('shopSaveBtn').addEventListener('click', async (e) => {
      window.STANNG.setLoading(e.currentTarget, true);
      try {
        await api('/api/settings', { method: 'POST', body: {
          shop_enabled: $('shopEnabled').checked,
          support_username: $('shopSupport').value.trim().replace(/^@/, ''),
          referral_bonus: parseFloat($('shopBonus').value || 0),
          shop_test_gb: parseFloat($('shopTestGb').value || 0),
          shop_test_days: parseInt($('shopTestDays').value || 0) } });
        window.STANNG.toast(window.STANNG.t('settings_saved'), 'success');
        loadTelegram();
      } catch (err) { window.STANNG.toast(err.detail || 'error', 'error'); }
      finally { window.STANNG.setLoading(e.currentTarget, false); }
    });

    // initial loads (dashboard visible by default)
    setTimeout(() => { loadTelegram(); loadSystem(); refreshUnread(); }, 800);
    setInterval(loadSystem, 15000);
    setInterval(refreshUnread, 20000);

    const _bell = $('notifBell');
    if (_bell) _bell.addEventListener('click', () => {
      const nav = document.querySelector('.nav-item[data-view="notifications"]');
      if (nav) nav.click();
    });
    // ---- AI chat wiring ----
    const _aiSend = $('aiSend');
    if (_aiSend) _aiSend.addEventListener('click', () => {
      const inp = $('aiInput');
      const v = inp.value.trim();
      if (!v) return;
      inp.value = '';
      window.PREMIUM.aiAsk(v);
    });
    const _aiInp = $('aiInput');
    if (_aiInp) _aiInp.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') { e.preventDefault(); _aiSend.click(); }
    });
    const _ruo = $('notifUnreadOnly');
    if (_ruo) _ruo.addEventListener('change', loadNotifications);
    const _ra = $('notifReadAll');
    if (_ra) _ra.addEventListener('click', async () => {
      await api('/api/notifications/read', { method: 'POST', body: { ids: 'all' } });
      loadNotifications();
    });

    // ---- security center wiring ----
    if ($('tfaSetupBtn')) $('tfaSetupBtn').addEventListener('click', async (e) => {
      window.STANNG.setLoading(e.currentTarget, true);
      try {
        const r = await api('/api/2fa/setup', { method: 'POST', body: { password: $('tfaPassword').value } });
        $('tfaSecret').textContent = r.secret;
        $('tfaQr').src = '/api/2fa/qr?t=' + Date.now();
        $('tfaEnroll').style.display = '';
        $('tfaCode').focus();
      } catch (err) { window.STANNG.toast(err.detail || 'error', 'error'); }
      finally { window.STANNG.setLoading(e.currentTarget, false); }
    });
    if ($('tfaVerifyBtn')) $('tfaVerifyBtn').addEventListener('click', async (e) => {
      window.STANNG.setLoading(e.currentTarget, true);
      try {
        await api('/api/2fa/verify', { method: 'POST', body: { code: $('tfaCode').value.trim() } });
        window.STANNG.toast(window.STANNG.t('done'), 'success');
        $('tfaEnroll').style.display = 'none';
        $('tfaPassword').value = ''; $('tfaCode').value = '';
        loadSecurity();
      } catch (err) { window.STANNG.toast(err.detail || 'error', 'error'); }
      finally { window.STANNG.setLoading(e.currentTarget, false); }
    });
    if ($('tfaDisableBtn')) $('tfaDisableBtn').addEventListener('click', async () => {
      if (!confirm(window.STANNG.t('sec_2fa_disable_confirm'))) return;
      try {
        await api('/api/2fa/disable', { method: 'POST', body: { password: $('tfaPassword').value } });
        window.STANNG.toast(window.STANNG.t('done'), 'success');
        $('tfaPassword').value = '';
        loadSecurity();
      } catch (err) { window.STANNG.toast(err.detail || 'error', 'error'); }
    });
    if ($('revokeBtn')) $('revokeBtn').addEventListener('click', async (e) => {
      if (!confirm(window.STANNG.t('sec_revoke_confirm'))) return;
      window.STANNG.setLoading(e.currentTarget, true);
      try {
        await api('/api/sessions/revoke-all', { method: 'POST', body: { password: $('revokePassword').value } });
        window.location.href = '/login';
      } catch (err) {
        window.STANNG.toast(err.detail || 'error', 'error');
        window.STANNG.setLoading(e.currentTarget, false);
      }
    });
    if ($('newAdminBtn')) $('newAdminBtn').addEventListener('click', () => {
      $('admId').value = ''; $('aName').value = ''; $('aName').disabled = false;
      $('aRole').value = 'viewer'; $('aPass').value = ''; $('aEnabled').checked = true;
      $('adminModal').classList.add('open');
    });
    if ($('adminSaveBtn')) $('adminSaveBtn').addEventListener('click', async (e) => {
      window.STANNG.setLoading(e.currentTarget, true);
      try {
        const aid = $('admId').value;
        if (aid) {
          const body = { role: $('aRole').value, enabled: $('aEnabled').checked };
          if ($('aPass').value) body.password = $('aPass').value;
          await api(`/api/admins/${aid}`, { method: 'PATCH', body });
        } else {
          await api('/api/admins', { method: 'POST', body: {
            username: $('aName').value.trim(), password: $('aPass').value, role: $('aRole').value } });
        }
        $('adminModal').classList.remove('open');
        window.STANNG.toast(window.STANNG.t('done'), 'success');
        loadSecurity();
      } catch (err) { window.STANNG.toast(err.detail || 'error', 'error'); }
      finally { window.STANNG.setLoading(e.currentTarget, false); }
    });

    // ---- servers wiring ----
    if ($('newServerBtn')) $('newServerBtn').addEventListener('click', () => {
      $('srvId').value = ''; $('sName').value = ''; $('sCountry').value = '';
      $('sHost').value = ''; $('sToken').value = ''; $('sNote').value = '';
      $('srvTestResult').innerHTML = '';
      $('serverModal').classList.add('open');
    });
    if ($('serverSaveBtn')) $('serverSaveBtn').addEventListener('click', async (e) => {
      window.STANNG.setLoading(e.currentTarget, true);
      $('srvTestResult').innerHTML = '';
      try {
        const sid = $('srvId').value;
        const body = { name: $('sName').value.trim(), host: $('sHost').value.trim(),
          country: $('sCountry').value.trim(), note: $('sNote').value.trim(),
          city: $('sCity').value.trim(), provider: $('sProvider').value.trim(),
          stype: $('sType').value, weight: parseInt($('sWeight').value || 100),
          maintenance: $('sMaint').checked };
        if ($('sToken').value.trim()) body.token = $('sToken').value.trim();
        if (sid) {
          if (!body.token) delete body.token;
          await api(`/api/servers/${sid}`, { method: 'PATCH', body });
        } else {
          if (!body.token) throw { detail: 'token-required' };
          body.token = $('sToken').value.trim();
          await api('/api/servers', { method: 'POST', body });
        }
        $('serverModal').classList.remove('open');
        window.STANNG.toast(window.STANNG.t('done'), 'success');
        loadServers();
      } catch (err) {
        $('srvTestResult').innerHTML = `<span style="color:var(--crimson)">✖ ${escapeHtml(err.detail || 'error')}</span>`;
      }
      finally { window.STANNG.setLoading(e.currentTarget, false); }
    });
    if ($('newServerBtn')) $('newServerBtn').addEventListener('click', () => {
      $('srvId').value = ''; $('sName').value = ''; $('sCountry').value = '';
      $('sHost').value = ''; $('sToken').value = ''; $('sNote').value = '';
      $('sCity').value = ''; $('sProvider').value = ''; $('sType').value = 'panel';
      $('sWeight').value = 100; $('sMaint').checked = false;
      $('srvTestResult').innerHTML = '';
      $('serverModal').classList.add('open');
    });
    if ($('lbToggle')) $('lbToggle').addEventListener('change', async (e) => {
      try {
        await api('/api/settings', { method: 'POST', body: { load_balancer_enabled: e.target.checked } });
        loadBest();
      } catch (err) { window.STANNG.toast(err.detail || 'error', 'error'); }
    });
    if ($('lbStrategy')) $('lbStrategy').addEventListener('change', async (e) => {
      try {
        await api('/api/settings', { method: 'POST', body: { lb_strategy: e.target.value } });
        loadBest();
      } catch (err) { window.STANNG.toast(err.detail || 'error', 'error'); }
    });
    if ($('newGroupBtn')) $('newGroupBtn').addEventListener('click', () => groupAction('new'));
    if ($('groupSaveBtn')) $('groupSaveBtn').addEventListener('click', async (e) => {
      window.STANNG.setLoading(e.currentTarget, true);
      try {
        const gid = $('grpId').value;
        const members = [...document.querySelectorAll('input[data-mem]:checked')].map(i => i.dataset.mem);
        if (gid) {
          await api(`/api/server-groups/${gid}`, { method: 'PATCH', body: { name: $('gName').value.trim(), description: $('gDesc').value.trim() } });
          await api(`/api/server-groups/${gid}/servers`, { method: 'POST', body: { server_ids: members } });
        } else {
          const r = await api('/api/server-groups', { method: 'POST', body: { name: $('gName').value.trim(), description: $('gDesc').value.trim() } });
          await api(`/api/server-groups/${r.group.id}/servers`, { method: 'POST', body: { server_ids: members } });
        }
        $('groupModal').classList.remove('open');
        loadServers();
      } catch (err) { window.STANNG.toast(err.detail || 'error', 'error'); }
      finally { window.STANNG.setLoading(e.currentTarget, false); }
    });
    if ($('assignOpenBtn')) $('assignOpenBtn').addEventListener('click', async () => {
      try {
        const [srv, plans] = await Promise.all([api('/api/servers'), api('/api/plans')]);
        $('asServer').innerHTML = [{ id: 'local', name: 'Local Server' }, ...srv.servers.filter(s => !s.local)]
          .map(s => `<option value="${s.id}">${escapeHtml(s.name)}</option>`).join('');
        $('asPlan').innerHTML = '<option value="">—</option>' + (plans.plans || []).filter(p => p.enabled)
          .map(p => `<option value="${p.id}">${escapeHtml(p.name)}</option>`).join('');
        $('asName').value = '';
        $('assignSrvModal').classList.add('open');
      } catch (e) { window.STANNG.toast(e.detail || 'error', 'error'); }
    });
    if ($('assignSrvBtn')) $('assignSrvBtn').addEventListener('click', async (e) => {
      window.STANNG.setLoading(e.currentTarget, true);
      try {
        const r = await api('/api/assign', { method: 'POST', body: {
          name: $('asName').value.trim() || 'User', server_id: $('asServer').value,
          plan_id: $('asPlan').value || undefined,
          quota_gb: parseFloat($('asQuota').value || 0), expire_days: parseInt($('asExpire').value || 0) } });
        $('assignSrvModal').classList.remove('open');
        const sub = r.inbound ? '' : (r.assignment ? ` (${r.assignment.id})` : '');
        window.STANNG.toast(`${window.STANNG.t('done')}${sub}`, 'success');
        loadServers();
        if (window.STANNG_INBOUNDS) window.STANNG_INBOUNDS.reload();
      } catch (err) { window.STANNG.toast(err.detail || 'error', 'error'); }
      finally { window.STANNG.setLoading(e.currentTarget, false); }
    });
    if ($('thSave')) $('thSave').addEventListener('click', async (e) => {
      window.STANNG.setLoading(e.currentTarget, true);
      try {
        await api('/api/settings', { method: 'POST', body: {
          alert_cpu: parseFloat($('thCpu').value || 80), alert_mem: parseFloat($('thMem').value || 85),
          alert_disk: parseFloat($('thDisk').value || 90), alert_latency_ms: parseFloat($('thLat').value || 1000),
          alert_conns: parseFloat($('thConns').value || 200),
          server_poll_interval: parseInt($('thPoll').value || 30) } });
        window.STANNG.toast(window.STANNG.t('settings_saved'), 'success');
      } catch (err) { window.STANNG.toast(err.detail || 'error', 'error'); }
      finally { window.STANNG.setLoading(e.currentTarget, false); }
    });
    if ($('cmpGo')) $('cmpGo').addEventListener('click', runCompare);
    // ---- analytics wiring ----
    document.querySelectorAll('#rangeBtns .range-btn').forEach(b => b.addEventListener('click', () => {
      document.querySelectorAll('#rangeBtns .range-btn').forEach(x => x.classList.remove('active'));
      b.classList.add('active');
      anRange = b.dataset.range;
      const custom = anRange === 'custom';
      $('rangeFrom').style.display = custom ? '' : 'none';
      $('rangeTo').style.display = custom ? '' : 'none';
      $('rangeGo').style.display = custom ? '' : 'none';
      if (!custom) loadAnalytics();
    }));
    if ($('rangeGo')) $('rangeGo').addEventListener('click', loadAnalytics);
  });

  // ---------- SERVERS ----------
  function svcDot(s) {
    if (s.online === true) return 'dot-ok';
    if (s.online === false) return 'dot-err';
    return 'dot-warn';
  }
  function timeAgo(ts) {
    if (!ts) return '—';
    const s = Math.max(0, Math.floor(Date.now() / 1000 - ts));
    if (s < 60) return window.STANNG.t('time_ago_s').replace('{n}', s);
    if (s < 3600) return window.STANNG.t('time_ago_m').replace('{n}', Math.floor(s / 60));
    return window.STANNG.t('time_ago_h').replace('{n}', Math.floor(s / 3600));
  }

  // ---------- PHASE 3: multi-server ----------
  function healthPill(s) {
    if (s.maintenance) return `<span class="pill pill-warn" style="font-size:.62rem;">MAINTENANCE</span>`;
    if (s.online === true) {
      const h = s.health;
      const cls = h == null ? 'pill-warn' : (h >= 70 ? 'pill-on' : (h >= 40 ? 'pill-warn' : 'pill-off'));
      return `<span class="pill ${cls}" style="font-size:.62rem;">Health ${h == null ? '?' : h}%</span>`;
    }
    if (s.online === false) return `<span class="pill pill-off" style="font-size:.62rem;">${window.STANNG.t('svc_offline')}</span>`;
    return `<span class="pill pill-warn" style="font-size:.62rem;">?</span>`;
  }

  function drawLine(cv, series, color) {
    if (!cv || !series.length) return;
    const dpr = window.devicePixelRatio || 1;
    const rect = cv.getBoundingClientRect();
    const W = Math.max(rect.width, 280), H = 160;
    cv.width = W * dpr; cv.height = H * dpr;
    cv.style.width = W + 'px'; cv.style.height = H + 'px';
    const ctx = cv.getContext('2d');
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, W, H);
    const max = Math.max(1, ...series.map(p => p[1]));
    const min = Math.min(0, ...series.map(p => p[1]));
    ctx.strokeStyle = getComputedStyle(document.documentElement).getPropertyValue('--border-soft') || '#444';
    for (let i = 0; i <= 3; i++) {
      const y = 10 + (H - 30) * i / 3;
      ctx.beginPath(); ctx.moveTo(34, y); ctx.lineTo(W - 8, y); ctx.stroke();
    }
    ctx.strokeStyle = color || '#e8b93e'; ctx.lineWidth = 2; ctx.beginPath();
    series.forEach((p, i) => {
      const x = 34 + (W - 42) * (series.length === 1 ? 1 : i / (series.length - 1));
      const y = 10 + (H - 30) * (1 - (p[1] - min) / Math.max(1e-9, max - min));
      if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    });
    ctx.stroke();
  }

  let _serversCache = [];
  let _groupsCache = [];

  async function loadServers() {
    try {
      const r = await api('/api/servers');
      const grid = $('serversGrid');
      if (!grid) return;
      $('navServerCount').textContent = r.servers.length;
      $('lbToggle').checked = !!r.load_balancer_enabled;
      _serversCache = r.servers;
      try {
        const g = await api('/api/server-groups');
        _groupsCache = g.groups || [];
      } catch (e) { _groupsCache = []; }
      renderGroups();
      grid.innerHTML = '';
      r.servers.forEach(s => {
        const m = s.metrics || {};
        const card = document.createElement('div');
        card.className = 'col-4 win stat-card';
        const sub = s.local ? 'local · v' + (m.version || '') :
          `${escapeHtml(s.host || '')} · ${escapeHtml(s.city || s.country || m.location || '')}`;
        const fmtR = (bps) => (bps == null || bps === undefined) ? '—'
          : (bps >= 1048576 ? (bps / 1048576).toFixed(2) + ' MB/s' : Math.round(bps / 1024) + ' KB/s');
        const diskLine = (m.disk_percent != null)
          ? `<div class="small muted">💾 ${m.disk_percent}%${m.disk_used_gb != null ? ` (${m.disk_used_gb}/${m.disk_total_gb} GB)` : ''}</div>` : '';
        const netLine = (m.net_up_bps != null || m.net_down_bps != null)
          ? `<div class="small muted">⇅ ⬆ ${fmtR(m.net_up_bps || 0)} · ⬇ ${fmtR(m.net_down_bps || 0)}</div>` : '';
        const compat = s.local ? '' : `<span class="small muted" style="direction:ltr;">${escapeHtml(s.version_compat || '')}</span>`;
        card.innerHTML = `
          <div class="label"><span class="dot ${svcDot(s)}"></span><span><b>${escapeHtml(s.name)}</b></span></div>
          <div class="small muted" style="direction:ltr; text-align:end;">${sub}</div>
          <div class="flex gap-8 mt-8" style="flex-wrap:wrap; align-items:center;">${healthPill(s)}
            ${s.load != null ? `<span class="small muted">Load ${s.load}%</span>` : ''}
            ${s.latency_ms != null ? `<span class="small muted" style="direction:ltr;">${s.latency_ms}ms</span>` : ''}${compat}</div>
          <div class="value" style="font-size:1.2rem;">${m.users || 0} <span class="small muted" style="font-size:.7rem;">${window.STANNG.t('dash_total_inbounds')}</span></div>
          <div class="small muted">${window.STANNG.fmtBytes((m.total_up || 0) + (m.total_down || 0))} · ${window.STANNG.t('dash_cpu')} ${m.cpu != null ? m.cpu + '%' : '—'} · RAM ${m.mem != null ? m.mem + '%' : '—'}</div>
          ${diskLine}${netLine}
          <div class="small muted">${window.STANNG.t('last_check')}: ${timeAgo(s.last_check)} · v${escapeHtml(m.version || '?')} · Xray ${escapeHtml(m.xray || '?')}</div>
          <div class="flex gap-8 mt-8" style="flex-wrap:wrap;">
            <button class="btn btn-azure btn-sm" data-sact="detail" data-sid="${s.id}">${window.STANNG.t('srv_detail')}</button>
            ${s.local ? '' : `<div class="flex gap-8" style="flex-wrap:wrap;">
              <button class="btn btn-ghost btn-sm" data-sact="test" data-sid="${s.id}">${window.STANNG.t('srv_test')}</button>
              <button class="btn btn-ghost btn-sm" data-sact="edit" data-sid="${s.id}">${window.STANNG.t('edit')}</button>
              <button class="btn btn-ghost btn-sm" data-sact="toggle" data-sid="${s.id}">${s.enabled ? window.STANNG.t('inb_disable') : window.STANNG.t('inb_enable')}</button>
              <button class="btn btn-ghost btn-sm" data-sact="failover" data-sid="${s.id}">${window.STANNG.t('srv_failover')}</button>
              <button class="btn btn-ghost btn-sm" data-sact="del" data-sid="${s.id}" style="color:var(--crimson)">${window.STANNG.t('delete')}</button>
            </div>`}
          </div>`;
        grid.appendChild(card);
      });
      grid.querySelectorAll('button[data-sact]').forEach(b => b.addEventListener('click', () => serverAction(b.dataset.sact, b.dataset.sid)));
      loadBest();
      loadAssignments();
    } catch (e) { window.STANNG.toast(e.detail || 'error', 'error'); }
  }

  async function loadBest() {
    try {
      const r = await api('/api/servers/best');
      const el = $('bestLine');
      if (!el) return;
      if ($('lbStrategy') && r.strategy) $('lbStrategy').value = r.strategy;
      if (!r.load_balancer_enabled) { el.textContent = window.STANNG.t('lb_off'); return; }
      const rec = (r.candidates || []).find(c => c.id === r.recommended);
      el.textContent = rec ? `★ ${rec.name} (${window.STANNG.t('lb_score')}: ${rec.score})` : '';
    } catch (e) { /* ignore */ }
  }

  async function serverAction(act, sid) {
    try {
      if (act === 'detail') return openServerDetail(sid);
      if (act === 'failover') return openFailover(sid);
      if (act === 'del') {
        if (!confirm(window.STANNG.t('srv_delete_confirm'))) return;
        await api(`/api/servers/${sid}`, { method: 'DELETE' });
      } else if (act === 'toggle') {
        const r = await api('/api/servers');
        const s = (r.servers || []).find(x => x.id === sid);
        await api(`/api/servers/${sid}`, { method: 'PATCH', body: { enabled: !(s && s.enabled) } });
        window.STANNG.toast(window.STANNG.t('settings_saved'), 'success');
      } else if (act === 'test') {
        const r = await api(`/api/servers/${sid}/test`, { method: 'POST' });
        window.STANNG.toast(`✔ ${r.metrics.users} ${window.STANNG.t('dash_total_inbounds')} · ${window.STANNG.t('dash_cpu')} ${r.metrics.cpu}%`, 'success');
      } else if (act === 'edit') {
        const r = await api('/api/servers');
        const s = (r.servers || []).find(x => x.id === sid);
        if (!s || s.local) return;
        $('srvId').value = s.id; $('sName').value = s.name; $('sCountry').value = s.country || '';
        $('sHost').value = s.host || ''; $('sToken').value = ''; $('sNote').value = s.note || '';
        $('srvTestResult').innerHTML = '';
        $('serverModal').classList.add('open');
        return;
      }
      loadServers();
    } catch (e) { window.STANNG.toast(e.detail || 'error', 'error'); }
  }

  // ---------- PHASE 3: groups ----------
  function renderGroups() {
    const box = $('groupsBox');
    if (!box) return;
    if (!_groupsCache.length) {
      box.innerHTML = `<div class="muted small">${window.STANNG.t('grp_empty')}</div>`;
      return;
    }
    const names = {};
    _serversCache.forEach(s => { names[s.id] = s.name; });
    names['local'] = 'Local Server';
    box.innerHTML = _groupsCache.map(g => `
      <div class="svc-row"><span class="svc-name">📁 <b>${escapeHtml(g.name)}</b>
        <span class="small muted">${(g.server_ids || []).map(id => escapeHtml(names[id] || id)).join(', ') || '—'}</span></span>
        <span class="flex gap-8">
          <button class="btn btn-ghost btn-sm" data-grp="edit" data-gid="${g.id}">${window.STANNG.t('edit')}</button>
          <button class="btn btn-ghost btn-sm" data-grp="del" data-gid="${g.id}" style="color:var(--crimson)">${window.STANNG.t('delete')}</button>
        </span></div>`).join('');
    box.querySelectorAll('button[data-grp]').forEach(b => b.addEventListener('click', () => groupAction(b.dataset.grp, b.dataset.gid)));
  }

  async function groupAction(act, gid) {
    if (act === 'del') {
      if (!confirm(window.STANNG.t('grp_del_confirm'))) return;
      try { await api(`/api/server-groups/${gid}`, { method: 'DELETE' }); loadServers(); }
      catch (e) { window.STANNG.toast(e.detail || 'error', 'error'); }
      return;
    }
    const g = _groupsCache.find(x => x.id === gid);
    $('grpId').value = gid || '';
    $('gName').value = g ? g.name : '';
    $('gDesc').value = g ? (g.description || '') : '';
    const mem = $('gMembers');
    const all = [{ id: 'local', name: 'Local Server' }, ..._serversCache.filter(s => !s.local)];
    mem.innerHTML = all.map(s => `<label class="small flex items-center gap-8"><input type="checkbox" data-mem="${s.id}" ${g && (g.server_ids || []).includes(s.id) ? 'checked' : ''}> ${escapeHtml(s.name)}</label>`).join('');
    $('groupModal').classList.add('open');
  }

  // ---------- PHASE 3: server detail drawer ----------
  let _sdSid = null, _sdTab = 'overview';
  async function openServerDetail(sid) {
    _sdSid = sid; _sdTab = 'overview';
    document.querySelectorAll('.sd-tab').forEach(b => {
      b.classList.toggle('active', b.dataset.tab === 'overview');
      b.onclick = () => { _sdTab = b.dataset.tab; document.querySelectorAll('.sd-tab').forEach(x => x.classList.toggle('active', x === b)); renderServerDetail(); };
    });
    $('serverDetailModal').classList.add('open');
    renderServerDetail();
  }
  async function renderServerDetail() {
    const box = $('sdBody');
    if (!box || !_sdSid) return;
    box.innerHTML = '<div class="muted small">…</div>';
    try {
      const s = (_serversCache.find(x => x.id === _sdSid)) || (await api('/api/servers')).servers.find(x => x.id === _sdSid);
      if (!s) { box.innerHTML = '—'; return; }
      $('sdTitle').textContent = s.name || _sdSid;
      const m = s.metrics || {};
      if (_sdTab === 'overview') {
        box.innerHTML = `
          <div class="svc-row"><span class="svc-name">Status</span>${healthPill(s)}</div>
          <div class="svc-row"><span class="svc-name">Host</span><span class="small muted" style="direction:ltr;">${escapeHtml(s.host || 'local')}</span></div>
          <div class="svc-row"><span class="svc-name">${window.STANNG.t('srv_city')}/${window.STANNG.t('srv_country')}</span><span class="small muted">${escapeHtml([s.city, s.country, m.location].filter(Boolean).join(' · ') || '—')}</span></div>
          <div class="svc-row"><span class="svc-name">${window.STANNG.t('srv_provider')}</span><span class="small muted">${escapeHtml(s.provider || m.platform || '—')}</span></div>
          <div class="svc-row"><span class="svc-name">IP/Port</span><span class="small muted" style="direction:ltr;">${escapeHtml(s.ip || '—')} : ${s.port || 443}</span></div>
          <div class="svc-row"><span class="svc-name">Version</span><span class="small muted" style="direction:ltr;">${escapeHtml(m.version || '?')} (${escapeHtml(s.version_compat || '?')})</span></div>
          <div class="svc-row"><span class="svc-name">CPU/RAM/Disk</span><span class="small muted">${m.cpu ?? '—'}% / ${m.mem ?? '—'}% / ${m.disk_percent ?? '—'}%</span></div>
          <div class="svc-row"><span class="svc-name">Load</span><b>${s.load ?? '—'}%</b></div>
          <div class="svc-row"><span class="svc-name">Latency</span><span class="small muted">${s.latency_ms ?? '—'} ms</span></div>
          <div class="svc-row"><span class="svc-name">Users/Traffic</span><span class="small muted">${m.users || 0} · ${window.STANNG.fmtBytes((m.total_up || 0) + (m.total_down || 0))}</span></div>
          <div class="svc-row"><span class="svc-name">Weight</span><span class="small muted">${s.weight || 100}</span></div>`;
      } else if (_sdTab === 'metrics') {
        const r = await api(`/api/servers/${_sdSid}/metrics?range=24h`);
        const sm = r.samples || [];
        box.innerHTML = `<div class="small muted mb-8">CPU %</div><canvas id="sdCpu" height="150"></canvas>
          <div class="small muted mb-8 mt-12">Latency ms</div><canvas id="sdLat" height="150"></canvas>`;
        drawLine($('sdCpu'), sm.map(p => [p.ts, p.cpu || 0]), '#e8b93e');
        drawLine($('sdLat'), sm.map(p => [p.ts, p.latency || 0]), '#4aa8ff');
        if (!sm.length) box.innerHTML += `<div class="muted small mt-8">${window.STANNG.t('sd_no_data')}</div>`;
      } else if (_sdTab === 'users') {
        const r = await api(`/api/servers/${_sdSid}/users`);
        const us = r.users || [];
        box.innerHTML = us.length
          ? us.slice(0, 50).map(u => `<div class="audit-item"><b>${escapeHtml(u.name || '')}</b><span class="muted">${window.STANNG.fmtBytes((u.used_up || 0) + (u.used_down || 0))}</span></div>`).join('')
          : `<div class="muted small">—</div>`;
      } else if (_sdTab === 'events') {
        const r = await api(`/api/servers/${_sdSid}/events`);
        box.innerHTML = (r.events || []).length
          ? r.events.map(l => `<div class="audit-item"><span class="audit-time">${fmtTime(l.ts)}</span><b>${escapeHtml(l.actor || '')}</b><span class="pill" style="font-size:.62rem;">${escapeHtml(window.ALOO_ACTION ? window.ALOO_ACTION(l.action) : (l.action || ''))}</span><span class="muted">${escapeHtml(l.detail || '')}</span></div>`).join('')
          : `<div class="muted small">—</div>`;
      } else if (_sdTab === 'alerts') {
        const r = await api(`/api/servers/${_sdSid}/alerts`);
        box.innerHTML = (r.alerts || []).length
          ? r.alerts.map(a => `<div class="alert-row"><span class="dot ${a.status === 'active' ? 'dot-err' : 'dot-ok'}"></span><span class="msg"><b>${escapeHtml(a.type)}</b> ${a.value ?? ''} / ${a.threshold ?? ''}</span><span class="small muted">${escapeHtml(a.status)}</span></div>`).join('')
          : `<div class="muted small">—</div>`;
      }
    } catch (e) { box.innerHTML = `<div class="muted small">${escapeHtml(e.detail || 'error')}</div>`; }
  }

  // ---------- PHASE 3: assignments + failover ----------
  async function loadAssignments() {
    try {
      const r = await api('/api/assignments');
      const tb = $('assignBody');
      if (!tb) return;
      tb.innerHTML = '';
      const names = { local: 'Local Server' };
      _serversCache.forEach(s => { names[s.id] = s.name; });
      (r.assignments || []).forEach(a => {
        const tr = document.createElement('tr');
        tr.innerHTML = `<td><b>${escapeHtml(a.name)}</b><div class="small muted">${a.id}</div></td>
          <td>${escapeHtml(names[a.server_id] || a.server_id)}</td>
          <td><span class="pill ${a.status === 'active' ? 'pill-on' : 'pill-warn'}" style="font-size:.62rem;">${escapeHtml(a.status)}</span></td>
          <td>${a.status === 'active' ? `<button class="btn btn-ghost btn-sm" data-fo="${a.server_id}" data-aid="${a.id}">${window.STANNG.t('srv_failover')}</button>` : ''}</td>`;
        tb.appendChild(tr);
      });
      if (!(r.assignments || []).length) tb.innerHTML = '<tr><td colspan="4" class="muted small" style="text-align:center;">—</td></tr>';
      tb.querySelectorAll('button[data-fo]').forEach(b => b.addEventListener('click', () => openFailover(b.dataset.fo, b.dataset.aid)));
    } catch (e) { /* perm-gated */ }
  }
  async function openFailover(sid, presetAid) {
    try {
      const r = await api('/api/assignments');
      const list = (r.assignments || []).filter(a => a.server_id === sid && a.status === 'active');
      if (!list.length) { window.STANNG.toast(window.STANNG.t('srv_no_assign'), 'error'); return; }
      const aid = presetAid || list[0].id;
      const fo = await api(`/api/servers/${sid}/failover`, { method: 'POST', body: { assignment_id: aid } });
      const alts = fo.alternatives || [];
      if (!alts.length) { window.STANNG.toast(window.STANNG.t('srv_no_alt'), 'error'); return; }
      const pick = prompt(`${window.STANNG.t('srv_failover')}: ${alts.map((a, i) => `\n${i + 1}. ${a.name} (score ${a.score})`).join('')}\n\n#?`, '1');
      const idx = parseInt(pick || '0', 10) - 1;
      if (!alts[idx] || !confirm(window.STANNG.t('srv_fo_confirm').replace('{name}', alts[idx].name))) return;
      const done = await api(`/api/servers/${sid}/failover`, { method: 'POST', body: { assignment_id: aid, confirm: true, target: alts[idx].id } });
      window.STANNG.toast(window.STANNG.t('done'), 'success');
      loadAssignments();
      if (window.STANNG_INBOUNDS) window.STANNG_INBOUNDS.reload();
    } catch (e) { window.STANNG.toast(e.detail || 'error', 'error'); }
  }

  // ---------- PHASE 3: alerts / map / compare ----------
  async function loadAlerts() {
    try {
      const [act, res] = await Promise.all([
        api('/api/alerts?status=active'), api('/api/alerts?status=resolved')]);
      $('navAlertCount').textContent = act.alerts.length;
      $('navAlertCount').style.display = act.alerts.length ? '' : 'none';
      $('alertsActiveCount').textContent = act.alerts.length;
      const tb = $('alertsActiveBody');
      tb.innerHTML = '';
      (act.alerts || []).forEach(a => {
        const tr = document.createElement('tr');
        tr.innerHTML = `<td><b>${escapeHtml(a.server_name || a.server_id)}</b><div class="small muted">${fmtTime(a.opened_at)}</div></td>
          <td><span class="pill ${a.severity === 'error' ? 'pill-off' : 'pill-warn'}" style="font-size:.62rem;">${escapeHtml(a.type)}</span></td>
          <td class="small">${a.value ?? '—'} / ${a.threshold ?? '—'}</td>
          <td class="small muted">${fmtTime(a.opened_at)}</td>`;
        tb.appendChild(tr);
      });
      if (!(act.alerts || []).length) tb.innerHTML = '<tr><td colspan="4" class="muted small" style="text-align:center;">—</td></tr>';
      $('alertsResolvedBox').innerHTML = (res.alerts || []).slice(0, 15).map(a =>
        `<div class="alert-row"><span class="dot dot-ok"></span><span class="msg">${escapeHtml(a.server_name || '')} · <b>${escapeHtml(a.type)}</b></span></div>`).join('') || '<div class="muted small">—</div>';
    } catch (e) { /* perm-gated */ }
  }
  async function loadThresholds() {
    try {
      const me = await api('/api/me');
      const s = me.settings || {};
      if ($('thCpu')) $('thCpu').value = s.alert_cpu ?? 80;
      if ($('thMem')) $('thMem').value = s.alert_mem ?? 85;
      if ($('thDisk')) $('thDisk').value = s.alert_disk ?? 90;
      if ($('thLat')) $('thLat').value = s.alert_latency_ms ?? 1000;
      if ($('thConns')) $('thConns').value = s.alert_conns ?? 200;
      if ($('thPoll')) $('thPoll').value = s.server_poll_interval ?? 30;
      if ($('lbStrategy')) $('lbStrategy').value = s.lb_strategy || 'least_load';
    } catch (e) { /* ignore */ }
  }
  async function loadMap() {
    const board = $('mapBoard');
    if (!board) return;
    try {
      const r = await api('/api/servers');
      const groups = {};
      r.servers.forEach(s => {
        const m = s.metrics || {};
        const key = s.local ? 'Local' : (s.country || m.location || '?');
        (groups[key] = groups[key] || []).push(s);
      });
      board.innerHTML = Object.keys(groups).sort().map(k => `
        <div class="win"><div class="win-head"><h3>📍 ${escapeHtml(k)} (${groups[k].length})</h3></div>
        <div class="win-body"><div class="grid">${groups[k].map(s => {
          const m = s.metrics || {};
          const bg = s.maintenance ? 'pill-warn' : (s.online === true ? 'pill-on' : (s.online === false ? 'pill-off' : 'pill-warn'));
          return `<div class="col-4 win stat-card" data-mapdetail="${s.id}" style="cursor:pointer;">
            <div class="label"><span class="dot ${s.maintenance ? 'dot-warn' : svcDot(s).split(' ')[0]}"></span><b>${escapeHtml(s.name)}</b></div>
            <div class="value" style="font-size:1.1rem;">${s.health != null ? s.health + '%' : '—'}</div>
            <div class="small muted">Load ${s.load ?? '—'}% · ${m.users || 0} users · ${s.latency_ms ?? '—'}ms</div>
            <div class="mt-8"><span class="pill ${bg}" style="font-size:.62rem;">${s.maintenance ? 'MAINTENANCE' : (s.online === true ? window.STANNG.t('svc_online') : '?')}</span></div>
          </div>`;
        }).join('')}</div></div></div>`).join('');
      board.querySelectorAll('[data-mapdetail]').forEach(el =>
        el.addEventListener('click', () => openServerDetail(el.dataset.mapdetail)));
    } catch (e) { board.innerHTML = '<div class="muted">—</div>'; }
  }
  async function loadCompare() {
    try {
      const [srv, best] = await Promise.all([api('/api/servers'), api('/api/servers/best')]);
      const box = $('cmpChecks');
      box.innerHTML = '';
      srv.servers.forEach(s => {
        const lb = document.createElement('label');
        lb.className = 'small flex items-center gap-8';
        lb.innerHTML = `<input type="checkbox" data-cmp="${s.id}" checked> ${escapeHtml(s.name)}`;
        box.appendChild(lb);
      });
      const tb = $('topBody');
      tb.innerHTML = '';
      [...best.candidates].sort((a, b) => (b.health ?? 50) - (a.health ?? 50)).slice(0, 10).forEach((c, i) => {
        const tr = document.createElement('tr');
        tr.innerHTML = `<td>${i + 1}</td><td><b>${escapeHtml(c.name)}</b></td><td>${c.health ?? '—'}%</td><td>${c.load ?? c.score}%</td><td>${c.cpu}%</td><td>${c.latency_ms ?? '—'} ms</td><td>—</td>`;
        tb.appendChild(tr);
      });
    } catch (e) { /* ignore */ }
  }
  async function runCompare() {
    try {
      const ids = [...document.querySelectorAll('input[data-cmp]:checked')].map(i => i.dataset.cmp);
      const r = await api('/api/servers');
      const rows = r.servers.filter(s => ids.includes(s.id));
      const metrics = [['Health %', s => s.health ?? '—'], ['Load %', s => s.load ?? '—'],
        ['CPU %', s => (s.metrics || {}).cpu ?? '—'], ['RAM %', s => (s.metrics || {}).mem ?? '—'],
        ['Disk %', s => (s.metrics || {}).disk_percent ?? '—'],
        ['Users', s => (s.metrics || {}).users ?? '—'],
        ['Traffic', s => window.STANNG.fmtBytes(((s.metrics || {}).total_up || 0) + ((s.metrics || {}).total_down || 0))],
        ['Conns', s => (s.metrics || {}).active_connections ?? '—'],
        ['Latency', s => (s.latency_ms ?? '—') + (s.latency_ms != null ? ' ms' : '')],
        ['Version', s => ((s.metrics || {}).version || '?') + ' / ' + (s.version_compat || '?')]];
      $('cmpHead').innerHTML = '<th></th>' + rows.map(s => `<th>${escapeHtml(s.name)}</th>`).join('');
      $('cmpBody').innerHTML = metrics.map(([label, fn]) =>
        `<tr><td><b>${label}</b></td>` + rows.map(s => `<td>${escapeHtml(String(fn(s)))}</td>`).join('') + `</tr>`).join('');
    } catch (e) { window.STANNG.toast(e.detail || 'error', 'error'); }
  }
  async function loadMsStrip() {
    const strip = $('msStrip');
    if (!strip) return;
    try {
      const [r, lv] = await Promise.all([api('/api/servers'), api('/api/live')]);
      const remotes = r.servers.filter(s => !s.local);
      const on = remotes.filter(s => s.online === true).length;
      const off = remotes.filter(s => s.online === false).length;
      const maint = remotes.filter(s => s.maintenance).length;
      const gconns = remotes.reduce((a, s) => a + (((s.metrics || {}).active_connections) || 0), 0) + (lv.active_connections || 0);
      if (!remotes.length) { strip.style.display = 'none'; return; }
      strip.style.display = '';
      $('msStripBody').innerHTML = `
        <span>🖥 <b>${r.servers.length}</b> ${window.STANNG.t('nav_servers')}</span>
        <span><span class="dot dot-ok"></span> ${on}</span>
        <span><span class="dot dot-err"></span> ${off}</span>
        <span><span class="dot dot-warn"></span> ${maint} MAINT</span>
        <span>⇅ <b>${gconns}</b> conns</span>`;
    } catch (e) { strip.style.display = 'none'; }
  }
  async function loadAnalytics() {
    try {
      let url = '/api/analytics?range=' + anRange;
      if (anRange === 'custom') {
        const f = $('rangeFrom').value, t = $('rangeTo').value;
        if (!f || !t) { window.STANNG.toast(window.STANNG.t('range_select'), 'error'); return; }
        url += `&from_ts=${new Date(f).getTime() / 1000}&to_ts=${new Date(t).getTime() / 1000}`;
      }
      const r = await api(url);
      $('anTotal').textContent = window.STANNG.fmtBytes(r.total || 0);
      $('anUp').textContent = window.STANNG.fmtBytes(r.total_up || 0);
      $('anDown').textContent = window.STANNG.fmtBytes(r.total_down || 0);
      $('anPeak').textContent = r.peak_hour
        ? `${window.STANNG.fmtBytes(r.peak_hour.up + r.peak_hour.down)} @ ${new Date(r.peak_hour.t * 1000).getHours()}:00`
        : '—';
      $('retentionNote').textContent = r.partial
        ? `⚠ ${window.STANNG.t('an_partial')} (~${r.retention_hours}h)`
        : `✓ ~${r.retention_hours}h`;
      renderTrafficChart($('analyticsChart'), r.buckets || []);
      const tb = $('anTopBody');
      tb.innerHTML = '';
      (r.top_users || []).forEach(u => {
        const tr = document.createElement('tr');
        tr.innerHTML = `<td><b>${escapeHtml(u.name)}</b></td><td class="small">${window.STANNG.fmtBytes(u.used)}</td>`;
        tb.appendChild(tr);
      });
      if (!(r.top_users || []).length) tb.innerHTML = '<tr><td class="muted small">—</td></tr>';
      const sb = $('anSrvBody');
      sb.innerHTML = '';
      (r.per_server || []).forEach(s => {
        const tr = document.createElement('tr');
        tr.innerHTML = `<td><b>${escapeHtml(s.name)}</b></td><td>${window.STANNG.fmtBytes(s.up || 0)}</td><td>${window.STANNG.fmtBytes(s.down || 0)}</td><td>${window.STANNG.fmtBytes((s.up || 0) + (s.down || 0))}</td><td>${s.users || 0}</td>`;
        sb.appendChild(tr);
      });
      try {
        const g = await api('/api/server-groups');
        const byId = {};
        (r.per_server || []).forEach(s => { byId[s.id] = s; });
        (g.groups || []).forEach(gr => {
          let up = 0, down = 0, users = 0;
          (gr.server_ids || []).forEach(id => {
            const s = byId[id];
            if (s) { up += s.up || 0; down += s.down || 0; users += s.users || 0; }
          });
          const tr = document.createElement('tr');
          tr.innerHTML = `<td>📁 <b>${escapeHtml(gr.name)}</b></td><td>${window.STANNG.fmtBytes(up)}</td><td>${window.STANNG.fmtBytes(down)}</td><td>${window.STANNG.fmtBytes(up + down)}</td><td>${users}</td>`;
          sb.appendChild(tr);
        });
      } catch (e) { /* perm-gated */ }
    } catch (e) { window.STANNG.toast(e.detail || 'error', 'error'); }
  }

  // ---------- LIVE ----------
  let liveTimer = null;
  const cpuHist = [];
  function drawCpuLine() {
    const cv = $('liveCpuChart');
    if (!cv || !cpuHist.length) return;
    const dpr = window.devicePixelRatio || 1;
    const rect = cv.getBoundingClientRect();
    const W = Math.max(rect.width, 280), H = 180;
    cv.width = W * dpr; cv.height = H * dpr;
    cv.style.width = W + 'px'; cv.style.height = H + 'px';
    const ctx = cv.getContext('2d');
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, W, H);
    const styles = getComputedStyle(document.documentElement);
    const gold = styles.getPropertyValue('--gold-500').trim() || '#c9a227';
    ctx.strokeStyle = gold; ctx.lineWidth = 2; ctx.beginPath();
    cpuHist.forEach((v, i) => {
      const x = (i / Math.max(1, cpuHist.length - 1)) * (W - 16) + 8;
      const y = H - 12 - (Math.min(100, v) / 100) * (H - 32);
      if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    });
    ctx.stroke();
    ctx.fillStyle = styles.getPropertyValue('--text-muted').trim() || '#888';
    ctx.font = '10px sans-serif';
    ctx.fillText('100%', 4, 12); ctx.fillText('0%', 4, H - 4);
  }

  async function liveTick() {
    try {
      const r = await api('/api/live');
      $('liveCpu').textContent = r.cpu_percent.toFixed(1) + '%';
      $('liveMem').textContent = r.mem_percent.toFixed(1) + '%';
      const fmtR = (bps) => bps >= 1048576 ? (bps / 1048576).toFixed(2) + ' MB/s' : Math.round(bps / 1024) + ' KB/s';
      $('liveNetUp').textContent = fmtR(r.net_up_bps || 0);
      $('liveNetDown').textContent = fmtR(r.net_down_bps || 0);
      cpuHist.push(r.cpu_percent || 0);
      if (cpuHist.length > 40) cpuHist.shift();
      drawCpuLine();
      const box = $('liveBox');
      if (box) {
        const x = (r.xray || {}).status;
        box.innerHTML = `
          <div class="svc-row"><span class="svc-name"><span class="dot ${x === 'online' ? 'dot-ok' : (x === 'mock' ? 'dot-warn' : 'dot-err')}"></span>${window.STANNG.t('svc_xray')}</span><span class="small muted">${x}</span></div>
          <div class="svc-row"><span class="svc-name"><span class="dot dot-ok"></span>${window.STANNG.t('dash_active_conn')}</span><b>${r.active_connections || 0}</b></div>
          <div class="svc-row"><span class="svc-name"><span class="dot dot-ok"></span>${window.STANNG.t('dash_total_inbounds')}</span><b>${r.users || 0}</b></div>
          <div class="svc-row"><span class="svc-name"><span class="dot dot-ok"></span>${window.STANNG.t('dash_uptime')}</span><span class="small muted">${window.STANNG.fmtDuration(r.uptime_seconds || 0)}</span></div>`;
      }
    } catch (e) { /* transient */ }
  }
  function startLive() { stopLive(); liveTick(); liveTimer = setInterval(liveTick, 3000); }
  function stopLive() { if (liveTimer) { clearInterval(liveTimer); liveTimer = null; } }

  // ---------- NOTIFICATIONS ----------
  function ntfText(n) {
    const key = 'ntf_' + (n.code || '');
    let tpl = window.STANNG.t(key);
    if (tpl === key) tpl = (n.code || '').replace(/_/g, ' ');
    const p = n.params || {};
    return tpl.replace(/\{(\w+)\}/g, (m, k) => (k in p ? escapeHtml(p[k]) : m));
  }

  function paintUnread(count) {
    const b = $('notifCount'), nav = $('navNotifCount');
    [[b, count], [nav, count]].forEach(([el, v]) => {
      if (!el) return;
      el.textContent = v > 99 ? '99+' : v;
      el.style.display = v > 0 ? '' : 'none';
    });
  }

  async function refreshUnread() {
    try {
      const r = await api('/api/notifications?limit=1');
      paintUnread(r.unread || 0);
    } catch (e) { /* transient */ }
  }

  async function loadNotifications() {
    const box = $('notifBox');
    if (!box) return;
    try {
      const onlyUnread = $('notifUnreadOnly') && $('notifUnreadOnly').checked;
      const r = await api('/api/notifications?limit=100' + (onlyUnread ? '&unread_only=true' : ''));
      paintUnread(r.unread || 0);
      const list = r.notifications || [];
      if (!list.length) {
        box.innerHTML = `<div class="empty-state small">${window.STANNG.t('ntf_empty')}</div>`;
        return;
      }
      box.innerHTML = list.map(n => {
        const dot = n.severity === 'error' ? 'dot-err' : (n.severity === 'warning' ? 'dot-warn' : 'dot-ok');
        let time = '';
        try { time = new Date(n.ts * 1000).toLocaleString(window.STANNG.getLang() === 'fa' ? 'fa-IR' : 'en-US'); } catch (e) {}
        return `<div class="notif-item${n.read ? '' : ' unread'}"><span class="dot ${dot}" style="margin-top:5px;"></span><span class="body">${ntfText(n)}</span><span class="time">${time}</span></div>`;
      }).join('');
    } catch (e) { box.innerHTML = '<div class="muted small">—</div>'; }
  }

  // ---------- SECURITY CENTER ----------
  async function loadSecurity() {
    try {
      const me = await api('/api/me');
      const pill = $('tfaPill');
      if (pill) {
        pill.textContent = me.totp_enabled ? '● ' + window.STANNG.t('sec_2fa_on') : '○ ' + window.STANNG.t('sec_2fa_off');
        pill.className = 'pill ' + (me.totp_enabled ? 'pill-on' : 'pill-off');
      }
      $('tfaDisableBtn').style.display = me.totp_enabled ? '' : 'none';
      let sessHtml = `👤 <b>${escapeHtml(me.username || '')}</b> · ${escapeHtml(me.role || '')} · 2FA ${me.totp_enabled ? '✓' : '—'}`;
      $('sessionInfo').innerHTML = sessHtml;
    } catch (e) { /* ignore */ }
    try {
      const ov = await api('/api/security/overview');
      $('failedCount').textContent = ov.failed_24h || 0;
      const box = $('locksBox');
      let html = `<div class="small muted">${window.STANNG.t('sec_policy')
        .replace('{n}', ov.policy.min_password_len)
        .replace('{a}', ov.policy.max_attempts)
        .replace('{s}', ov.policy.lock_seconds)}</div>`;
      if ((ov.locked_ips || []).length) {
        html += ov.locked_ips.map(l => `<div class="svc-row"><span class="svc-name"><span class="dot dot-err"></span><code style="direction:ltr;">${escapeHtml(l.ip)}</code></span><span><span class="small muted">${l.remaining}s</span> <button class="btn btn-ghost btn-sm" data-unblock="${escapeHtml(l.ip)}">${window.STANNG.t('sec_unblock')}</button></span></div>`).join('');
      } else {
        html += `<div class="small muted">${window.STANNG.t('sec_no_locks')}</div>`;
      }
      if ((ov.recent_failed || []).length) {
        html += `<div class="small muted mt-8"><b>${window.STANNG.t('sec_recent_failed')}</b></div>` + ov.recent_failed.map(l => {
          let t = '';
          try { t = new Date(l.ts * 1000).toLocaleString(window.STANNG.getLang() === 'fa' ? 'fa-IR' : 'en-US'); } catch (e) {}
          return `<div class="audit-item"><span class="audit-time">${t}</span><b>${escapeHtml(l.actor || '')}</b><span class="muted">${escapeHtml(l.detail || '')}</span></div>`;
        }).join('');
      }
      box.innerHTML = html;
      box.querySelectorAll('button[data-unblock]').forEach(b => b.addEventListener('click', async () => {
        await api('/api/security/unblock', { method: 'POST', body: { ip: b.dataset.unblock } });
        loadSecurity();
      }));
      if ((ov.recent_logins || []).length) {
        const si = $('sessionInfo');
        si.innerHTML += `<div class="mt-8"><div class="small muted mb-8"><b>${window.STANNG.t('sec_recent_logins')}</b></div>` +
          ov.recent_logins.slice(0, 8).map(l => {
            let t = '';
            try { t = new Date(l.ts * 1000).toLocaleString(window.STANNG.getLang() === 'fa' ? 'fa-IR' : 'en-US'); } catch (e) {}
            return `<div class="audit-item"><span class="audit-time">${t}</span><b>${escapeHtml(l.actor || '')}</b>${l.ip ? `<code class="small" style="direction:ltr;">${escapeHtml(l.ip)}</code>` : ''}</div>`;
          }).join('') + `</div>`;
      }
    } catch (e) {
      $('locksBox').innerHTML = `<div class="muted small">${window.STANNG.t('forbidden') || 'forbidden'}</div>`;
    }
    try {
      const r = await api('/api/admins');
      $('adminsCard').style.display = '';
      const tb = $('adminsBody');
      tb.innerHTML = '';
      r.admins.forEach(a => {
        const tr = document.createElement('tr');
        tr.innerHTML = `<td><b>${escapeHtml(a.username)}</b>${a.is_self ? ' (' + window.STANNG.t('sec_you') + ')' : ''}${a.totp_enabled ? ' 🔑' : ''}</td>
          <td><span class="pill" style="font-size:.66rem;">${escapeHtml(a.role)}</span></td>
          <td>${a.totp_enabled ? '✓' : '—'}</td>
          <td>${a.enabled ? `<span class="pill pill-on"><span class="pill-dot"></span>${window.STANNG.t('active')}</span>` : `<span class="pill pill-off"><span class="pill-dot"></span>${window.STANNG.t('inactive')}</span>`}</td>
          <td><div class="row-actions">
            <button class="icon-btn btn-sm" data-aact="edit" data-aid="${a.id}"><svg width="15" height="15"><use href="#icon-edit"/></svg></button>
            ${a.is_self ? '' : `<button class="icon-btn btn-sm" data-aact="del" data-aid="${a.id}" style="color:var(--crimson)"><svg width="15" height="15"><use href="#icon-trash"/></svg></button>`}
          </div></td>`;
        tb.appendChild(tr);
      });
      tb.querySelectorAll('button[data-aact]').forEach(b => b.addEventListener('click', () => adminAction(b.dataset.aact, b.dataset.aid)));
    } catch (e) { $('adminsCard').style.display = 'none'; }
    try {
      const r = await api('/api/roles');
      const head = $('matrixHead'), body = $('matrixBody');
      head.innerHTML = `<th></th>` + r.roles.map(x => `<th>${escapeHtml(x)}</th>`).join('');
      const editable = { admin: true, support: true, viewer: true };
      body.innerHTML = r.permissions.map(p => `<tr><td><code style="font-size:.68rem;">${escapeHtml(p)}</code></td>` +
        r.roles.map(x => {
          const has = (r.matrix[x] || []).includes(p) || (r.matrix[x] || []).includes('*');
          if (x === 'owner') return `<td style="text-align:center;">✓</td>`;
          return `<td style="text-align:center;"><input type="checkbox" data-role="${x}" data-perm="${escapeHtml(p)}" ${has ? 'checked' : ''}></td>`;
        }).join('') + `</tr>`).join('');
      let foot = $('matrixSave');
      if (!foot) {
        const bar = document.createElement('div');
        bar.className = 'win-body';
        bar.innerHTML = `<button class="btn btn-primary btn-sm" id="matrixSave"><span>${window.STANNG.t('save')}</span></button>`;
        body.closest('.win').appendChild(bar);
        foot = $('matrixSave');
        foot.addEventListener('click', async () => {
          window.STANNG.setLoading(foot, true);
          try {
            const roles = await api('/api/roles');
            for (const x of roles.roles) {
              if (x === 'owner') continue;
              const perms = [...document.querySelectorAll(`input[data-role="${x}"]:checked`)].map(i => i.dataset.perm);
              await api(`/api/roles/${x}`, { method: 'PATCH', body: { permissions: perms } });
            }
            window.STANNG.toast(window.STANNG.t('settings_saved'), 'success');
            loadSecurity();
          } catch (err) { window.STANNG.toast(err.detail || 'error', 'error'); }
          finally { window.STANNG.setLoading(foot, false); }
        });
      }
    } catch (e) { /* ignore */ }
  }

  async function adminAction(act, aid) {
    try {
      if (act === 'del') {
        if (!confirm(window.STANNG.t('sec_admin_del_confirm'))) return;
        await api(`/api/admins/${aid}`, { method: 'DELETE' });
      } else if (act === 'edit') {
        const r = await api('/api/admins');
        const a = (r.admins || []).find(x => x.id === aid);
        if (!a) return;
        $('admId').value = a.id; $('aName').value = a.username; $('aName').disabled = true;
        $('aRole').value = a.role; $('aPass').value = ''; $('aEnabled').checked = !!a.enabled;
        $('adminModal').classList.add('open');
        return;
      }
      loadSecurity();
    } catch (e) { window.STANNG.toast(e.detail || 'error', 'error'); }
  }

  // ---------- BACKUPS ----------
  function fmtDT(ts) {
    try { return new Date(ts * 1000).toLocaleString(window.STANNG.getLang() === 'fa' ? 'fa-IR' : 'en-US'); }
    catch (e) { return ''; }
  }
  async function loadBackups() {
    try {
      const r = await api('/api/backups');
      const sc = r.schedule || {};
      if ($('bkEnabled')) $('bkEnabled').checked = !!sc.enabled;
      if ($('bkHour')) $('bkHour').value = sc.hour ?? 4;
      if ($('bkMin')) $('bkMin').value = sc.minute ?? 0;
      if ($('bkKeep')) $('bkKeep').value = sc.keep ?? 7;
      if ($('bkTg')) $('bkTg').checked = sc.send_telegram !== false;
      const tb = $('bkBody');
      if (tb) {
        tb.innerHTML = '';
        (r.backups || []).forEach(b => {
          const tr = document.createElement('tr');
          tr.innerHTML = `<td class="small">${fmtDT(b.ts)}</td>
            <td>${window.STANNG.fmtBytes(b.size || 0)}</td>
            <td>${b.auto ? `<span class="pill" style="font-size:.62rem;">auto</span>` : `<span class="pill pill-on" style="font-size:.62rem;">${window.STANNG.t('bk_manual')}</span>`}</td>
            <td><div class="row-actions">
              <button class="icon-btn btn-sm" data-bact="dl" data-bid="${b.id}" title="download"><svg width="15" height="15"><use href="#icon-download"/></svg></button>
              <button class="icon-btn btn-sm" data-bact="restore" data-bid="${b.id}" title="restore"><svg width="15" height="15"><use href="#icon-refresh"/></svg></button>
              <button class="icon-btn btn-sm" data-bact="del" data-bid="${b.id}" style="color:var(--crimson)"><svg width="15" height="15"><use href="#icon-trash"/></svg></button>
            </div></td>`;
          tb.appendChild(tr);
        });
        if (!(r.backups || []).length) tb.innerHTML = `<tr><td colspan="4" class="muted small" style="text-align:center;">—</td></tr>`;
        tb.querySelectorAll('button[data-bact]').forEach(x => x.addEventListener('click', () => backupAction(x.dataset.bact, x.dataset.bid)));
      }
    } catch (e) { window.STANNG.toast(e.detail || 'error', 'error'); }
  }
  async function backupAction(act, bid) {
    try {
      if (act === 'dl') {
        const a = document.createElement('a');
        a.href = `/api/backups/${bid}/download`;
        a.click();
      } else if (act === 'del') {
        if (!confirm(window.STANNG.t('bk_del_confirm'))) return;
        await api(`/api/backups/${bid}`, { method: 'DELETE' });
        loadBackups();
      } else if (act === 'restore') {
        const pw = prompt(window.STANNG.t('sec_old_pass') + ':');
        if (pw === null) return;
        if (!confirm(window.STANNG.t('bk_restore_confirm'))) return;
        await api('/api/backups/restore', { method: 'POST', body: { id: bid, password: pw } });
        window.STANNG.toast(window.STANNG.t('done'), 'success');
        setTimeout(() => window.location.reload(), 1200);
      }
    } catch (e) { window.STANNG.toast(e.detail || 'error', 'error'); }
  }

  // ---------- DIAGNOSTICS ----------
  async function runDiagnostics(btn) {
    window.STANNG.setLoading(btn, true);
    const box = $('dgBox');
    try {
      const r = await api('/api/diagnostics/run');
      box.innerHTML = (r.checks || []).map(c => {
        const dot = c.status === 'ok' ? 'dot-ok' : (c.status === 'warning' ? 'dot-warn' : 'dot-err');
        return `<div class="dg-row"><span class="dot ${dot}" style="margin-top:5px;"></span><span class="body"><b>${escapeHtml(window.STANNG.t('dg_' + c.key) === ('dg_' + c.key) ? c.key : window.STANNG.t('dg_' + c.key))}</b> — ${escapeHtml(c.detail || '')}${c.hint ? `<br><code>${escapeHtml(c.hint)}</code>` : ''}</span></div>`;
      }).join('');
    } catch (e) {
      box.innerHTML = `<div class="muted small">${escapeHtml(e.detail || 'error')}</div>`;
    } finally { window.STANNG.setLoading(btn, false); }
  }

  // ---------- SHOP ADMIN ----------
  async function loadShop() {
    try {
      const ov = await api('/api/shop/overview');
      $('shopCustomers').textContent = ov.customers || 0;
      $('shopPending').textContent = ov.pending_topups || 0;
      $('shopRevenue').textContent = Number(ov.approved_total || 0).toLocaleString();
      const tp = await api('/api/shop/topups');
      const tb = $('topupsBody');
      tb.innerHTML = '';
      (tp.topups || []).forEach(t => {
        const tr = document.createElement('tr');
        const pill = t.status === 'approved' ? 'pill-on' : (t.status === 'denied' ? 'pill-off' : 'pill-warn');
        tr.innerHTML = `<td><b>${escapeHtml(t.first_name || t.username || t.tg_id)}</b><div class="small muted" style="direction:ltr;">${t.tg_id} · ${t.id}</div></td>
          <td>${Number(t.amount || 0).toLocaleString()}</td>
          <td><span class="pill ${pill}" style="font-size:.62rem;">${escapeHtml(t.status)}</span></td>
          <td>${t.status === 'pending' ? `<div class="row-actions">
            <button class="btn btn-emerald btn-sm" data-top="ok" data-rid="${t.id}">✓</button>
            <button class="btn btn-crimson btn-sm" data-top="no" data-rid="${t.id}">✖</button></div>` : ''}</td>`;
        tb.appendChild(tr);
      });
      if (!(tp.topups || []).length) tb.innerHTML = '<tr><td colspan="4" class="muted small" style="text-align:center;">—</td></tr>';
      tb.querySelectorAll('button[data-top]').forEach(b => b.addEventListener('click', async () => {
        await api(`/api/shop/topups/${b.dataset.rid}/decide`, { method: 'POST', body: { approve: b.dataset.top === 'ok' } });
        loadShop();
      }));
      const us = await api('/api/shop/users');
      const ub = $('shopUsersBody');
      ub.innerHTML = '';
      (us.users || []).forEach(u => {
        const tr = document.createElement('tr');
        tr.innerHTML = `<td style="direction:ltr;">${u.tg_id}</td>
          <td><b>${escapeHtml(u.first_name || u.username || '')}</b><div class="small muted" style="direction:ltr;">@${escapeHtml(u.username || '')}</div></td>
          <td>${(u.inbound_uids || []).length}</td>
          <td>${Number(u.balance || 0).toLocaleString()}</td>
          <td><div class="row-actions">
            <button class="btn btn-ghost btn-sm" data-bal="1" data-tg="${u.tg_id}">+10k</button>
            <button class="btn btn-ghost btn-sm" data-bal="-1" data-tg="${u.tg_id}">−10k</button>
          </div></td>`;
        ub.appendChild(tr);
      });
      if (!(us.users || []).length) ub.innerHTML = '<tr><td colspan="5" class="muted small" style="text-align:center;">—</td></tr>';
      ub.querySelectorAll('button[data-bal]').forEach(b => b.addEventListener('click', async () => {
        await api('/api/shop/adjust-balance', { method: 'POST', body: { tg_id: +b.dataset.tg, delta: b.dataset.bal === '1' ? 10000 : -10000 } });
        loadShop();
      }));
    } catch (e) { window.STANNG.toast(e.detail || 'error', 'error'); }
  }

  // ---------- AI ASSISTANT ----------
  const AI_FINDING_KEYS = {
    users_expired: 'ai_f_users_expired', users_quota: 'ai_f_users_quota',
    users_near_expiry: 'ai_f_users_near', servers_offline: 'ai_f_servers_offline',
    high_cpu: 'alert_high_cpu', high_mem: 'alert_high_mem',
    backup_off: 'ai_f_backup_off', backup_none: 'ai_f_backup_none',
    telegram_off: 'ai_f_telegram_off', disabled_pile: 'ai_f_disabled',
  };
  function aiFindingText(f) {
    const key = AI_FINDING_KEYS[f.code] || null;
    let tpl = key ? window.STANNG.t(key) : f.code;
    if (tpl === key) tpl = f.code;
    const p = Object.assign({ n: '', v: '', names: '' }, f.params || {});
    return tpl.replace(/\{(\w+)\}/g, (m, k) => (k in p ? escapeHtml(String(p[k])) : m));
  }
  function aiAddMsg(text, mine, cards) {
    const log = $('aiLog');
    const div = document.createElement('div');
    div.className = 'ai-msg ' + (mine ? 'me' : 'bot');
    div.textContent = text;
    if (cards && cards.length) {
      const wrap = document.createElement('div');
      wrap.className = 'ai-cards';
      cards.forEach(c => {
        if (c.type === 'findings') {
          (c.items || []).forEach(f => {
            const r = document.createElement('div');
            r.className = 'ai-card-row';
            const dot = f.severity === 'critical' ? 'dot-err' : (f.severity === 'warning' ? 'dot-warn' : 'dot-ok');
            r.innerHTML = `<span class="dot ${dot}"></span><span style="flex:1;">${aiFindingText(f)}</span>`;
            wrap.appendChild(r);
          });
        } else if (c.type === 'users') {
          (c.items || []).slice(0, 6).forEach(u => {
            const r = document.createElement('div');
            r.className = 'ai-card-row';
            r.innerHTML = `<b>${escapeHtml(u.name || '')}</b><span class="muted">${window.STANNG.fmtBytes(u.used || 0)}</span>`;
            wrap.appendChild(r);
          });
        } else if (c.type === 'servers') {
          (c.items || []).forEach(s => {
            const r = document.createElement('div');
            r.className = 'ai-card-row';
            const m = s.metrics || {};
            r.innerHTML = `<b>${escapeHtml(s.name || '')}</b><span class="muted">${s.online === true ? '●' : '✖'} ${m.users || 0} users</span>`;
            wrap.appendChild(r);
          });
        } else if (c.type === 'metric') {
          const r = document.createElement('div');
          r.className = 'ai-card-row';
          r.innerHTML = `<b>${escapeHtml(c.metric)}</b><span>${c.value}%</span>`;
          wrap.appendChild(r);
        }
      });
      if (wrap.children.length) div.appendChild(wrap);
    }
    log.appendChild(div);
    log.scrollTop = log.scrollHeight;
    return div;
  }
  function aiChips(keys) {
    const box = $('aiChips');
    if (!box) return;
    box.innerHTML = '';
    (keys || []).forEach(k => {
      const b = document.createElement('button');
      b.className = 'chip';
      b.textContent = window.STANNG.t(k);
      b.addEventListener('click', () => aiAsk(window.STANNG.t(k)));
      box.appendChild(b);
    });
  }
  async function aiAsk(text) {
    if (!text.trim()) return;
    aiAddMsg(text, true);
    const typing = aiAddMsg('…', false);
    typing.classList.add('typing');
    try {
      const r = await api('/api/ai/chat', { method: 'POST', body: { message: text } });
      typing.remove();
      aiAddMsg(r.reply, false, r.cards);
      aiChips(r.suggest);
    } catch (e) {
      typing.remove();
      aiAddMsg(e.detail || 'error', false);
    }
  }
  async function loadAi() {
    const log = $('aiLog');
    if (!log || log.children.length) return;
    const typing = aiAddMsg('…', false);
    typing.classList.add('typing');
    try {
      const lang = window.STANNG.getLang();
      const r = await api('/api/ai/chat', { method: 'POST', body: {
        message: lang === 'fa' ? 'وضعیت کلی چطوره؟' : 'overall status' } });
      typing.remove();
      aiAddMsg(r.reply, false, r.cards);
      aiChips(r.suggest);
    } catch (e) {
      typing.remove();
      aiAddMsg(e.detail || 'error', false);
    }
  }

  // ---------- EXTENSIONS ----------
  async function loadExtensions() {
    try {
      const [pl, wg] = await Promise.all([api('/api/plugins'), api('/api/plugins/widgets')]);
      const lang = window.STANNG.getLang();
      const grid = $('extCards');
      grid.innerHTML = '';
      (wg.cards || []).forEach(c => {
        const t = c.title || {};
        const div = document.createElement('div');
        div.className = 'col-4 win stat-card';
        div.innerHTML = `<div class="label"><span data-i18n="nav_extensions">${window.STANNG.t('nav_extensions')}</span></div>
          <div class="value" style="font-size:1.2rem;">${escapeHtml(c.value || '')}</div>
          <div class="small muted">${escapeHtml(t[lang] || t.en || '')}${c.hint ? ' · ' + escapeHtml(c.hint) : ''}</div>`;
        grid.appendChild(div);
      });
      const tb = $('extBody');
      tb.innerHTML = '';
      $('extEmpty').style.display = (pl.plugins || []).length ? 'none' : 'block';
      (pl.plugins || []).forEach(p => {
        const tr = document.createElement('tr');
        tr.innerHTML = `<td><b>${escapeHtml(p.name)}</b><div class="small muted" style="direction:ltr;">${escapeHtml(p.id)} · ${escapeHtml(p.author || '')}</div></td>
          <td style="direction:ltr;">${escapeHtml(p.version || '')}${p.has_widget ? ' 🧩' : ''}</td>
          <td class="small muted">${escapeHtml(p.description || '')}</td>
          <td>${p.enabled ? `<span class="pill pill-on"><span class="pill-dot"></span>${window.STANNG.t('active')}</span>` : `<span class="pill pill-off"><span class="pill-dot"></span>${window.STANNG.t('inactive')}</span>`}</td>
          <td><button class="btn btn-ghost btn-sm" data-ext="${p.id}" data-en="${p.enabled ? 0 : 1}">${p.enabled ? window.STANNG.t('inb_disable') : window.STANNG.t('inb_enable')}</button></td>`;
        tb.appendChild(tr);
      });
      tb.querySelectorAll('button[data-ext]').forEach(b => b.addEventListener('click', async () => {
        try {
          await api(`/api/plugins/${b.dataset.ext}/toggle`, { method: 'POST', body: { enabled: b.dataset.en === '1' } });
          loadExtensions();
        } catch (e) { window.STANNG.toast(e.detail || 'error', 'error'); }
      }));
    } catch (e) { window.STANNG.toast(e.detail || 'error', 'error'); }
  }

  // ---------- PHASE 3 enhanced: monitoring ----------
  async function loadMonitoring() {
    try {
      const r = await api('/api/servers/monitoring');
      const set = (id, v) => { const el = $(id); if (el) el.textContent = v; };
      set('monOnline', r.online || 0);
      set('monOffline', r.offline || 0);
      set('monMaint', r.maintenance || 0);
      set('monAlerts', r.active_alerts || 0);
      set('monAvgHealth', r.avg_health != null ? r.avg_health + '%' : '—');
      set('monAvgLoad', r.avg_load != null ? r.avg_load + '%' : '—');
      set('monAvgLat', r.avg_latency != null ? r.avg_latency + 'ms' : '—');
      set('monConns', r.total_connections || 0);
    } catch (e) { /* ignore */ }
    try {
      const topR = await api('/api/servers/top?sort_by=' + (($('topSortSelect') || {}).value || 'health'));
      const tb = $('topServersBody');
      if (tb) {
        tb.innerHTML = '';
        (topR.servers || []).forEach((s, i) => {
          const tr = document.createElement('tr');
          tr.innerHTML = `<td>${i + 1}</td><td><b>${escapeHtml(s.name)}</b><div class="small muted">${escapeHtml(s.country || '')} ${escapeHtml(s.city || '')}</div></td>
            <td>${healthPill({health: s.health})}</td>
            <td>${s.load != null ? s.load + '%' : '—'}</td>
            <td>—</td><td>—</td>
            <td>${s.latency_ms != null ? s.latency_ms + 'ms' : '—'}</td>
            <td>—</td>
            <td>${s.uptime_seconds ? window.STANNG.fmtDuration(s.uptime_seconds) : '—'}</td>`;
          tb.appendChild(tr);
        });
      }
      const topSortEl = $('topSortSelect');
      if (topSortEl && !topSortEl._bound) {
        topSortEl._bound = true;
        topSortEl.addEventListener('change', loadMonitoring);
      }
    } catch (e) { /* ignore */ }
    try {
      const srv = await api('/api/servers');
      const sb = $('monSrvBody');
      if (sb) {
        sb.innerHTML = '';
        const all = srv.servers || [];
        all.forEach(s => {
          const m = s.metrics || {};
          const total = (m.total_up || 0) + (m.total_down || 0);
          const tr = document.createElement('tr');
          tr.innerHTML = `<td><b>${escapeHtml(s.name)}</b></td>
            <td><span class="dot ${svcDot(s)}"></span> ${s.online ? 'Online' : (s.online === false ? 'Offline' : '—')}</td>
            <td>${window.STANNG.fmtBytes(m.total_up || 0)}</td>
            <td>${window.STANNG.fmtBytes(m.total_down || 0)}</td>
            <td>${window.STANNG.fmtBytes(total)}</td>
            <td>${m.users || 0}</td>`;
          sb.appendChild(tr);
        });
      }
    } catch (e) { /* ignore */ }
  }

  // ---------- PHASE 3 enhanced: events ----------
  async function loadEvents() {
    try {
      const filterSid = ($('eventsFilterServer') || {}).value || '';
      const url = '/api/server-events?limit=200' + (filterSid ? '&server_id=' + encodeURIComponent(filterSid) : '');
      const r = await api(url);
      const box = $('eventsTimeline');
      if (!box) return;
      const events = r.events || [];
      if (!events.length) {
        box.innerHTML = `<div class="muted small">${window.STANNG.t('events_empty')}</div>`;
        return;
      }
      const sevColor = { info: 'var(--emerald)', warning: 'var(--gold-500)', error: 'var(--crimson)' };
      box.innerHTML = events.map(e => `
        <div class="svc-row" style="border-bottom:1px solid var(--border); padding:8px 0;">
          <span class="flex gap-8" style="align-items:center;">
            <span class="pill-dot" style="color:${sevColor[e.severity] || 'var(--muted)'}"></span>
            <b>${escapeHtml(e.server_name || e.server_id)}</b>
            <span class="small muted">${escapeHtml(e.type)}</span>
          </span>
          <div class="small">${escapeHtml(e.message)}</div>
          <div class="small muted">${fmtTime(e.ts)}</div>
        </div>
      `).join('');
      // populate filter dropdown
      const sel = $('eventsFilterServer');
      if (sel && sel.options.length <= 1) {
        const srv = await api('/api/servers');
        (srv.servers || []).forEach(s => {
          const opt = document.createElement('option');
          opt.value = s.id;
          opt.textContent = s.name;
          sel.appendChild(opt);
        });
        sel.addEventListener('change', loadEvents);
      }
    } catch (e) { /* ignore */ }
  }

  window.PREMIUM = { loadTelegram, loadTokens, loadAudit, loadSystem, loadPlans, openAssign, loadXray, loadServers, loadBest, loadAnalytics, startLive, stopLive, loadNotifications, refreshUnread, loadSecurity, loadBackups, loadShop, runDiagnostics, loadAi, aiAsk, loadExtensions, loadAlerts, loadThresholds, loadMap, loadCompare, runCompare, loadMsStrip, loadAssignments, loadMonitoring, loadEvents, refreshTelemetry, startTelemetry, exportTelemetry,
    reloadActive() {
      const active = document.querySelector('.view.active');
      const id = active ? active.id : '';
      if (id === 'view-servers') loadServers();
      else if (id === 'view-analytics') loadAnalytics();
      else if (id === 'view-plans') loadPlans();
      else if (id === 'view-xray') loadXray();
      else if (id === 'view-tokens' || id === 'view-api') loadTokens();
      else if (id === 'view-logs') loadAudit();
      else if (id === 'view-telegram') loadTelegram();
      else if (id === 'view-notifications') loadNotifications();
      else if (id === 'view-security') loadSecurity();
      else if (id === 'view-backup') loadBackups();
      else if (id === 'view-shop') loadShop();
      else if (id === 'view-ai') loadAi();
      else if (id === 'view-extensions') loadExtensions();
      else if (id === 'view-alerts') { loadAlerts(); loadThresholds(); }
      else if (id === 'view-map') loadMap();
      else if (id === 'view-compare') loadCompare();
      else if (id === 'view-monitoring') loadMonitoring();
      else if (id === 'view-events') loadEvents();
      else if (id === 'view-dashboard') { loadSystem(); loadMsStrip(); }
    } };
})();

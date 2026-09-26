/* Headless front-end harness (faithful global scope).

   Key detail: in a real browser, every classic <script> shares ONE global
   lexical environment, so top-level `const STANNG` is visible to later
   scripts as bare `STANNG` — but NOT as `window.STANNG`. To reproduce that
   exactly we concatenate all files and eval them once.

   Run:  node tests/ui_probe.js
*/
const fs = require('fs');
const path = require('path');
const { JSDOM, VirtualConsole } = require('jsdom');

const ROOT = path.resolve(__dirname, '..');
const BASE = process.env.PANEL_BASE || 'http://127.0.0.1:10000';
const USER = process.env.PANEL_USER || 'admin';
const PASS = process.env.PANEL_PASS || 'AlooPanel#2026';

const cookieJar = new Map();
const cookieHeader = () => [...cookieJar.entries()].map(([k, v]) => `${k}=${v}`).join('; ');
function storeCookies(res) {
  const raw = res.headers.getSetCookie ? res.headers.getSetCookie() : [];
  for (const c of raw) {
    const [pair] = c.split(';');
    const i = pair.indexOf('=');
    if (i > 0) cookieJar.set(pair.slice(0, i).trim(), pair.slice(i + 1).trim());
  }
}

const errors = [];
const netFails = [];
const netLog = [];
process.on('uncaughtException', (e) => errors.push({ kind: 'uncaught', msg: e.message }));
process.on('unhandledRejection', (e) => errors.push({ kind: 'unhandled', msg: String(e && e.message || e) }));

(async () => {
  const login = await fetch(BASE + '/api/login', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: USER, password: PASS }),
  });
  storeCookies(login);
  console.log('login ->', login.status);

  let html = fs.readFileSync(path.join(ROOT, 'templates/dashboard.html'), 'utf8')
    .replace(/\{\{[^}]*\}\}/g, '1.0.0')
    .replace(/<script src="[^"]*"><\/script>/g, '');

  const vc = new VirtualConsole();
  vc.on('jsdomError', (e) => errors.push({ kind: 'jsdomError', msg: e.message }));
  vc.on('error', (...a) => errors.push({ kind: 'console.error', msg: a.join(' ') }));
  vc.on('warn', () => {}); vc.on('log', () => {}); vc.on('info', () => {});

  const dom = new JSDOM(html, {
    url: BASE + '/dashboard', runScripts: 'dangerously',
    pretendToBeVisual: true, virtualConsole: vc,
  });
  const { window } = dom;

  window.Audio = class { play() { return Promise.resolve(); } set volume(_) {} };
  window.HTMLCanvasElement.prototype.getContext = () => null;
  window.requestAnimationFrame = (cb) => setTimeout(() => cb(Date.now()), 0);
  window.matchMedia = () => ({ matches: false, addListener() {}, removeListener() {}, addEventListener() {}, removeEventListener() {} });
  // jsdom lacks these two browser APIs; the panel legitimately uses them.
  window.prompt = () => 'probe-token-name';
  window.document.execCommand = () => true;
  window.addEventListener('error', (e) => errors.push({ kind: 'window.error', msg: e.message || String(e.error && e.error.message) }));
  window.addEventListener('unhandledrejection', (e) => errors.push({ kind: 'unhandledrejection', msg: (e.reason && (e.reason.detail || e.reason.message)) || String(e.reason) }));

  window.fetch = async (url, opts = {}) => {
    const u = String(url).startsWith('http') ? String(url) : BASE + String(url);
    opts.headers = Object.assign({}, opts.headers, { Cookie: cookieHeader() });
    let res;
    try { res = await fetch(u, opts); }
    catch (err) { netFails.push({ url: u, err: String(err) }); throw err; }
    storeCookies(res);
    const text = await res.text();
    netLog.push({ url: String(url), status: res.status });
    return {
      ok: res.ok, status: res.status, statusText: res.statusText, headers: res.headers,
      json: async () => JSON.parse(text), text: async () => text,
      blob: async () => new window.Blob([text]),
    };
  };
  window.URL.createObjectURL = () => 'blob:stub';

  // ---- one combined eval == shared global scope, exactly like the browser ----
  const files = ['static/js/i18n.js', 'static/js/common.js', 'static/js/chart-mini.js',
                 'static/js/dashboard.js', 'static/js/premium-features.js', 'static/js/ultimate.js'];
  const combined = files.map((f) => `\n/*===== ${f} =====*/\n` + fs.readFileSync(path.join(ROOT, f), 'utf8')).join('\n');
  try { window.eval(combined); }
  catch (e) { errors.push({ kind: 'load', msg: e.message }); }

  window.document.dispatchEvent(new window.Event('DOMContentLoaded', { bubbles: true }));
  await new Promise((r) => setTimeout(r, 3000));

  const $ = (id) => window.document.getElementById(id);
  const errsSince = (n) => errors.slice(n);

  // ---------- 1. navigate every view ----------
  const navItems = [...window.document.querySelectorAll('.nav-item[data-view]')];
  console.log('\n--- navigating ' + navItems.length + ' views ---');
  const viewReport = [];
  for (const item of navItems) {
    const view = item.dataset.view;
    const before = errors.length;
    try { item.click(); } catch (e) { errors.push({ kind: 'click-nav:' + view, msg: e.message }); }
    await new Promise((r) => setTimeout(r, 900));
    const active = window.document.querySelector('.view.active');
    const shown = active ? active.id : '(none)';
    const ne = errsSince(before);
    viewReport.push({ view, shown, errors: ne.length, msgs: [...new Set(ne.map((x) => x.msg))].slice(0, 3) });
    console.log(ne.length
      ? `  !! ${view.padEnd(14)} shown=${shown.padEnd(18)} errors=${ne.length} :: ${ne[0].msg.slice(0, 110)}`
      : `  ok ${view.padEnd(14)} shown=${shown}`);
  }

  // ---------- 2. click every button in every view ----------
  console.log('\n--- clicking buttons ---');
  const btnReport = [];
  for (const item of navItems) {
    const view = item.dataset.view;
    item.click();
    await new Promise((r) => setTimeout(r, 400));
    const viewEl = $('view-' + view);
    if (!viewEl) continue;
    for (const b of [...viewEl.querySelectorAll('button')]) {
      const label = (b.id || b.textContent.trim().slice(0, 26) || b.className).replace(/\s+/g, ' ');
      const danger = /delete|cleanup|reset-all|revoke|restore|remove/i.test(b.id + ' ' + label);
      const before = errors.length;
      const oc = window.confirm; window.confirm = () => !danger;
      try { b.click(); } catch (e) { errors.push({ kind: `click:${view}:${label}`, msg: e.message }); }
      window.confirm = oc;
      await new Promise((r) => setTimeout(r, 300));
      const ne = errsSince(before);
      if (ne.length) {
        btnReport.push({ view, label, err: ne[0].msg.slice(0, 170) });
        console.log(`  !! [${view}] "${label}" -> ${ne[0].msg.slice(0, 125)}`);
      }
      window.document.querySelectorAll('.modal-overlay.open').forEach((m) => m.classList.remove('open'));
    }
  }

  console.log('\n' + '='.repeat(72));
  console.log('UNIQUE JS ERRORS:', new Set(errors.map((e) => e.kind + e.msg)).size,
              '| TOTAL:', errors.length, '| NET FAILS:', netFails.length);
  console.log('='.repeat(72));
  const seen = new Set();
  for (const e of errors) {
    const k = e.kind + '|' + e.msg;
    if (seen.has(k)) continue; seen.add(k);
    console.log(`  [${e.kind}] ${String(e.msg).slice(0, 175)}`);
  }
  for (const n of netFails) console.log(`  [net] ${n.url} ${n.err.slice(0, 120)}`);

  const bad = netLog.filter((x) => x.status >= 400);
  if (bad.length) {
    console.log('\n--- HTTP >=400 responses seen by the UI ---');
    for (const b of bad.slice(0, 40)) console.log(`  ${b.status}  ${b.url}`);
  }

  fs.writeFileSync(path.join(ROOT, 'tests', '_ui_report.json'),
    JSON.stringify({ errors, netFails, netLog, viewReport, btnReport }, null, 2));
  console.log('\nwrote tests/_ui_report.json');
  process.exit(0);
})().catch((e) => { console.error('HARNESS CRASH', e); process.exit(1); });

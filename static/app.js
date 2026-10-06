'use strict';
/* MailBlaster UI — single-page app, no build step, no external requests. */

/* ================================================================== core */
const $ = (s, r = document) => r.querySelector(s);
// optional UI pieces are passed as null/false — never render them as text
for (const m of ['replaceChildren', 'append']) {
  const orig = Element.prototype[m];
  Element.prototype[m] = function (...k) { return orig.apply(this, k.filter(x => x != null && x !== false && x !== '')); };
}
function h(tag, attrs, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v == null || v === false) continue;
    if (k === 'html') e.innerHTML = v;
    else if (k === 'class') e.className = v;
    else if (k === 'style') e.style.cssText = v;
    else if (k.startsWith('on') && typeof v === 'function') e.addEventListener(k.slice(2), v);
    else if (k === 'value' || k === 'checked') e[k] = v;
    else e.setAttribute(k, v === true ? '' : v);
  }
  for (const c of kids.flat(Infinity)) {
    if (c == null || c === false) continue;
    e.append(c.nodeType ? c : document.createTextNode(String(c)));
  }
  return e;
}
const frag = (...k) => { const f = document.createDocumentFragment(); k.flat(Infinity).forEach(x => x && f.append(x)); return f; };

const ICONS = {
  dashboard: '<rect x="3" y="3" width="7" height="9" rx="1.5"/><rect x="14" y="3" width="7" height="5" rx="1.5"/><rect x="14" y="12" width="7" height="9" rx="1.5"/><rect x="3" y="16" width="7" height="5" rx="1.5"/>',
  send: '<path d="m22 2-7 20-4-9-9-4Z"/><path d="M22 2 11 13"/>',
  inbox: '<polyline points="22 12 16 12 14 15 10 15 8 12 2 12"/><path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/>',
  users: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
  layout: '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18"/><path d="M9 21V9"/>',
  server: '<rect x="2" y="3" width="20" height="7" rx="2"/><rect x="2" y="14" width="20" height="7" rx="2"/><path d="M6 6.5h.01M6 17.5h.01"/>',
  shield: '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="m9 12 2 2 4-4"/>',
  sliders: '<path d="M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3M1 14h6M9 8h6M17 16h6"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/>',
  trash: '<path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>',
  check: '<path d="M20 6 9 17l-5-5"/>',
  x: '<path d="M18 6 6 18M6 6l12 12"/>',
  pause: '<rect x="6" y="4" width="4" height="16" rx="1"/><rect x="14" y="4" width="4" height="16" rx="1"/>',
  play: '<polygon points="6 3 20 12 6 21 6 3"/>',
  stop: '<rect x="5" y="5" width="14" height="14" rx="2"/>',
  refresh: '<path d="M21 12a9 9 0 1 1-3-6.7L21 8"/><path d="M21 3v5h-5"/>',
  download: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><path d="M12 15V3"/>',
  upload: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><path d="M12 3v12"/>',
  mail: '<rect x="2" y="4" width="20" height="16" rx="2"/><path d="m22 7-10 6L2 7"/>',
  reply: '<polyline points="9 17 4 12 9 7"/><path d="M20 18v-2a4 4 0 0 0-4-4H4"/>',
  tag: '<path d="M12 2H2v10l9.29 9.29a1 1 0 0 0 1.41 0l8.59-8.59a1 1 0 0 0 0-1.41Z"/><circle cx="7" cy="7" r="1.5"/>',
  folder: '<path d="M4 20h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.93a2 2 0 0 1-1.66-.9l-.82-1.2A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13c0 1.1.9 2 2 2Z"/>',
  flame: '<path d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.07-2.14-.22-4.05 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.15.43-2.29 1-3a2.5 2.5 0 0 0 2.5 2.5z"/>',
  alert: '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><path d="M12 9v4M12 17h.01"/>',
  info: '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/>',
  left: '<path d="m15 18-6-6 6-6"/>', right: '<path d="m9 18 6-6-6-6"/>', down: '<path d="m6 9 6 6 6-6"/>',
  dots: '<circle cx="12" cy="5" r="1.2"/><circle cx="12" cy="12" r="1.2"/><circle cx="12" cy="19" r="1.2"/>',
  edit: '<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"/>',
  eye: '<path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/>',
  pointer: '<path d="m4 4 7.07 16.97 2.51-7.39 7.39-2.51L4 4z"/>',
  ban: '<circle cx="12" cy="12" r="10"/><path d="m4.9 4.9 14.2 14.2"/>',
  zap: '<polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>',
  copy: '<rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>',
  globe: '<circle cx="12" cy="12" r="10"/><path d="M2 12h20"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>',
  archive: '<rect x="2" y="3" width="20" height="5" rx="1"/><path d="M4 8v11a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8"/><path d="M10 12h4"/>',
  star: '<polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>',
  calendar: '<rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/>',
  thumbdown: '<path d="M17 14V2"/><path d="M9 18.12 10 14H4.17a2 2 0 0 1-1.92-2.56l2.33-8A2 2 0 0 1 6.5 2H20a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-2.76a2 2 0 0 0-1.79 1.11L12 22a3.13 3.13 0 0 1-3-3.88Z"/>',
  bot: '<rect x="3" y="11" width="18" height="10" rx="2"/><circle cx="12" cy="5" r="2"/><path d="M12 7v4M8 16h.01M16 16h.01"/>',
  bounce: '<path d="M22 13V6a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h9"/><path d="m22 7-10 6L2 7"/><path d="m17 17 4 4M21 17l-4 4"/>',
  user: '<circle cx="12" cy="8" r="5"/><path d="M20 21a8 8 0 0 0-16 0"/>',
  userplus: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M19 8v6M22 11h-6"/>',
  clock: '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
  activity: '<polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>',
  menu: '<path d="M4 6h16M4 12h16M4 18h16"/>',
  monitor: '<rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8M12 17v4"/>',
  phone: '<rect x="7" y="2" width="10" height="20" rx="2"/><path d="M12 18h.01"/>',
  sparkles: '<path d="M12 3l1.9 5.8L20 11l-6.1 2.2L12 19l-1.9-5.8L4 11l6.1-2.2z"/>',
  lock: '<rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>',
  link: '<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>',
  minus: '<path d="M5 12h14"/>',
  filter: '<polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/>',
  mailcheck: '<path d="M22 13V6a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h8"/><path d="m22 7-10 6L2 7"/><path d="m16 19 2 2 4-4"/>',
  broom: '<path d="m13 11 9-9"/><path d="M14.6 12.6c.8.8.9 2.1.2 3L10 22l-8-8 6.4-4.8c.9-.7 2.2-.6 3 .2Z"/><path d="m6.8 10.4 6.8 6.8"/>',
};
function icon(name, size = 18, sw = 2) {
  const s = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  s.setAttribute('viewBox', '0 0 24 24'); s.setAttribute('width', size); s.setAttribute('height', size);
  s.setAttribute('fill', 'none'); s.setAttribute('stroke', 'currentColor'); s.setAttribute('stroke-width', sw);
  s.setAttribute('stroke-linecap', 'round'); s.setAttribute('stroke-linejoin', 'round'); s.setAttribute('class', 'i');
  s.innerHTML = ICONS[name] || ''; return s;
}
function btn(label, o = {}) {
  const b = h('button', { class: 'btn ' + (o.kind || '') + (o.size ? ' ' + o.size : ''), type: 'button', title: o.title,
    disabled: !!o.disabled, onclick: o.onclick }, o.icon ? icon(o.icon, o.size === 'sm' ? 15 : 16) : null, label);
  if (o.id) b.id = o.id; return b;
}
function iconBtn(name, title, onclick, sm) { return h('button', { class: 'icon-btn' + (sm ? ' sm' : ''), title, type: 'button', onclick }, icon(name, sm ? 15 : 17)); }
function pill(text, c = 'm', dot) { return h('span', { class: 'pill ' + c }, dot ? h('span', { class: 'dot', style: 'background:currentColor' }) : null, text); }
function chip(g) { return h('span', { class: 'chip', title: g.name }, h('span', { class: 'dot', style: 'background:' + (g.color || '#94a3b8') }), h('span', { class: 't' }, g.name)); }
function toggle(label, val, onchange, sub) {
  const i = h('input', { type: 'checkbox' }); i.checked = !!val; i.addEventListener('change', () => onchange(i.checked));
  return h('label', { class: 'toggle' }, i, h('span', { class: 'tk' }), h('span', { class: 'tl' }, label, sub ? h('small', {}, sub) : null));
}
function field(label, input, opt, hint) { return h('div', { class: 'fld' }, h('label', { class: 'f' }, label, opt ? h('span', { class: 'opt' }, ' · ' + opt) : null), input, hint ? h('div', { class: 'help', style: 'margin:6px 0 0' }, hint) : null); }
function banner(kind, text, actions) {
  const ic = { info: 'info', ok: 'check', warn: 'alert', err: 'alert' }[kind] || 'info';
  return h('div', { class: 'banner ' + kind }, icon(ic, 17), h('div', { style: 'flex:1' }, text), actions ? h('div', { class: 'ba' }, actions) : null);
}
function card(title, sub, actions, ...body) {
  return h('div', { class: 'card' }, h('div', { class: 'card-h' }, h('div', {}, h('h2', {}, title), sub ? h('div', { class: 'sub' }, sub) : null),
    actions ? h('div', { class: 'act' }, actions) : null), ...body);
}
function emptyState(ic, title, text, action) {
  return h('div', { class: 'empty' }, h('div', { class: 'ei' }, icon(ic, 24)), h('h3', {}, title), h('p', {}, text), action || null);
}
function kpi(ic, color, bg, lab, num, foot, cls) {
  return h('div', { class: 'kpi ' + (cls || '') }, h('div', { class: 'top-l' }, h('div', { class: 'lab' }, lab),
    h('div', { class: 'ic', style: `background:${bg};color:${color}` }, icon(ic, 16))), h('div', { class: 'num' }, num), foot ? h('div', { class: 'foot' }, foot) : null);
}

/* ---------------------------------------------------------------- api */
async function api(url, data) {
  const opt = {};
  if (data !== undefined) {
    const fd = new FormData();
    for (const [k, v] of Object.entries(data)) {
      if (v == null) continue;
      if (Array.isArray(v)) v.forEach(x => fd.append(k, x)); else if (v instanceof File) fd.append(k, v); else fd.append(k, String(v));
    }
    opt.method = 'POST'; opt.body = fd;
  }
  let r;
  try { r = await fetch(url, opt); } catch (e) { return { ok: false, error: 'Cannot reach MailBlaster — is the app still running?' }; }
  let j;
  try { j = await r.json(); } catch (e) { j = { ok: r.ok, error: r.ok ? '' : 'Server error (' + r.status + ')' }; }
  if (!r.ok && j && typeof j === 'object' && !Array.isArray(j) && j.ok === undefined) j.ok = false;
  return j;
}
const GET = u => api(u), POST = (u, d = {}) => api(u, d);

/* ---------------------------------------------------------------- format */
const fmt = n => Number(n || 0).toLocaleString();
const pct = (a, b) => b ? (Math.round(a / b * 1000) / 10) + '%' : '0%';
const pnum = (a, b) => b ? a / b * 100 : 0;
function timeAgo(ts) {
  if (!ts) return '—'; const s = Date.now() / 1000 - ts;
  if (s < 50) return 'just now'; if (s < 3600) return Math.round(s / 60) + 'm ago'; if (s < 86400) return Math.round(s / 3600) + 'h ago';
  if (s < 7 * 86400) return Math.round(s / 86400) + 'd ago'; return new Date(ts * 1000).toLocaleDateString();
}
const dt = ts => ts ? new Date(ts * 1000).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '—';
const dur = s => { s = Math.max(0, Math.round(s || 0)); if (s < 60) return s + 's'; if (s < 3600) return Math.round(s / 60) + ' min'; if (s < 86400) return (s / 3600).toFixed(1) + ' h'; return (s / 86400).toFixed(1) + ' days'; };
const AV_COLORS = ['#6366f1', '#0ea5e9', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#14b8a6'];
function avatar(name, email, size) {
  const s = (name || email || '?').trim(); let hsh = 0; for (const c of (email || s)) hsh = (hsh * 31 + c.charCodeAt(0)) | 0;
  const ini = s.split(/[\s@._-]+/).filter(Boolean).slice(0, 2).map(x => x[0]).join('') || '?';
  return h('div', { class: 'avatar', style: `background:${AV_COLORS[Math.abs(hsh) % AV_COLORS.length]}` + (size ? `;width:${size}px;height:${size}px;font-size:${size / 2.6}px` : '') }, ini);
}
function debounce(fn, ms) { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; }
const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

/* ---------------------------------------------------------------- toast / modal / menu */
function toast(msg, kind = 'ok', ms = 4200) {
  const ic = { ok: 'check', err: 'alert', warn: 'alert', info: 'info' }[kind] || 'info';
  const t = h('div', { class: 'toast ' + kind }, icon(ic, 17), h('div', { style: 'flex:1' }, msg), h('span', { class: 'x', onclick: () => t.remove() }, icon('x', 14)));
  $('#toasts').append(t); setTimeout(() => t.remove(), ms);
}
let MODAL_STACK = [];
function modal({ title, body, footer, wide, onClose, icon: ic }) {
  const bg = h('div', { class: 'modal-bg' });
  const close = () => { bg.remove(); MODAL_STACK = MODAL_STACK.filter(x => x !== close); onClose && onClose(); };
  const box = h('div', { class: 'modal' + (wide ? ' wide' : '') },
    h('div', { class: 'modal-h' }, ic ? h('div', { style: 'width:34px;height:34px;border-radius:9px;background:var(--brand-l);color:var(--brand);display:grid;place-items:center' }, icon(ic, 17)) : null,
      h('h3', {}, title), iconBtn('x', 'Close', close)),
    h('div', { class: 'modal-b' }, body), footer ? h('div', { class: 'modal-f' }, footer) : null);
  bg.append(box); bg.addEventListener('mousedown', e => { if (e.target === bg) close(); });
  $('#modalRoot').append(bg); MODAL_STACK.push(close);
  setTimeout(() => { const f = box.querySelector('input:not([type=checkbox]):not([type=radio]),textarea'); f && f.focus(); }, 30);
  return { close, box };
}
document.addEventListener('keydown', e => { if (e.key === 'Escape') { if ($('#menuRoot').firstChild) closeMenu(); else if (MODAL_STACK.length) MODAL_STACK[MODAL_STACK.length - 1](); } });
function confirmBox({ title, text, ok = 'Confirm', danger = false, typeText = null, icon: ic }) {
  return new Promise(res => {
    let done = false; const inp = typeText ? h('input', { placeholder: `Type ${typeText} to confirm`, style: 'margin-top:12px' }) : null;
    const okb = btn(ok, { kind: danger ? 'danger-solid' : 'primary', disabled: !!typeText, onclick: () => { done = true; m.close(); res(true); } });
    if (inp) inp.addEventListener('input', () => { okb.disabled = inp.value.trim() !== typeText; });
    const m = modal({ title, icon: ic || (danger ? 'alert' : 'info'), body: h('div', {}, h('div', { class: 'muted', style: 'font-size:13.5px;line-height:1.6' }, text), inp),
      footer: [btn('Cancel', { onclick: () => m.close() }), okb], onClose: () => { if (!done) res(false); } });
  });
}
function promptBox({ title, label, value = '', placeholder = '', ok = 'Save', icon: ic }) {
  return new Promise(res => {
    let done = false; const inp = h('input', { value, placeholder });
    const submit = () => { if (!inp.value.trim()) { inp.focus(); return; } done = true; m.close(); res(inp.value.trim()); };
    inp.addEventListener('keydown', e => { if (e.key === 'Enter') submit(); });
    const m = modal({ title, icon: ic, body: field(label, inp), footer: [btn('Cancel', { onclick: () => m.close() }), btn(ok, { kind: 'primary', onclick: submit })],
      onClose: () => { if (!done) res(null); } });
  });
}
function closeMenu() { $('#menuRoot').replaceChildren(); }
function openMenu(anchor, items) {
  closeMenu();
  const m = h('div', { class: 'menu' });
  items.filter(Boolean).forEach(it => {
    if (it === 'sep') m.append(h('div', { class: 'msep' }));
    else if (it.section) m.append(h('div', { class: 'mlab' }, it.section));
    else m.append(h('button', { class: it.danger ? 'danger' : '', type: 'button', onclick: () => { closeMenu(); it.onclick(); } }, it.icon ? icon(it.icon, 15) : h('span', { style: 'width:15px' }), it.label));
  });
  $('#menuRoot').append(m);
  const r = anchor.getBoundingClientRect(); const mw = m.offsetWidth, mh = m.offsetHeight;
  let left = Math.min(r.right - mw, window.innerWidth - mw - 8); left = Math.max(8, left);
  let top = r.bottom + 4; if (top + mh > window.innerHeight - 8) top = Math.max(8, r.top - mh - 4);
  m.style.left = left + 'px'; m.style.top = top + 'px';
  setTimeout(() => document.addEventListener('mousedown', function f(e) { if (!m.contains(e.target)) { closeMenu(); document.removeEventListener('mousedown', f); } }), 0);
}

/* ================================================================== app shell */
const APP = { state: {}, view: 'dashboard', sub: null, id: null, live: null, prevJobs: {}, tick: 0 };
const NAV = [
  { sec: 'Workspace' },
  { id: 'dashboard', ic: 'dashboard', label: 'Dashboard' },
  { id: 'campaigns', ic: 'send', label: 'Campaigns' },
  { id: 'inbox', ic: 'inbox', label: 'Inbox' },
  { id: 'contacts', ic: 'users', label: 'Contacts' },
  { id: 'templates', ic: 'layout', label: 'Templates' },
  { sec: 'Sending' },
  { id: 'senders', ic: 'server', label: 'Senders' },
  { id: 'deliverability', ic: 'shield', label: 'Deliverability' },
  { id: 'settings', ic: 'sliders', label: 'Settings' },
];
const TITLES = {
  dashboard: ['Dashboard', 'Your sending at a glance'], campaigns: ['Campaigns', 'Create, launch and track campaigns'],
  inbox: ['Inbox', 'Every reply from every sender, in one place'], contacts: ['Contacts', 'Your audience, organized into groups'],
  templates: ['Templates', 'Start from a proven layout'], senders: ['Senders', 'Sending accounts, warm-up and inbox sync'],
  deliverability: ['Deliverability', 'Bounces, safety brakes, suppression and domain health'], settings: ['Settings', 'Tracking and sending options'],
};
const jobsList = () => Object.values(APP.state.jobs || {});
const runningJobs = () => jobsList().filter(j => j.status === 'running');

function renderNav() {
  const st = APP.state, run = runningJobs().length, unread = (st.inbox || {}).unread || 0;
  const paused = (st.accounts || []).filter(a => a.paused_reason).length;
  $('#nav').replaceChildren(...NAV.map(n => {
    if (n.sec) return h('div', { class: 'nav-sec' }, n.sec);
    let badge = null;
    if (n.id === 'campaigns' && run) badge = h('span', { class: 'cnt live', title: run + ' sending now' }, run);
    if (n.id === 'inbox' && unread) badge = h('span', { class: 'cnt', title: unread + ' unread replies' }, unread > 99 ? '99+' : unread);
    if (n.id === 'senders' && paused) badge = h('span', { class: 'cnt', style: 'background:#f59e0b', title: paused + ' sender(s) auto-paused' }, '!');
    return h('button', { class: 'nav-btn' + (APP.view === n.id ? ' on' : ''), type: 'button', onclick: () => go(n.id) }, icon(n.ic, 18), n.label, badge);
  }));
  renderSyncLine();
}
function renderSyncLine() {
  const im = APP.state.imap || {}, on = (APP.state.accounts || []).some(a => a.imap_enabled);
  const el = $('#syncLine'); if (!el) return;
  if (!on) { el.replaceChildren(h('span', { class: 'dot' }), 'Inbox sync off'); return; }
  el.replaceChildren(h('span', { class: 'dot ' + (im.running ? 'spin' : 'g') }), im.running ? 'Syncing inbox…' : ('Inbox synced ' + (im.last_run ? timeAgo(im.last_run) : '—')));
}
function toggleSide(v) { $('#side').classList.toggle('open', v); $('#backdrop').classList.toggle('show', v); }
async function loadState() { const s = await GET('/api/state'); if (s && s.contacts) { APP.state = s; APP.prevJobs = snapshotJobs(s.jobs); } renderNav(); }
function snapshotJobs(jobs) { const o = {}; Object.values(jobs || {}).forEach(j => o[j.campaign_id] = { status: j.status, brake: j.brake }); return o; }

function go(view, sub = null, id = null) {
  const hash = '#' + [view, sub, id].filter(x => x != null && x !== '').join('/');
  if (location.hash === hash) route(); else location.hash = hash;
}
function route() {
  const [v, s, i] = location.hash.replace(/^#/, '').split('/');
  APP.view = TITLES[v] ? v : 'dashboard'; APP.sub = s || null; APP.id = i ? (isNaN(+i) ? i : +i) : null;
  toggleSide(false); render();
}
window.addEventListener('hashchange', route);
async function render() {
  closeMenu(); APP.live = null;
  const [t, s] = TITLES[APP.view] || ['', '']; $('#ttl').textContent = t; $('#tsub').textContent = s;
  $('#topright').replaceChildren(); renderNav();
  const fn = { dashboard: viewDashboard, campaigns: viewCampaigns, inbox: viewInbox, contacts: viewContacts, templates: viewTemplates,
    senders: viewSenders, deliverability: viewDeliverability, settings: viewSettings }[APP.view] || viewDashboard;
  window.scrollTo(0, 0);
  try { await fn(); } catch (e) { console.error(e); $('#view').replaceChildren(banner('err', 'Something went wrong rendering this page: ' + e.message)); }
}
function setTop(...els) { $('#topright').replaceChildren(...els.filter(Boolean)); }

/* live polling: running campaigns, brakes, inbox badge */
async function poll() {
  APP.tick++;
  const anyRunning = runningJobs().length > 0;
  if (anyRunning || APP.tick % 8 === 0) {
    const jobs = await GET('/api/campaigns/running');
    if (jobs && !jobs.error) {
      const prev = APP.prevJobs; APP.state.jobs = jobs; const now = snapshotJobs(jobs); let finished = false;
      for (const [cid, j] of Object.entries(now)) {
        const p = prev[cid];
        if (j.brake && (!p || p.brake !== j.brake)) toast(h('span', {}, h('b', {}, 'Safety brake: '), (jobs[cid].name || 'Campaign') + ' was auto-paused. ' + j.brake), 'err', 12000);
        if (p && p.status === 'running' && j.status !== 'running') { finished = true; toast(`“${jobs[cid].name || 'Campaign'}” ${j.status === 'done' ? 'finished' : j.status} — ${fmt(jobs[cid].sent)} sent.`, j.status === 'done' ? 'ok' : 'warn'); }
      }
      APP.prevJobs = now;
      if (finished) { await loadState(); if (!MODAL_STACK.length && ['dashboard', 'campaigns'].includes(APP.view)) render(); }
      else { renderNav(); if (APP.live && !MODAL_STACK.length) APP.live(); }
    }
  }
  if (APP.tick % 10 === 0) {
    const s = await GET('/api/inbox/status');
    if (s && s.counts) {
      const before = (APP.state.inbox || {}).unread || 0; APP.state.inbox = s.counts; APP.state.imap = s;
      if (s.counts.unread > before && APP.tick > 10) toast(`${s.counts.unread - before} new repl${s.counts.unread - before > 1 ? 'ies' : 'y'} in your inbox`, 'info');
      renderNav();
    }
  }
}
setInterval(poll, 2000);

/* ================================================================== DASHBOARD */
async function viewDashboard() {
  const v = $('#view'); const d = await GET('/api/dashboard'); const c = d.contacts || {};
  setTop(btn('New campaign', { kind: 'primary', icon: 'plus', onclick: () => newCampaign() }));
  const br = d.bounce_rate || 0;
  const kpis = h('div', { class: 'grid g5' },
    kpi('users', '#4f46e5', 'var(--brand-l)', 'Active contacts', fmt(c.active), fmt(c.total) + ' total'),
    kpi('send', '#0ea5e9', 'var(--sky-l)', 'Emails sent', fmt(d.total_sent), fmt(d.campaigns) + ' campaigns'),
    kpi('eye', '#8b5cf6', 'var(--violet-l)', 'Open rate', (d.open_rate || 0) + '%', fmt(d.opens) + ' opens'),
    kpi('reply', '#10b981', 'var(--green-l)', 'Reply rate', (d.reply_rate || 0) + '%', fmt(d.replies) + ' replies', d.replies ? 'good' : ''),
    kpi('bounce', br >= 5 ? '#ef4444' : br >= 2 ? '#f59e0b' : '#10b981', br >= 5 ? 'var(--red-l)' : br >= 2 ? 'var(--amber-l)' : 'var(--green-l)', 'Bounce rate', br + '%',
      br >= 5 ? 'Too high — clean your lists' : br >= 2 ? 'Watch this' : 'Healthy (under 2%)', br >= 5 ? 'bad' : br >= 2 ? 'warn' : 'good'));
  const liveBox = h('div');
  APP.live = () => {
    const run = runningJobs();
    liveBox.replaceChildren(run.length ? card(h('span', { class: 'hstack' }, h('span', { class: 'live-dot' }), `Sending now (${run.length})`), null, null,
      h('div', { class: 'card-b' }, run.map(runCard))) : '');
  };
  APP.live();
  // chart
  const chartCard = card('Last 14 days', 'Emails sent and replies received', h('div', { class: 'legend' },
    h('span', {}, h('i', { style: 'background:#c7d2fe' }), 'Sent'), h('span', {}, h('i', { style: 'background:#8b5cf6' }), 'Opens'), h('span', {}, h('i', { style: 'background:#10b981' }), 'Replies')),
    h('div', { class: 'card-b' }, chart(d.series || [])));
  // latest replies
  const rep = card('Latest replies', 'From your unified inbox', btn('Open inbox', { size: 'sm', onclick: () => go('inbox') }));
  if (!(d.latest_replies || []).length) rep.append(emptyState('inbox', 'No replies yet', (APP.state.accounts || []).some(a => a.imap_enabled) ? 'Replies to your campaigns will appear here automatically.' : 'Turn on inbox sync for your senders to collect replies and bounces automatically.',
    (APP.state.accounts || []).some(a => a.imap_enabled) ? null : btn('Set up inbox sync', { size: 'sm', onclick: () => go('senders') })));
  else d.latest_replies.forEach(r => rep.append(h('div', { class: 'list-item', onclick: () => go('inbox', 'm', r.id) }, avatar(r.from_name, r.from_email),
    h('div', { style: 'flex:1;min-width:0' }, h('div', { class: 'hstack' }, h('b', { class: 'ellipsis', style: 'max-width:60%' }, r.from_name || r.from_email), r.label ? labelPill(r.label) : null, h('span', { class: 'spacer' }), h('span', { class: 'xs dim' }, timeAgo(r.received_at))),
      h('div', { class: 'small muted ellipsis' }, r.snippet || r.subject)))));
  // recent campaigns
  const rc = card('Recent campaigns', null, btn('View all', { size: 'sm', onclick: () => go('campaigns') }));
  if (!(d.recent || []).length) rc.append(emptyState('send', 'No campaigns yet', 'Create your first campaign — pick a group, write your email, and send.', btn('Create campaign', { kind: 'primary', icon: 'plus', onclick: () => newCampaign() })));
  else rc.append(h('div', { class: 'tbl-wrap' }, h('table', { class: 't' }, h('thead', {}, h('tr', {}, h('th', {}, 'Campaign'), h('th', {}, 'Status'), h('th', { class: 'num' }, 'Sent'), h('th', { class: 'num' }, 'Opens'), h('th', { class: 'num' }, 'Replies'))),
    h('tbody', {}, d.recent.map(r => h('tr', { class: 'click', onclick: () => go('campaigns', 'report', r.id) }, h('td', {}, h('b', {}, r.name)), h('td', {}, statusPill(liveStatus(r))),
      h('td', { class: 'num' }, fmt(liveSent(r))), h('td', { class: 'num' }, pct(r.opens, liveSent(r))), h('td', { class: 'num' }, fmt(r.replies))))))));
  // checklist
  const accs = APP.state.accounts || [];
  const items = [
    [accs.length > 0, 'Add a sender account', 'Gmail, Outlook, SendGrid, SES…', () => go('senders', 'new')],
    [accs.some(a => a.warmup_enabled), 'Turn on warm-up for new senders', 'Ramp up volume safely', () => go('senders')],
    [accs.some(a => a.imap_enabled), 'Enable inbox sync (bounces + replies)', 'Auto-clean bounces, collect replies', () => go('senders')],
    [(c.total || 0) > 0, 'Import your contacts into groups', 'CSV upload', () => go('contacts')],
    [(d.campaigns || 0) > 0, 'Launch your first campaign', 'Design, send and track', () => newCampaign()],
  ];
  const doneN = items.filter(x => x[0]).length;
  const chk = card('Setup checklist', `${doneN} of ${items.length} done`, null, h('div', { style: 'padding:0 0 4px' }, h('div', { style: 'padding:12px 20px 4px' }, h('div', { class: 'pbar g' }, h('div', { style: `width:${doneN / items.length * 100}%` }))),
    items.map(([ok, t, s, fn]) => h('div', { class: 'check-row' + (ok ? ' done' : ''), onclick: fn }, h('div', { class: 'ck' }, icon('check', 14, 3)),
      h('div', { style: 'flex:1' }, h('div', { class: 't b small' }, t), h('div', { class: 'xs muted' }, s)), ok ? null : icon('right', 16)))));
  const trackWarn = (APP.state.tracking || 'none') === 'none' && (APP.state.accounts || []).length ? h('div', { style: 'margin-bottom:18px' }, banner('warn', h('span', {}, h('b', {}, 'Open tracking is off. '), 'Turn it on to see who opened your emails — one click, free, no setup.'), [btn('Turn on tracking', { size: 'sm', kind: 'primary', onclick: () => go('settings') })])) : null;
  v.replaceChildren(trackWarn, kpis, h('div', { style: 'height:18px' }), liveBox, h('div', { class: 'split' }, h('div', {}, chartCard, rc), h('div', {}, rep, doneN < items.length ? chk : null)));
}
function chart(series) {
  const W = 720, H = 190, P = 26, n = series.length || 1, bw = (W - P * 2) / n;
  const max = Math.max(4, ...series.map(s => Math.max(s.sent, s.opens, s.replies)));
  const y = v => H - 22 - (v / max) * (H - 40);
  let bars = '', opens = '', reps = '', labels = '', grid = '';
  for (let g = 0; g <= 3; g++) { const yy = y(max / 3 * g); grid += `<line x1="${P}" x2="${W - 8}" y1="${yy}" y2="${yy}" stroke="#eef0f5"/><text x="${P - 6}" y="${yy + 4}" font-size="10" fill="#94a3b8" text-anchor="end">${Math.round(max / 3 * g)}</text>`; }
  series.forEach((s, i) => {
    const x = P + i * bw; bars += `<rect x="${x + bw * .18}" y="${y(s.sent)}" width="${bw * .64}" height="${Math.max(0, H - 22 - y(s.sent))}" rx="3" fill="#c7d2fe"><title>${s.d}: ${s.sent} sent, ${s.opens} opens, ${s.replies} replies</title></rect>`;
    opens += `${i ? 'L' : 'M'}${x + bw / 2},${y(s.opens)}`; reps += `${i ? 'L' : 'M'}${x + bw / 2},${y(s.replies)}`;
    if (i % 2 === 0 || n < 8) labels += `<text x="${x + bw / 2}" y="${H - 6}" font-size="10" fill="#94a3b8" text-anchor="middle">${s.d.slice(5).replace('-', '/')}</text>`;
  });
  const dots = series.map((s, i) => s.replies ? `<circle cx="${P + i * bw + bw / 2}" cy="${y(s.replies)}" r="3.5" fill="#10b981"/>` : '').join('');
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg'); svg.setAttribute('viewBox', `0 0 ${W} ${H}`); svg.setAttribute('class', 'chart'); svg.setAttribute('preserveAspectRatio', 'none');
  svg.innerHTML = grid + bars + `<path d="${opens}" fill="none" stroke="#8b5cf6" stroke-width="2"/><path d="${reps}" fill="none" stroke="#10b981" stroke-width="2.2"/>` + dots + labels;
  return svg;
}

/* ================================================================== CAMPAIGNS */
function trackingControls() {
  const m = APP.state.tracking || 'none';
  if (m === 'full') return h('div', { class: 'hstack', style: 'gap:26px;margin-top:16px' }, toggle('Track opens', CB.track_opens, v => CB.track_opens = v), toggle('Track clicks', CB.track_clicks, v => CB.track_clicks = v));
  if (m === 'opens') return h('div', { style: 'margin-top:16px' }, toggle('Track opens', CB.track_opens, v => CB.track_opens = v, 'Via your secure public tracking link'),
    h('div', { class: 'help', style: 'margin-top:8px' }, 'Links go straight to your URLs (never through this PC), so they always work. Clicks also count as opens when you use your own permanent tracking address — see Settings.'));
  return h('div', { style: 'margin-top:16px' }, banner('warn', h('span', {}, h('b', {}, 'Open tracking is off. '), 'Recipients’ mail apps can’t reach this PC, so opens can’t be counted. Links still work normally.'), [btn('Turn on', { size: 'sm', onclick: () => go('settings') })]));
}
function hasPublicUrl() {
  const b = ((APP.state.settings || {}).track_base || '').trim(); const m = b.match(/^https?:\/\/([^/:]+)/i);
  return !!m && !/^(127\.|localhost$|0\.0\.0\.0$|192\.168\.|10\.)/i.test(m[1]);
}
function liveSent(c) { const j = (APP.state.jobs || {})[c.id]; return j && j.status === 'running' ? j.sent : c.sent; }
function liveStatus(c) { const j = (APP.state.jobs || {})[c.id]; if (j && j.status === 'running') return j.brake ? 'braked' : j.pause ? 'paused' : j.waiting ? 'waiting' : 'running'; return c.status; }
function statusPill(s) {
  const m = { done: ['Completed', 'g'], running: ['Sending', 'b'], scheduled: ['Scheduled', 'a'], queued: ['Queued', 'a'], draft: ['Draft', 'm'], error: ['Error', 'r'],
    stopped: ['Stopped', 'm'], interrupted: ['Interrupted', 'a'], cancelled: ['Cancelled', 'm'], paused: ['Paused', 'a'], braked: ['Auto-paused', 'r'], waiting: ['Waiting', 's'] }[s] || [s || 'Draft', 'm'];
  return pill(m[0], m[1], true);
}
function labelPill(l) { const m = { interested: ['Interested', 'g'], meeting: ['Meeting', 's'], not_interested: ['Not interested', 'm'], unsubscribe: ['Unsubscribe', 'r'] }[l]; return m ? pill(m[0], m[1]) : null; }
async function ctrl(cid, action) { await POST('/api/campaign/control', { campaign_id: cid, action }); const j = await GET('/api/campaigns/running'); if (j && !j.error) { APP.state.jobs = j; APP.prevJobs = snapshotJobs(j); } APP.live && APP.live(); renderNav(); }
function runCard(j) {
  const done = (j.sent || 0) + (j.failed || 0) + (j.skipped || 0) + (j.bounced || 0), p = j.total ? Math.min(100, done / j.total * 100) : 0;
  const state = j.brake ? 'braked' : j.pause ? 'paused' : j.waiting ? 'waiting' : 'running';
  const box = h('div', { class: 'run' + (state === 'braked' ? ' braked' : state === 'paused' ? ' paused' : '') },
    h('div', { class: 'rh' }, h('b', { style: 'font-size:14px' }, j.name || ('Campaign ' + j.campaign_id)), statusPill(state), h('span', { class: 'spacer' }),
      state === 'braked' ? null : (j.pause ? btn('Resume', { size: 'sm', icon: 'play', onclick: () => ctrl(j.campaign_id, 'resume') }) : btn('Pause', { size: 'sm', icon: 'pause', onclick: () => ctrl(j.campaign_id, 'pause') })),
      btn('Stop', { size: 'sm', kind: 'danger', icon: 'stop', onclick: async () => { if (await confirmBox({ title: 'Stop this campaign?', text: 'Sending stops now. You can resume later — only people who haven’t been emailed yet will get it.', ok: 'Stop sending', danger: true })) ctrl(j.campaign_id, 'stop'); } }),
      APP.sub === 'report' ? null : btn('Report', { size: 'sm', icon: 'activity', onclick: () => go('campaigns', 'report', j.campaign_id) })),
    h('div', { class: 'pbar lg' + (state === 'braked' ? ' r' : state === 'paused' ? ' a' : ''), style: 'margin-top:10px' }, h('div', { style: `width:${p}%` })),
    h('div', { class: 'stats' }, h('span', {}, h('b', {}, fmt(done)), ' / ' + fmt(j.total) + ` (${Math.round(p)}%)`), h('span', {}, 'Sent ', h('b', {}, fmt(j.sent))),
      h('span', {}, 'Bounced ', h('b', { style: j.bounced ? 'color:var(--red-d)' : '' }, fmt(j.bounced))), h('span', {}, 'Failed ', h('b', {}, fmt(j.failed))), h('span', {}, 'Skipped ', h('b', {}, fmt(j.skipped))),
      state === 'running' ? h('span', {}, h('b', {}, fmt(j.rate)), '/min') : null, state === 'running' && j.eta ? h('span', {}, '~', h('b', {}, dur(j.eta)), ' left') : null,
      j.current && state === 'running' ? h('span', { class: 'ellipsis', style: 'max-width:240px' }, '→ ' + j.current) : null));
  if (state === 'braked') box.append(h('div', { style: 'margin-top:12px' }, banner('err', h('span', {}, h('b', {}, 'Safety brake triggered. '), j.brake), [
    btn('Resume anyway', { size: 'sm', onclick: async () => { if (await confirmBox({ title: 'Resume sending?', text: 'The brake protects your sender reputation. Only resume if you fixed the cause (cleaned the list, fixed the sender). The brake keeps watching after you resume.', ok: 'Resume sending' })) ctrl(j.campaign_id, 'resume'); } })])));
  else if (state === 'waiting') box.append(h('div', { style: 'margin-top:12px' }, banner('info', j.waiting)));
  if ((j.senders || []).some(s => s.dropped)) box.append(h('div', { style: 'margin-top:10px' }, banner('warn', 'Auto-paused senders: ' + j.senders.filter(s => s.dropped).map(s => `${s.email} (${s.error})`).join(' · '))));
  return box;
}
const CAMP_TABS = [['all', 'All'], ['active', 'Active'], ['done', 'Completed'], ['attention', 'Needs attention']];
let CAMP_TAB = 'all';
async function viewCampaigns() {
  if (APP.sub === 'new' || APP.sub === 'builder') return campaignBuilder();
  if (APP.sub === 'report') return showReport(APP.id);
  await loadState();
  const v = $('#view');
  setTop(btn('New campaign', { kind: 'primary', icon: 'plus', onclick: () => newCampaign() }));
  const liveBox = h('div');
  APP.live = () => { const run = runningJobs(); liveBox.replaceChildren(run.length ? card(h('span', { class: 'hstack' }, h('span', { class: 'live-dot' }), `Sending now (${run.length})`), null, null, h('div', { class: 'card-b' }, run.map(runCard))) : ''); };
  APP.live();
  const camps = APP.state.campaigns || [];
  const cat = c => { const s = liveStatus(c); if (['running', 'queued', 'scheduled', 'paused', 'waiting', 'braked'].includes(s)) return 'active'; if (s === 'done') return 'done'; if (['interrupted', 'stopped', 'error'].includes(s)) return 'attention'; return 'other'; };
  const counts = { all: camps.length }; camps.forEach(c => counts[cat(c)] = (counts[cat(c)] || 0) + 1);
  const listCard = h('div', { class: 'card' });
  const sel = new Set();
  const isRunning = c => ['running', 'paused', 'waiting', 'braked'].includes(liveStatus(c));
  const renderList = () => {
    const rows = camps.filter(c => CAMP_TAB === 'all' || cat(c) === CAMP_TAB);
    [...sel].forEach(id => { if (!rows.some(c => c.id === id)) sel.delete(id); });
    const tabs = h('div', { class: 'tabs' }, CAMP_TABS.map(([k, l]) => h('button', { class: CAMP_TAB === k ? 'on' : '', onclick: () => { CAMP_TAB = k; renderList(); } }, l, h('span', { class: 'c' }, counts[k] || 0))));
    let body;
    if (!camps.length) body = emptyState('send', 'No campaigns yet', 'Pick a contact group, write your email (or start from a template), choose your senders and launch. Safety brakes watch every send.', btn('Create your first campaign', { kind: 'primary', icon: 'plus', onclick: () => newCampaign() }));
    else if (!rows.length) body = h('div', { class: 'empty', style: 'padding:30px' }, 'Nothing here.');
    else {
      const deletable = rows.filter(c => !isRunning(c)), allOn = deletable.length > 0 && deletable.every(c => sel.has(c.id));
      const hcb = h('input', { type: 'checkbox', title: 'Select all', checked: allOn, disabled: !deletable.length });
      hcb.indeterminate = !allOn && sel.size > 0;
      hcb.addEventListener('change', () => { if (hcb.checked) deletable.forEach(c => sel.add(c.id)); else sel.clear(); renderList(); });
      body = h('div', {}, sel.size ? h('div', { class: 'bulkbar' }, h('b', {}, `${fmt(sel.size)} selected`), h('span', { class: 'spacer' }),
        btn('Clear selection', { size: 'sm', kind: 'quiet', onclick: () => { sel.clear(); renderList(); } }),
        btn(`Delete ${fmt(sel.size)}`, { size: 'sm', kind: 'danger', icon: 'trash', onclick: () => deleteCampaigns([...sel], () => { sel.clear(); viewCampaigns(); }) })) : null,
      h('div', { class: 'tbl-wrap' }, h('table', { class: 't' },
      h('thead', {}, h('tr', {}, h('th', { class: 'w-cb' }, hcb), h('th', {}, 'Campaign'), h('th', {}, 'Status'), h('th', { class: 'num' }, 'Sent'), h('th', { class: 'num' }, 'Opens'), h('th', { class: 'num' }, 'Clicks'), h('th', { class: 'num' }, 'Replies'), h('th', { class: 'num' }, 'Bounced'), h('th', {}, ''))),
      h('tbody', {}, rows.map(c => {
        const s = liveStatus(c), run = isRunning(c);
        const cb = h('input', { type: 'checkbox', checked: sel.has(c.id), disabled: run, title: run ? 'Stop it before deleting' : 'Select', onchange: e => { e.target.checked ? sel.add(c.id) : sel.delete(c.id); renderList(); } });
        return h('tr', { class: 'click' + (sel.has(c.id) ? ' sel' : ''), onclick: e => { if (!e.target.closest('button,input')) go('campaigns', 'report', c.id); } },
          h('td', { class: 'w-cb' }, cb),
          h('td', { style: 'max-width:340px' }, h('div', { class: 'b ellipsis' }, c.name), h('div', { class: 'sub-t ellipsis' }, c.subject || ''),
            c.brake_reason && s !== 'running' ? h('div', { class: 'xs', style: 'color:var(--red-d)' }, '⚠ ' + c.brake_reason.slice(0, 90)) : null),
          h('td', {}, statusPill(s), c.status === 'scheduled' && c.scheduled_at ? h('div', { class: 'xs muted', style: 'margin-top:3px' }, dt(c.scheduled_at)) : null),
          h('td', { class: 'num' }, fmt(liveSent(c))), h('td', { class: 'num' }, fmt(c.opens), h('div', { class: 'xs muted' }, pct(c.opens, liveSent(c)))),
          h('td', { class: 'num' }, fmt(c.clicks), h('div', { class: 'xs muted' }, pct(c.clicks, c.sent))), h('td', { class: 'num' }, h('b', { style: c.replies ? 'color:var(--green-d)' : '' }, fmt(c.replies)), h('div', { class: 'xs muted' }, pct(c.replies, c.sent))),
          h('td', { class: 'num' }, fmt(c.bounced), h('div', { class: 'xs muted' }, pct(c.bounced, (c.sent || 0) + (c.bounced || 0)))),
          h('td', { class: 'nowrap', style: 'width:76px;text-align:right' }, run ? null : iconBtn('trash', 'Delete campaign', () => deleteCampaigns([c.id], () => viewCampaigns()), true),
            iconBtn('dots', 'Actions', e => campMenu(e.currentTarget, c), true)));
      })))));
    }
    listCard.replaceChildren(tabs, body);
  };
  renderList();
  v.replaceChildren(liveBox, listCard);
}
function campMenu(anchor, c) {
  const s = liveStatus(c), running = ['running', 'paused', 'waiting', 'braked'].includes(s);
  openMenu(anchor, [
    { label: 'Open report', icon: 'activity', onclick: () => go('campaigns', 'report', c.id) },
    { label: 'Duplicate', icon: 'copy', onclick: () => duplicateCampaign(c.id) },
    ['interrupted', 'stopped', 'error'].includes(s) ? { label: 'Resume sending', icon: 'play', onclick: () => resumeRun(c.id) } : null,
    ['scheduled', 'queued'].includes(s) ? { label: 'Cancel schedule', icon: 'x', onclick: async () => { await POST(`/api/campaign/${c.id}/cancel`); toast('Schedule cancelled.'); render(); } } : null,
    { label: 'Export CSV report', icon: 'download', onclick: () => location.href = `/api/export/report/${c.id}.csv` },
    'sep',
    running ? { label: 'Stop it first to delete', icon: 'trash', onclick: () => toast('Stop the campaign (Stop button above) — then you can delete it.', 'info') } :
      { label: 'Delete campaign', icon: 'trash', danger: true, onclick: () => deleteCampaigns([c.id], () => render()) },
  ]);
}
async function deleteCampaigns(ids, after) {
  const one = ids.length === 1, c = one ? (APP.state.campaigns || []).find(x => x.id === ids[0]) : null;
  if (!await confirmBox({ title: one ? 'Delete campaign?' : `Delete ${fmt(ids.length)} campaigns?`,
    text: (one ? `“${c ? c.name : 'This campaign'}”` : 'These campaigns') + ' will be permanently deleted with their follow-up steps, reports and open/click stats. Your contacts are not affected, and bounced/unsubscribed addresses stay blocked.',
    ok: one ? 'Delete' : `Delete ${fmt(ids.length)}`, danger: true })) return;
  const r = one ? await POST(`/api/campaign/${ids[0]}/delete`) : await POST('/api/campaigns/delete', { ids });
  if (!r.ok) return toast(r.error, 'err');
  toast(one ? 'Campaign deleted.' : `Deleted ${fmt(r.count)} campaign(s).` + (r.skipped_running ? ` ${r.skipped_running} still sending — stop them first.` : ''));
  await loadState(); after && after();
}
async function resumeRun(cid) {
  const r = await POST(`/api/campaign/${cid}/resume-run`);
  if (!r.ok) return toast(r.error, 'err');
  if (r.nothing) toast('Everyone in this campaign was already emailed — marked as completed.', 'info');
  else toast(`Resumed — ${fmt(r.remaining)} people still to email.`);
  await loadState(); render();
}

/* ---------------- builder ---------------- */
function CBdefault() {
  return { step: 1, name: '', group_ids: [], exclude_group_ids: [], showExclude: false, subject: '', subject_b: '', ab: false, html: '', text: '',
    account_ids: [], rate: '30', jitter: '3', track_opens: true, track_clicks: true, brakes: true, schedule: '', testTo: '', followups: [], device: 'desktop', count: null };
}
let CB = CBdefault();
function newCampaign(preset) { CB = Object.assign(CBdefault(), preset || {}); go('campaigns', 'new'); }
async function duplicateCampaign(id) {
  const c = await GET('/api/campaign/' + id); if (!c || !c.id) return toast('Could not load campaign.', 'err');
  newCampaign({ name: c.name + ' (copy)', subject: c.subject, subject_b: c.subject_b || '', ab: !!c.subject_b, html: c.html, text: c.text || '',
    group_ids: c.group_ids || [], exclude_group_ids: c.exclude_group_ids || [], showExclude: (c.exclude_group_ids || []).length > 0,
    account_ids: (c.account_ids || []).map(String), rate: String(c.rate || 30), jitter: String(c.jitter || 3), track_opens: !!c.track_opens, track_clicks: !!c.track_clicks,
    brakes: c.brakes !== 0, followups: c.followups || [] });
}
function campaignBuilder() {
  setTop(btn('Cancel', { onclick: async () => { if (!CB.subject && !CB.html || await confirmBox({ title: 'Discard this campaign?', text: 'Your unsent changes will be lost.', ok: 'Discard', danger: true })) go('campaigns'); } }));
  $('#ttl').textContent = CB.name || 'New campaign';
  $('#view').replaceChildren(h('div', { id: 'cbsteps' }), h('div', { id: 'cbstep' }));
  renderStep();
}
function renderStep() {
  const labels = [['Audience', 'Groups & subject'], ['Content', 'Design your email'], ['Send', 'Senders, safety & schedule']];
  $('#cbsteps').replaceChildren(h('div', { class: 'steps' }, labels.map(([l, s], i) => {
    const n = i + 1, cls = CB.step === n ? 'on' : CB.step > n ? 'done link' : '';
    return h('div', { class: 'st ' + cls, onclick: () => { if (n < CB.step) { CB.step = n; renderStep(); } } }, h('span', { class: 'n' }, CB.step > n ? icon('check', 13, 3) : n), h('div', {}, l, h('small', {}, s)));
  })));
  const box = $('#cbstep'); box.replaceChildren();
  window.scrollTo(0, 0);
  [stepAudience, stepContent, stepSend][CB.step - 1](box);
}
const refreshCount = debounce(async (el) => {
  const q = `groups=${CB.group_ids.join(',')}&exclude=${CB.exclude_group_ids.join(',')}`;
  const r = await GET('/api/recipients/count?' + q); CB.count = r.count || 0; if (el) el.textContent = fmt(CB.count);
}, 200);
function stepAudience(box) {
  const groups = APP.state.groups || [], cs = APP.state.contacts || {};
  const name = h('input', { value: CB.name, placeholder: 'e.g. October outreach — SaaS founders', oninput: e => { CB.name = e.target.value; $('#ttl').textContent = CB.name || 'New campaign'; } });
  const countEl = h('span', { class: 'big' }, CB.count == null ? '…' : fmt(CB.count));
  const pickBox = h('div'), exBox = h('div');
  const renderPicks = () => {
    const allOn = !CB.group_ids.length;
    pickBox.replaceChildren(h('div', { class: 'pick-grid' },
      h('div', { class: 'pick' + (allOn ? ' on' : ''), onclick: () => { CB.group_ids = []; renderPicks(); refreshCount(countEl); } },
        h('input', { type: 'radio', checked: allOn }), h('div', { class: 'pt' }, h('b', {}, 'All active contacts'), h('span', {}, fmt(cs.active) + ' contacts'))),
      groups.map(g => { const on = CB.group_ids.includes(g.id); return h('div', { class: 'pick' + (on ? ' on' : ''), onclick: () => {
        CB.group_ids = on ? CB.group_ids.filter(x => x !== g.id) : [...CB.group_ids, g.id]; CB.exclude_group_ids = CB.exclude_group_ids.filter(x => x !== g.id); renderPicks(); refreshCount(countEl); } },
        h('input', { type: 'checkbox', checked: on }), h('span', { class: 'dot', style: `width:10px;height:10px;border-radius:3px;background:${g.color}` }),
        h('div', { class: 'pt' }, h('b', {}, g.name), h('span', {}, fmt(g.active) + ' active' + (g.n !== g.active ? ` · ${fmt(g.n)} total` : '')))); })));
    exBox.replaceChildren(!CB.showExclude ? btn('Exclude groups…', { kind: 'quiet', size: 'sm', icon: 'minus', onclick: () => { CB.showExclude = true; renderPicks(); } }) :
      h('div', {}, h('label', { class: 'f' }, 'Exclude anyone who is also in', h('span', { class: 'opt' }, ' · optional')), h('div', { class: 'pick-grid' },
        groups.filter(g => !CB.group_ids.includes(g.id)).map(g => { const on = CB.exclude_group_ids.includes(g.id); return h('div', { class: 'pick ex' + (on ? ' on' : ''), onclick: () => {
          CB.exclude_group_ids = on ? CB.exclude_group_ids.filter(x => x !== g.id) : [...CB.exclude_group_ids, g.id]; renderPicks(); refreshCount(countEl); } },
          h('input', { type: 'checkbox', checked: on }), h('span', { class: 'dot', style: `width:10px;height:10px;border-radius:3px;background:${g.color}` }), h('div', { class: 'pt' }, h('b', {}, g.name), h('span', {}, fmt(g.active) + ' active'))); }))));
  };
  renderPicks(); refreshCount(countEl);
  const subject = h('input', { value: CB.subject, placeholder: 'Quick question, {{first_name|there}}', oninput: e => { CB.subject = e.target.value; lenHint(); } });
  const lenEl = h('span', { class: 'xs muted' }); const lenHint = () => { const n = CB.subject.length; lenEl.textContent = n ? `${n} characters${n > 60 ? ' · may be cut off on mobile' : ''}` : ''; lenEl.style.color = n > 60 ? 'var(--amber-d)' : ''; }; lenHint();
  const subjectB = h('input', { value: CB.subject_b, placeholder: 'Alternative subject (variant B)', oninput: e => CB.subject_b = e.target.value });
  const abWrap = h('div', { style: CB.ab ? '' : 'display:none' }, field('Subject — variant B', subjectB, null, 'Half of your recipients get A, half get B. The report shows which one gets more opens.'));
  const sugg = h('div');
  box.append(h('div', { class: 'split' },
    h('div', {},
      card('Who should receive it?', 'Pick one or more groups — contacts in several groups get it only once. Unsubscribed and bounced people are always skipped.', null,
        h('div', { class: 'card-b' }, pickBox, h('div', { style: 'margin-top:10px' }, exBox),
          h('div', { class: 'aud-sum' }, icon('users', 22), h('div', {}, countEl, h('div', { class: 'small muted' }, 'unique active recipients')),
            groups.length ? null : h('div', { class: 'small muted', style: 'margin-left:auto;max-width:300px' }, 'Tip: organize contacts into groups on the Contacts page to target them separately.')))),
    ),
    h('div', {},
      card('Campaign details', null, null, h('div', { class: 'card-b' },
        field('Campaign name', name, null, 'Only you see this.'),
        field('Subject line', subject), h('div', { class: 'hstack', style: 'margin-top:6px' }, lenEl),
        h('div', { class: 'hstack', style: 'margin-top:14px;justify-content:space-between' }, toggle('A/B test the subject', CB.ab, v => { CB.ab = v; abWrap.style.display = v ? '' : 'none'; }),
          btn('Suggest subjects', { size: 'sm', kind: 'quiet', icon: 'sparkles', onclick: () => loadSuggestions(sugg, subject) })),
        abWrap, sugg)))),
    h('div', { class: 'hstack', style: 'justify-content:flex-end;margin-top:4px' }, btn('Continue to content', { kind: 'primary', size: 'lg', icon: 'right', onclick: () => {
      if (!CB.subject.trim()) { subject.focus(); return toast('Add a subject line.', 'warn'); }
      if (CB.ab && !CB.subject_b.trim()) { subjectB.focus(); return toast('Add the B subject, or turn off the A/B test.', 'warn'); }
      if (CB.count === 0) return toast('No active contacts match these groups.', 'warn');
      CB.step = 2; renderStep(); } })));
}
async function loadSuggestions(box, subjInput) {
  const r = await GET('/api/suggest/subjects');
  box.replaceChildren(h('div', { style: 'margin-top:12px' }, h('div', { class: 'xs muted', style: 'margin-bottom:6px' }, 'Click one to use it:'),
    ...(r.subjects || []).map(s => h('span', { class: 'tagbtn', onclick: () => { CB.subject = s; subjInput.value = s; subjInput.dispatchEvent(new Event('input')); } }, s)),
    h('div', { style: 'margin-top:8px' }, banner('info', (r.tips || []).join(' · ')))));
}
function previewFill(s) {
  return (s || '').replace(/\{\{\s*([\w.]+)\s*(?:\|\s*([^}]*?)\s*)?\}\}/g, (m, k, f) => {
    const map = { first_name: 'Alex', last_name: 'Morgan', name: 'Alex Morgan', email: 'alex@example.com', 'data.company': 'Acme Inc', unsubscribe: '#' };
    return map[k] != null ? map[k] : (f || ''); });
}
function stepContent(box) {
  const tags = ['first_name|there', 'last_name', 'email', 'data.company|your team', 'unsubscribe'];
  const html = h('textarea', { class: 'code', style: 'min-height:340px', placeholder: '<p>Hi {{first_name|there}},</p>\n<p>…</p>\n<p><a href="{{unsubscribe}}">Unsubscribe</a></p>', oninput: e => { CB.html = e.target.value; upd(); } }); html.value = CB.html;
  const text = h('textarea', { class: 'code', style: 'min-height:90px', placeholder: 'Plain-text version — leave blank to generate it automatically from the HTML', oninput: e => CB.text = e.target.value }); text.value = CB.text;
  const insert = tag => { const s = html.selectionStart ?? html.value.length; html.value = html.value.slice(0, s) + tag + html.value.slice(html.selectionEnd ?? s); CB.html = html.value; html.focus(); html.selectionStart = html.selectionEnd = s + tag.length; upd(); };
  const spam = h('div'), testTo = h('input', { value: CB.testTo, placeholder: 'you@example.com', oninput: e => CB.testTo = e.target.value });
  const frame = h('iframe', { title: 'Preview' });
  const pv = h('div', { class: 'preview' + (CB.device === 'mobile' ? ' mobile' : '') });
  const acc = (APP.state.accounts || [])[0];
  const subjEl = h('div', { class: 'subj ellipsis' }), fromEl = h('div', { class: 'from muted ellipsis' }, acc ? `${acc.from_name || ''} <${acc.from_email}>` : 'Your sender');
  const seg = h('div', { class: 'seg', style: 'margin-left:auto' }, [['desktop', 'monitor'], ['mobile', 'phone']].map(([d, ic]) => h('button', { class: CB.device === d ? 'on' : '', title: d, onclick: () => { CB.device = d; pv.classList.toggle('mobile', d === 'mobile'); seg.querySelectorAll('button').forEach(b => b.classList.toggle('on', b.title === d)); } }, icon(ic, 15))));
  pv.append(h('div', { class: 'ph' }, avatar(acc ? acc.from_name : 'Y', acc ? acc.from_email : 'y', 30), h('div', { style: 'min-width:0;flex:1' }, subjEl, fromEl), seg), h('div', { class: 'frame-wrap' }, frame));
  const upd = debounce(() => { subjEl.textContent = previewFill(CB.subject); frame.srcdoc = '<meta charset="utf-8"><style>body{font-family:Arial,Helvetica,sans-serif;margin:18px;color:#222;line-height:1.55}img{max-width:100%}</style>' + (previewFill(CB.html) || '<p style="color:#999">Your email preview appears here.</p>'); }, 120);
  upd();
  const noUnsub = () => !/unsubscribe/i.test(CB.html);
  box.append(h('div', { class: 'grid g2', style: 'align-items:start' },
    h('div', {}, card('Email content', 'HTML is supported. Use merge tags to personalize each email.', h('div', { class: 'hstack' },
      btn('Templates', { size: 'sm', icon: 'layout', onclick: () => templatePicker(t => { html.value = CB.html = t.html || ''; if (!CB.subject) CB.subject = t.subject || ''; text.value = CB.text = t.text || ''; upd(); }) })),
      h('div', { class: 'card-b' },
        h('div', { class: 'xs muted', style: 'margin-bottom:6px' }, 'Insert merge tag'), h('div', {}, tags.map(t => h('span', { class: 'tagbtn', onclick: () => insert('{{' + t + '}}') }, '{{' + t.split('|')[0] + '}}'))),
        h('label', { class: 'f' }, 'HTML'), html,
        h('label', { class: 'f' }, 'Plain-text version', h('span', { class: 'opt' }, ' · optional')), text,
        h('div', { class: 'hstack', style: 'margin-top:14px' }, btn('Check spam score', { icon: 'shield', onclick: () => checkSpam(spam) }), h('span', { class: 'spacer' }),
          btn('Save as template', { icon: 'layout', onclick: () => { if (!CB.html.trim()) return toast('Write the email content first.', 'warn'); templateModal({ name: CB.name, subject: CB.subject, html: CB.html, text: CB.text }); } })),
        spam,
        hrule(),
        h('div', { class: 'b small' }, 'Send yourself a test'), h('div', { class: 'help' }, 'Uses your first selected sender. Subject is prefixed with [TEST].'),
        h('div', { class: 'hstack' }, h('div', { style: 'flex:1' }, testTo), btn('Send test', { icon: 'send', onclick: () => sendTest(CB.testTo) }))))),
    h('div', {}, pv)),
    h('div', { class: 'hstack', style: 'justify-content:space-between;margin-top:16px' }, btn('Back', { icon: 'left', onclick: () => { CB.step = 1; renderStep(); } }),
      btn('Continue to sending', { kind: 'primary', size: 'lg', icon: 'right', onclick: async () => {
        if (!CB.html.trim()) { html.focus(); return toast('Add your email content.', 'warn'); }
        if (noUnsub() && !await confirmBox({ title: 'No unsubscribe link?', text: 'MailBlaster adds an unsubscribe link at the bottom automatically. For best deliverability, place {{unsubscribe}} in your footer yourself. Continue anyway?', ok: 'Continue' })) return;
        CB.step = 3; renderStep(); } })));
}
const hrule = () => h('hr', { class: 'sep' });
async function checkSpam(box) {
  const r = await POST('/api/spam-check', { subject: CB.subject, html: CB.html });
  const k = r.grade === 'Great' ? 'ok' : r.grade === 'OK' ? 'warn' : 'err';
  box.replaceChildren(h('div', { style: 'margin-top:12px' }, banner(k, h('div', {}, h('b', {}, `Spam score ${r.score}/100 · ${r.grade}`),
    (r.issues || []).length ? h('ul', { style: 'margin:6px 0 0;padding-left:18px' }, r.issues.map(i => h('li', {}, i))) : h('div', {}, 'Looks clean — nothing that typically triggers spam filters.')))));
}
async function sendTest(to) {
  if (!to) return toast('Enter an address for the test.', 'warn');
  toast('Sending test…', 'info', 2000);
  const r = await POST('/api/test-send', { to, subject: CB.subject, html: CB.html, text: CB.text, account_ids: CB.account_ids });
  r.ok ? toast(r.message) : toast(r.error, 'err', 8000);
}
async function templatePicker(onPick) {
  const grid = h('div', { class: 'tpl-grid' });
  const m = modal({ title: 'Choose a template', icon: 'layout', wide: true, body: grid });
  for (const t of APP.state.templates || []) {
    const full = await GET('/api/templates/' + t.id);
    grid.append(h('div', { class: 'tpl', onclick: () => { m.close(); onPick(full); } }, h('div', { class: 'pv' }, h('iframe', { srcdoc: '<meta charset="utf-8">' + previewFill(full.html || ''), tabindex: '-1' })),
      h('div', { class: 'meta' }, h('div', { style: 'flex:1;min-width:0' }, h('b', { class: 'small' }, t.name), h('div', { class: 'xs muted' }, t.category)))));
  }
}
function stepSend(box) {
  const accs = APP.state.accounts || [];
  const accBox = h('div'); const capEl = h('div');
  const chosen = () => accs.filter(a => a.active && !a.paused_reason && (!CB.account_ids.length || CB.account_ids.includes(String(a.id))));
  const renderCap = () => {
    const cap = chosen().reduce((s, a) => s + Math.max(0, a.effective_limit - (a.sent_today || 0)), 0), n = CB.count || 0;
    const days = cap ? Math.ceil(n / Math.max(1, cap)) : 0;
    capEl.replaceChildren(cap >= n ? banner('ok', `Today’s capacity on the selected senders: ${fmt(cap)} emails — enough for all ${fmt(n)} recipients.`) :
      banner('warn', `Today’s capacity is ${fmt(cap)} but you have ${fmt(n)} recipients. MailBlaster sends ${fmt(cap)} today and continues automatically each day (about ${days} day${days > 1 ? 's' : ''}). Add senders or raise limits to go faster.`));
  };
  const renderAccs = () => {
    if (!accs.length) { accBox.replaceChildren(banner('err', 'You need a sender account first.', [btn('Add sender', { size: 'sm', onclick: () => go('senders', 'new') })])); return; }
    accBox.replaceChildren(h('div', { class: 'pick-grid', style: 'grid-template-columns:repeat(auto-fill,minmax(260px,1fr))' }, accs.map(a => {
      const on = CB.account_ids.includes(String(a.id)), usable = a.active && !a.paused_reason, left = Math.max(0, a.effective_limit - (a.sent_today || 0));
      return h('div', { class: 'pick' + (on ? ' on' : ''), style: usable ? '' : 'opacity:.55', title: a.paused_reason || '', onclick: () => {
        if (!usable) return toast(a.paused_reason ? 'This sender is auto-paused: ' + a.paused_reason : 'This sender is turned off.', 'warn');
        CB.account_ids = on ? CB.account_ids.filter(x => x !== String(a.id)) : [...CB.account_ids, String(a.id)]; renderAccs(); renderCap(); } },
        h('input', { type: 'checkbox', checked: on }), h('div', { class: 'pt' }, h('b', {}, a.from_email || a.label),
          h('span', {}, usable ? `${fmt(left)} left today` + (a.warmup && a.warmup.active && !a.warmup.done ? ` · warm-up day ${a.warmup.day}` : '') : (a.paused_reason ? 'Auto-paused' : 'Off'))));
    })), h('div', { class: 'help', style: 'margin-top:8px' }, CB.account_ids.length ? `Rotating across ${CB.account_ids.length} sender(s).` : 'None selected = rotate across all active senders.'));
  };
  renderAccs(); if (CB.count == null) refreshCount(null); setTimeout(renderCap, 260);
  const rate = h('input', { type: 'number', min: '1', value: CB.rate, oninput: e => { CB.rate = e.target.value; etaUpd(); } });
  const jit = h('input', { type: 'number', min: '0', value: CB.jitter, oninput: e => CB.jitter = e.target.value });
  const etaEl = h('div', { class: 'help', style: 'margin-top:6px' }); const etaUpd = () => { const r = Math.max(1, +CB.rate || 1); etaEl.textContent = `≈ ${dur((CB.count || 0) / r * 60)} to send ${fmt(CB.count || 0)} emails at ${r}/min (before daily limits). Cold email: 10–40/min per sender looks natural.`; }; etaUpd();
  const sched = h('input', { type: 'datetime-local', value: CB.schedule, oninput: e => { CB.schedule = e.target.value; sendBtnUpd(); } });
  const fuList = h('div');
  const renderFU = () => {
    fuList.replaceChildren(...CB.followups.map((fu, i) => {
      const dh = h('input', { type: 'number', min: '1', value: fu.delay_hours, oninput: e => fu.delay_hours = e.target.value });
      const to = h('select', { onchange: e => fu.send_to = e.target.value }, [['non_openers', 'People who didn’t open'], ['all', 'Everyone who received it'], ['openers', 'Only people who opened']].map(([v, l]) => h('option', { value: v, selected: fu.send_to === v }, l)));
      const subj = h('input', { value: fu.subject, oninput: e => fu.subject = e.target.value });
      const body = h('textarea', { class: 'code', style: 'min-height:100px', oninput: e => fu.html = e.target.value }); body.value = fu.html;
      return h('div', { class: 'fu' }, h('div', { class: 'hstack' }, h('span', { class: 'fu-n' }, i + 1), h('b', {}, 'Follow-up ' + (i + 1)), h('span', { class: 'spacer' }),
        btn('Remove', { size: 'sm', kind: 'quiet', icon: 'trash', onclick: () => { CB.followups.splice(i, 1); renderFU(); } })),
        h('div', { class: 'row' }, field('Send after (hours)', dh), field('Send to', to)), field('Subject', subj), field('Content (HTML)', body));
    }));
  };
  renderFU();
  const sendBtn = btn('', { kind: 'primary', size: 'lg', disabled: !accs.length, onclick: () => doSend() });
  const sendBtnUpd = () => { sendBtn.replaceChildren(icon(CB.schedule ? 'calendar' : 'send', 17), CB.schedule ? 'Schedule campaign' : 'Launch campaign'); }; sendBtnUpd();
  const groupsTxt = CB.group_ids.length ? (APP.state.groups || []).filter(g => CB.group_ids.includes(g.id)).map(g => g.name).join(', ') : 'All active contacts';
  const exTxt = (APP.state.groups || []).filter(g => CB.exclude_group_ids.includes(g.id)).map(g => g.name).join(', ');
  box.append(h('div', { class: 'split' },
    h('div', {},
      card('Senders', 'Pick the accounts that send this campaign. Volume rotates between them and every daily limit / warm-up step is respected.', null, h('div', { class: 'card-b' }, accBox, h('div', { style: 'margin-top:12px' }, capEl))),
      card('Speed & schedule', null, null, h('div', { class: 'card-b' },
        h('div', { class: 'row' }, field('Emails per minute', rate), field('Random extra delay (0–N sec)', jit, null)), etaEl,
        field('Schedule for later', sched, 'optional', 'Leave empty to start now. Keep MailBlaster running for scheduled sends. Your sending-window setting also applies.'),
        trackingControls())),
      card('Follow-up sequence', 'Automatic follow-ups — the #1 way to get more replies. Anyone who replies is removed from the sequence automatically.', btn('Add step', { size: 'sm', icon: 'plus', onclick: () => { CB.followups.push({ delay_hours: String(48 * (CB.followups.length + 1)), subject: 'Re: ' + CB.subject, html: CB.html, text: '', send_to: 'non_openers' }); renderFU(); } }),
        h('div', { class: 'card-b' }, fuList, CB.followups.length ? null : h('div', { class: 'muted small' }, 'No follow-ups. Add one to automatically nudge people who didn’t respond.')))),
    h('div', {},
      card('Safety', null, null, h('div', { class: 'card-b' },
        toggle('Safety brakes', CB.brakes, v => CB.brakes = v, 'Auto-pause if bounces, complaints, unsubscribes or failures spike'),
        h('div', { class: 'help', style: 'margin-top:10px' }, 'Thresholds are set on the Deliverability page. Senders that fail repeatedly are paused automatically, and the campaign keeps going on the others.'))),
      card('Review', null, null, h('div', { class: 'card-b' }, h('dl', { class: 'review' },
        h('dt', {}, 'Campaign'), h('dd', {}, CB.name || 'Campaign'), h('dt', {}, 'Subject'), h('dd', {}, CB.subject + (CB.ab ? '  /  B: ' + CB.subject_b : '')),
        h('dt', {}, 'Audience'), h('dd', {}, groupsTxt, exTxt ? h('div', { class: 'xs muted' }, 'Excluding: ' + exTxt) : null),
        h('dt', {}, 'Recipients'), h('dd', {}, CB.count == null ? '…' : fmt(CB.count)), h('dt', {}, 'Follow-ups'), h('dd', {}, CB.followups.length ? CB.followups.length + ' step(s)' : 'None')),
        h('div', { style: 'margin-top:18px' }, sendBtn), h('div', { class: 'xs muted', style: 'margin-top:8px' }, 'Every email includes a working unsubscribe link and one-click List-Unsubscribe header.'))))),
    h('div', { style: 'margin-top:4px' }, btn('Back', { icon: 'left', onclick: () => { CB.step = 2; renderStep(); } })));
}
async function doSend() {
  const n = CB.count || 0;
  const when = CB.schedule ? new Date(CB.schedule) : null;
  if (when && when.getTime() < Date.now()) return toast('The scheduled time is in the past.', 'warn');
  const ok = await confirmBox({ title: when ? 'Schedule this campaign?' : 'Launch this campaign?', icon: 'send', ok: when ? 'Schedule' : 'Launch now',
    text: when ? `“${CB.name || 'Campaign'}” will start ${when.toLocaleString()} to ${fmt(n)} recipients.` : `“${CB.name || 'Campaign'}” will start sending to ${fmt(n)} recipients now.` + (CB.followups.length ? ` ${CB.followups.length} follow-up step(s) will be scheduled.` : '') });
  if (!ok) return;
  const r = await POST('/api/campaign/send', { name: CB.name || 'Campaign', subject: CB.subject, subject_b: CB.ab ? CB.subject_b : '', html: CB.html, text: CB.text,
    group_ids: CB.group_ids, exclude_group_ids: CB.exclude_group_ids, account_ids: CB.account_ids, rate_per_min: CB.rate || 30, jitter: CB.jitter || 0,
    track_opens: CB.track_opens ? 1 : 0, track_clicks: CB.track_clicks ? 1 : 0, brakes: CB.brakes ? 1 : 0,
    followups: CB.followups.length ? JSON.stringify(CB.followups) : '', scheduled_at: when ? Math.floor(when.getTime() / 1000) : '' });
  if (!r.ok) return toast(r.error, 'err', 8000);
  await loadState();
  if (r.scheduled) { toast('Scheduled! It starts automatically — keep MailBlaster running.'); go('campaigns'); }
  else if (r.queued) { toast('Queued — it starts as soon as a sending slot frees up.', 'info'); go('campaigns'); }
  else { toast(`Launched — sending to ${fmt(r.total)} people.`); go('campaigns', 'report', r.campaign_id); }
}

/* ---------------- report ---------------- */
async function showReport(id) {
  const r = await GET('/api/report/' + id); const v = $('#view');
  if (!r || !r.campaign) { v.replaceChildren(emptyState('alert', 'Campaign not found', 'It may have been deleted.', btn('All campaigns', { onclick: () => go('campaigns') }))); return; }
  const c = r.campaign, by = r.by_status || {};
  $('#ttl').textContent = c.name; $('#tsub').textContent = c.subject || '';
  const status = liveStatus(c);
  setTop(btn('All campaigns', { icon: 'left', onclick: () => go('campaigns') }), btn('Duplicate', { icon: 'copy', onclick: () => duplicateCampaign(id) }),
    ['interrupted', 'stopped', 'error'].includes(status) ? btn('Resume sending', { kind: 'primary', icon: 'play', onclick: () => resumeRun(id) }) : null,
    h('a', { class: 'btn', href: `/api/export/report/${id}.csv` }, icon('download', 16), 'Export'),
    ['running', 'paused', 'waiting', 'braked'].includes(status) ? null : btn('Delete', { kind: 'danger', icon: 'trash', onclick: () => deleteCampaigns([id], () => c.parent_id ? go('campaigns', 'report', c.parent_id) : go('campaigns')) }));
  const liveBox = h('div');
  APP.live = () => { const j = (APP.state.jobs || {})[id]; if (j && j.status === 'running') liveBox.replaceChildren(card(h('span', { class: 'hstack' }, h('span', { class: 'live-dot' }), 'Live'), null, null, h('div', { class: 'card-b' }, runCard(j)))); else if (liveBox.firstChild) { liveBox.replaceChildren(); showReport(id); } };
  APP.live();
  const sent = by.sent || c.sent || 0, bounced = by.bounced || 0, attempted = sent + bounced, hl = r.health || {};
  const brate = pnum(bounced + Math.max(0, (hl.hard || 0) - bounced), attempted);
  const kp = h('div', { class: 'grid g6' },
    kpi('send', '#4f46e5', 'var(--brand-l)', 'Delivered', fmt(sent), `${fmt(by.failed || 0)} failed · ${fmt(by.skipped || 0)} skipped`),
    kpi('eye', '#8b5cf6', 'var(--violet-l)', 'Opened', pct(r.opens, sent), fmt(r.opens) + ' people'),
    kpi('pointer', '#0ea5e9', 'var(--sky-l)', 'Clicked', pct(r.clicks, sent), fmt(r.clicks) + ' people'),
    kpi('reply', '#10b981', 'var(--green-l)', 'Replied', pct(r.replies, sent), fmt(r.replies) + ' people', r.replies ? 'good' : ''),
    kpi('bounce', '#ef4444', 'var(--red-l)', 'Bounced', (Math.round(brate * 10) / 10) + '%', fmt(hl.hard || bounced) + ' hard bounces', brate >= 5 ? 'bad' : brate >= 2 ? 'warn' : ''),
    kpi('ban', '#64748b', '#eef1f6', 'Unsubscribed', pct(hl.unsubs, sent), `${fmt(hl.unsubs)} · ${fmt(hl.complaints)} complaints`));
  const parts = [liveBox, h('div', { class: 'hstack', style: 'margin-bottom:14px' }, statusPill(status), (r.groups || []).map(chip), (r.excluded || []).length ? h('span', { class: 'xs muted' }, 'excluding') : null, (r.excluded || []).map(chip),
    h('span', { class: 'xs muted' }, 'Created ' + dt(c.created_at))), kp, h('div', { style: 'height:18px' })];
  if (c.tracking === 'none' && sent) parts.push(h('div', { style: 'margin-bottom:16px' }, banner('warn', h('span', {}, h('b', {}, 'Opens weren’t tracked for this campaign. '), 'It was sent while open tracking was off, so recipients’ mail apps couldn’t report opens. Turn tracking on in Settings before your next send.'), [btn('Settings', { size: 'sm', onclick: () => go('settings') })])));
  if (c.brake_reason && status !== 'braked') parts.push(h('div', { style: 'margin-bottom:16px' }, banner('err', h('span', {}, h('b', {}, 'Safety brake: '), c.brake_reason))));
  const left = [], right = [];
  const variants = r.variants || {};
  if (variants.A && variants.B) {
    const ra = pnum(variants.A.opens || 0, variants.A.sent || 0), rb = pnum(variants.B.opens || 0, variants.B.sent || 0), win = ra >= rb ? 'A' : 'B';
    left.push(card('A/B subject test', 'Open rate by subject line', null, h('div', { class: 'card-b' }, [['A', c.subject, ra, variants.A], ['B', c.subject_b, rb, variants.B]].map(([k, s, rate, vv]) =>
      h('div', { style: 'margin-bottom:12px' }, h('div', { class: 'hstack' }, h('b', {}, k), h('span', { class: 'small ellipsis', style: 'flex:1' }, s), win === k ? pill('Winner', 'g') : null, h('b', {}, (Math.round(rate * 10) / 10) + '%')),
        h('div', { class: 'pbar' + (win === k ? ' g' : ''), style: 'margin-top:6px' }, h('div', { style: `width:${Math.min(100, rate)}%` })), h('div', { class: 'xs muted', style: 'margin-top:3px' }, `${fmt(vv.opens || 0)} opens of ${fmt(vv.sent || 0)}`))))));
  }
  if ((r.replies || []).length) left.push(card('Replies', `${fmt(r.replies.length)} most recent`, btn('Open inbox', { size: 'sm', onclick: () => go('inbox') }), h('div', {}, r.replies.map(x =>
    h('div', { class: 'list-item', onclick: () => go('inbox', 'm', x.id) }, avatar(x.from_name, x.from_email), h('div', { style: 'flex:1;min-width:0' },
      h('div', { class: 'hstack' }, h('b', { class: 'small' }, x.from_name || x.from_email), x.kind === 'auto' ? pill('Auto-reply', 'm') : labelPill(x.label), h('span', { class: 'spacer' }), h('span', { class: 'xs dim' }, timeAgo(x.received_at))),
      h('div', { class: 'small muted ellipsis' }, x.snippet)))))));
  if ((r.children || []).length) left.push(card('Follow-up sequence', 'Repliers are removed automatically', null, h('div', { class: 'tbl-wrap' }, h('table', { class: 't' },
    h('thead', {}, h('tr', {}, h('th', {}, 'Step'), h('th', {}, 'Sends to'), h('th', {}, 'Status'), h('th', { class: 'num' }, 'Sent'), h('th', {}, 'When'), h('th', {}, ''))),
    h('tbody', {}, r.children.map(ch => h('tr', {}, h('td', {}, h('b', {}, 'Follow-up ' + ch.step_no)), h('td', { class: 'small' }, { non_openers: 'Non-openers', openers: 'Openers', all: 'Everyone' }[ch.send_to] || ch.send_to),
      h('td', {}, statusPill(liveStatus(ch))), h('td', { class: 'num' }, fmt(ch.sent)), h('td', { class: 'small muted' }, dt(ch.scheduled_at)),
      h('td', { class: 'nowrap', style: 'text-align:right' }, ['scheduled', 'queued'].includes(ch.status) ? btn('Cancel', { size: 'sm', kind: 'quiet', onclick: async () => { await POST(`/api/campaign/${ch.id}/cancel`); toast('Follow-up cancelled.'); showReport(id); } }) :
        h('a', { class: 'small', href: '#campaigns/report/' + ch.id, style: 'margin-right:8px' }, 'Report'),
        ['running', 'paused', 'waiting', 'braked'].includes(liveStatus(ch)) ? null : iconBtn('trash', 'Delete this follow-up step', async () => {
          if (!await confirmBox({ title: `Delete follow-up ${ch.step_no}?`, text: 'This step and its stats are deleted. It will not be sent. The main campaign and other steps are kept.', ok: 'Delete step', danger: true })) return;
          const x = await POST(`/api/campaign/${ch.id}/delete`); x.ok ? toast('Follow-up deleted.') : toast(x.error, 'err'); showReport(id);
        }, true)))))))));
  if ((r.failures || []).length) left.push(card('Bounces & failures', 'Hard bounces are removed from your list automatically', null, h('div', { class: 'tbl-wrap', style: 'max-height:360px;overflow:auto' }, h('table', { class: 't' },
    h('thead', {}, h('tr', {}, h('th', {}, 'Email'), h('th', {}, 'Type'), h('th', {}, 'Reason'))),
    h('tbody', {}, r.failures.map(f => h('tr', {}, h('td', { class: 'small' }, f.email), h('td', {}, f.status === 'bounced' ? pill('Bounced', 'r') : pill('Failed', 'a')), h('td', { class: 'xs muted', style: 'max-width:420px' }, f.error))))))));
  right.push(card('Delivery breakdown', null, null, h('div', { class: 'card-b' }, [['Delivered', by.sent || 0, 'g'], ['Hard bounced', by.bounced || 0, 'r'], ['Failed / deferred', by.failed || 0, 'a'], ['Skipped (unsubscribed etc.)', by.skipped || 0, '']].map(([l, n, k]) => {
    const tot = Object.values(by).reduce((a, b) => a + b, 0) || 1;
    return h('div', { class: 'meter', style: 'margin-bottom:12px' }, h('div', { class: 'ml' }, h('span', {}, l), h('b', {}, fmt(n))), h('div', { class: 'pbar ' + k }, h('div', { style: `width:${n / tot * 100}%` })));
  }))));
  if ((r.links || []).length) right.push(card('Top links', null, null, h('div', { class: 'card-b' }, r.links.map(l => h('div', { class: 'hstack', style: 'margin-bottom:8px' }, icon('link', 14), h('span', { class: 'small ellipsis', style: 'flex:1', title: l.url }, l.url), h('b', { class: 'small' }, fmt(l.n)))))));
  if ((r.activity || []).length) right.push(card('Recent activity', null, null, h('div', { class: 'card-b', style: 'max-height:380px;overflow:auto' }, r.activity.slice(0, 30).map(a =>
    h('div', { class: 'hstack small', style: 'padding:6px 0;border-bottom:1px solid var(--line)' }, icon(a.type === 'open' ? 'eye' : a.type === 'click' ? 'pointer' : 'ban', 14),
      h('span', { class: 'ellipsis', style: 'flex:1' }, (a.email || 'someone') + ' ' + ({ open: 'opened', click: 'clicked', unsub: 'unsubscribed' }[a.type] || a.type)), h('span', { class: 'xs dim' }, timeAgo(a.ts)))))));
  if (!left.length && !sent) left.push(card('Nothing to report yet', null, null, h('div', { class: 'card-b muted' }, status === 'scheduled' ? 'This campaign is scheduled for ' + dt(c.scheduled_at) + '.' : 'Stats appear here as soon as emails go out.')));
  parts.push(h('div', { class: 'split' }, h('div', {}, left), h('div', {}, right)));
  v.replaceChildren(...parts);
}

/* ================================================================== INBOX */
const IBQ = { box: 'replies', q: '', page: 0, sel: null };
const IB_BOXES = [['replies', 'All replies', 'inbox'], ['unread', 'Unread', 'mail'], ['interested', 'Interested', 'star'], ['meeting', 'Meeting', 'calendar'],
  ['not_interested', 'Not interested', 'thumbdown'], ['unsubscribe', 'Unsubscribe requests', 'ban'], ['auto', 'Auto-replies', 'bot'], ['bounces', 'Bounces', 'bounce'], ['archived', 'Archived', 'archive']];
async function viewInbox() {
  if (APP.sub === 'm' && APP.id) { IBQ.sel = APP.id; }
  const v = $('#view');
  const anyImap = (APP.state.accounts || []).some(a => a.imap_enabled);
  const syncBtn = btn('Sync now', { icon: 'refresh', onclick: () => syncInbox(syncBtn) });
  setTop(btn('Mark all read', { icon: 'check', onclick: async () => { await POST('/api/inbox/read-all'); await refreshInboxCounts(); loadInbox(); } }), syncBtn);
  const top = anyImap ? null : h('div', { style: 'margin-bottom:14px' }, banner('warn', h('span', {}, h('b', {}, 'Inbox sync is off. '), 'Connect IMAP for your senders so MailBlaster can collect replies and process bounces automatically.'), [btn('Set up', { size: 'sm', onclick: () => go('senders') })]));
  const f = h('div', { class: 'ib-f', id: 'ibf' }), l = h('div', { class: 'ib-l' }), r = h('div', { class: 'ib-r', id: 'ibr' });
  const search = h('input', { placeholder: 'Search replies…', value: IBQ.q, oninput: debounce(e => { IBQ.q = e.target.value; IBQ.page = 0; loadInbox(); }, 250) });
  IBQ.chk = new Set();
  l.append(h('div', { class: 'lh' }, h('div', { class: 'inp-ic' }, icon('search', 15), search), h('div', { id: 'ibbulk' })), h('div', { class: 'items', id: 'ibitems' }));
  v.replaceChildren(...[top, h('div', { class: 'ib' }, f, l, r)].filter(Boolean));
  renderInboxFilters(); loadInbox();
  if (IBQ.sel) openInboxItem(IBQ.sel); else r.replaceChildren(emptyState('inbox', 'Select a message', 'Replies are matched to the campaign and contact they belong to. Label them to track your pipeline.'));
}
async function refreshInboxCounts() { const s = await GET('/api/inbox/status'); if (s && s.counts) { APP.state.inbox = s.counts; APP.state.imap = s; renderNav(); renderInboxFilters(); } }
function renderInboxFilters() {
  const f = $('#ibf'); if (!f) return; const c = APP.state.inbox || {};
  f.replaceChildren(...IB_BOXES.map(([k, l, ic], i) => {
    const n = k === 'replies' ? c.unread : c[k];
    return frag(i === 2 ? h('div', { class: 'glab' }, 'Labels') : null, i === 6 ? h('div', { class: 'glab' }, 'System') : null,
      h('div', { class: 'gitem' + (IBQ.box === k ? ' on' : ''), onclick: () => { IBQ.box = k; IBQ.page = 0; IBQ.sel = null; renderInboxFilters(); loadInbox(); } }, icon(ic, 15), h('span', { class: 'gn' }, l), n ? h('span', { class: 'gc' }, fmt(n)) : null));
  }));
}
async function loadInbox() {
  const box = $('#ibitems'); if (!box) return;
  const per = 40 * (IBQ.page + 1);
  const d = await GET(`/api/inbox?box=${IBQ.box}&q=${encodeURIComponent(IBQ.q)}&page=0&per=${per}`);
  if (d.counts) { APP.state.inbox = d.counts; renderNav(); renderInboxFilters(); }
  IBQ.chk = IBQ.chk || new Set();
  const ids = (d.rows || []).map(x => x.id); [...IBQ.chk].forEach(i => { if (!ids.includes(i)) IBQ.chk.delete(i); });
  renderInboxBulk(d.total || 0);
  if (!(d.rows || []).length) { box.replaceChildren(h('div', { class: 'empty', style: 'padding:40px 16px' }, h('div', { class: 'small' }, IBQ.q ? 'No matches.' : 'Nothing here yet.'))); return; }
  const kindIc = { bounce: 'bounce', complaint: 'alert', auto: 'bot' };
  box.replaceChildren(...d.rows.map(x => h('div', { class: 'ib-item' + (IBQ.sel === x.id ? ' on' : '') + (!x.is_read && x.kind === 'reply' ? ' unread' : ''), onclick: e => { if (e.target.closest('input')) return; IBQ.sel = x.id; box.querySelectorAll('.ib-item').forEach(n => n.classList.remove('on')); e.currentTarget.classList.add('on'); e.currentTarget.classList.remove('unread'); openInboxItem(x.id); } },
    h('input', { type: 'checkbox', class: 'ib-cb', title: 'Select', checked: IBQ.chk.has(x.id), onchange: e => { e.target.checked ? IBQ.chk.add(x.id) : IBQ.chk.delete(x.id); renderInboxBulk(d.total || 0); } }),
    kindIc[x.kind] ? h('div', { class: 'avatar', style: 'background:#eef1f6;color:#64748b' }, icon(kindIc[x.kind], 16)) : avatar(x.from_name, x.from_email),
    h('div', { class: 'body' }, h('div', { class: 'hstack', style: 'gap:6px;flex-wrap:nowrap' }, h('span', { class: 'who ellipsis', style: 'flex:1' }, x.from_name || x.from_email), h('span', { class: 'when' }, timeAgo(x.received_at))),
      h('div', { class: 'subj ellipsis' }, x.subject || '(no subject)'), h('div', { class: 'snip' }, x.snippet),
      h('div', { class: 'hstack', style: 'margin-top:5px;gap:5px' }, labelPill(x.label), x.campaign ? h('span', { class: 'chip', style: 'font-size:11px' }, icon('send', 11), h('span', { class: 't' }, x.campaign)) : null)))),
    d.total > d.rows.length ? h('div', { style: 'padding:10px;text-align:center' }, btn(`Load more (${fmt(d.total - d.rows.length)} older)`, { size: 'sm', onclick: () => { IBQ.page++; loadInbox(); } })) : null);
}
function renderInboxBulk(total) {
  const b = $('#ibbulk'); if (!b) return;
  const n = IBQ.chk.size, folder = (IB_BOXES.find(x => x[0] === IBQ.box) || [])[1] || 'this folder';
  const afterDelete = async (r, msg) => {
    if (!r.ok) return toast(r.error, 'err'); toast(msg.replace('#', fmt(r.count)));
    if (IBQ.sel && (r.all || IBQ.chk.has(IBQ.sel))) { IBQ.sel = null; const p = $('#ibr'); p && p.replaceChildren(emptyState('inbox', 'Select a message', '')); }
    IBQ.chk.clear(); await refreshInboxCounts(); loadInbox();
  };
  b.replaceChildren(n ? h('div', { class: 'hstack ib-bulk' }, h('b', { class: 'small' }, `${fmt(n)} selected`), h('span', { class: 'spacer' }),
    h('a', { class: 'xs', style: 'cursor:pointer', onclick: () => { IBQ.chk.clear(); loadInbox(); } }, 'Clear'),
    btn('Delete', { size: 'sm', kind: 'danger', icon: 'trash', onclick: async () => {
      if (!await confirmBox({ title: `Delete ${fmt(n)} message(s)?`, text: 'They are removed from MailBlaster only — the emails in your real mailbox are not touched.', ok: 'Delete', danger: true })) return;
      const sel = IBQ.sel && IBQ.chk.has(IBQ.sel); const r = await POST('/api/inbox/delete', { ids: [...IBQ.chk] }); r.all = sel; afterDelete(r, 'Deleted # message(s).');
    } })) :
    total ? h('div', { class: 'hstack ib-bulk' }, h('span', { class: 'xs muted' }, `${fmt(total)} in ${folder}`), h('span', { class: 'spacer' }),
      h('a', { class: 'xs', style: 'cursor:pointer;color:var(--red-d)', onclick: async () => {
        if (!await confirmBox({ title: `Delete all ${fmt(total)} in “${folder}”${IBQ.q ? ' matching your search' : ''}?`, text: 'They are removed from MailBlaster only — the emails in your real mailbox are not touched.', ok: 'Delete all', danger: true, typeText: total >= 50 ? 'DELETE' : null })) return;
        const r = await POST('/api/inbox/delete', { all: 1, box: IBQ.box, q: IBQ.q }); r.all = true; afterDelete(r, 'Deleted # message(s).');
      } }, 'Delete all')) : null);
}
async function openInboxItem(id) {
  const r = $('#ibr'); if (!r) return; r.replaceChildren(h('div', { class: 'empty' }, 'Loading…'));
  const it = await GET('/api/inbox/' + id);
  if (!it || !it.id) { r.replaceChildren(emptyState('alert', 'Message not found', '')); return; }
  refreshInboxCounts();
  const isSys = ['bounce', 'complaint'].includes(it.kind);
  const setLabel = async l => {
    const nl = it.label === l ? '' : l;
    if (nl === 'unsubscribe' && !await confirmBox({ title: 'Unsubscribe this contact?', text: `${it.from_email} will be unsubscribed and never emailed again.`, ok: 'Unsubscribe', danger: true })) return;
    await POST('/api/inbox/' + id, { label: nl }); it.label = nl; toast(nl ? 'Labeled “' + nl.replace('_', ' ') + '”.' : 'Label removed.'); openInboxItem(id); loadInbox();
  };
  const labels = h('div', { class: 'labels' }, [['interested', 'Interested', 'star'], ['meeting', 'Meeting', 'calendar'], ['not_interested', 'Not interested', 'thumbdown'], ['unsubscribe', 'Unsubscribe', 'ban']].map(([k, l, ic]) =>
    h('button', { class: 'lbtn ' + k + (it.label === k ? ' on' : ''), onclick: () => setLabel(k) }, icon(ic, 13), l)));
  const actions = h('div', { class: 'hstack' },
    iconBtn('archive', it.archived ? 'Move to inbox' : 'Archive', async () => { await POST('/api/inbox/' + id, { archived: it.archived ? 0 : 1 }); toast(it.archived ? 'Moved back to inbox.' : 'Archived.'); IBQ.sel = null; loadInbox(); r.replaceChildren(emptyState('inbox', 'Select a message', '')); refreshInboxCounts(); }),
    iconBtn('mail', 'Mark as unread', async () => { await POST('/api/inbox/' + id, { is_read: 0 }); toast('Marked unread.'); loadInbox(); refreshInboxCounts(); }),
    it.contact_id ? iconBtn('user', 'Open contact', () => contactModal(it.contact_id)) : null,
    iconBtn('trash', 'Delete message', async () => {
      if (!await confirmBox({ title: 'Delete this message?', text: 'It is removed from MailBlaster only — the email in your real mailbox is not touched.', ok: 'Delete', danger: true })) return;
      const x = await POST('/api/inbox/delete', { ids: id }); if (!x.ok) return toast(x.error, 'err');
      toast('Message deleted.'); IBQ.sel = null; r.replaceChildren(emptyState('inbox', 'Select a message', '')); refreshInboxCounts(); loadInbox();
    }));
  const thread = (it.thread && it.thread.length ? it.thread : [it]);
  const msgs = thread.map(m => h('div', { class: 'msg' + (m.kind === 'outgoing' ? ' out' : m.kind === 'auto' ? ' auto' : '') },
    h('div', { class: 'mh' }, m.kind === 'outgoing' ? h('b', {}, 'You') : h('b', {}, m.from_name || m.from_email), m.kind === 'auto' ? pill('Auto-reply', 'm') : null, h('span', { class: 'spacer' }), dt(m.received_at)),
    h('pre', {}, (m.body || m.snippet || '').trim().slice(0, 12000) || '(empty)')));
  const composer = isSys ? null : (() => {
    const ta = h('textarea', { placeholder: `Reply to ${it.from_name || it.from_email}…` });
    const send = btn('Send reply', { kind: 'primary', icon: 'reply', onclick: async () => {
      if (!ta.value.trim()) return ta.focus(); send.disabled = true;
      const x = await POST(`/api/inbox/${id}/reply`, { body: ta.value }); send.disabled = false;
      if (x.ok) { toast(x.message); openInboxItem(id); } else toast(x.error, 'err', 8000);
    } });
    return h('div', { class: 'composer' }, ta, h('div', { class: 'hstack', style: 'margin-top:10px' }, h('span', { class: 'xs muted' }, 'Sends from ' + (it.account_email || 'your sender') + ' in the same thread'), h('span', { class: 'spacer' }), send));
  })();
  const ct = it.contact;
  r.replaceChildren(
    h('div', { class: 'rh' }, h('div', { class: 'hstack', style: 'align-items:flex-start;flex-wrap:nowrap' }, avatar(it.from_name, it.from_email, 42),
      h('div', { style: 'flex:1;min-width:0' }, h('div', { class: 'b', style: 'font-size:15px' }, it.from_name || it.from_email), h('div', { class: 'small muted' }, it.from_email + ' · ' + dt(it.received_at)),
        ct ? h('div', { class: 'hstack', style: 'margin-top:6px;gap:5px' }, statusPillC(ct.status), (ct.groups || []).map(chip)) : null), actions),
      h('div', { class: 'b', style: 'margin:14px 0 6px;font-size:15.5px' }, it.subject || '(no subject)'),
      h('div', { class: 'hstack' }, it.campaign ? h('a', { class: 'chip', href: '#campaigns/report/' + it.campaign_id, style: 'text-decoration:none' }, icon('send', 12), h('span', { class: 't' }, it.campaign)) : null,
        isSys ? pill(it.kind === 'complaint' ? 'Spam complaint' : 'Bounce — contact removed from sending', 'r') : null, h('span', { class: 'spacer' }), isSys ? null : labels)),
    h('div', { class: 'rb' }, msgs), composer);
}
async function syncInbox(b) {
  const r = await POST('/api/inbox/sync'); if (!r.ok) return toast(r.error, 'warn', 7000);
  b.disabled = true; b.replaceChildren(icon('refresh', 16), 'Syncing…'); toast('Checking your inboxes…', 'info', 2500);
  for (let i = 0; i < 90; i++) {
    await new Promise(res => setTimeout(res, 1500));
    const s = await GET('/api/inbox/status'); if (s && !s.running) {
      APP.state.inbox = s.counts; APP.state.imap = s; renderNav(); const lr = s.last_result || {};
      const errs = (s.accounts || []).filter(a => a.enabled && a.error);
      errs.length ? toast('Sync problem: ' + errs.map(a => `${a.email}: ${a.error}`).join(' · '), 'err', 10000) :
        toast(`Inbox synced — ${fmt(lr.reply || 0)} new replies, ${fmt(lr.bounce || 0)} bounces, ${fmt(lr.auto || 0)} auto-replies.`);
      break;
    }
  }
  b.disabled = false; b.replaceChildren(icon('refresh', 16), 'Sync now'); if (APP.view === 'inbox') { loadInbox(); }
}

/* ================================================================== CONTACTS */
const CQ = { q: '', status: '', group: '', page: 0, per: 50, sel: new Set(), all: false, rows: [], total: 0 };
function statusPillC(s) { const m = { active: ['Active', 'g'], unsubscribed: ['Unsubscribed', 'm'], bounced: ['Bounced', 'r'], invalid: ['Invalid', 'a'] }[s] || [s, 'm']; return pill(m[0], m[1]); }
async function viewContacts() {
  await loadState();
  const v = $('#view'), c = APP.state.contacts || {};
  setTop(btn('Import CSV', { icon: 'upload', onclick: () => importModal() }), btn('Add contact', { kind: 'primary', icon: 'userplus', onclick: () => addContactModal() }));
  const kp = h('div', { class: 'grid g5', style: 'margin-bottom:18px' },
    kpi('users', '#4f46e5', 'var(--brand-l)', 'Total contacts', fmt(c.total), fmt(c.ungrouped) + ' not in a group'),
    kpi('check', '#10b981', 'var(--green-l)', 'Active', fmt(c.active), 'can be emailed'),
    kpi('reply', '#0ea5e9', 'var(--sky-l)', 'Replied', fmt(c.replied), 'answered a campaign'),
    kpi('ban', '#64748b', '#eef1f6', 'Unsubscribed', fmt(c.unsubscribed), 'never emailed again'),
    kpi('bounce', '#ef4444', 'var(--red-l)', 'Bounced / invalid', fmt((c.bounced || 0) + (c.invalid || 0)), 'auto-cleaned'));
  const gp = h('div', { class: 'gpanel' }), main = h('div', { class: 'card', id: 'ctmain', style: 'margin:0' });
  v.replaceChildren(kp, h('div', { class: 'ct-layout' }, gp, main));
  renderGroupPanel(gp); renderContactMain(main);
}
function renderGroupPanel(gp) {
  gp = gp || $('.gpanel'); if (!gp) return;
  const groups = APP.state.groups || [], c = APP.state.contacts || {};
  const item = (key, label, n, color, g) => h('div', { class: 'gitem' + (String(CQ.group) === String(key) ? ' on' : ''), onclick: e => { if (e.target.closest('.gm')) return; CQ.group = key; CQ.page = 0; clearSel(); renderGroupPanel(); renderContactMain(); } },
    color ? h('span', { class: 'sw', style: 'background:' + color }) : icon(key === 'none' ? 'minus' : 'users', 15), h('span', { class: 'gn' }, label), h('span', { class: 'gc' }, fmt(n)),
    g ? h('span', { class: 'gm', style: 'display:inline-flex' }, iconBtn('trash', 'Delete group', e => { e.stopPropagation(); deleteGroupModal(g); }, true),
      iconBtn('dots', 'Group options', e => { e.stopPropagation(); groupMenu(e.currentTarget, g); }, true)) : null);
  gp.replaceChildren(h('div', { class: 'card', style: 'margin:0' }, h('div', { class: 'card-b' },
    item('', 'All contacts', c.total), item('none', 'Not in a group', c.ungrouped),
    h('div', { class: 'glab' }, 'Groups', h('span', { class: 'spacer' }), iconBtn('plus', 'New group', () => groupModal(), true)),
    groups.length ? groups.map(g => item(g.id, g.name, g.n, g.color, g)) : h('div', { class: 'xs muted', style: 'padding:6px 10px 10px' }, 'No groups yet. Create one, then add contacts to it — e.g. “Leads – USA” or “Webinar Oct”.'),
    h('div', { style: 'padding:8px 4px 4px' }, btn('New group', { size: 'sm', icon: 'plus', onclick: () => groupModal() })))));
}
function groupMenu(anchor, g) {
  openMenu(anchor, [
    { label: 'Send campaign to this group', icon: 'send', onclick: () => newCampaign({ group_ids: [g.id], name: g.name + ' campaign' }) },
    { label: 'Import CSV into group', icon: 'upload', onclick: () => importModal(g.id) },
    { label: 'Rename / color', icon: 'edit', onclick: () => groupModal(g) },
    { label: 'Export group CSV', icon: 'download', onclick: () => location.href = '/api/export/contacts.csv?group=' + g.id },
    'sep',
    { label: 'Delete group…', icon: 'trash', danger: true, onclick: () => deleteGroupModal(g) },
  ]);
}
const SWATCHES = ['#6366f1', '#0ea5e9', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#14b8a6', '#f97316', '#64748b'];
function groupModal(g, onCreated) {
  let color = g ? g.color : SWATCHES[(APP.state.groups || []).length % SWATCHES.length];
  const name = h('input', { value: g ? g.name : '', placeholder: 'e.g. Leads – USA' });
  const sw = h('div', { class: 'swatches' }); const drawSw = () => sw.replaceChildren(...SWATCHES.map(c => h('button', { class: c === color ? 'on' : '', style: 'background:' + c, type: 'button', onclick: () => { color = c; drawSw(); } }))); drawSw();
  const save = async () => {
    if (!name.value.trim()) return name.focus();
    const r = g ? await POST('/api/groups/' + g.id, { name: name.value, color }) : await POST('/api/groups', { name: name.value, color });
    if (!r.ok) return toast(r.error, 'err');
    m.close(); toast(g ? 'Group updated.' : `Group “${name.value.trim()}” created.`); await loadState(); renderGroupPanel(); onCreated ? onCreated(r.id) : renderContactMain();
  };
  name.addEventListener('keydown', e => { if (e.key === 'Enter') save(); });
  const m = modal({ title: g ? 'Edit group' : 'New group', icon: 'folder', body: h('div', {}, field('Group name', name), field('Color', sw)), footer: [btn('Cancel', { onclick: () => m.close() }), btn(g ? 'Save' : 'Create group', { kind: 'primary', onclick: save })] });
}
function deleteGroupModal(g) {
  let mode = 'group';
  const opts = h('div');
  const draw = () => opts.replaceChildren(
    h('label', { class: 'radio-card' + (mode === 'group' ? ' on' : '') }, h('input', { type: 'radio', name: 'dg', checked: mode === 'group', onchange: () => { mode = 'group'; draw(); } }),
      h('div', {}, h('b', { class: 'small' }, 'Delete the group only'), h('div', { class: 'xs muted' }, `The ${fmt(g.n)} contacts stay in your list (and in any other groups).`))),
    h('label', { class: 'radio-card danger' + (mode === 'all' ? ' on' : '') }, h('input', { type: 'radio', name: 'dg', checked: mode === 'all', onchange: () => { mode = 'all'; draw(); } }),
      h('div', {}, h('b', { class: 'small', style: 'color:var(--red-d)' }, `Delete the group AND its ${fmt(g.n)} contacts`), h('div', { class: 'xs muted' }, 'Removes these contacts everywhere, including other groups. Unsubscribed/bounced addresses stay on the suppression list so they can never be emailed again.'))),
    mode === 'all' ? h('input', { placeholder: 'Type DELETE to confirm', id: 'dgconf', style: 'margin-top:6px', oninput: e => okb.disabled = e.target.value.trim() !== 'DELETE' }) : null);
  const okb = btn('Delete', { kind: 'danger-solid', onclick: async () => {
    const r = await POST(`/api/groups/${g.id}/delete`, { delete_contacts: mode === 'all' ? 1 : 0 });
    if (!r.ok) return toast(r.error, 'err'); m.close();
    toast(mode === 'all' ? `Group deleted with ${fmt(r.deleted_contacts)} contacts.` : 'Group deleted — contacts kept.');
    if (String(CQ.group) === String(g.id)) CQ.group = ''; clearSel(); await loadState(); viewContacts();
  } });
  draw();
  const m = modal({ title: `Delete “${g.name}”?`, icon: 'trash', body: opts, footer: [btn('Cancel', { onclick: () => m.close() }), okb] });
  const obs = () => { okb.disabled = mode === 'all' && (!$('#dgconf') || $('#dgconf').value.trim() !== 'DELETE'); }; opts.addEventListener('change', obs); obs();
}
function clearSel() { CQ.sel = new Set(); CQ.all = false; }
function currentGroupName() { if (CQ.group === 'none') return 'Not in a group'; const g = (APP.state.groups || []).find(x => String(x.id) === String(CQ.group)); return g ? g.name : 'All contacts'; }
function renderContactMain(main) {
  main = main || $('#ctmain'); if (!main) return;
  const g = (APP.state.groups || []).find(x => String(x.id) === String(CQ.group));
  const search = h('input', { placeholder: 'Search email or name…', value: CQ.q, oninput: debounce(e => { CQ.q = e.target.value; CQ.page = 0; clearSel(); loadContacts(); }, 300) });
  const status = h('select', { style: 'width:auto', onchange: e => { CQ.status = e.target.value; CQ.page = 0; clearSel(); loadContacts(); } },
    [['', 'Any status'], ['active', 'Active'], ['replied', 'Replied'], ['unsubscribed', 'Unsubscribed'], ['bounced', 'Bounced'], ['invalid', 'Invalid']].map(([v, l]) => h('option', { value: v, selected: CQ.status === v }, l)));
  const more = iconBtn('dots', 'More', e => openMenu(e.currentTarget, [
    { label: 'Export these contacts (CSV)', icon: 'download', onclick: () => location.href = `/api/export/contacts.csv?q=${encodeURIComponent(CQ.q)}&status=${CQ.status}&group=${CQ.group}` },
    { label: 'Verify all emails (MX check)', icon: 'mailcheck', onclick: () => verifyModal() },
    g ? { label: 'Send campaign to this group', icon: 'send', onclick: () => newCampaign({ group_ids: [g.id], name: g.name + ' campaign' }) } : null,
    'sep',
    { label: 'Delete ALL contacts…', icon: 'trash', danger: true, onclick: () => deleteAllContacts() },
  ]));
  main.replaceChildren(
    h('div', { class: 'card-h' }, h('div', {}, h('h2', { class: 'hstack' }, g ? h('span', { class: 'sw', style: `width:11px;height:11px;border-radius:3px;background:${g.color}` }) : null, currentGroupName()), h('div', { class: 'sub', id: 'ctcount' }, '…')),
      h('div', { class: 'act' }, g ? btn('Send to group', { size: 'sm', icon: 'send', onclick: () => newCampaign({ group_ids: [g.id], name: g.name + ' campaign' }) }) : null)),
    h('div', { class: 'toolbar' }, h('div', { class: 'inp-ic', style: 'flex:1;min-width:200px;max-width:360px' }, icon('search', 15), search), status, h('span', { class: 'spacer' }), more),
    h('div', { id: 'ctbulk' }), h('div', { id: 'cttable', class: 'tbl-wrap' }), h('div', { id: 'ctpager' }));
  loadContacts();
}
async function loadContacts() {
  const tb = $('#cttable'); if (!tb) return;
  tb.style.opacity = '.55';
  const d = await GET(`/api/contacts/list?q=${encodeURIComponent(CQ.q)}&status=${CQ.status}&group=${CQ.group}&page=${CQ.page}&per=${CQ.per}`);
  tb.style.opacity = '';
  CQ.rows = d.rows || []; CQ.total = d.total || 0;
  $('#ctcount').textContent = `${fmt(CQ.total)} contact${CQ.total === 1 ? '' : 's'}` + (CQ.q || CQ.status ? ' match your filters' : '');
  renderContactTable(); renderBulk(); renderPager();
}
function renderContactTable() {
  const tb = $('#cttable'); if (!tb) return;
  if (!CQ.rows.length) {
    const filtered = CQ.q || CQ.status;
    tb.replaceChildren(filtered ? h('div', { class: 'empty' }, 'No contacts match these filters.') :
      emptyState('users', CQ.group ? 'This group is empty' : 'No contacts yet', CQ.group && CQ.group !== 'none' ? 'Import a CSV straight into this group, or select contacts in “All contacts” and use “Add to group”.' : 'Import a CSV with an “email” column — names and any other columns come along for personalization.',
        h('div', { class: 'hstack', style: 'justify-content:center' }, btn('Import CSV', { kind: 'primary', icon: 'upload', onclick: () => importModal(CQ.group && CQ.group !== 'none' ? +CQ.group : null) }), btn('Add contact', { icon: 'userplus', onclick: () => addContactModal() }))));
    return;
  }
  const pageIds = CQ.rows.map(r => r.id), allPage = pageIds.every(id => CQ.sel.has(id)) || CQ.all, somePage = pageIds.some(id => CQ.sel.has(id));
  const hcb = h('input', { type: 'checkbox', title: 'Select all on this page', checked: allPage });
  hcb.indeterminate = !allPage && somePage;
  hcb.addEventListener('change', () => { if (hcb.checked) pageIds.forEach(id => CQ.sel.add(id)); else { pageIds.forEach(id => CQ.sel.delete(id)); CQ.all = false; } renderContactTable(); renderBulk(); });
  tb.replaceChildren(h('table', { class: 't' },
    h('thead', {}, h('tr', {}, h('th', { class: 'w-cb' }, hcb), h('th', {}, 'Contact'), h('th', {}, 'Groups'), h('th', {}, 'Status'), h('th', {}, 'Added'), h('th', {}, ''))),
    h('tbody', {}, CQ.rows.map(r => {
      const on = CQ.all || CQ.sel.has(r.id);
      const cb = h('input', { type: 'checkbox', checked: on, onclick: e => e.stopPropagation(), onchange: e => { if (e.target.checked) CQ.sel.add(r.id); else { CQ.sel.delete(r.id); if (CQ.all) { CQ.all = false; pageIds.forEach(id => id !== r.id && CQ.sel.add(id)); } } renderContactTable(); renderBulk(); } });
      const nm = ((r.first_name || '') + ' ' + (r.last_name || '')).trim();
      return h('tr', { class: 'click' + (on ? ' sel' : ''), onclick: e => { if (e.target.closest('input,button')) return; contactModal(r.id); } },
        h('td', { class: 'w-cb' }, cb),
        h('td', {}, h('div', { class: 'hstack', style: 'flex-wrap:nowrap' }, avatar(nm, r.email, 30), h('div', { style: 'min-width:0' }, h('div', { class: 'b small ellipsis' }, nm || r.email), nm ? h('div', { class: 'xs muted ellipsis' }, r.email) : null))),
        h('td', {}, h('div', { class: 'hstack', style: 'gap:4px' }, (r.groups || []).slice(0, 3).map(chip), (r.groups || []).length > 3 ? h('span', { class: 'xs muted' }, '+' + (r.groups.length - 3)) : null, !(r.groups || []).length ? h('span', { class: 'xs dim' }, '—') : null)),
        h('td', {}, statusPillC(r.status), r.replied_at ? h('span', { style: 'margin-left:4px' }, pill('Replied', 's')) : null),
        h('td', { class: 'xs muted nowrap' }, new Date(r.created_at * 1000).toLocaleDateString()),
        h('td', { style: 'width:40px;text-align:right' }, iconBtn('trash', 'Delete contact', async () => {
          if (!await confirmBox({ title: 'Delete contact?', text: r.email + ' will be removed permanently from MailBlaster and all groups. If they unsubscribed or bounced they stay blocked.', ok: 'Delete', danger: true })) return;
          const x = await POST(`/api/contacts/${r.id}/delete`); if (x.ok === false) return toast(x.error, 'err');
          CQ.sel.delete(r.id); toast('Contact deleted.'); await loadState(); renderGroupPanel(); loadContacts();
        }, true)));
    }))));
}
function selCount() { return CQ.all ? CQ.total : CQ.sel.size; }
function renderBulk() {
  const b = $('#ctbulk'); if (!b) return;
  const n = selCount(); const pageIds = CQ.rows.map(r => r.id); const allPage = pageIds.length && pageIds.every(id => CQ.sel.has(id));
  const parts = [];
  if (n) {
    const inGroup = CQ.group && CQ.group !== 'none';
    parts.push(h('div', { class: 'bulkbar' }, h('b', { style: 'margin-right:6px' }, `${fmt(n)} selected`),
      btn('Add to group', { icon: 'folder', onclick: e => addToGroupMenu(e.currentTarget) }),
      inGroup ? btn('Remove from this group', { icon: 'minus', onclick: () => bulkAction('remove_group', { group_id: CQ.group }) }) : null,
      btn('Unsubscribe', { icon: 'ban', onclick: async () => { if (await confirmBox({ title: `Unsubscribe ${fmt(n)} contact(s)?`, text: 'They will never be emailed again (added to the suppression list).', ok: 'Unsubscribe', danger: true })) bulkAction('unsubscribe'); } }),
      CQ.status === 'invalid' ? btn('Reactivate', { icon: 'refresh', onclick: () => bulkAction('reactivate') }) : null,
      h('span', { class: 'spacer' }),
      btn('Clear', { kind: 'quiet', onclick: () => { clearSel(); renderContactTable(); renderBulk(); } }),
      btn('Delete', { kind: 'danger', icon: 'trash', onclick: async () => {
        if (await confirmBox({ title: `Delete ${fmt(n)} contact(s)?`, text: 'This permanently removes them from MailBlaster and all groups. Unsubscribed/bounced addresses stay suppressed so they can’t be re-imported by mistake.', ok: 'Delete ' + fmt(n), danger: true, typeText: n >= 100 ? 'DELETE' : null })) bulkAction('delete');
      } })));
    if (allPage && !CQ.all && CQ.total > pageIds.length) parts.push(h('div', { class: 'selbanner' }, `All ${fmt(pageIds.length)} contacts on this page are selected. `, h('a', { onclick: () => { CQ.all = true; renderContactTable(); renderBulk(); } }, `Select all ${fmt(CQ.total)} contacts${CQ.q || CQ.status || CQ.group ? ' matching this view' : ''}`)));
    if (CQ.all && CQ.total > pageIds.length) parts.push(h('div', { class: 'selbanner' }, `All ${fmt(CQ.total)} contacts are selected. `, h('a', { onclick: () => { clearSel(); renderContactTable(); renderBulk(); } }, 'Clear selection')));
  }
  b.replaceChildren(...parts);
}
function addToGroupMenu(anchor) {
  const groups = (APP.state.groups || []).filter(g => String(g.id) !== String(CQ.group));
  openMenu(anchor, [{ section: 'Add selected to' }, ...groups.map(g => ({ label: g.name, icon: 'folder', onclick: () => bulkAction('add_group', { group_id: g.id }) })),
    groups.length ? 'sep' : null, { label: 'New group…', icon: 'plus', onclick: async () => { const name = await promptBox({ title: 'New group', label: 'Group name', placeholder: 'e.g. Hot leads', ok: 'Create & add', icon: 'folder' }); if (name) bulkAction('add_group', { new_group: name }); } }]);
}
async function bulkAction(action, extra = {}) {
  const data = Object.assign({ action }, extra);
  if (CQ.all) Object.assign(data, { all: 1, q: CQ.q, status: CQ.status, group: CQ.group }); else data.ids = [...CQ.sel].join(',');
  const r = await POST('/api/contacts/bulk', data);
  if (!r.ok) return toast(r.error, 'err');
  const gname = extra.new_group || ((APP.state.groups || []).find(g => String(g.id) === String(extra.group_id)) || {}).name;
  toast({ delete: `Deleted ${fmt(r.count)} contact(s).`, add_group: `Added ${fmt(r.count)} contact(s) to “${gname}”.`, remove_group: `Removed ${fmt(r.count)} contact(s) from this group.`,
    unsubscribe: `Unsubscribed ${fmt(r.count)} contact(s).`, reactivate: `Reactivated ${fmt(r.count)} contact(s).` }[action]);
  clearSel(); await loadState(); renderGroupPanel(); refreshKpis(); loadContacts();
}
function refreshKpis() {
  if (APP.view !== 'contacts') return;
  const c = APP.state.contacts || {}, k = $('#view .grid'); if (!k) return;
  const nums = k.querySelectorAll('.kpi .num'), foots = k.querySelectorAll('.kpi .foot'); if (nums.length < 5) return;
  nums[0].textContent = fmt(c.total); foots[0].textContent = fmt(c.ungrouped) + ' not in a group'; nums[1].textContent = fmt(c.active); nums[2].textContent = fmt(c.replied); nums[3].textContent = fmt(c.unsubscribed); nums[4].textContent = fmt((c.bounced || 0) + (c.invalid || 0));
}
function renderPager() {
  const p = $('#ctpager'); if (!p) return; if (!CQ.total) { p.replaceChildren(); return; }
  const pages = Math.max(1, Math.ceil(CQ.total / CQ.per)), from = CQ.page * CQ.per + 1, to = Math.min(CQ.total, (CQ.page + 1) * CQ.per);
  const per = h('select', { onchange: e => { CQ.per = +e.target.value; CQ.page = 0; loadContacts(); } }, [25, 50, 100, 250, 500].map(n => h('option', { value: n, selected: CQ.per === n }, n + ' / page')));
  p.replaceChildren(h('div', { class: 'pager' }, h('span', {}, `${fmt(from)}–${fmt(to)} of ${fmt(CQ.total)}`), h('span', { class: 'spacer' }), per,
    btn('', { size: 'sm', icon: 'left', disabled: CQ.page <= 0, onclick: () => { CQ.page--; loadContacts(); } }), h('span', {}, `Page ${CQ.page + 1} of ${fmt(pages)}`),
    btn('', { size: 'sm', icon: 'right', disabled: CQ.page + 1 >= pages, onclick: () => { CQ.page++; loadContacts(); } })));
}
function importModal(groupId) {
  let file = null;
  const groups = APP.state.groups || [];
  const pre = groupId || (CQ.group && CQ.group !== 'none' ? +CQ.group : '');
  const target = h('select', {}, h('option', { value: '' }, 'Don’t add to a group'), groups.map(g => h('option', { value: g.id, selected: String(g.id) === String(pre) }, g.name)), h('option', { value: '__new' }, '＋ Create a new group…'));
  const newName = h('input', { placeholder: 'New group name, e.g. Leads – USA', style: 'margin-top:8px;display:none' });
  target.addEventListener('change', () => { newName.style.display = target.value === '__new' ? '' : 'none'; if (target.value === '__new') newName.focus(); });
  const fin = h('input', { type: 'file', accept: '.csv,.txt,text/csv', style: 'display:none' });
  const fname = h('div', { class: 'small muted', style: 'margin-top:4px' }, 'Needs an “email” column. First/last name and any other columns are kept for personalization ({{data.column}}).');
  const setFile = f => { file = f; fname.replaceChildren(h('b', { style: 'color:var(--ink)' }, f.name), ` · ${(f.size / 1024 / 1024).toFixed(2)} MB`); };
  fin.addEventListener('change', () => fin.files[0] && setFile(fin.files[0]));
  const drop = h('div', { class: 'drop', onclick: () => fin.click() }, h('div', { class: 'di' }, icon('upload', 22)), h('div', { class: 'b' }, 'Drop your CSV here, or click to browse'), fname);
  drop.addEventListener('dragover', e => { e.preventDefault(); drop.classList.add('over'); }); drop.addEventListener('dragleave', () => drop.classList.remove('over'));
  drop.addEventListener('drop', e => { e.preventDefault(); drop.classList.remove('over'); e.dataTransfer.files[0] && setFile(e.dataTransfer.files[0]); });
  const res = h('div');
  const go_ = btn('Import', { kind: 'primary', icon: 'upload', onclick: async () => {
    if (!file) return toast('Choose a CSV file first.', 'warn');
    if (target.value === '__new' && !newName.value.trim()) return newName.focus();
    go_.disabled = true; go_.replaceChildren(icon('refresh', 16), 'Importing…'); res.replaceChildren(h('div', { style: 'margin-top:12px' }, h('div', { class: 'pbar' }, h('div', { style: 'width:100%;opacity:.5' }))));
    const data = { file };
    if (target.value === '__new') data.group_name = newName.value.trim(); else if (target.value) data.group_id = target.value;
    const r = await POST('/api/contacts/import', data);
    go_.disabled = false; go_.replaceChildren(icon('upload', 16), 'Import');
    if (!r.ok) { res.replaceChildren(h('div', { style: 'margin-top:12px' }, banner('err', r.error + (r.headers ? ' Columns found: ' + r.headers.join(', ') : '')))); return; }
    res.replaceChildren(h('div', { style: 'margin-top:14px' }, banner('ok', h('div', {}, h('b', {}, `Imported ${fmt(r.rows)} rows. `), `${fmt(r.added)} new · ${fmt(r.updated)} updated · ${fmt(r.skipped_dupes)} duplicates · ${fmt(r.invalid)} invalid`,
      r.suppressed ? h('div', {}, `${fmt(r.suppressed)} were previously unsubscribed/bounced and stay blocked.`) : null))));
    m.box.querySelector('.modal-f').replaceChildren(btn('Done', { kind: 'primary', onclick: () => m.close() }));
    await loadState(); if (r.group_id) { CQ.group = r.group_id; } CQ.page = 0; clearSel(); if (APP.view === 'contacts') viewContacts();
  } });
  const m = modal({ title: 'Import contacts', icon: 'upload', body: h('div', {}, drop, fin, field('Add imported contacts to', target), newName, res), footer: [btn('Cancel', { onclick: () => m.close() }), go_] });
}
function addContactModal() {
  const email = h('input', { placeholder: 'name@company.com', type: 'email' }), fn = h('input', { placeholder: 'First name' }), ln = h('input', { placeholder: 'Last name' });
  const sel = new Set(CQ.group && CQ.group !== 'none' ? [+CQ.group] : []);
  const gbox = h('div', { class: 'hstack' }); const drawG = () => gbox.replaceChildren(...(APP.state.groups || []).map(g => h('label', { class: 'pick' + (sel.has(g.id) ? ' on' : ''), style: 'padding:6px 10px', onclick: e => { e.preventDefault(); sel.has(g.id) ? sel.delete(g.id) : sel.add(g.id); drawG(); } },
    h('input', { type: 'checkbox', checked: sel.has(g.id) }), h('span', { class: 'dot', style: `width:9px;height:9px;border-radius:3px;background:${g.color}` }), h('span', { class: 'small b' }, g.name))), (APP.state.groups || []).length ? null : h('span', { class: 'xs muted' }, 'No groups yet.')); drawG();
  const save = async () => {
    const r = await POST('/api/contacts/add', { email: email.value, first_name: fn.value, last_name: ln.value, group_ids: [...sel] });
    if (!r.ok) return toast(r.error || 'Failed', 'err'); m.close(); toast('Contact added.'); await loadState(); if (APP.view === 'contacts') viewContacts();
  };
  const m = modal({ title: 'Add contact', icon: 'userplus', body: h('div', {}, field('Email', email), h('div', { class: 'row' }, field('First name', fn), field('Last name', ln)), field('Groups', gbox, 'optional')),
    footer: [btn('Cancel', { onclick: () => m.close() }), btn('Add contact', { kind: 'primary', onclick: save })] });
}
async function contactModal(id) {
  const d = await GET('/api/contacts/' + id); if (!d || !d.id) return toast('Contact not found.', 'err');
  const nm = ((d.first_name || '') + ' ' + (d.last_name || '')).trim();
  const acts = [...(d.sends || []).map(s => ({ ic: s.status === 'sent' ? 'send' : s.status === 'bounced' ? 'bounce' : 'alert', t: (s.status === 'sent' ? 'Sent ' : s.status === 'bounced' ? 'Bounced · ' : s.status + ' · ') + (s.name || 'campaign ' + s.campaign_id), sub: s.status !== 'sent' ? s.error : '', ts: s.sent_at })),
    ...(d.events || []).map(e => ({ ic: e.type === 'open' ? 'eye' : e.type === 'click' ? 'pointer' : 'ban', t: { open: 'Opened email', click: 'Clicked ' + (e.url || ''), unsub: 'Unsubscribed' }[e.type] || e.type, ts: e.ts })),
    ...(d.replies || []).map(x => ({ ic: 'reply', t: (x.kind === 'reply' ? 'Replied: ' : x.kind === 'auto' ? 'Auto-reply: ' : x.kind + ': ') + (x.snippet || x.subject || ''), ts: x.received_at, rid: x.id }))].sort((a, b) => b.ts - a.ts).slice(0, 40);
  const data = Object.entries(d.data || {}).filter(([k, v]) => v !== '' && v != null);
  const gsel = h('select', { style: 'width:auto;min-height:31px;font-size:12.5px' }, h('option', { value: '' }, '＋ Add to group'), (APP.state.groups || []).filter(g => !(d.groups || []).some(x => x.id === g.id)).map(g => h('option', { value: g.id }, g.name)));
  gsel.addEventListener('change', async () => { if (!gsel.value) return; await POST('/api/contacts/bulk', { action: 'add_group', ids: id, group_id: gsel.value }); toast('Added to group.'); m.close(); await loadState(); contactModal(id); if (APP.view === 'contacts') { renderGroupPanel(); loadContacts(); } });
  const m = modal({ title: nm || d.email, icon: 'user', wide: true, body: h('div', {},
    h('div', { class: 'hstack', style: 'margin-bottom:14px' }, avatar(nm, d.email, 44), h('div', { style: 'flex:1' }, h('div', { class: 'b' }, d.email), h('div', { class: 'hstack', style: 'margin-top:4px' }, statusPillC(d.status), d.status_reason ? h('span', { class: 'xs muted' }, d.status_reason) : null, d.replied_at ? pill('Replied ' + timeAgo(d.replied_at), 's') : null))),
    h('div', { class: 'hstack', style: 'margin-bottom:16px' }, (d.groups || []).map(g => h('span', { class: 'chip' }, h('span', { class: 'dot', style: 'background:' + g.color }), h('span', { class: 't' }, g.name),
      h('span', { style: 'cursor:pointer;display:inline-flex', title: 'Remove from group', onclick: async () => { await POST('/api/contacts/bulk', { action: 'remove_group', ids: id, group_id: g.id }); toast('Removed from group.'); m.close(); await loadState(); contactModal(id); if (APP.view === 'contacts') { renderGroupPanel(); loadContacts(); } } }, icon('x', 12)))), gsel),
    h('div', { class: 'grid g2', style: 'align-items:start' },
      h('div', {}, h('div', { class: 'section-t' }, 'Activity'), acts.length ? h('div', {}, acts.map(a => h('div', { class: 'hstack small', style: 'padding:8px 0;border-bottom:1px solid var(--line);flex-wrap:nowrap;align-items:flex-start' + (a.rid ? ';cursor:pointer' : ''), onclick: a.rid ? () => { m.close(); go('inbox', 'm', a.rid); } : null },
        h('span', { style: 'color:var(--muted);margin-top:2px' }, icon(a.ic, 14)), h('div', { style: 'flex:1;min-width:0' }, h('div', { class: 'ellipsis' }, a.t), a.sub ? h('div', { class: 'xs muted' }, a.sub) : null), h('span', { class: 'xs dim nowrap' }, timeAgo(a.ts))))) : h('div', { class: 'muted small' }, 'No activity yet.')),
      h('div', {}, h('div', { class: 'section-t' }, 'Details'), h('dl', { class: 'review', style: 'grid-template-columns:120px 1fr;font-size:13px' },
        h('dt', {}, 'First name'), h('dd', {}, d.first_name || '—'), h('dt', {}, 'Last name'), h('dd', {}, d.last_name || '—'), h('dt', {}, 'Added'), h('dd', {}, new Date(d.created_at * 1000).toLocaleString()),
        data.map(([k, v]) => frag(h('dt', { class: 'ellipsis', title: k }, k), h('dd', { style: 'word-break:break-word' }, String(v))))),
        data.length ? h('div', { class: 'xs muted', style: 'margin-top:8px' }, 'Use these in emails as {{data.column_name}}') : null))),
    footer: [d.status === 'active' ? btn('Unsubscribe', { icon: 'ban', onclick: async () => { if (!await confirmBox({ title: 'Unsubscribe contact?', text: d.email + ' will never be emailed again.', ok: 'Unsubscribe', danger: true })) return; await POST('/api/contacts/bulk', { action: 'unsubscribe', ids: id }); toast('Unsubscribed.'); m.close(); await loadState(); if (APP.view === 'contacts') loadContacts(); } }) : null,
      btn('Delete', { kind: 'danger', icon: 'trash', onclick: async () => { if (!await confirmBox({ title: 'Delete contact?', text: d.email + ' will be removed permanently.', ok: 'Delete', danger: true })) return; await POST(`/api/contacts/${id}/delete`); toast('Contact deleted.'); m.close(); await loadState(); if (APP.view === 'contacts') { renderGroupPanel(); loadContacts(); } } }),
      h('span', { class: 'spacer' }), btn('Close', { onclick: () => m.close() })].filter(Boolean) });
}
async function deleteAllContacts() {
  const n = (APP.state.contacts || {}).total || 0; if (!n) return toast('There are no contacts to delete.', 'info');
  if (!await confirmBox({ title: `Delete all ${fmt(n)} contacts?`, text: 'Every contact and group membership will be permanently removed. Groups themselves, campaigns and reports are kept. Unsubscribed and bounced addresses stay on the suppression list so they are never emailed again.', ok: 'Delete everything', danger: true, typeText: 'DELETE' })) return;
  const r = await POST('/api/contacts/delete-all', { confirm: 'DELETE' });
  if (!r.ok) return toast(r.error, 'err'); toast(`Deleted ${fmt(r.count)} contacts.`); clearSel(); CQ.page = 0; await loadState(); viewContacts();
}
function verifyModal() {
  const bar = h('div', { class: 'pbar lg' }, h('div', { style: 'width:0' })), info = h('div', { class: 'small muted', style: 'margin-top:8px' }, 'Checks every active address for valid syntax and a real mail server (MX record). Bad addresses are marked invalid so they never bounce.');
  const start = btn('Start verification', { kind: 'primary', icon: 'mailcheck', onclick: async () => {
    start.disabled = true; const r = await POST('/api/validate', { check_mx: 1 }); if (!r.ok && r.error) toast(r.error, 'warn');
    const poll_ = async () => { const s = await GET('/api/validate/status'); const p = s.total ? s.done / s.total * 100 : 0; bar.firstChild.style.width = p + '%'; info.textContent = `Checked ${fmt(s.done)} of ${fmt(s.total)} · ${fmt(s.invalid)} invalid found`;
      if (s.status === 'running') setTimeout(poll_, 800); else { info.textContent = `Done — ${fmt(s.invalid)} invalid addresses cleaned out of ${fmt(s.total)}.`; start.disabled = false; await loadState(); if (APP.view === 'contacts') viewContacts(); } };
    poll_();
  } });
  const m = modal({ title: 'Verify email addresses', icon: 'mailcheck', body: h('div', {}, bar, info), footer: [btn('Close', { onclick: () => m.close() }), start] });
}

/* ================================================================== TEMPLATES */
async function viewTemplates() {
  await loadState();
  const all = APP.state.templates || [], mine = all.filter(t => !t.builtin), built = all.filter(t => t.builtin), hidden = APP.state.hidden_templates || 0;
  setTop(btn('New template', { kind: 'primary', icon: 'plus', onclick: () => templateModal() }));
  const myGrid = h('div', { class: 'tpl-grid' }), grid = h('div', { class: 'tpl-grid' });
  const restore = hidden ? btn(`Restore ${hidden} removed`, { size: 'sm', icon: 'refresh', onclick: async () => { await POST('/api/templates/restore'); toast('Built-in templates restored.'); viewTemplates(); } }) : null;
  $('#view').replaceChildren(
    card('My templates', 'Your own saved emails. Save one from the campaign builder (step 2) or click “New template”.', null,
      h('div', { class: 'card-b' }, mine.length ? myGrid : h('div', { class: 'small muted' }, 'No saved templates yet.'))),
    card('Template gallery', 'Click a template to start a campaign with it. Every template is personalized with merge tags and includes an unsubscribe link.', restore,
      h('div', { class: 'card-b' }, built.length ? grid : h('div', { class: 'small muted' }, 'All built-in templates were removed.'))));
  const tile = async (t, into) => {
    const full = await GET('/api/templates/' + t.id); if (!full || !full.id) return;
    const del = h('button', { class: 'icon-btn sm del', type: 'button', title: t.builtin ? 'Remove from gallery' : 'Delete template', onclick: async e => {
      e.stopPropagation();
      if (!await confirmBox({ title: t.builtin ? `Remove “${t.name}”?` : `Delete “${t.name}”?`, text: t.builtin ? 'It is hidden from the gallery. You can bring it back with “Restore removed”.' : 'This saved template is deleted permanently. Campaigns already sent with it are not affected.', ok: t.builtin ? 'Remove' : 'Delete', danger: true })) return;
      const r = await POST(`/api/templates/${t.id}/delete`); r.ok ? toast(t.builtin ? 'Template removed.' : 'Template deleted.') : toast(r.error, 'err'); viewTemplates();
    } }, icon('trash', 15));
    into.append(h('div', { class: 'tpl', onclick: () => newCampaign({ subject: full.subject || '', html: full.html || '', text: full.text || '', name: t.name + ' campaign' }) },
      h('div', { class: 'pv' }, del, h('iframe', { srcdoc: '<meta charset="utf-8"><style>body{font-family:Arial,sans-serif;margin:24px;color:#222}</style>' + previewFill(full.html || ''), tabindex: '-1' })),
      h('div', { class: 'meta' }, h('div', { style: 'flex:1;min-width:0' }, h('b', { class: 'small' }, t.name), h('div', { class: 'xs muted ellipsis' }, full.subject || '')), pill(t.category, t.builtin ? 'b' : 'g'))));
  };
  for (const t of mine) await tile(t, myGrid);
  for (const t of built) await tile(t, grid);
}
function templateModal(preset = {}) {
  const name = h('input', { value: preset.name || '', placeholder: 'e.g. Agency intro v2' }), subj = h('input', { value: preset.subject || '', placeholder: 'Subject line' });
  const html = h('textarea', { style: 'min-height:200px;font-family:monospace;font-size:12.5px', placeholder: '<p>Hi {{first_name|there}},</p>…' }); html.value = preset.html || '';
  const m = modal({ title: 'Save as template', icon: 'layout', wide: true, body: h('div', {}, field('Template name', name), field('Subject', subj, 'optional'), field('Email content (HTML)', html)),
    footer: [btn('Cancel', { onclick: () => m.close() }), btn('Save template', { kind: 'primary', icon: 'check', onclick: async () => {
      const r = await POST('/api/templates', { name: name.value.trim(), subject: subj.value, html: html.value, text: preset.text || '' });
      if (!r.ok) return toast(r.error, 'warn'); toast('Template saved — find it under Templates › My templates.'); m.close(); await loadState(); if (APP.view === 'templates') viewTemplates();
    } })] });
}

/* ================================================================== SENDERS */
async function viewSenders() {
  if (APP.sub === 'new' || APP.sub === 'edit') return senderForm(APP.sub === 'edit' ? APP.id : null);
  await loadState();
  const v = $('#view'), accs = APP.state.accounts || [];
  setTop(btn('Add sender', { kind: 'primary', icon: 'plus', onclick: () => go('senders', 'new') }));
  if (!accs.length) { v.replaceChildren(card('Sending accounts', null, null, emptyState('server', 'No sender accounts yet', 'Connect Gmail, Outlook, Zoho, SendGrid, Mailgun, Amazon SES, Brevo or any SMTP server. Add several to rotate volume.', btn('Add your first sender', { kind: 'primary', icon: 'plus', onclick: () => go('senders', 'new') })))); return; }
  const grid = h('div', { class: 'acc-grid' }, accs.map(accCard));
  v.replaceChildren(h('div', { style: 'margin-bottom:16px' }, banner('info', 'MailBlaster rotates between the senders chosen for each campaign, respects each daily limit and warm-up step, and auto-pauses a sender that fails 5 times in a row (the campaign continues on the others).')), grid);
}
function accCard(a) {
  const w = a.warmup || {}, lim = a.effective_limit || 0, used = a.sent_today || 0, p = lim ? Math.min(100, used / lim * 100) : 0;
  const statusP = a.paused_reason ? pill('Auto-paused', 'r', true) : a.active ? pill('Active', 'g', true) : pill('Off', 'm', true);
  const imapLine = !a.imap_enabled ? h('div', { class: 'statusline' }, h('span', { class: 'dot' }), 'Inbox sync off — bounces & replies aren’t collected') :
    a.imap_error ? h('div', { class: 'statusline', style: 'color:var(--red-d)' }, h('span', { class: 'dot r' }), 'Inbox sync error: ' + a.imap_error) :
      h('div', { class: 'statusline' }, h('span', { class: 'dot g' }), 'Inbox sync on · checked ' + (a.imap_last_check ? timeAgo(a.imap_last_check) : 'soon'));
  const bRate = pnum(a.bounced7, (a.sent7 || 0) + (a.bounced7 || 0));
  return h('div', { class: 'acc' },
    h('div', { class: 'ah' }, h('div', { class: 'av' }, icon('mail', 19)), h('div', { style: 'flex:1;min-width:0' }, h('div', { class: 'b ellipsis' }, a.from_email || a.label), h('div', { class: 'xs muted ellipsis' }, `${a.label && a.label !== a.from_email ? a.label + ' · ' : ''}${a.host}:${a.port}`)), statusP),
    h('div', { class: 'ab' },
      a.paused_reason ? banner('err', a.paused_reason, [btn('Unpause', { size: 'sm', onclick: async () => { await POST(`/api/accounts/${a.id}/unpause`); toast('Sender unpaused.'); viewSenders(); } })]) : null,
      h('div', { class: 'meter' }, h('div', { class: 'ml' }, h('span', {}, 'Sent today'), h('b', {}, `${fmt(used)} / ${fmt(lim)}`)), h('div', { class: 'pbar' + (p >= 100 ? ' a' : '') }, h('div', { style: `width:${p}%` }))),
      w.active ? h('div', {}, h('div', { class: 'ml hstack', style: 'justify-content:space-between;font-size:12px;color:var(--muted)' },
        h('span', { class: 'hstack', style: 'gap:5px' }, icon('flame', 14), w.done ? 'Warm-up complete' : `Warm-up day ${w.day} of ${w.total_days}`), h('b', { style: 'color:var(--ink)' }, `${fmt(w.limit)}/day today → ${fmt(w.target)}`)),
        h('div', { class: 'ramp', title: 'Daily limit ramp' }, (w.schedule || []).map((x, i) => h('div', { class: i < w.day - 1 ? 'past' : i === w.day - 1 ? 'today' : '', style: `height:${Math.max(4, x / (w.target || 1) * 100)}%`, title: `Day ${i + 1}: ${x}/day` })))) :
        h('div', { class: 'statusline' }, icon('flame', 14), 'Warm-up off — full ' + fmt(a.daily_limit) + '/day from day one'),
      h('div', { class: 'mini-stats' }, h('div', {}, h('b', {}, fmt(a.sent7)), h('span', {}, 'sent · 7 days')), h('div', {}, h('b', { style: bRate >= 5 ? 'color:var(--red-d)' : '' }, (Math.round(bRate * 10) / 10) + '%'), h('span', {}, 'bounce rate')), h('div', {}, h('b', {}, fmt(a.failed7)), h('span', {}, 'failed · 7 days'))),
      imapLine),
    h('div', { class: 'af' }, btn('Test SMTP', { size: 'sm', icon: 'zap', onclick: async e => { const b = e.currentTarget; b.disabled = true; const r = await POST(`/api/accounts/${a.id}/test`); b.disabled = false; r.ok ? toast(r.message) : toast(r.error, 'err', 9000); } }),
      a.imap_enabled ? btn('Sync inbox', { size: 'sm', icon: 'refresh', onclick: async () => { await POST(`/api/accounts/${a.id}/sync`); toast('Syncing this inbox…', 'info'); setTimeout(viewSenders, 6000); } }) : btn('Enable inbox sync', { size: 'sm', icon: 'inbox', onclick: () => go('senders', 'edit', a.id) }),
      h('span', { class: 'spacer' }), btn('Edit', { size: 'sm', icon: 'edit', onclick: () => go('senders', 'edit', a.id) }),
      iconBtn('trash', 'Remove sender', () => removeSender(a), true),
      iconBtn('dots', 'More', e => openMenu(e.currentTarget, [
        { label: a.active ? 'Turn off' : 'Turn on', icon: a.active ? 'pause' : 'play', onclick: async () => { await POST('/api/accounts/' + a.id, { active: a.active ? 0 : 1 }); viewSenders(); } },
        w.active ? { label: 'Restart warm-up from day 1', icon: 'flame', onclick: async () => { await POST(`/api/accounts/${a.id}/warmup-restart`); toast('Warm-up restarted.'); viewSenders(); } } : null,
        'sep', { label: 'Remove sender', icon: 'trash', danger: true, onclick: () => removeSender(a) }]), true)));
}
async function removeSender(a) {
  if (!await confirmBox({ title: 'Remove this sender?', text: `${a.from_email} and its saved password will be removed from MailBlaster. Campaign history is kept. Campaigns still using it continue on their other senders.`, ok: 'Remove', danger: true })) return;
  const r = await POST('/api/accounts/' + a.id, { _delete: 1 }); if (r.ok === false) return toast(r.error, 'err');
  toast('Sender removed.'); await loadState(); go('senders');
}
const PRESET_NAMES = { gmail: 'Gmail', outlook: 'Outlook / 365', yahoo: 'Yahoo', zoho: 'Zoho', sendgrid: 'SendGrid', mailgun: 'Mailgun', ses: 'Amazon SES', brevo: 'Brevo' };
function senderForm(id) {
  const a = id ? (APP.state.accounts || []).find(x => x.id === id) || {} : {};
  const P = APP.state.presets || {}, IP = APP.state.imap_presets || {};
  $('#ttl').textContent = id ? 'Edit sender' : 'Add sender'; $('#tsub').textContent = a.from_email || 'Connect an email account to send from';
  setTop(btn('Cancel', { onclick: () => go('senders') }));
  const I = (k, o = {}) => { const e = h('input', Object.assign({ value: a[k] != null ? a[k] : (o.def != null ? o.def : '') }, o)); return e; };
  const label = I('label', { placeholder: 'e.g. Main Gmail' }), host = I('host', { placeholder: 'smtp.gmail.com' }), port = I('port', { type: 'number', def: 587 });
  const sec = h('select', {}, [['starttls', 'STARTTLS (587)'], ['ssl', 'SSL/TLS (465)'], ['none', 'None']].map(([v, l]) => h('option', { value: v, selected: (a.security || 'starttls') === v }, l)));
  const user = I('username', { placeholder: 'you@gmail.com' }), pass = h('input', { type: 'password', placeholder: id ? '•••••• (leave blank to keep)' : 'App password' });
  const fname = I('from_name', { placeholder: 'Your Name' }), femail = I('from_email', { placeholder: 'you@yourdomain.com' }), reply = I('reply_to', { placeholder: 'optional' });
  const limit = I('daily_limit', { type: 'number', def: 500 });
  const preset = h('div', { class: 'hstack' }, Object.keys(P).filter(k => k !== 'custom').map(k => h('button', { class: 'lbtn', type: 'button', onclick: () => { host.value = P[k].host; port.value = P[k].port; sec.value = P[k].security; ihost.value = ''; autoImap(); } }, PRESET_NAMES[k] || k)));
  // warm-up
  let wOn = !!a.warmup_enabled; const wStart = I('warmup_start', { type: 'number', def: 20, min: 1 }), wGrowth = I('warmup_growth', { type: 'number', def: 20, min: 1 });
  const ramp = h('div'); const wBox = h('div', { style: wOn ? '' : 'display:none' });
  const drawRamp = () => {
    const s = Math.max(1, +wStart.value || 20), g = Math.max(0, +wGrowth.value || 0) / 100, t = Math.max(1, +limit.value || 500); const sched = [];
    for (let n = 0; n < 90; n++) { const x = Math.min(t, Math.max(s, Math.round(s * Math.pow(1 + g, n)))); sched.push(x); if (x >= t) break; }
    ramp.replaceChildren(h('div', { class: 'ramp', style: 'height:60px' }, sched.map(x => h('div', { style: `height:${Math.max(4, x / t * 100)}%`, title: x + '/day' }))),
      h('div', { class: 'small muted', style: 'margin-top:6px' }, `Day 1: ${fmt(sched[0])}/day → day 7: ${fmt(sched[Math.min(6, sched.length - 1)])}/day → full ${fmt(t)}/day on day ${sched.length}.`));
  };
  [wStart, wGrowth, limit].forEach(x => x.addEventListener('input', drawRamp)); drawRamp();
  // imap
  let iOn = !!a.imap_enabled;
  const ihost = I('imap_host', { placeholder: 'imap.gmail.com' }), iport = I('imap_port', { type: 'number', def: 993 });
  const isec = h('select', {}, [['ssl', 'SSL/TLS (993)'], ['starttls', 'STARTTLS (143)'], ['none', 'None']].map(([v, l]) => h('option', { value: v, selected: (a.imap_security || 'ssl') === v }, l)));
  const iuser = I('imap_user', { placeholder: 'same as SMTP username' }), ipass = h('input', { type: 'password', placeholder: id && a.imap_password ? '•••••• (leave blank to keep)' : 'blank = same as SMTP password' });
  const ifold = I('imap_folders', { def: 'INBOX', placeholder: 'INBOX' });
  const iBox = h('div', { style: iOn ? '' : 'display:none' });
  const autoImap = () => { const p = IP[(host.value || '').trim().toLowerCase()]; if (p && !ihost.value) { ihost.value = p.host; iport.value = p.port; isec.value = p.security; } };
  host.addEventListener('change', autoImap);
  const collect = () => {
    const d = { label: label.value, host: host.value, port: port.value, security: sec.value, username: user.value, from_name: fname.value, from_email: femail.value, reply_to: reply.value, daily_limit: limit.value,
      warmup_enabled: wOn ? 1 : 0, warmup_start: wStart.value, warmup_growth: wGrowth.value, imap_enabled: iOn ? 1 : 0, imap_host: ihost.value, imap_port: iport.value, imap_security: isec.value, imap_user: iuser.value, imap_folders: ifold.value || 'INBOX' };
    if (pass.value) d.password = pass.value; if (ipass.value) d.imap_password = ipass.value; return d;
  };
  const testImap = btn('Test inbox connection', { icon: 'zap', onclick: async () => { testImap.disabled = true; const r = await POST('/api/imap/test', Object.assign({ id: id || '' }, collect())); testImap.disabled = false; r.ok ? toast(r.message) : toast(r.error, 'err', 10000); } });
  wBox.append(h('div', { class: 'row' }, field('Start at (emails/day)', wStart), field('Grow by (% per day)', wGrowth)), h('div', { style: 'margin-top:12px' }, ramp),
    h('div', { style: 'margin-top:10px' }, banner('info', 'New domains and mailboxes should start low and ramp up over 2–4 weeks. The daily limit above is the target; MailBlaster enforces today’s step automatically.')));
  iBox.append(h('div', { class: 'row' }, field('IMAP server', ihost, null, 'Auto-filled for Gmail, Outlook, Yahoo, Zoho'), field('Port', iport), field('Security', isec)),
    h('div', { class: 'row' }, field('IMAP username', iuser, 'optional'), field('IMAP password', ipass, 'optional')), field('Folders to scan', ifold, null, 'Comma-separated, e.g. INBOX, [Gmail]/Spam — bounces sometimes land in spam.'),
    h('div', { class: 'hstack', style: 'margin-top:14px' }, testImap), h('div', { style: 'margin-top:12px' }, banner('info', 'Read-only: MailBlaster never deletes, moves or marks your mail as read. Only messages related to your campaigns are stored; personal mail is ignored.')));
  const sec_ = (ic, title, sub, ...body) => h('div', { class: 'form-sec' }, h('div', { class: 'fh' }, h('div', { class: 'fi' }, icon(ic, 17)), h('div', {}, h('h3', {}, title), h('p', {}, sub))), h('div', { class: 'fb' }, ...body));
  const save = async () => {
    if (!host.value || !femail.value) return toast('SMTP host and From email are required.', 'warn');
    const d = collect(); if (id) d.active = a.active != null ? a.active : 1;
    const r = await POST(id ? '/api/accounts/' + id : '/api/accounts', d);
    if (!r.ok) return toast(r.error, 'err'); toast(id ? 'Sender saved.' : 'Sender added.'); await loadState(); go('senders');
  };
  $('#view').replaceChildren(h('div', { style: 'max-width:900px' },
    sec_('server', 'SMTP connection', 'Where your email is sent from', h('label', { class: 'f' }, 'Quick setup'), preset,
      h('div', { class: 'row' }, field('SMTP host', host), field('Port', port), field('Security', sec)),
      h('div', { class: 'row' }, field('Username', user), field('Password', pass)),
      h('div', { style: 'margin-top:12px' }, banner('info', 'Gmail/Outlook need an “app password” (not your normal password). For more than ~2,000/day use SendGrid, Mailgun, Amazon SES or Brevo — or add several senders.'))),
    sec_('user', 'Sender identity', 'What recipients see', h('div', { class: 'row' }, field('From name', fname), field('From email', femail), field('Reply-to', reply, 'optional')), field('Label', label, 'optional', 'A nickname shown inside MailBlaster.')),
    sec_('flame', 'Daily limit & warm-up', 'Protect a new sender’s reputation', field('Daily sending limit', limit, null, 'The most this account will ever send in one day.'),
      h('div', { style: 'margin-top:16px' }, toggle('Warm up this sender', wOn, x => { wOn = x; wBox.style.display = x ? '' : 'none'; }, 'Start low and increase the daily limit a little every day')), h('div', { style: 'margin-top:12px' }, wBox)),
    sec_('inbox', 'Inbox sync (IMAP)', 'Automatic bounce processing & reply detection', toggle('Sync this inbox', iOn, x => { iOn = x; iBox.style.display = x ? '' : 'none'; autoImap(); }, 'Read bounces, complaints and replies from this mailbox every few minutes'), h('div', { style: 'margin-top:14px' }, iBox)),
    h('div', { class: 'hstack' }, btn(id ? 'Save changes' : 'Add sender', { kind: 'primary', size: 'lg', icon: 'check', onclick: save }), btn('Cancel', { size: 'lg', onclick: () => go('senders') }),
      id && a.id ? h('span', { class: 'spacer' }) : null, id && a.id ? btn('Remove sender', { size: 'lg', kind: 'danger', icon: 'trash', onclick: () => removeSender(a) }) : null)));
}

/* ================================================================== DELIVERABILITY */
let DTAB = 'bounces';
async function viewDeliverability() {
  const d = await GET('/api/deliverability'); const s = d.stats || {}, st = d.settings || {};
  const v = $('#view');
  const grade = (val, good, warn) => val <= good ? 'good' : val <= warn ? 'warn' : 'bad';
  const kp = h('div', { class: 'grid g5', style: 'margin-bottom:18px' },
    kpi('bounce', '#ef4444', 'var(--red-l)', 'Bounce rate · 30d', s.bounce_rate + '%', `${fmt(s.hard)} hard · ${fmt(s.soft)} soft`, s.sent ? grade(s.bounce_rate, 2, 5) : ''),
    kpi('alert', '#f59e0b', 'var(--amber-l)', 'Spam complaints', s.complaint_rate + '%', `${fmt(s.complaints)} complaints · keep < 0.1%`, s.sent ? grade(s.complaint_rate, 0.1, 0.3) : ''),
    kpi('reply', '#10b981', 'var(--green-l)', 'Reply rate · 30d', s.reply_rate + '%', fmt(s.replies) + ' replies'),
    kpi('ban', '#64748b', '#eef1f6', 'Unsubscribe rate', s.unsub_rate + '%', fmt(s.unsubs) + ' unsubscribes'),
    kpi('lock', '#4f46e5', 'var(--brand-l)', 'Suppressed', fmt(s.suppressed), 'never emailed again'));
  const num = (k, o = {}) => h('input', Object.assign({ type: 'number', step: 'any', value: st[k] || '', 'data-k': k }, o));
  const setBox = h('div');
  let brakeOn = st.brake_enabled !== '0';
  const brakeFields = h('div', { class: 'grid g2', style: 'gap:4px 16px;margin-top:6px' },
    field('Pause if bounce rate reaches (%)', num('brake_bounce_pct')), field('…after at least (emails)', num('brake_min_sample')),
    field('Pause if failure rate reaches (%)', num('brake_fail_pct'), null, 'Over the last 50 sends — catches blocks/throttling'), field('Pause after N failures in a row', num('brake_consec_fail')),
    field('Pause after N spam complaints', num('brake_complaints'), null, '0 = off'), field('Pause if unsubscribe rate reaches (%)', num('brake_unsub_pct'), null, '0 = off'));
  const saveSettings = async (box, extra = {}) => {
    const data = Object.assign({}, extra); box.querySelectorAll('[data-k]').forEach(i => data[i.dataset.k] = i.value);
    const r = await POST('/api/settings', data); r.ok ? toast('Settings saved.') : toast(r.error, 'err'); await loadState();
  };
  const brakesCard = card('Safety brakes', 'Automatically pause a campaign before it damages your sender reputation', null, h('div', { class: 'card-b' },
    toggle('Safety brakes enabled', brakeOn, x => brakeOn = x, 'Applies to every campaign that has brakes turned on'), brakeFields,
    h('div', { class: 'hstack', style: 'margin-top:16px' }, btn('Save brakes', { kind: 'primary', icon: 'check', onclick: e => saveSettings(brakesCard, { brake_enabled: brakeOn ? 1 : 0 }) }))));
  let stopFu = st.stop_followups_on_reply !== '0', autoUnsub = st.auto_unsub_on_request !== '0';
  const procCard = card('Bounce & reply processing', 'How inbox sync treats what it finds', null, h('div', { class: 'card-b' },
    h('div', { class: 'row' }, field('Check inboxes every (minutes)', num('imap_interval_min', { min: 1 })), field('Soft bounces before removing', num('soft_bounce_limit', { min: 1 }), null, 'e.g. mailbox full 3 times')),
    h('div', { class: 'vstack', style: 'margin-top:16px;gap:14px' }, toggle('Stop follow-ups when someone replies', stopFu, x => stopFu = x, 'Nobody gets a “just following up” after they answered'),
      toggle('Auto-unsubscribe “remove me” replies', autoUnsub, x => autoUnsub = x, 'Replies asking to be removed are honored automatically')),
    h('div', { class: 'hstack', style: 'margin-top:16px' }, btn('Save', { kind: 'primary', icon: 'check', onclick: () => saveSettings(procCard, { stop_followups_on_reply: stopFu ? 1 : 0, auto_unsub_on_request: autoUnsub ? 1 : 0 }) }))));
  // warm-up overview
  const accs = d.accounts || [];
  const wu = card('Sender warm-up', 'Today’s effective limit for each sender', btn('Manage senders', { size: 'sm', onclick: () => go('senders') }), accs.length ? h('div', { class: 'tbl-wrap' }, h('table', { class: 't' },
    h('thead', {}, h('tr', {}, h('th', {}, 'Sender'), h('th', {}, 'Warm-up'), h('th', { class: 'num' }, 'Today'), h('th', { class: 'num' }, 'Target'), h('th', {}, 'Inbox sync'), h('th', { class: 'num' }, 'Bounce · 7d'))),
    h('tbody', {}, accs.map(a => { const w = a.warmup || {}; return h('tr', {}, h('td', { class: 'small b' }, a.from_email), h('td', {}, w.active ? (w.done ? pill('Complete', 'g') : pill(`Day ${w.day}/${w.total_days}`, 'a')) : pill('Off', 'm')),
      h('td', { class: 'num' }, `${fmt(a.sent_today)} / ${fmt(a.effective_limit)}`), h('td', { class: 'num' }, fmt(a.daily_limit)),
      h('td', {}, a.imap_enabled ? (a.imap_error ? pill('Error', 'r') : pill('On', 'g')) : pill('Off', 'm')), h('td', { class: 'num' }, pct(a.bounced7, (a.sent7 || 0) + (a.bounced7 || 0)))); })))) :
    h('div', { class: 'card-b muted small' }, 'No senders yet.'));
  // tabs: bounces / suppression
  const tabCard = h('div', { class: 'card' }); const tabBody = h('div');
  const drawTabs = () => { tabCard.replaceChildren(h('div', { class: 'tabs' }, [['bounces', 'Recent bounces'], ['suppression', 'Suppression list']].map(([k, l]) => h('button', { class: DTAB === k ? 'on' : '', onclick: () => { DTAB = k; drawTabs(); } }, l))), tabBody); DTAB === 'bounces' ? drawBounces(d.bounces || []) : drawSupp(); };
  const reloadBounces = async () => { const x = await GET('/api/deliverability'); d.bounces = x.bounces || []; drawBounces(d.bounces); };
  const delBounces = async (body, msg) => { const r = await POST('/api/bounces/delete', body); if (!r.ok) return toast(r.error, 'err'); toast(msg.replace('#', fmt(r.count))); reloadBounces(); };
  const drawBounces = rows => tabBody.replaceChildren(rows.length ? h('div', {},
    h('div', { class: 'toolbar' }, h('span', { class: 'xs muted' }, 'Deleting log entries does not un-block the address — use the Suppression list for that.'), h('span', { class: 'spacer' }),
      btn('Clear bounce log', { size: 'sm', kind: 'danger', icon: 'trash', onclick: async () => { if (await confirmBox({ title: 'Clear the whole bounce log?', text: 'All bounce records are deleted (bounce-rate stats reset). Bounced addresses stay on the suppression list, so they still won’t be emailed.', ok: 'Clear log', danger: true })) delBounces({ all: 1 }, 'Deleted # bounce record(s).'); } })),
    h('div', { class: 'tbl-wrap', style: 'max-height:460px;overflow:auto' }, h('table', { class: 't' },
    h('thead', {}, h('tr', {}, h('th', {}, 'Email'), h('th', {}, 'Type'), h('th', {}, 'Reason'), h('th', {}, 'Campaign'), h('th', {}, 'Source'), h('th', {}, 'When'), h('th', {}, ''))),
    h('tbody', {}, rows.map(b => h('tr', {}, h('td', { class: 'small' }, b.email), h('td', {}, b.kind === 'hard' ? pill('Hard', 'r') : b.kind === 'soft' ? pill('Soft', 'a') : pill('Complaint', 'v')),
      h('td', { class: 'xs muted', style: 'max-width:380px' }, (b.code && !(b.reason || '').includes(b.code) ? b.code + ' ' : '') + (b.reason || '')), h('td', { class: 'small' }, b.campaign || '—'), h('td', { class: 'xs' }, b.source === 'imap' ? 'Inbox' : 'SMTP'), h('td', { class: 'xs muted nowrap' }, timeAgo(b.ts)),
      h('td', { style: 'width:40px' }, iconBtn('trash', 'Delete this record', () => delBounces({ ids: b.id }, 'Bounce record deleted.'), true)))))))) :
    emptyState('shield', 'No bounces', 'When an address bounces — at send time or via a bounce email in your inbox — it shows up here and is removed from sending automatically.'));
  const SQ = { q: '', page: 0 };
  const drawSupp = async () => {
    const list = h('div'); const q = h('input', { placeholder: 'Search suppressed emails…', value: SQ.q, oninput: debounce(e => { SQ.q = e.target.value; SQ.page = 0; load(); }, 250) });
    const chk = new Set();
    const removeSupp = async emails => {
      if (!await confirmBox({ title: emails.length === 1 ? 'Remove from suppression?' : `Remove ${fmt(emails.length)} addresses from suppression?`, text: `${emails.length === 1 ? emails[0] : 'These addresses'} could be emailed again if they are (re)imported and active. Only do this if you are sure they want your emails.`, ok: 'Remove', danger: true })) return;
      const r = await POST('/api/suppression/remove', { email: emails }); if (!r.ok) return toast(r.error, 'err');
      toast(`Removed ${fmt(r.count)} address(es).`); chk.clear(); load();
    };
    const load = async () => {
      const r = await GET(`/api/suppression?q=${encodeURIComponent(SQ.q)}&page=${SQ.page}`);
      const rows = r.rows || [], allOn = rows.length > 0 && rows.every(x => chk.has(x.email));
      const hcb = h('input', { type: 'checkbox', checked: allOn, title: 'Select all on this page', onchange: e => { rows.forEach(x => e.target.checked ? chk.add(x.email) : chk.delete(x.email)); load(); } });
      list.replaceChildren(!rows.length ? h('div', { class: 'empty', style: 'padding:30px' }, 'No suppressed addresses.') : h('div', {},
        chk.size ? h('div', { class: 'bulkbar' }, h('b', {}, `${fmt(chk.size)} selected`), h('span', { class: 'spacer' }), btn('Clear selection', { size: 'sm', onclick: () => { chk.clear(); load(); } }),
          btn(`Remove ${fmt(chk.size)}`, { size: 'sm', kind: 'danger', icon: 'trash', onclick: () => removeSupp([...chk]) })) : null,
        h('div', { class: 'tbl-wrap' }, h('table', { class: 't' },
        h('thead', {}, h('tr', {}, h('th', { class: 'w-cb' }, hcb), h('th', {}, 'Email'), h('th', {}, 'Reason'), h('th', {}, 'Since'), h('th', {}, ''))),
        h('tbody', {}, rows.map(x => h('tr', { class: chk.has(x.email) ? 'sel' : '' }, h('td', { class: 'w-cb' }, h('input', { type: 'checkbox', checked: chk.has(x.email), onchange: e => { e.target.checked ? chk.add(x.email) : chk.delete(x.email); load(); } })),
          h('td', { class: 'small' }, x.email), h('td', {}, pill(x.reason, x.reason === 'bounce' ? 'r' : x.reason === 'complaint' ? 'v' : 'm')), h('td', { class: 'xs muted' }, timeAgo(x.ts)),
          h('td', { style: 'text-align:right' }, btn('Remove', { size: 'sm', kind: 'quiet', icon: 'trash', onclick: () => removeSupp([x.email]) })))))))),
        h('div', { class: 'pager' }, h('span', {}, `${fmt(r.total)} suppressed`), h('span', { class: 'spacer' }), btn('', { size: 'sm', icon: 'left', disabled: SQ.page <= 0, onclick: () => { SQ.page--; load(); } }), btn('', { size: 'sm', icon: 'right', disabled: (SQ.page + 1) * r.per >= r.total, onclick: () => { SQ.page++; load(); } })));
    };
    tabBody.replaceChildren(h('div', { class: 'toolbar' }, h('div', { class: 'inp-ic', style: 'flex:1;max-width:340px' }, icon('search', 15), q), h('span', { class: 'spacer' }),
      btn('Add emails', { size: 'sm', icon: 'plus', onclick: () => { const ta = h('textarea', { placeholder: 'one@example.com\ntwo@example.com', style: 'min-height:160px' }); const m = modal({ title: 'Add to suppression list', icon: 'lock', body: field('Emails (one per line, or comma-separated)', ta, null, 'These addresses will never be emailed, even if imported later.'),
        footer: [btn('Cancel', { onclick: () => m.close() }), btn('Add', { kind: 'primary', onclick: async () => { const r = await POST('/api/suppression/add', { emails: ta.value }); toast(`${fmt(r.count)} address(es) suppressed.`); m.close(); load(); } })] }); } }),
      h('a', { class: 'btn sm', href: '/api/export/suppression.csv' }, icon('download', 15), 'Export')), list);
    load();
  };
  drawTabs();
  // domain check
  const dom = h('input', { placeholder: 'yourdomain.com', value: ((accs[0] || {}).from_email || '').split('@')[1] || '' }); const dres = h('div', { style: 'margin-top:14px' });
  const domCard = card('Domain health check', 'Inboxes trust you more when these DNS records exist', null, h('div', { class: 'card-b' }, h('div', { class: 'hstack' }, h('div', { style: 'flex:1;max-width:340px' }, dom), btn('Check domain', { icon: 'globe', onclick: () => domainCheck(dom.value, dres) })), dres));
  v.replaceChildren(kp, h('div', { class: 'grid g2', style: 'align-items:start' }, brakesCard, procCard), wu, tabCard, domCard);
}
async function domainCheck(domain, box) {
  if (!domain) return toast('Enter a domain.', 'warn'); box.replaceChildren(h('div', { class: 'muted small' }, 'Looking up DNS…'));
  const r = await GET('/api/domain-check?domain=' + encodeURIComponent(domain));
  if (!r.ok) { box.replaceChildren(banner('err', r.error)); return; }
  const row = (ok, name, help, rec) => h('div', { class: 'hstack', style: 'padding:10px 0;border-bottom:1px solid var(--line);flex-wrap:nowrap;align-items:flex-start' }, ok ? pill('Found', 'g', true) : pill('Missing', 'r', true),
    h('div', { style: 'flex:1;min-width:0' }, h('b', { class: 'small' }, name), h('div', { class: 'xs muted' }, help), rec ? h('div', { class: 'mono xs', style: 'margin-top:4px;word-break:break-all;color:var(--ink-2)' }, rec) : null));
  const allOk = r.spf && r.dmarc && r.mx;
  box.replaceChildren(row(r.mx, 'MX (mail server)', 'Your domain can receive mail — replies and bounces need this'), row(r.spf, 'SPF', 'Authorizes which servers may send for your domain', r.spf_record),
    row(r.dmarc, 'DMARC' + (r.dmarc_policy ? ` · policy: ${r.dmarc_policy}` : ''), 'Protects your domain from spoofing; required by Gmail & Yahoo for bulk senders', r.dmarc_record),
    h('div', { style: 'margin-top:12px' }, allOk ? banner('ok', 'Your domain is set up for good deliverability. Also make sure DKIM is enabled in your email provider’s settings.') : banner('warn', 'Add the missing records in your domain’s DNS (your email provider has copy-paste values). Also enable DKIM signing in your provider.')));
}

/* ================================================================== SETTINGS */
function viewSettings() {
  const s = APP.state.settings || {};
  const custom = s.track_mode === 'custom';
  const base = h('input', { value: custom ? (s.track_base || '') : '', placeholder: 'https://track.yourdomain.com' });
  const ws = h('input', { type: 'number', min: 0, max: 23, value: s.sending_window_start || '0' }), we = h('input', { type: 'number', min: 1, max: 24, value: s.sending_window_end || '24' });
  const trackBox = h('div');
  let pollT = null;
  const drawTrack = async () => {
    const t = await GET('/api/tunnel/status'); const st = APP.state.settings || {};
    clearTimeout(pollT);
    if (APP.view !== 'settings') return;
    let body;
    if (st.track_mode === 'custom') body = banner('ok', h('span', {}, h('b', {}, 'Full tracking is on '), '(opens + clicks) through your own address ', h('span', { class: 'mono' }, st.track_base), '. It must stay online while people open and click your emails.'));
    else if (t.status === 'on') body = h('div', {}, banner('ok', h('span', {}, h('b', {}, 'Open tracking is ON. '), 'Secure public link: ', h('span', { class: 'mono' }, t.url)), [btn('Turn off', { size: 'sm', onclick: async () => { await POST('/api/tunnel/stop'); await loadState(); toast('Open tracking turned off.', 'info'); drawTrack(); } })]),
      h('div', { class: 'help', style: 'margin-top:10px' }, 'Opens are counted while MailBlaster is running, and it reconnects automatically every time the app starts. Links in your emails go straight to your website, so they never break — even when this PC is off.'));
    else if (['downloading', 'starting'].includes(t.status)) { body = banner('info', t.status === 'downloading' ? `Downloading Cloudflare’s free tunnel tool… ${t.progress || 0}% (one time, ~55 MB)` : 'Connecting to Cloudflare…'); pollT = setTimeout(async () => { await loadState(); drawTrack(); }, 1500); }
    else body = h('div', {}, t.status === 'error' ? h('div', { style: 'margin-bottom:12px' }, banner('err', t.error)) : null,
      h('div', { class: 'hstack', style: 'flex-wrap:nowrap;align-items:flex-start;gap:14px' }, h('div', { style: 'flex:1' }, h('b', {}, 'See who opens your emails'),
        h('div', { class: 'small muted', style: 'margin-top:4px' }, 'Gmail, Outlook and Apple Mail load the tracking image from the internet, so MailBlaster needs a public address. One click creates a secure, free Cloudflare link — no account, no router setup. Only the tracking image and unsubscribe page are reachable through it; your dashboard stays private.')),
        btn('Turn on open tracking', { kind: 'primary', icon: 'eye', onclick: async () => { await POST('/api/tunnel/start'); await loadState(); drawTrack(); } })));
    trackBox.replaceChildren(body);
    if (t.status === 'on' && APP.state.tracking !== 'opens') await loadState();
  };
  drawTrack();
  $('#view').replaceChildren(h('div', { style: 'max-width:860px' },
    card('Open & click tracking', 'Know who opened your emails', null, h('div', { class: 'card-b' }, trackBox,
      h('details', { style: 'margin-top:18px' }, h('summary', { class: 'small b', style: 'cursor:pointer' }, 'Advanced: use my own permanent address (adds click tracking)'),
        h('div', { style: 'margin-top:12px' }, field('Public URL that reaches this app', base, null, 'For example a named Cloudflare Tunnel on track.yourdomain.com. Links in emails then pass through it, so it must stay online permanently — if it is down, tracked links won’t open. Leave empty to remove it.'),
          h('div', { class: 'hstack', style: 'margin-top:10px' }, btn('Save address', { onclick: async () => { const r = await POST('/api/settings', { track_base: base.value.trim() }); r.ok ? toast(base.value.trim() ? 'Custom tracking address saved.' : 'Custom address removed.') : toast(r.error, 'err'); await loadState(); drawTrack(); } })))))),
    card('Sending window', 'Only send during these local hours', null, h('div', { class: 'card-b' }, h('div', { class: 'row' }, field('Start hour (0–23)', ws), field('End hour (1–24)', we)),
      h('div', { class: 'help', style: 'margin-top:8px' }, '0 → 24 = any time. Campaigns pause outside the window and continue automatically. Great for cold email: e.g. 8 → 17.'))),
    h('div', { class: 'hstack', style: 'margin-bottom:18px' }, btn('Save settings', { kind: 'primary', icon: 'check', onclick: async () => { const r = await POST('/api/settings', { sending_window_start: ws.value, sending_window_end: we.value }); r.ok ? toast('Settings saved.') : toast(r.error, 'err'); await loadState(); } })),
    card('Your data', 'Everything is stored locally on this computer', null, h('div', { class: 'card-b hstack' },
      h('a', { class: 'btn', href: '/api/export/contacts.csv' }, icon('download', 16), 'Export all contacts'), h('a', { class: 'btn', href: '/api/export/suppression.csv' }, icon('download', 16), 'Export suppression list'))),
    card('Delete data', 'Permanently remove data from this computer. Tip: export a CSV first.', null, h('div', { class: 'card-b' },
      [['campaigns', 'All campaigns & reports', 'Every campaign, follow-up, send log and open/click stat. Contacts are kept.'],
        ['inbox', 'Inbox', 'All replies, auto-replies and bounce emails stored in MailBlaster (your real mailbox is not touched).'],
        ['bounces', 'Bounce log', 'The bounce history. Bounced addresses stay blocked on the suppression list.'],
        ['templates', 'My templates', 'Templates you saved yourself. Built-in templates are not affected.'],
        ['contacts', 'All contacts', 'Every contact and group membership. Groups and campaigns are kept.'],
        ['everything', 'Everything', 'Campaigns, contacts, groups, inbox, bounce log and your templates — a fresh start. Senders, settings and the suppression list are kept.']].map(([k, t, d]) =>
        h('div', { class: 'danger-row' }, h('div', { style: 'flex:1;min-width:0' }, h('b', { class: 'small' }, t), h('div', { class: 'xs muted' }, d)),
          btn('Delete', { size: 'sm', kind: 'danger', icon: 'trash', onclick: async () => {
            if (!await confirmBox({ title: `Delete ${t.toLowerCase()}?`, text: d + ' This cannot be undone.', ok: 'Delete permanently', danger: true, typeText: 'DELETE' })) return;
            const r = k === 'contacts' ? await POST('/api/contacts/delete-all', { confirm: 'DELETE' }) : await POST('/api/data/clear', { what: k, confirm: 'DELETE' });
            if (!r.ok) return toast(r.error, 'err'); toast(`Done — ${fmt(r.count)} item(s) deleted.`); await loadState(); renderNav();
          } }))))),
    card('Compliance', null, null, h('div', { class: 'card-b small muted', style: 'line-height:1.7' },
      'Every email carries a working unsubscribe link and List-Unsubscribe header. Unsubscribes, complaints and hard bounces go on a permanent suppression list that survives deleting and re-importing contacts. Only send to people who agreed to hear from you or have a legitimate business reason, identify yourself honestly, and include your postal address in the footer.'))));
}

/* ================================================================== boot */
$('#hamb').append(icon('menu', 20)); $('#hamb').addEventListener('click', () => toggleSide(true)); $('#backdrop').addEventListener('click', () => toggleSide(false));
(async () => { await loadState(); route(); })();

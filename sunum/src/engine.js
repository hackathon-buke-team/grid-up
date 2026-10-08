/* ======================================================================
   Sunum motoru — slayt, adım, animasyon tetikleme, konuşmacı ekranı, PDF baskısı.
   Bağımlılık yok; dosya çevrimdışı açılır.
   ====================================================================== */
(function () {
'use strict';
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const REDUCED = matchMedia('(prefers-reduced-motion: reduce)').matches;
const SPEAKER = new URLSearchParams(location.search).has('speaker');
/* ?print: her slayt bir sayfa, tüm adımlar açık, sahneler son karede (build.py --pdf). */
const PRINT = new URLSearchParams(location.search).has('print');

const fmtCache = {};
function fmt(v, dec = 0) {
  const k = dec;
  fmtCache[k] = fmtCache[k] || new Intl.NumberFormat('tr-TR', { minimumFractionDigits: dec, maximumFractionDigits: dec });
  return fmtCache[k].format(v).replace('-', '−');
}
window.fmt = fmt;

/* ---------------- sayaç ---------------- */
function countUp(n) {
  if (n._cu) return; n._cu = 1;
  const to = +n.dataset.count, dec = +(n.dataset.dec || 0), from = +(n.dataset.from || 0);
  const pre = n.dataset.pre || '', suf = n.dataset.suf || '';
  const put = v => { n.textContent = pre + (n.dataset.plain ? String(Math.round(v)) : fmt(v, dec)) + suf; };
  if (REDUCED || PRINT) { put(to); return; }
  const delay = parseFloat(getComputedStyle(n).getPropertyValue('--d')) || 0;
  const dur = (+(n.dataset.dur || 1.3)) * 1000;
  const t0 = performance.now() + delay * 1000;
  put(from);
  const tick = t => {
    const p = Math.min(1, Math.max(0, (t - t0) / dur));
    put(from + (to - from) * (1 - Math.pow(1 - p, 3)));
    if (p < 1 && n.isConnected) requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}

/* ---------------- animasyon kapsamı ---------------- */
function closedStep(n, root) {
  const st = n.closest('[data-step]');
  return st && root.contains(st) && !st.classList.contains('on');
}
function activate(scope, root) {
  const nodes = $$('[data-a],[data-count]', scope);
  if (scope.matches && scope.matches('[data-a],[data-count]')) nodes.push(scope);
  for (const n of nodes) {
    if (closedStep(n, root)) continue;
    if (n.hasAttribute('data-a')) n.classList.add('go');
    if (n.hasAttribute('data-count')) countUp(n);
  }
}
function deactivate(scope) {
  const nodes = $$('[data-a],[data-count]', scope);
  if (scope.matches('[data-a],[data-count]')) nodes.push(scope);
  for (const n of nodes) {
    n.classList.remove('go');
    if (n.hasAttribute('data-count')) { n._cu = 0; n.textContent = (n.dataset.pre || '') + fmt(+(n.dataset.from || 0), +(n.dataset.dec || 0)) + (n.dataset.suf || ''); }
  }
}

/* ---------------- slayt kabuğu ---------------- */
const MARK = '<svg viewBox="0 0 32 32"><circle cx="16" cy="16" r="9" fill="none" stroke="#4aa3ff" stroke-width="3"/><circle cx="16" cy="16" r="3.4" fill="#ffea46"/></svg>';
function chrome(s) {
  let h = '';
  if (!s.noCorner) h += `<div class="cnr"><img src="${A.adm}" alt="ADM Elektrik Dağıtım"><i></i><img src="${A.gdz}" alt="GDZ Elektrik Dağıtım"></div>`;
  if (!s.noFoot) h += `<div class="foot">${MARK}<span>PANO GÖZ${s.section ? ' · ' + s.section : ''}</span></div>`;
  h += '<div class="hint-next">→</div>';
  return h;
}
function renderInto(el, i) {
  const s = SL[i];
  const html = PRINT && s.printHtml ? s.printHtml : s.html;
  el.innerHTML = (typeof html === 'function' ? html() : html) + chrome(s)
    + (PRINT && i ? `<div class="pgno">${i + 1} / ${SL.length}</div>` : '');
  el.dataset.i = i;
  for (const p of el.querySelectorAll('[data-a="draw"]')) {
    try { if (p.getTotalLength) p.style.setProperty('--len', Math.ceil(p.getTotalLength() + 4)); } catch (e) { /* görünmeyen öğe */ }
  }
  return Math.max(0, ...$$('[data-step]', el).map(n => +n.dataset.step || 0));
}
function applyStep(el, n, maxStep, animate = true) {
  for (const st of $$('[data-step]', el)) {
    const k = +st.dataset.step;
    if (k <= n) {
      if (!st.classList.contains('on')) { st.classList.add('on'); if (animate) activate(st, el); }
    } else if (st.classList.contains('on')) { st.classList.remove('on'); deactivate(st); }
  }
  for (const d of $$('[data-dim-at]', el)) d.classList.toggle('dimmed', n >= +d.dataset.dimAt);
  for (const d of $$('[data-show-at]', el)) d.style.opacity = n >= +d.dataset.showAt ? '' : '0';
  el.classList.toggle('has-more', n < maxStep);
}
function startScene(el, i, step) {
  const s = SL[i];
  const still = REDUCED || PRINT;
  if (!s.scene || still && s.sceneNoReduced || PRINT && s.printHtml) return null;
  try { return s.scene(el, { step, fmt, A, REDUCED: still }) || null; } catch (e) { console.error('sahne', i, e); return null; }
}

/* ---------------- yayın kanalı (sunum ↔ konuşmacı) ---------------- */
let bc = null;
try { bc = new BroadcastChannel('panogoz-sunum'); } catch (e) { /* eski tarayıcı */ }
function post(msg) {
  try { bc && bc.postMessage(msg); } catch (e) {}
  try { localStorage.setItem('panogoz-sunum', JSON.stringify({ ...msg, _n: Math.random() })); } catch (e) {}
}
function onMsg(fn) {
  if (bc) bc.onmessage = e => fn(e.data);
  addEventListener('storage', e => { if (e.key === 'panogoz-sunum' && e.newValue) { try { fn(JSON.parse(e.newValue)); } catch (_) {} } });
}

/* ---------------- yardımcı paneller ---------------- */
function buildToc(goFn) {
  $('#tocl').innerHTML = SL.map((s, i) =>
    `<li data-i="${i}"><b>${i + 1}.</b><span>${s.title}</span><em>${s.time || ''}</em></li>`).join('');
  $$('#tocl li').forEach(li => li.onclick = () => { goFn(+li.dataset.i, 0); $('#toc').classList.remove('on'); });
}
function buildQa() {
  const render = q => {
    const t = (q || '').toLocaleLowerCase('tr');
    $('#qal').innerHTML = QA.filter(x => !t || (x.q + ' ' + x.a).toLocaleLowerCase('tr').includes(t))
      .map(x => `<div class="q"><h5>${x.q}</h5><p>${x.a}</p>${x.ref ? `<small>${x.ref}</small>` : ''}</div>`).join('')
      || '<p class="sub">Eşleşen soru yok.</p>';
  };
  render('');
  $('#qa input').oninput = e => render(e.target.value);
}
function printScript() {
  const w = window.open('', '_blank');
  if (!w) return;
  const esc = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;');
  const body = SL.map((s, i) => `
    <section><h2><span>${i + 1}</span> ${s.title}<em>${s.time || ''}</em></h2>
    <div class="t">${esc(s.notes || '')}</div>
    ${s.use ? `<div class="u">${s.use}</div>` : ''}</section>`).join('');
  w.document.write(`<!doctype html><html lang="tr"><head><meta charset="utf-8"><title>PANO GÖZ · Konuşma metni</title>
  <style>body{font:15px/1.6 "Segoe UI",system-ui,sans-serif;color:#111;max-width:860px;margin:40px auto;padding:0 24px}
  h1{font-size:26px;margin:0 0 4px}p.s{color:#666;margin:0 0 28px}
  section{break-inside:avoid;border-top:1px solid #ddd;padding:16px 0}
  h2{font-size:18px;margin:0 0 8px;display:flex;gap:10px;align-items:baseline}h2 span{color:#e06d00;font-family:Consolas,monospace}
  h2 em{margin-left:auto;font:500 12px Consolas,monospace;color:#888;font-style:normal}
  .t{white-space:pre-wrap}.u{margin-top:10px;padding:10px 12px;background:#f6f6f6;border-radius:8px;font-size:13.5px;color:#333}
  .u b{color:#b85200}</style></head><body><h1>PANO GÖZ · Final sunumu konuşma metni</h1>
  <p class="s">ADM & GDZ Elektrik · Grid Up Hackathon · ${SL.length} slayt</p>${body}
  <h2 style="margin-top:30px">Jüri soruları — hazır cevaplar</h2>
  ${QA.map(x => `<section><b>${x.q}</b><div>${x.a}</div></section>`).join('')}</body></html>`);
  w.document.close();
}

/* =====================================================================
   PDF BASKISI
   Slaytlar alt alta dizilir; her biri 1280×720 bir sayfadır (deck.css @page).
   Adımların hepsi açılır, sayaçlar son değerine, canlı sahneler REDUCED
   yoluyla son karelerine oturur. Slayt printHtml verirse o kullanılır.
   ===================================================================== */
if (PRINT) {
  document.documentElement.classList.add('print');
  const deck = $('#deck');
  SL.forEach((s, i) => {
    const el = document.createElement('section');
    el.className = 'slide active static';
    deck.appendChild(el);
    const max = renderInto(el, i);
    applyStep(el, max, max, false);
    activate(el, el);
    const sc = startScene(el, i, max);
    if (sc && sc.step) sc.step(max);
    if (sc && sc.stop) sc.stop();
  });
  document.documentElement.dataset.ready = '1';
  return;
}

/* =====================================================================
   KONUŞMACI EKRANI
   ===================================================================== */
if (SPEAKER) {
  document.body.classList.add('speaker');
  document.title = 'Konuşmacı · ' + document.title;
  const box = $('#spk');
  let ci = -1, cs = 0, cmax = 0, scn = null, t0 = null, acc = 0, running = false;
  const curHost = $('#mcur'), nxtHost = $('#mnxt');
  const scale = () => {
    for (const h of [curHost, nxtHost]) {
      const p = h.parentElement; const s = Math.min(p.clientWidth / 1280, p.clientHeight / 720);
      h.style.transform = `scale(${s})`;
      h.style.left = ((p.clientWidth - 1280 * s) / 2) + 'px'; h.style.top = ((p.clientHeight - 720 * s) / 2) + 'px';
    }
  };
  const mk = host => { host.innerHTML = '<section class="slide active"></section>'; return host.firstChild; };
  function show(i, st) {
    i = Math.max(0, Math.min(SL.length - 1, i));
    if (i !== ci) {
      if (scn && scn.stop) scn.stop();
      const el = mk(curHost); cmax = renderInto(el, i); ci = i;
      requestAnimationFrame(() => { activate(el, el); scn = startScene(el, i, st); applyStep(el, st, cmax); scn && scn.step && scn.step(st); });
    } else {
      const el = curHost.firstChild; applyStep(el, st, cmax); scn && scn.step && scn.step(st);
    }
    cs = st < 0 ? cmax : st;
    // sıradaki
    const nx = mk(nxtHost); nx.parentElement.classList.add('static');
    if (cs < cmax) { const m = renderInto(nx, i); applyStep(nx, cs + 1, m, false); activate(nx, nx); $('#spk .nxt .lbl').textContent = `SIRADAKİ · ADIM ${cs + 1}/${cmax}`; }
    else if (i + 1 < SL.length) { const m = renderInto(nx, i + 1); applyStep(nx, m, m, false); activate(nx, nx); $('#spk .nxt .lbl').textContent = `SIRADAKİ · ${i + 2}. ${SL[i + 1].title}`; }
    else { nx.innerHTML = '<div class="center" style="height:100%;font:600 40px var(--sans);color:var(--dim)">Son</div>'; $('#spk .nxt .lbl').textContent = 'SIRADAKİ'; }
    $('#stxt').textContent = SL[i].notes || '';
    $('#suse').innerHTML = SL[i].use || '';
    $('#spk .ttl').textContent = `${i + 1}/${SL.length} · ${SL[i].title}`;
    $('#spk .steps').textContent = cmax ? `adım ${cs}/${cmax}` : '';
    $('#spk .tgt').textContent = SL[i].time ? 'hedef ' + SL[i].time : '';
    scale();
  }
  function nav(d) {
    let i = ci, st = cs;
    if (d > 0) { if (st < cmax) st++; else if (i < SL.length - 1) { i++; st = 0; } }
    else { if (st > 0) st--; else if (i > 0) { i--; st = -1; } }
    if (!running && t0 === null) startTimer();
    show(i, st); post({ t: 'go', i, step: st });
  }
  function startTimer() { running = true; t0 = performance.now(); }
  setInterval(() => {
    const now = new Date();
    $('#spk .clock').textContent = now.toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' });
    const ms = acc + (running && t0 !== null ? performance.now() - t0 : 0);
    const s = Math.floor(ms / 1000);
    $('#spk .timer').textContent = String(Math.floor(s / 60)).padStart(2, '0') + ':' + String(s % 60).padStart(2, '0');
  }, 250);
  $('#tstart').onclick = () => { if (running) { acc += performance.now() - t0; running = false; } else { t0 = performance.now(); running = true; } };
  $('#treset').onclick = () => { acc = 0; t0 = running ? performance.now() : null; };
  addEventListener('resize', scale);
  addEventListener('keydown', e => {
    if (['ArrowRight', ' ', 'PageDown'].includes(e.key)) { e.preventDefault(); nav(1); }
    else if (['ArrowLeft', 'PageUp'].includes(e.key)) { e.preventDefault(); nav(-1); }
  });
  onMsg(m => {
    if (!m || m.t !== 'state' || (m.i === ci && m.step === cs)) return;
    if (!running && t0 === null) startTimer();
    show(m.i, m.step);
  });
  const h = (parseInt(location.hash.slice(1)) || 1) - 1;
  show(h, 0);
  post({ t: 'hello' });
  return;
}

/* =====================================================================
   ANA SUNUM
   ===================================================================== */
const deck = $('#deck');
const slides = SL.map((s, i) => { const el = document.createElement('section'); el.className = 'slide'; el.dataset.i = i; deck.appendChild(el); return el; });
let cur = -1, step = 0, maxStep = 0, scene = null;

function setStep(n) {
  step = Math.max(0, Math.min(maxStep, n));
  applyStep(slides[cur], step, maxStep);
  scene && scene.step && scene.step(step);
  hud();
}
function go(i, st = 0) {
  i = Math.max(0, Math.min(SL.length - 1, i));
  if (i !== cur) {
    if (scene && scene.stop) scene.stop();
    scene = null;
    const prev = slides[cur];
    slides.forEach((el, j) => el.classList.toggle('active', j === i));
    if (prev) setTimeout(() => { if (!prev.classList.contains('active')) prev.innerHTML = ''; }, 450);
    cur = i;
    const el = slides[i];
    maxStep = renderInto(el, i);
    step = 0;
    const target = st < 0 ? maxStep : st;
    requestAnimationFrame(() => {
      if (cur !== i) return;
      activate(el, el);
      scene = startScene(el, i, target);
      setStep(target);
    });
  } else setStep(st < 0 ? maxStep : st);
  hud();
}
function hud() {
  $('#cur').textContent = cur + 1;
  $('#tot').textContent = SL.length;
  $('#bar').style.width = ((cur + 1) / SL.length * 100) + '%';
  const s = SL[cur];
  $('#nttl').textContent = `${cur + 1}. ${s.title}`;
  $('#ntime').textContent = (s.time ? '⏱ ' + s.time : '') + (maxStep ? ` · adım ${step}/${maxStep}` : '');
  $('#ntxt').textContent = s.notes || '';
  $('#nuse').innerHTML = s.use || '';
  $('#navp').disabled = cur === 0 && step === 0;
  $('#navn').disabled = cur === SL.length - 1 && step >= maxStep;
  $$('#tocl li').forEach(li => li.classList.toggle('cur', +li.dataset.i === cur));
  const h = '#' + (cur + 1);
  if (location.hash !== h) history.replaceState(null, '', h);
  post({ t: 'state', i: cur, step });
}
function next() { if (step < maxStep) setStep(step + 1); else if (cur < SL.length - 1) go(cur + 1, 0); }
function prev() { if (step > 0) setStep(step - 1); else if (cur > 0) go(cur - 1, -1); }

/* Slayt, iki yanda ok düğmeleri için boşluk bırakacak biçimde ölçeklenir; oklar bu
   boşluğun ortasına, sayaç slaytın altındaki boşluğa oturur. Hiçbiri slayta değmez. */
const NAV = 44, NAV_GAP = 16;
function fit() {
  const W = innerWidth, Hh = innerHeight;
  const side = NAV + 2 * NAV_GAP;
  const s = Math.max(.2, Math.min((W - 2 * side) / 1280, (Hh - 80) / 720));
  deck.style.transform = `scale(${s})`;
  const sw = 1280 * s, sh = 720 * s, gx = (W - sw) / 2, gy = (Hh - sh) / 2;
  const x = Math.max(6, (gx - NAV) / 2);
  $('#navp').style.left = x + 'px';
  $('#navn').style.right = x + 'px';
  const hudEl = $('#hud');
  hudEl.style.right = gx + 'px';
  hudEl.style.bottom = Math.max(4, (gy - 16) / 2) + 'px';
  const help = $('#help');
  help.style.left = gx + 'px';
  help.style.bottom = Math.max(4, (gy - 25) / 2) + 'px';
}
addEventListener('resize', fit);

/* kenar okları */
let navT = 0;
function navShow() { document.body.classList.add('navon'); clearTimeout(navT); navT = setTimeout(() => document.body.classList.remove('navon'), 1800); }
addEventListener('mousemove', navShow);
$('#navp').onclick = e => { e.stopPropagation(); prev(); };
$('#navn').onclick = e => { e.stopPropagation(); next(); };

const overlay = id => $(id).classList.contains('on');
function closeAll() { ['#notes', '#toc', '#qa'].forEach(id => $(id).classList.remove('on')); }
let numBuf = '', numT = 0;
addEventListener('keydown', e => {
  if (e.target.tagName === 'INPUT') { if (e.key === 'Escape') { $('#qa').classList.remove('on'); e.target.blur(); } return; }
  if (e.ctrlKey || e.metaKey || e.altKey) return;
  const k = e.key;
  if (k === 'Escape') { closeAll(); $('#black').classList.remove('on'); return; }
  if (/^[0-9]$/.test(k)) { numBuf += k; clearTimeout(numT); numT = setTimeout(() => numBuf = '', 1500); return; }
  if (k === 'Enter' && numBuf) { go(parseInt(numBuf, 10) - 1, 0); numBuf = ''; return; }
  if (['ArrowRight', ' ', 'PageDown', 'ArrowDown'].includes(k)) { e.preventDefault(); next(); }
  else if (['ArrowLeft', 'PageUp', 'ArrowUp'].includes(k)) { e.preventDefault(); prev(); }
  else if (k === 'Home') go(0, 0);
  else if (k === 'End') go(SL.length - 1, -1);
  else if (k === 'n' || k === 'N') $('#notes').classList.toggle('on');
  else if (k === 'o' || k === 'O') $('#toc').classList.toggle('on');
  else if (k === 'q' || k === 'Q') { $('#qa').classList.toggle('on'); if (overlay('#qa')) setTimeout(() => $('#qa input').focus(), 50); }
  else if (k === 's' || k === 'S') window.open(location.pathname + '?speaker#' + (cur + 1), 'panogoz-konusmaci', 'width=1400,height=860');
  else if (k === 'f' || k === 'F') { if (document.fullscreenElement) document.exitFullscreen(); else document.documentElement.requestFullscreen().catch(() => {}); }
  else if (k === 'b' || k === 'B' || k === '.') $('#black').classList.toggle('on');
  else if (k === 'p' || k === 'P') printScript();
  else if (k === 'r' || k === 'R') { const c = cur; cur = -1; go(c, 0); }
  else if (k === '?' || k === 'h' || k === 'H') flashHelp();
});
addEventListener('click', e => {
  if (e.target.closest('.panel') || e.target.closest('.nav') || e.target.closest('#black')) return;
  if (e.target.closest('.slide')) return;
  e.clientX < innerWidth * 0.5 ? prev() : next();
});
$('#black').onclick = () => $('#black').classList.remove('on');
onMsg(m => {
  if (!m) return;
  if (m.t === 'go') { if (m.i !== cur) go(m.i, m.step); else setStep(m.step < 0 ? maxStep : m.step); }
  else if (m.t === 'hello') post({ t: 'state', i: cur, step });
});
function flashHelp() { const h = $('#help'); h.classList.add('on'); clearTimeout(h._t); h._t = setTimeout(() => h.classList.remove('on'), 4200); }

addEventListener('hashchange', () => { const n = parseInt(location.hash.slice(1), 10); if (n && n - 1 !== cur) go(n - 1, 0); });
/* prova ve otomatik kontrol için */
window.__deck = { go, next, prev, get cur() { return cur; }, get step() { return step; }, get maxStep() { return maxStep; }, count: SL.length };

buildToc(go);
buildQa();
fit();
go(Math.max(0, (parseInt(location.hash.slice(1)) || 1) - 1), 0);
setTimeout(flashHelp, 700);
})();

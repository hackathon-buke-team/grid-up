// PANO GÖZ · aranabilir seçim listesi.
//
// Tarayıcının yerleşik <select> öğesi 112 panoda işe yaramaz: arama yok, alt
// satır yok, seviye rozeti yok ve açılır kutu işletim sisteminin kendi
// çizdiği penceredir - temayı da tipografiyi de tanımaz. Burası onun yerini
// alır ve şunları verir:
//
//   * yazarak süzme (Türkçe sıralama ve harf katlaması ile)
//   * her satırda etiket + alt satır + seviye rozeti
//   * klavye: yukarı/aşağı, Enter, Esc, Home/End
//   * liste GÖVDEYE çizilir, üst şeridin overflow:hidden'ı onu kırpmasın diye
//
// Bağımlılık yok; bir bileşen kütüphanesi eklemek bu depodaki tek üçüncü taraf
// paket olurdu ve sıfır bağımlılık iddiası oradan giderdi.

import { h, mount, clear } from './dom.js';

/** Türkçe arama: "İ" ile "i", "I" ile "ı" aynı kabul edilir. */
function fold(s) {
  return String(s || '')
    .replace(/İ/g, 'i').replace(/I/g, 'ı')
    .toLocaleLowerCase('tr')
    .replace(/ı/g, 'i').replace(/ş/g, 's').replace(/ğ/g, 'g')
    .replace(/ü/g, 'u').replace(/ö/g, 'o').replace(/ç/g, 'c');
}

/**
 * @param {object} o
 *   placeholder  seçim yokken yazılacak metin
 *   ara          arama kutusu başlığı
 *   bos          liste boşken yazılacak metin
 *   genislik     düğme genişliği (css)
 *   onPick(value)
 */
export function combo(o = {}) {
  let items = [];
  let value = null;
  let open = false;
  let aktif = -1;      // klavyeyle gezilen satır
  let suzulmus = [];

  const etiket = h('span.cb-lbl', { text: o.placeholder || 'Seç…' });
  const btn = h('button.cb-btn', {
    type: 'button',
    'aria-haspopup': 'listbox',
    'aria-expanded': 'false',
    onclick: (ev) => { ev.stopPropagation(); toggle(); },
    onkeydown: (ev) => {
      if (ev.key === 'ArrowDown' || ev.key === 'Enter' || ev.key === ' ') {
        ev.preventDefault();
        if (!open) toggle(true);
      }
    },
  }, etiket, h('span.cb-caret', { text: '▾', 'aria-hidden': 'true' }));
  if (o.genislik) btn.style.width = o.genislik;

  const arama = h('input.cb-search', {
    type: 'text',
    placeholder: o.ara || 'Ara…',
    autocomplete: 'off',
    spellcheck: 'false',
    oninput: () => { aktif = 0; renderList(); },
    onkeydown: onKey,
  });
  const liste = h('div.cb-list', { role: 'listbox' });
  const pop = h('div.cb-pop', h('div.cb-search-row', arama), liste);
  pop.addEventListener('click', (ev) => ev.stopPropagation());

  // ------------------------------------------------------------- konum --

  function place() {
    const r = btn.getBoundingClientRect();
    // Satırda anahtar + alt satır + rozet yan yana durur; 300 px'de anahtar
    // kırpılıyordu. Düğme dar olsa da liste geniş açılır.
    const w = Math.min(Math.max(r.width, 430), window.innerWidth - 24);
    pop.style.width = w + 'px';
    pop.style.left = Math.min(r.left, window.innerWidth - w - 8) + 'px';
    // Aşağıda yer yoksa yukarı aç.
    const alt = window.innerHeight - r.bottom;
    if (alt < 240 && r.top > alt) {
      pop.style.top = '';
      pop.style.bottom = (window.innerHeight - r.top + 4) + 'px';
      pop.style.maxHeight = (r.top - 16) + 'px';
    } else {
      pop.style.bottom = '';
      pop.style.top = (r.bottom + 4) + 'px';
      pop.style.maxHeight = (alt - 16) + 'px';
    }
  }

  // ------------------------------------------------------------- çizim --

  function renderList() {
    const q = fold(arama.value.trim());
    suzulmus = !q ? items.slice()
      : items.filter((it) => fold(it.label).includes(q) || fold(it.sub).includes(q));
    if (aktif >= suzulmus.length) aktif = suzulmus.length - 1;
    if (aktif < 0 && suzulmus.length) aktif = Math.max(0, suzulmus.findIndex((it) => it.value === value));

    if (!suzulmus.length) {
      mount(liste, h('div.cb-empty', { text: q ? 'eşleşen pano yok' : (o.bos || 'liste boş') }));
      return;
    }
    mount(liste, ...suzulmus.map((it, i) => {
      const row = h('div.cb-row' + (it.value === value ? '.sel' : '') + (i === aktif ? '.on' : ''), {
        role: 'option',
        'aria-selected': String(it.value === value),
        onclick: () => pick(it.value),
        onmousemove: () => { if (aktif !== i) { aktif = i; markActive(); } },
      },
        h('span.cb-row-t',
          h('span.cb-row-l', { text: it.label }),
          it.sub ? h('span.cb-row-s', { text: it.sub }) : null),
        it.badge || null);
      return row;
    }));
    scrollToActive();
  }

  function markActive() {
    const rows = liste.children;
    for (let i = 0; i < rows.length; i++) rows[i].classList.toggle('on', i === aktif);
  }

  function scrollToActive() {
    const el = liste.children[aktif];
    if (!el) return;
    const lr = liste.getBoundingClientRect(), er = el.getBoundingClientRect();
    if (er.top < lr.top) liste.scrollTop -= lr.top - er.top;
    else if (er.bottom > lr.bottom) liste.scrollTop += er.bottom - lr.bottom;
  }

  function onKey(ev) {
    if (ev.key === 'ArrowDown') { aktif = Math.min(suzulmus.length - 1, aktif + 1); markActive(); scrollToActive(); }
    else if (ev.key === 'ArrowUp') { aktif = Math.max(0, aktif - 1); markActive(); scrollToActive(); }
    else if (ev.key === 'Home') { aktif = 0; markActive(); scrollToActive(); }
    else if (ev.key === 'End') { aktif = suzulmus.length - 1; markActive(); scrollToActive(); }
    else if (ev.key === 'Enter') { if (suzulmus[aktif]) pick(suzulmus[aktif].value); }
    else if (ev.key === 'Escape') { toggle(false); btn.focus(); }
    else if (ev.key === 'Tab') { toggle(false); return; }
    else return;
    ev.preventDefault();
  }

  // ------------------------------------------------------------- durum --

  function toggle(force) {
    const want = force === undefined ? !open : force;
    if (want === open) return;
    open = want;
    btn.setAttribute('aria-expanded', String(open));
    btn.classList.toggle('on', open);
    if (open) {
      document.body.appendChild(pop);
      arama.value = '';
      aktif = -1;
      renderList();
      place();
      arama.focus();
      document.addEventListener('pointerdown', onOutside, true);
      window.addEventListener('resize', place);
      window.addEventListener('scroll', place, true);
    } else {
      if (pop.parentNode) pop.parentNode.removeChild(pop);
      document.removeEventListener('pointerdown', onOutside, true);
      window.removeEventListener('resize', place);
      window.removeEventListener('scroll', place, true);
    }
  }

  function onOutside(ev) {
    if (pop.contains(ev.target) || btn.contains(ev.target)) return;
    toggle(false);
  }

  function pick(v) {
    value = v;
    syncLabel();
    toggle(false);
    btn.focus();
    if (o.onPick) o.onPick(v);
  }

  function syncLabel() {
    const it = items.find((x) => x.value === value);
    clear(etiket);
    if (!it) { etiket.textContent = o.placeholder || 'Seç…'; etiket.classList.add('bos'); return; }
    etiket.classList.remove('bos');
    etiket.appendChild(h('span.cb-row-l', { text: it.label }));
    if (it.sub) etiket.appendChild(h('span.cb-row-s', { text: it.sub }));
  }

  return {
    el: btn,
    /** items: [{value, label, sub, badge}] · badge bir DOM düğümü olabilir */
    setItems(next) { items = next || []; syncLabel(); if (open) renderList(); },
    setValue(v) { value = v; syncLabel(); if (open) renderList(); },
    value: () => value,
    close: () => toggle(false),
    destroy() { toggle(false); },
  };
}

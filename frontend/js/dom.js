// PANO GÖZ · minik DOM yardımcıları.
// Çerçeve yok, sanal DOM yok: 6 ekranlık bir konsol için gereken tek şey
// element üretmek ve olay bağlamak. Toplam ~90 satır, hiçbir bağımlılık yok.

const SVG_NS = 'http://www.w3.org/2000/svg';

/**
 * h('div.card#x', {attr: v}, child, child...) -> HTMLElement
 * Etiket kısayolu: 'tag.class1.class2#id'
 */
export function h(spec, attrs, ...kids) {
  const m = /^([a-zA-Z0-9-]+)?((?:\.[^.#]+)*)?(?:#([^.#]+))?$/.exec(spec) || [];
  const node = document.createElement(m[1] || 'div');
  if (m[2]) for (const c of m[2].split('.').filter(Boolean)) node.classList.add(c);
  if (m[3]) node.id = m[3];
  applyAttrs(node, attrs, kids);
  return node;
}

/** SVG sürümü. s('circle.dot', {cx: 1}) */
export function s(spec, attrs, ...kids) {
  const m = /^([a-zA-Z0-9-]+)?((?:\.[^.#]+)*)?(?:#([^.#]+))?$/.exec(spec) || [];
  const node = document.createElementNS(SVG_NS, m[1] || 'g');
  if (m[2]) for (const c of m[2].split('.').filter(Boolean)) node.classList.add(c);
  if (m[3]) node.setAttribute('id', m[3]);
  applyAttrs(node, attrs, kids, true);
  return node;
}

function applyAttrs(node, attrs, kids, isSvg) {
  if (attrs && (typeof attrs !== 'object' || attrs instanceof Node || Array.isArray(attrs))) {
    kids = [attrs, ...kids];
    attrs = null;
  }
  if (attrs) {
    for (const [k, v] of Object.entries(attrs)) {
      if (v === null || v === undefined || v === false) continue;
      if (k === 'text') { node.textContent = String(v); continue; }
      // NOT: 'html' YALNIZCA bu depodaki sabit ikon/işaret metinleri için kullanılır.
      // API'den gelen hiçbir değer buraya geçirilmez; metin daima 'text' ile yazılır.
      if (k === 'html') { node.innerHTML = v; continue; }
      if (k === 'style' && typeof v === 'object') { Object.assign(node.style, v); continue; }
      if (k === 'dataset') { Object.assign(node.dataset, v); continue; }
      if (k.startsWith('on') && typeof v === 'function') {
        node.addEventListener(k.slice(2).toLowerCase(), v);
        continue;
      }
      if (!isSvg && (k === 'value' || k === 'checked' || k === 'disabled')) {
        node[k] = v;
        continue;
      }
      node.setAttribute(k, v === true ? '' : String(v));
    }
  }
  add(node, kids);
}

function add(node, kids) {
  for (const kid of kids.flat(4)) {
    if (kid === null || kid === undefined || kid === false || kid === '') continue;
    node.appendChild(kid instanceof Node ? kid : document.createTextNode(String(kid)));
  }
}

export function clear(node) {
  while (node && node.firstChild) node.removeChild(node.firstChild);
  return node;
}

export function mount(node, ...kids) {
  clear(node);
  add(node, kids);
  return node;
}

export function qs(sel, root) { return (root || document).querySelector(sel); }
export function qsa(sel, root) { return Array.from((root || document).querySelectorAll(sel)); }

/** Boş durum bloğu - hata yerine daima bir şey göster. */
export function empty(title, detail) {
  return h('div.empty',
    s('svg', { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '1.5' },
      s('circle', { cx: 12, cy: 12, r: 9 }),
      s('path', { d: 'M8 12h8' })),
    h('div.big', { text: title }),
    detail ? h('div.small', { text: detail }) : null);
}

/** Basit ipucu: metnin altını noktalı çizer, üstüne gelince kutuyu açar. */
export function hint(label, text, cls) {
  return h('span.hint' + (cls ? '.' + cls : ''), { tabindex: '0' },
    label, h('span.hint-box', { text }));
}

export function copyToClipboard(text) {
  if (navigator.clipboard && window.isSecureContext) {
    return navigator.clipboard.writeText(text).catch(() => fallbackCopy(text));
  }
  return Promise.resolve(fallbackCopy(text));
}

function fallbackCopy(text) {
  const ta = document.createElement('textarea');
  ta.value = text;
  ta.style.position = 'fixed';
  ta.style.opacity = '0';
  document.body.appendChild(ta);
  ta.select();
  try { document.execCommand('copy'); } catch (e) { /* yoksay */ }
  document.body.removeChild(ta);
}

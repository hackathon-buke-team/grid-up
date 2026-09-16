// PANO GÖZ · SVG yakınlaştırma ve kaydırma.
//
// Tek bir yerde çözülür, iki yerde kullanılır: filo haritası ve pano dijital
// ikizi. Dönüşüm viewBox üzerinden yapılır, CSS transform üzerinden değil;
// çünkü viewBox değişince çizgi kalınlıkları vector-effect ile sabit kalır ve
// metin yeniden dizilir. transform ile yakınlaştırılan bir SVG'de 1 px'lik
// sınır çizgisi 8 px'e şişer ve çizim kabalaşır.
//
// Tekerlek imlecin altındaki noktayı sabit tutar. Sürükleme sol tuşla.
// Klavye: + - yakınlaştırır/uzaklaştırır, 0 sığdırır, oklar kaydırır.

const clamp = (v, lo, hi) => (v < lo ? lo : (v > hi ? hi : v));

function parseBox(str) {
  const p = String(str || '').trim().split(/[\s,]+/).map(Number);
  if (p.length !== 4 || p.some((n) => !Number.isFinite(n))) return null;
  return { x: p[0], y: p[1], w: p[2], h: p[3] };
}

const fmtBox = (b) => `${b.x} ${b.y} ${b.w} ${b.h}`;

/**
 * @param {SVGSVGElement} svg
 * @param {object} opts
 *   base    {x,y,w,h}  başlangıç ve "sığdır" görünümü (varsayılan: viewBox)
 *   limit   {x,y,w,h}  kaydırmanın çıkamayacağı sınır (varsayılan: base + %60)
 *   minKat  en fazla uzaklaşma (base genişliğinin katı olarak, >1 = daha geniş)
 *   maxKat  en fazla yaklaşma
 *   onChange(kat, box)
 */
export function zoomPan(svg, opts = {}) {
  const base = opts.base || parseBox(svg.getAttribute('viewBox')) || { x: 0, y: 0, w: 100, h: 100 };
  const minKat = opts.minKat ?? 1;      // 1 = base'den daha geniş görünemez
  const maxKat = opts.maxKat ?? 40;
  const limit = opts.limit || {
    x: base.x - base.w * 0.3, y: base.y - base.h * 0.3,
    w: base.w * 1.6, h: base.h * 1.6,
  };

  // opts.view verilirse o gorunumle acilir: cizim yeniden kurulunca kullanicinin
  // yakinlastirmasi sifirlanmasin diye.
  let view = { ...base };
  let raf = 0;
  let dragging = null;
  let pinch = null;
  let dead = false;
  let touched = false;   // dışarıdan bir görünüm istendi mi?

  /** %100 = çerçeveye tam sığan görünüm. Kullanıcıya gösterilen oran budur;
   *  base kutusunun genişliğine göre ölçmek "her şey görünüyor ama %65" gibi
   *  anlamsız bir sayı üretiyordu. */
  function scale() { return fitWidth() / view.w; }

  function fitWidth() { return Math.max(base.w, base.h * aspect()); }

  /**
   * Öğenin GERÇEK en-boy oranı. viewBox'ı buna eşitliyoruz; aksi hâlde
   * preserveAspectRatio "meet" devreye girer, çizim kutulanır ve "şu kutuya
   * yakınlaş" dediğimiz yer ekranda başka bir yere düşer. Filo haritası
   * açılışta Ege yerine ülkenin yarısını gösteriyordu, sebebi tam buydu.
   */
  function aspect() {
    const r = svg.getBoundingClientRect();
    return (r.width > 0 && r.height > 0) ? r.width / r.height : base.w / base.h;
  }

  function clampView(v) {
    const a = aspect();
    // En geniş görünüm: base kutusunu bu oranda KAPSAYAN çerçeve.
    const fitW = fitWidth();
    const maxW = fitW / minKat;
    const minW = fitW / maxKat;
    let w = clamp(v.w, minW, maxW);
    let h = w / a;
    let x = v.x + (v.w - w) / 2;
    let y = v.y + (v.h - h) / 2;
    // Görünüm sınırdan genişse ortala, değilse sınırın içinde tut.
    if (w >= limit.w) x = limit.x + (limit.w - w) / 2;
    else x = clamp(x, limit.x, limit.x + limit.w - w);
    if (h >= limit.h) y = limit.y + (limit.h - h) / 2;
    else y = clamp(y, limit.y, limit.y + limit.h - h);
    return { x, y, w, h };
  }

  function commit() {
    if (raf) return;
    raf = requestAnimationFrame(() => {
      raf = 0;
      svg.setAttribute('viewBox', fmtBox(view));
      if (opts.onChange) opts.onChange(scale(), view);
    });
  }

  function set(v) { touched = true; view = clampView(v); commit(); }

  /** Ekran koordinatını kullanıcı koordinatına çevir. */
  function toUser(clientX, clientY) {
    const r = svg.getBoundingClientRect();
    if (!r.width || !r.height) return { x: view.x, y: view.y };
    // viewBox oranı öğenin oranına eşitlendiği için kutulama payı sıfırdır;
    // yine de payı hesaba katıyoruz, bir kare gecikmede oran henüz
    // güncellenmemiş olabilir.
    const sc = Math.min(r.width / view.w, r.height / view.h);
    const offX = (r.width - view.w * sc) / 2;
    const offY = (r.height - view.h * sc) / 2;
    return {
      x: view.x + (clientX - r.left - offX) / sc,
      y: view.y + (clientY - r.top - offY) / sc,
    };
  }

  /** İmlecin altındaki noktayı sabit tutarak ölçekle. */
  function zoomAt(factor, clientX, clientY) {
    const p = (clientX === undefined)
      ? { x: view.x + view.w / 2, y: view.y + view.h / 2 }
      : toUser(clientX, clientY);
    const w = view.w / factor;
    const h = view.h / factor;
    set({ x: p.x - (p.x - view.x) * (w / view.w), y: p.y - (p.y - view.y) * (h / view.h), w, h });
  }

  // ------------------------------------------------------------ olaylar --

  const onWheel = (ev) => {
    ev.preventDefault();
    // Dokunmatik yüzeyde kıstırma ctrl+wheel gelir ve adımları çok küçüktür.
    const unit = ev.deltaMode === 1 ? 16 : (ev.deltaMode === 2 ? 400 : 1);
    const d = ev.deltaY * unit * (ev.ctrlKey ? 2.2 : 1);
    zoomAt(Math.exp(-d * 0.0022), ev.clientX, ev.clientY);
  };

  const onDown = (ev) => {
    if (ev.button !== 0 || ev.target.closest('[data-nodrag]')) return;
    // İşaretçi burada YAKALANMAZ. pointerdown'da setPointerCapture çağırmak,
    // ondan sonraki pointerup'ı ve türediği CLICK olayını svg'ye yönlendirir:
    // olay artık harita işaretinin ya da ikizdeki bağlantının içinden geçmez,
    // o düğümlerdeki click dinleyicileri hiç çalışmaz. Yakalama, gerçekten
    // sürükleme başlayınca (birkaç piksel) onMove içinde yapılır.
    dragging = {
      id: ev.pointerId, ...toUser(ev.clientX, ev.clientY), moved: 0,
      cx: ev.clientX, cy: ev.clientY, captured: false,
    };
    svg.classList.add('zp-drag');
  };

  const onMove = (ev) => {
    if (!dragging || ev.pointerId !== dragging.id) return;
    if (!dragging.captured) {
      // Eşiğin altındaki titreme sürükleme değildir; tıklamayı bozmayalım.
      if (Math.abs(ev.clientX - dragging.cx) + Math.abs(ev.clientY - dragging.cy) < 3) return;
      dragging.captured = true;
      try { svg.setPointerCapture(ev.pointerId); } catch (e) { /* yoksay */ }
    }
    const p = toUser(ev.clientX, ev.clientY);
    const dx = dragging.x - p.x, dy = dragging.y - p.y;
    dragging.moved += Math.abs(dx) + Math.abs(dy);
    set({ x: view.x + dx, y: view.y + dy, w: view.w, h: view.h });
  };

  const onUp = (ev) => {
    if (!dragging || ev.pointerId !== dragging.id) return;
    // Sürüklemeden sonraki tıklamayı yut: harita üstünde sürükleyen biri
    // altındaki panoya gitmek istemiyordur.
    const moved = dragging.moved > view.w * 0.01;
    const captured = dragging.captured;
    dragging = null;
    svg.classList.remove('zp-drag');
    if (captured) { try { svg.releasePointerCapture(ev.pointerId); } catch (e) { /* yoksay */ } }
    if (moved) {
      const eat = (e) => { e.stopPropagation(); e.preventDefault(); };
      svg.addEventListener('click', eat, { capture: true, once: true });
      setTimeout(() => svg.removeEventListener('click', eat, { capture: true }), 0);
    }
  };

  const onTouchStart = (ev) => {
    if (ev.touches.length !== 2) return;
    const [a, b] = ev.touches;
    pinch = { d: Math.hypot(a.clientX - b.clientX, a.clientY - b.clientY) };
  };

  const onTouchMove = (ev) => {
    if (!pinch || ev.touches.length !== 2) return;
    ev.preventDefault();
    const [a, b] = ev.touches;
    const d = Math.hypot(a.clientX - b.clientX, a.clientY - b.clientY);
    if (pinch.d > 0) zoomAt(d / pinch.d, (a.clientX + b.clientX) / 2, (a.clientY + b.clientY) / 2);
    pinch.d = d;
  };

  const onTouchEnd = () => { pinch = null; };

  const onKey = (ev) => {
    const step = view.w * 0.12;
    const k = ev.key;
    if (k === '+' || k === '=') zoomAt(1.3);
    else if (k === '-' || k === '_') zoomAt(1 / 1.3);
    else if (k === '0') set(cover(base, 0));
    else if (k === 'ArrowLeft') set({ ...view, x: view.x - step });
    else if (k === 'ArrowRight') set({ ...view, x: view.x + step });
    else if (k === 'ArrowUp') set({ ...view, y: view.y - step });
    else if (k === 'ArrowDown') set({ ...view, y: view.y + step });
    else return;
    ev.preventDefault();
  };

  if (opts.view) {
    touched = true;
    view = clampView(opts.view);
    svg.setAttribute('viewBox', fmtBox(view));
  }

  // Kuruluş anında öğe henüz ölçülmemiş olabilir (genişlik 0). Bir kare sonra
  // gerçek oranı öğrenip çerçeveyi ona uyduruyoruz: ilk görünüm de kutulanmaz.
  // Bu arada çağıran bir görünüm istediyse (harita filo bölgesine yakınlaşır)
  // ona dokunmayız - yoksa kullanıcının gördüğü ilk kare yanlış yere oturur.
  requestAnimationFrame(() => {
    if (dead || touched) return;
    set(cover(base, 0));
  });

  svg.addEventListener('wheel', onWheel, { passive: false });
  svg.addEventListener('pointerdown', onDown);
  svg.addEventListener('pointermove', onMove);
  svg.addEventListener('pointerup', onUp);
  svg.addEventListener('pointercancel', onUp);
  svg.addEventListener('touchstart', onTouchStart, { passive: true });
  svg.addEventListener('touchmove', onTouchMove, { passive: false });
  svg.addEventListener('touchend', onTouchEnd);
  svg.addEventListener('keydown', onKey);
  if (!svg.hasAttribute('tabindex')) svg.setAttribute('tabindex', '0');
  svg.style.touchAction = 'none';

  /** Kutuyu öğenin oranında KAPSAYAN çerçeve; kutunun tamamı hep görünür. */
  function cover(box, pad) {
    const a = aspect();
    let w = box.w * (1 + pad * 2);
    let hh = box.h * (1 + pad * 2);
    if (w / hh < a) w = hh * a; else hh = w / a;
    return { x: box.x + box.w / 2 - w / 2, y: box.y + box.h / 2 - hh / 2, w, h: hh };
  }

  // Pencere yeniden boyutlanınca oran değişir; çerçeveyi yeni orana uydur.
  const onResize = () => set({ ...view });
  window.addEventListener('resize', onResize);

  return {
    /** Bir kutuya yakınlaş; pay oranla verilir. */
    goto(box, pad = 0.12) { set(cover(box, pad)); },
    fit() { set(cover(base, 0)); },
    /** Öğe boyutu pencere olayı olmadan değiştiyse (tam ekran gibi) çağrılır:
     *  çerçeveyi yeni en-boy oranına uydurur, ölçeği korur. */
    refit() { set({ ...view }); },
    zoomBy(f) { zoomAt(f); },
    scale,
    view: () => ({ ...view }),
    destroy() {
      if (dead) return;
      dead = true;
      if (raf) cancelAnimationFrame(raf);
      window.removeEventListener('resize', onResize);
      svg.removeEventListener('wheel', onWheel);
      svg.removeEventListener('pointerdown', onDown);
      svg.removeEventListener('pointermove', onMove);
      svg.removeEventListener('pointerup', onUp);
      svg.removeEventListener('pointercancel', onUp);
      svg.removeEventListener('touchstart', onTouchStart);
      svg.removeEventListener('touchmove', onTouchMove);
      svg.removeEventListener('touchend', onTouchEnd);
      svg.removeEventListener('keydown', onKey);
    },
  };
}

/** Tam ekran yardımcıları; tarayıcı desteklemezse sessizce yok sayılır. */
export function fullscreen(el) {
  const req = el.requestFullscreen || el.webkitRequestFullscreen;
  if (req) { try { req.call(el); return true; } catch (e) { /* yoksay */ } }
  return false;
}

export function exitFullscreen() {
  const ex = document.exitFullscreen || document.webkitExitFullscreen;
  if (ex) { try { ex.call(document); } catch (e) { /* yoksay */ } }
}

export function isFullscreen(el) {
  const fe = document.fullscreenElement || document.webkitFullscreenElement;
  return !!fe && (!el || fe === el || fe.contains(el));
}

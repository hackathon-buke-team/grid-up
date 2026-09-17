// PANO GÖZ · S1 Filo.
//
// Sol: filonun gerçek coğrafya üzerinde görünümü. Harita altlığı (tile sunucusu)
// YOKTUR ve olmayacaktır - kurulum hava boşluklu. Ama il sınırları 110 KB'lık
// yerel bir dosyada duruyor (data/turkiye.js), bu yüzden operatör Kuşadası ile
// Söke'nin arasındaki mesafeyi tahmin etmek zorunda kalmaz. Ayrıntı map.js'te.
//
// Sağ sütunun ÜÇ KİPİ vardır ve her biri sütunun TAMAMINI kaplar:
//   liste  · seçim yokken sıralanabilir pano tablosu
//   künye  · tek pano seçiliyken o panonun kartı ve gidiş düğmeleri
//   çoklu  · Ctrl ile birden çok pano seçiliyken karşılaştırma listesi
// "← Liste" her kipten listeye döner ve seçimi bırakır; Esc de aynısını yapar.
//
// Seçim ile gidiş ayrıdır: haritada bir noktaya ya da tabloda bir satıra
// tıklamak panoyu SEÇER. Ekran değiştirmek künyedeki düğmelerle olur. 112
// panoluk bir filoda yanlış satıra tıklayıp başka ekrana düşmek, geri
// gelmekten daha pahalıdır.
//
// VARSAYILAN SIRALAMA "Δ7 gün"dür, risk değil. Kontrol odası operatörü şu an
// en kötü olanı ister; varlık mühendisi en hızlı bozulanı ister. İkincisi
// ürünün kendisidir: bugün 78 sağlıkla duran ve haftada 1,2 K kötüleşen bir
// pano, bugün 62'de duran ama sabit olandan daha acildir.

import { h, mount, empty, hint } from './dom.js';
import * as fmt from './fmt.js';
import * as store from './store.js';
import { createMap } from './map.js';
import { fullscreen, exitFullscreen, isFullscreen } from './zoompan.js';

const COLS = [
  { key: 'panel_key', label: 'Pano', type: 'text' },
  { key: 'severity', label: 'Seviye', type: 'sev' },
  { key: 'health_index', label: 'Sağlık', type: 'hi' },
  { key: 'theta_max', label: 'θ maks', type: 'num', dec: 2, unit: 'K' },
  {
    key: 'theta_delta_7d', label: 'Δ7 gün', type: 'delta', dec: 2, unit: 'K',
    tip: 'θ değerinin son 7 gündeki değişimi. Bu tablo VARSAYILAN olarak buna göre sıralanır, '
       + 'riske göre değil: kontrol odası "şu an en kötü"yü ister, varlık mühendisi "en hızlı '
       + 'bozulanı" ister. Ürün olan sütun budur - bugün iyi görünen ama haftada 1 K tırmanan '
       + 'bir bağlantı, sabit duran kötü bir bağlantıdan daha acildir.',
  },
  {
    key: 'eta', label: 'Eşiğe', type: 'eta',
    tip: 'Bu gidişle bir sonraki seviye basamağına kalan gün, %90 nominal güven '
       + 'aralığıyla. Aralık θ eğiminin parametrik olmayan güven aralığından '
       + 'gelir; alt sınır sıfırı içeriyorsa üst gün sınırı ∞ olur. Sıralama '
       + 'ÖNCE hedefin ağırlığına, sonra güne bakar: IZLE’ye 3 gün, KRITIK’e '
       + '18 günün önüne geçmez. Sayı yerine gerekçe yazıyorsa sistem susmayı '
       + 'seçmiştir - yetersiz geçmiş, görünürlük düşük ya da eğim yok.',
  },
  { key: 'sensitivity_pct', label: 'Görünürlük', type: 'sens',
    tip: 'θ ancak yük varsa görülür: θ_min = 3σ / f². Yük faktörü 0,35’in altına düşerse '
       + 'sistem "görünürlük düşük" der ve bunu saklamaz.' },
  { key: 'load_factor', label: 'Yük', type: 'pct100' },
  { key: 'alarm_count', label: 'Alarm', type: 'int' },
  { key: 'devices_online', label: 'Cihaz', type: 'dev' },
  { key: 'data_age_s', label: 'Veri yaşı', type: 'age' },
];

// Veri yaşı eşikleri. "Veri gelmiyor" ayrı bir arıza değil, göremediğimiz
// durumdur; bu yüzden süzgeçte kendi basamağı var.
const YAS = [
  { label: 'hepsi', s: 0 },
  { label: '1 dk+', s: 60 },
  { label: '5 dk+', s: 300 },
  { label: '15 dk+', s: 900 },
];

const IC = {
  full: 'M9 4H4v5M15 4h5v5M15 20h5v-5M9 20H4v-5',
  fullOut: 'M4 9h5V4M20 9h-5V4M20 15h-5v5M4 15h5v5',
  liste: 'M4 6h16M4 12h16M4 18h10',
};

function simge(d) {
  const e = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  e.setAttribute('viewBox', '0 0 24 24');
  e.setAttribute('fill', 'none');
  e.setAttribute('stroke', 'currentColor');
  e.setAttribute('stroke-width', '1.8');
  e.setAttribute('stroke-linecap', 'round');
  const pa = document.createElementNS('http://www.w3.org/2000/svg', 'path');
  pa.setAttribute('d', d);
  e.appendChild(pa);
  return e;
}

export function create(ctx) {
  const el = h('div.view', { tabindex: '-1' });
  let sortKey = 'theta_delta_7d';
  let sortDir = -1;
  let lastPanels = [];

  // Seçim: sıfır, bir ya da çok. `birincil` künyesi açık olandır ve diğer
  // ekranların "son bakılan pano" bilgisini de o sürer.
  const secililer = new Set();
  let birincil = null;
  let sonPanelKey = null;

  let tabloSig = '';
  let detaySig = '';
  let tblBody = null;
  const satirlar = new Map();
  const detayRef = { v: [] };

  let fsBtn = null;
  let listeBtn = null;
  let sigdirBtn = null;
  let suzgecRozet = null;

  const f = { sev: new Set(), yukMin: 0, yukMax: 100, yas: 0, kor: false };

  const readouts = h('div.readouts');
  const headChips = h('div.row.wrap');
  const filtreBar = h('div.filter-bar');
  const mapSlot = h('div.surface.map-panel');
  const detayCard = h('div.surface.fr-detay.hidden');
  const tblCard = h('div.surface.fr-tablo');
  const sagSutun = h('div.col.fleet-right', detayCard, tblCard);
  const head = h('div.view-head', h('h1', { text: 'Filo' }), readouts,
    h('span.sp.grow'), headChips);

  mount(el, head, filtreBar, h('div.fleet-grid', mapSlot, sagSutun));

  // ================================================================ süzgeç ==

  function gecer(p) {
    if (f.sev.size && !f.sev.has(p.severity || 'BILGI')) return false;
    const yuk = 100 * Number(p.load_factor || 0);
    if (yuk < f.yukMin || yuk > f.yukMax) return false;
    if (f.yas && Number(p.data_age_s || 0) < f.yas) return false;
    if (f.kor && !(p.status_flags || []).some((x) => fmt.BLIND_FLAGS.has(x))) return false;
    return true;
  }

  const varsayilan = () => f.sev.size === 0 && f.yukMin === 0 && f.yukMax === 100
    && f.yas === 0 && !f.kor;

  const sevSayisi = (panels, k) =>
    panels.reduce((n, p) => n + ((p.severity || 'BILGI') === k ? 1 : 0), 0);

  const gorunurKume = () => new Set(lastPanels.filter(gecer).map((p) => p.panel_key));

  // Süzgeç çubuğu BİR KEZ kurulur, sonra yalnız sayılar ve basılı durumlar
  // tazelenir. Her çerçevede yeniden kurulsaydı kullanıcı yük aralığına sayı
  // yazarken kutu elinin altından kaybolurdu.
  const ref = { sev: new Map(), yas: new Map(), sayac: null, temizle: null,
                kor: null, min: null, maks: null };

  function sayiKutu(alan, al, yaz) {
    const inp = h('input.f-num', {
      type: 'number', min: '0', max: '100', step: '5',
      value: String(al()),
      'aria-label': alan,
      oninput: (ev) => {
        const v = Number(ev.target.value);
        if (!Number.isFinite(v)) return;
        yaz(Math.max(0, Math.min(100, v)));
        tazeleFiltre();
        uygulaSuzgec();
      },
      onblur: () => { inp.value = String(al()); },
    });
    return inp;
  }

  function tazeleFiltre() {
    const panels = lastPanels;
    for (const [k, b] of ref.sev) {
      const on = f.sev.has(k);
      b.classList.toggle('on', on);
      b.setAttribute('aria-pressed', String(on));
      const n = sevSayisi(panels, k);
      b.querySelector('.f-n').textContent = String(n);
      b.title = `${fmt.sevMeta(k).label} · ${n} pano`;
    }
    for (const [s, b] of ref.yas) b.setAttribute('aria-pressed', String(f.yas === s));
    if (ref.kor) {
      ref.kor.classList.toggle('on', f.kor);
      ref.kor.setAttribute('aria-pressed', String(f.kor));
    }
    const kalan = panels.filter(gecer).length;
    if (ref.sayac) {
      ref.sayac.querySelector('b').textContent = fmt.int(kalan);
      ref.sayac.querySelector('span').textContent = ` / ${fmt.int(panels.length)} pano`;
    }
    const acik = !varsayilan();
    if (ref.temizle) ref.temizle.classList.toggle('hidden', !acik);
    if (ref.min && document.activeElement !== ref.min) ref.min.value = String(f.yukMin);
    if (ref.maks && document.activeElement !== ref.maks) ref.maks.value = String(f.yukMax);
    if (suzgecRozet) {
      suzgecRozet.classList.toggle('hidden', !acik);
      if (acik) suzgecRozet.textContent = `süzgeç etkin · ${fmt.int(kalan)} pano`;
    }
    if (sigdirBtn) {
      sigdirBtn.textContent = acik ? 'Süzgece sığdır' : 'Filo bölgesi';
      sigdirBtn.title = acik
        ? 'Süzgeçten geçen panoların tamamını çerçeveye al'
        : 'Panoların bulunduğu alana dön';
    }
  }

  function cizFiltre() {
    ref.sev.clear(); ref.yas.clear();
    ref.min = sayiKutu('en düşük yük yüzdesi', () => f.yukMin,
      (v) => { f.yukMin = Math.min(v, f.yukMax); });
    ref.maks = sayiKutu('en yüksek yük yüzdesi', () => f.yukMax,
      (v) => { f.yukMax = Math.max(v, f.yukMin); });
    ref.sayac = h('span.f-count', h('b', { text: '0' }), h('span', { text: '' }));
    ref.temizle = h('button.btn.sm', {
      type: 'button',
      text: 'Süzgeci temizle',
      onclick: () => {
        f.sev.clear(); f.yukMin = 0; f.yukMax = 100; f.yas = 0; f.kor = false;
        tazeleFiltre(); uygulaSuzgec();
      },
    });
    ref.kor = h('button.f-chip', {
      type: 'button',
      title: 'Yalnızca görüşümüzün kısıtlı olduğu panolar: düşük yük, bayat veri, '
           + 'montaj kaybı, nişan kayması, enerjisiz pano.',
      onclick: () => { f.kor = !f.kor; tazeleFiltre(); uygulaSuzgec(); },
    }, h('span', { text: 'Görüşü kısıtlı' }));

    mount(filtreBar,
      h('span.f-lbl', { text: 'Seviye' }),
      h('div.f-sev', ...fmt.SEVERITY_ORDER.map((k) => {
        // Seviye rengi yalnız şekilde; düğme basılı/basılı değil ayrımını
        // taşır. Rengi zemine yayarsak beş renkli kutu sırası olur ve
        // hangisinin seçili olduğu kaybolur.
        const b = h('button.f-sev-b', {
          type: 'button',
          onclick: () => {
            if (f.sev.has(k)) f.sev.delete(k); else f.sev.add(k);
            tazeleFiltre(); uygulaSuzgec();
          },
        }, h('span.sw', { style: { color: fmt.sevColor(k) } }, fmt.sevShape(k, 11)),
           h('span', { text: fmt.sevMeta(k).label }),
           h('span.f-n', { text: '0' }));
        ref.sev.set(k, b);
        return b;
      })),

      h('span.f-sep'),
      h('span.f-lbl', { text: 'Yük' }),
      ref.min, h('span.f-dash', { text: '–' }), ref.maks, h('span.f-unit', { text: '%' }),

      h('span.f-sep'),
      h('span.f-lbl', hint('Veri yaşı', 'Son ölçümün üstünden geçen süre. "Veri gelmiyor" bir '
        + 'pano arızası değildir; ağ geçidi, hücresel kapsama veya pil de olabilir. Bu yüzden '
        + 'ayrı bir süzgeçtir ve seviyeye karıştırılmaz.')),
      h('span.seg', ...YAS.map((y) => {
        const b = h('button', {
          type: 'button', text: y.label,
          onclick: () => { f.yas = y.s; tazeleFiltre(); uygulaSuzgec(); },
        });
        ref.yas.set(y.s, b);
        return b;
      })),

      h('span.f-sep'),
      ref.kor,
      h('span.sp.grow'),
      ref.sayac,
      ref.temizle);

    tazeleFiltre();
  }

  function uygulaSuzgec() {
    if (map) map.setPanels(lastPanels, secililer, gorunurKume());
    tabloSig = '';
    cizSag();
  }

  // ================================================================ harita ==

  let map = null;
  let mapReady = false;

  function kurHarita() {
    if (map) return map;
    map = createMap({
      onSelect: (key, ev) => sec(key, { coklu: cokluTus(ev), yakinlas: true }),
    });

    fsBtn = h('button.tool.ic', {
      type: 'button',
      title: 'Tam ekran (Esc ile çık)',
      onclick: () => { if (isFullscreen(el)) exitFullscreen(); else fullscreen(el); },
    }, simge(IC.full));

    listeBtn = h('button.tool.ic.fs-only', {
      type: 'button',
      title: 'Sağ paneli gizle',
      'aria-pressed': 'true',
      onclick: () => {
        const kapali = el.classList.toggle('liste-kapali');
        listeBtn.setAttribute('aria-pressed', String(!kapali));
        listeBtn.title = kapali ? 'Sağ paneli göster' : 'Sağ paneli gizle';
        if (map) requestAnimationFrame(() => map.refit());
      },
    }, simge(IC.liste));

    sigdirBtn = h('button.tool', {
      type: 'button', text: 'Filo bölgesi', title: 'Panoların bulunduğu alana dön',
      onclick: () => map.fitFleet(),
    });
    suzgecRozet = h('span.tag.blind.hidden', { text: '' });

    mount(mapSlot,
      h('header',
        h('h2', { text: 'Coğrafi görünüm' }),
        suzgecRozet,
        h('span.sp.grow'),
        h('div.tool-row',
          sigdirBtn,
          h('button.tool', { type: 'button', text: 'Türkiye', title: 'Ülke geneline uzaklaş',
            onclick: () => map.fitCountry() }),
          h('button.tool.ic', { type: 'button', text: '−', title: 'Uzaklaş',
            onclick: () => map.zoomOut() }),
          h('button.tool.ic', { type: 'button', text: '+', title: 'Yaklaş',
            onclick: () => map.zoomIn() }),
          listeBtn,
          fsBtn)),
      map.el,
      h('div.strip',
        ...fmt.SEVERITY_ORDER.map((k) => h('span.li',
          h('span.sw', { style: { color: fmt.sevColor(k) } }, fmt.sevShape(k, 12)),
          h('span', { text: fmt.sevMeta(k).label }))),
        h('span.sp.grow'),
        h('span.li.muted', { text: 'tıkla künyeyi aç · Ctrl+tıkla çoklu seç · sürükle kaydır' })));
    mapReady = true;
    return map;
  }

  function fsSenkron() {
    const acik = isFullscreen(el);
    el.classList.toggle('tam-ekran', acik);
    if (fsBtn) {
      mount(fsBtn, simge(acik ? IC.fullOut : IC.full));
      fsBtn.title = acik ? 'Tam ekrandan çık (Esc)' : 'Tam ekran';
    }
    // Öğe boyutu pencere olayı olmadan değişti; çerçeveyi yeni orana uydur.
    if (map) requestAnimationFrame(() => map.refit());
  }
  document.addEventListener('fullscreenchange', fsSenkron);

  // ================================================================= seçim ==

  const cokluTus = (ev) => !!(ev && (ev.ctrlKey || ev.metaKey));

  /** @param {object} o  { coklu: Ctrl basılı mı, yakinlas: haritayı götür mü } */
  function sec(key, o = {}) {
    if (o.coklu) {
      if (secililer.has(key) && secililer.size > 1) {
        secililer.delete(key);
        if (birincil === key) birincil = [...secililer][0] || null;
      } else {
        secililer.add(key);
        birincil = key;
      }
    } else {
      secililer.clear();
      secililer.add(key);
      birincil = key;
    }
    if (birincil) { sonPanelKey = birincil; store.set({ panelKey: birincil }); }
    if (map) {
      map.setPanels(lastPanels, secililer, gorunurKume());
      // Çoklu seçimde haritayı oynatmıyoruz: kullanıcı işaretlerken çerçeve
      // altından kayarsa bir sonraki noktayı ıskalar.
      if (!o.coklu) map.gotoPanel(key, !!o.yakinlas);
    }
    detaySig = ''; tabloSig = '';
    cizSag();
  }

  /** Listeye dön: seçim bırakılır, haritanın çerçevesi olduğu yerde kalır. */
  function listeyeDon() {
    secililer.clear();
    birincil = null;
    detayRef.v = [];
    if (map) map.setPanels(lastPanels, secililer, gorunurKume());
    detaySig = ''; tabloSig = '';
    cizSag();
  }

  el.addEventListener('keydown', (ev) => {
    if (ev.key !== 'Escape' || !secililer.size || isFullscreen(el)) return;
    listeyeDon();
    ev.stopPropagation();
  });

  // ================================================================== künye ==

  function okuma(k, v, u, not) {
    const deger = h('span.pk-v', { text: v });
    const altNot = h('div.stat-n', { text: not || '' });
    detayRef.v.push({ deger, altNot });
    return h('div.stat',
      h('div.stat-k', { text: k }),
      h('div.stat-v', deger, u ? h('span.stat-u', { text: ' ' + u }) : null),
      altNot);
  }

  const geriDugmesi = () => h('button.btn.sm.geri', {
    type: 'button', text: '← Liste', title: 'Seçimi bırak ve pano listesine dön (Esc)',
    onclick: listeyeDon,
  });

  function cizTek(p) {
    const bayrak = (p.status_flags || []).filter((x) => fmt.BLIND_FLAGS.has(x));

    // İSKELET yalnız pano, seviye ya da görüş kısıtları değişince kurulur.
    // Sayılar her çerçevede tazelenir ama düğümler yerinde kalır: aksi hâlde
    // "Dijital ikiz" düğmesine uzanan el, düğme altından kaybolduğu için ıskalar.
    const iskelet = ['tek', p.panel_key, p.severity, bayrak.join(',')].join('|');
    const degerler = [
      [fmt.num(p.theta_max, 2), p.theta_max_joint || '—'],
      [fmt.signed(p.theta_delta_7d, 2), 'θ değişimi'],
      [fmt.num(p.health_index, 0), 'endeks'],
      [fmt.num(100 * Number(p.load_factor || 0), 0), 'anma 2312 A'],
      [fmt.num(p.sensitivity_pct, 0), '3σ/f² ölçütü'],
      [fmt.dur(p.data_age_s),
       `${fmt.int(p.devices_online)}/9 cihaz · ${fmt.int(p.alarm_count)} alarm`],
    ];

    if (iskelet === detaySig && detayRef.v.length === degerler.length) {
      degerler.forEach(([d, n], i) => {
        if (detayRef.v[i].deger.textContent !== d) detayRef.v[i].deger.textContent = d;
        if (detayRef.v[i].altNot.textContent !== n) detayRef.v[i].altNot.textContent = n;
      });
      return;
    }
    detaySig = iskelet;
    detayRef.v = [];

    const git = (view, etiket) => h('button.btn', {
      type: 'button', text: etiket, onclick: () => ctx.navigate(view, p.panel_key),
    });

    mount(detayCard,
      h('header',
        geriDugmesi(),
        h('h2', { text: p.panel_key }),
        fmt.sevBadge(p.severity),
        h('span.sp.grow')),
      h('div.pano-kart-sub', { text: `${p.name || ''} · ${p.dso || ''} · ${p.site || ''}` }),
      h('div.grid-2.pk-grid',
        okuma('θ maks', degerler[0][0], 'K', degerler[0][1]),
        okuma('Δ7 gün', degerler[1][0], 'K', degerler[1][1]),
        okuma('Sağlık', degerler[2][0], '', degerler[2][1]),
        okuma('Yük', degerler[3][0], '%', degerler[3][1]),
        okuma('Görünürlük', degerler[4][0], '%', degerler[4][1]),
        okuma('Veri yaşı', degerler[5][0], '', degerler[5][1])),
      bayrak.length
        ? h('div.pad.col',
            h('div.tiny.muted', { text: 'Görüş kısıtları (pano arızası değil):' }),
            h('div.flags', ...bayrak.map((x) => fmt.flagTag(x))))
        : null,
      h('div.pad.col',
        h('div.tiny.muted', { text: 'Bu pano için:' }),
        h('div.row.wrap',
          git('pano', 'Dijital ikiz →'),
          git('kanit', 'Kanıt →'),
          git('prpd', 'PRPD →'),
          git('scada', 'SCADA →'))),
      h('div.strip',
        h('span.li.muted', { text: 'Ctrl+tıkla başka pano ekle · Esc listeye döner' })));
  }

  function cokluHucreler(p) {
    const v = Number(p.theta_delta_7d || 0);
    const cls = v > 0.5 ? 'delta-up' : (v < -0.5 ? 'delta-down' : 'delta-flat');
    return [
      h('td', h('div', { text: p.panel_key }),
        h('div.tiny.muted', { text: `${p.dso || ''} · ${p.site || ''}` })),
      h('td', fmt.sevBadge(p.severity)),
      h('td.n', { text: fmt.num(p.theta_max, 2) + ' K' }),
      h('td.n', h('span.' + cls, { text: fmt.signed(v, 2) + ' K' })),
      h('td.c-cikar', h('button.tool.ic', {
        type: 'button', text: '×', title: 'Seçimden çıkar',
        onclick: (ev) => {
          ev.stopPropagation();
          secililer.delete(p.panel_key);
          if (birincil === p.panel_key) birincil = [...secililer][0] || null;
          if (!secililer.size) { listeyeDon(); return; }
          if (map) map.setPanels(lastPanels, secililer, gorunurKume());
          detaySig = ''; tabloSig = '';
          cizSag();
        },
      })),
    ];
  }

  function cizCoklu(secList) {
    const sirali = secList.slice()
      .sort((a, b) => (Number(b.theta_delta_7d) || 0) - (Number(a.theta_delta_7d) || 0));
    const iskelet = ['coklu', sirali.map((p) => p.panel_key + p.severity).join(','),
      birincil].join('|');

    if (iskelet === detaySig) {
      for (const p of sirali) {
        const kayit = satirlar.get('c:' + p.panel_key);
        if (!kayit) continue;
        const s = satirImza(p);
        if (s === kayit.sig) continue;
        kayit.sig = s;
        mount(kayit.tr, ...cokluHucreler(p));
      }
      return;
    }
    detaySig = iskelet;
    detayRef.v = [];

    const tbody = h('tbody', ...sirali.map((p) => {
      const tr = h('tr.click' + (p.panel_key === birincil ? '.sel' : ''), ...cokluHucreler(p));
      tr.addEventListener('click', (ev) => {
        if (ev.target.closest('.c-cikar')) return;
        sec(p.panel_key, { coklu: cokluTus(ev), yakinlas: false });
      });
      satirlar.set('c:' + p.panel_key, { tr, sig: satirImza(p) });
      return tr;
    }));

    mount(detayCard,
      h('header',
        geriDugmesi(),
        h('h2', { text: `${fmt.int(sirali.length)} pano seçili` }),
        h('span.sp.grow'),
        h('button.btn.sm', { type: 'button', text: 'Seçimi temizle', onclick: listeyeDon })),
      h('div.pano-kart-sub', {
        text: 'Δ7 güne göre sıralı · satıra tıkla künyeyi aç · × ile seçimden çıkar',
      }),
      h('div.fleet-table-wrap', h('table.tbl',
        h('thead', h('tr',
          h('th.nosort', { text: 'Pano' }),
          h('th.nosort', { text: 'Seviye' }),
          h('th.nosort', { text: 'θ maks' }),
          h('th.nosort', { text: 'Δ7 gün' }),
          h('th.nosort', { text: '' }))),
        tbody)),
      h('div.strip',
        h('span.li.muted', { text: 'haritada Ctrl+tıkla ekle veya çıkar' })));
  }

  function cizDetay() {
    const secList = lastPanels.filter((p) => secililer.has(p.panel_key));
    if (!secList.length) return;
    if (secList.length > 1) cizCoklu(secList);
    else cizTek(secList[0]);
  }

  // ================================================================= okuma ==

  function readout(value, key, note) {
    return h('div.read',
      h('div.read-v', { text: value }),
      h('div.read-k', { text: key }),
      note ? h('div.read-n', { text: note }) : null);
  }

  function cizOkumalar(fleet) {
    const panels = (fleet && fleet.panels) || [];
    const worst = panels.reduce((a, p) => Math.max(a, fmt.sevRank(p.severity)), 0);
    const alarms = panels.reduce((a, p) => a + (p.alarm_count || 0), 0);
    const blind = panels.filter((p) => (p.status_flags || []).some((x) => fmt.BLIND_FLAGS.has(x))).length;

    mount(readouts,
      readout(fmt.int(panels.length), 'pano', 'izlenen dağıtım panosu'),
      readout(fmt.int(alarms), 'aktif alarm', 'ekip kuyruğu ' + fmt.int(fleet && fleet.dispatch_queue)),
      readout(fmt.int(fleet && fleet.suppressed_24h), 'bastırılan · 24 sa', 'gerekçeleriyle kayıtlı'),
      readout(fmt.int(blind), 'görüşü kısıtlı', 'arıza değil, göremediğimiz durum'));

    mount(headChips,
      h('span.chip', h('span', { text: 'En yüksek seviye' }), fmt.sevBadge(fmt.SEVERITY_ORDER[worst])),
      h('span.chip', h('span', { text: 'Dedektör gecikmesi' }),
        h('b', { text: fmt.dur(fleet && fleet.detector_lag_s) })));
  }

  // ================================================================== tablo ==

  function hucre(col, p) {
    switch (col.type) {
      case 'sev': return h('td', fmt.sevBadge(p.severity));
      case 'hi': {
        const hi = Number(p.health_index || 0);
        return h('td.n',
          h('span.hi-bar', h('i', { class: fmt.hiClass(hi), style: { width: Math.max(2, hi) + '%' } })),
          h('span', { text: fmt.num(hi, 0) }));
      }
      case 'delta': {
        const v = Number(p.theta_delta_7d || 0);
        const cls = v > 0.5 ? 'delta-up' : (v < -0.5 ? 'delta-down' : 'delta-flat');
        return h('td.n', h('span.' + cls, { text: fmt.signed(v, 2) + ' K' }));
      }
      case 'num': return h('td.n', { text: fmt.num(p[col.key], col.dec) + ' ' + (col.unit || '') });
      case 'int': return h('td.n', { text: fmt.int(p[col.key]) });
      case 'pct100': return h('td.n', { text: fmt.pct(100 * Number(p.load_factor || 0), 0) });
      case 'eta': {
        const e = p.eta || {};
        if (!fmt.etaHasDays(e)) {
          const why = fmt.etaReason(e);
          return h('td.n', h('span.muted', { text: '—', title: why || 'veri yok' }),
            why ? h('span.tiny.muted', { text: ' ' + why }) : null);
        }
        // Agir hedefler goze carpar; hafif olanlar sakin durur.
        const w = fmt.ETA_TARGET_W[e.target] || 0;
        return h('td.n', h('span.' + (w >= 3 ? 'delta-up' : 'delta-flat'),
          { text: fmt.eta(e) }));
      }
      case 'sens': {
        const v = Number(p.sensitivity_pct || 0);
        const low = (p.status_flags || []).includes('SENSITIVITY_LOW') || v < 50;
        return h('td.n', h('span', { text: fmt.pct(v, 0), style: { color: low ? 'var(--sev-uyari)' : '' } }));
      }
      case 'dev': {
        const on = Number(p.devices_online || 0);
        return h('td.n', h('span', {
          text: `${fmt.int(on)}/9`,
          style: { color: on < 9 ? 'var(--sev-uyari)' : '' },
        }));
      }
      case 'age': {
        const a = Number(p.data_age_s || 0);
        return h('td.n', h('span', { text: fmt.dur(a), style: { color: a > 90 ? 'var(--sev-kritik)' : '' } }));
      }
      default:
        return h('td',
          h('div', { text: p.panel_key }),
          h('div.tiny.muted', { text: `${p.dso || ''} · ${p.site || ''}` }));
    }
  }

  /** Hücreyi kendi sütun sınıfıyla işaretler: dar panelde hangi sütunun
   *  düşeceğine CSS karar verir, sıraya değil sütun adına bakarak. */
  function cellFor(col, p) {
    const td = hucre(col, p);
    td.classList.add('c-' + col.key);
    return td;
  }

  /** Bir satırın GÖRÜNEN içeriği. Değişmediyse o satıra hiç dokunmayız. */
  function satirImza(p) {
    return [p.severity, fmt.num(p.health_index, 0), fmt.num(p.theta_max, 2),
      fmt.signed(p.theta_delta_7d, 2), fmt.eta(p.eta), fmt.etaReason(p.eta),
      fmt.num(p.sensitivity_pct, 0),
      fmt.num(100 * Number(p.load_factor || 0), 0), p.alarm_count, p.devices_online,
      fmt.dur(p.data_age_s)].join('|');
  }

  function cizTablo() {
    const rows = lastPanels.filter(gecer).sort((a, b) => {
      const va = a[sortKey], vb = b[sortKey];
      if (sortKey === 'severity') return (fmt.sevRank(a.severity) - fmt.sevRank(b.severity)) * sortDir;
      if (sortKey === 'eta') {
        const ea = a.eta || {}, eb = b.eta || {};
        const na = !fmt.etaHasDays(ea), nb = !fmt.etaHasDays(eb);
        // Sayi vermeyen satirlar siralama yonu ne olursa olsun SONA gider:
        // bos bir hucre "en yakin" listesinin basinda durmamalidir.
        if (na !== nb) return na ? 1 : -1;
        if (na && nb) return 0;
        // ONCE hedefin agirligi, SONRA gun. Sadece gune bakmak IZLE'ye 3 gun
        // kalan bir baglantiyi KRITIK'e 18 gun kalanin onune gecirirdi.
        const wa = fmt.ETA_TARGET_W[ea.target] || 0;
        const wb = fmt.ETA_TARGET_W[eb.target] || 0;
        if (wa !== wb) return (wb - wa) * sortDir;
        return ((Number(ea.days) || 0) - (Number(eb.days) || 0)) * sortDir;
      }
      if (typeof va === 'string' || typeof vb === 'string') {
        return String(va || '').localeCompare(String(vb || ''), 'tr') * sortDir;
      }
      return ((Number(va) || 0) - (Number(vb) || 0)) * sortDir;
    });

    // Veri yaşı her saniye değişir. Tabloyu bu yüzden baştan kurmak, listeyi
    // kaydıran operatörü saniyede bir başa atardı. Satır DİZİLİMİ aynıysa
    // tablo yerinde kalır ve yalnız değişen satırın hücreleri yenilenir.
    const dizilim = [sortKey, sortDir, rows.map((p) => p.panel_key).join(',')].join('#');
    if (dizilim === tabloSig && tblBody) {
      for (const p of rows) {
        const kayit = satirlar.get(p.panel_key);
        if (!kayit) continue;
        const s = satirImza(p);
        if (s === kayit.sig) continue;
        kayit.sig = s;
        mount(kayit.tr, ...COLS.map((c) => cellFor(c, p)));
      }
      return;
    }
    tabloSig = dizilim;
    satirlar.clear();

    const thead = h('thead', h('tr', ...COLS.map((c) => {
      const arrow = sortKey === c.key ? h('span.arrow', { text: sortDir < 0 ? '▼' : '▲' }) : null;
      const label = c.tip ? hint(c.label, c.tip) : h('span', { text: c.label });
      const th = h('th.c-' + c.key + (sortKey === c.key ? '.sorted' : ''), label, arrow);
      th.addEventListener('click', () => {
        if (sortKey === c.key) sortDir = -sortDir;
        else { sortKey = c.key; sortDir = c.key === 'panel_key' ? 1 : -1; }
        tabloSig = '';
        cizTablo();
      });
      return th;
    })));

    const tbody = h('tbody', ...rows.map((p) => {
      const tr = h('tr.click', ...COLS.map((c) => cellFor(c, p)));
      tr.addEventListener('click', (ev) => sec(p.panel_key, { coklu: cokluTus(ev), yakinlas: false }));
      tr.addEventListener('dblclick', () => ctx.navigate('pano', p.panel_key));
      satirlar.set(p.panel_key, { tr, sig: satirImza(p) });
      return tr;
    }));
    tblBody = tbody;

    mount(tblCard,
      h('header',
        h('h2', { text: 'Panolar' }),
        h('span.sp.grow'),
        h('span.tiny.muted', { text: `${fmt.int(rows.length)} kayıt` }),
        h('span.tiny.muted', { text: 'sıralama' }),
        h('span.tiny', { text: COLS.find((c) => c.key === sortKey).label })),
      rows.length
        ? h('div.fleet-table-wrap', h('table.tbl', thead, tbody))
        : h('div.pad', empty('Süzgeçle eşleşen pano yok',
            'Seviye, yük aralığı veya veri yaşı ölçütlerini gevşetin')),
      h('div.strip',
        h('span.li.muted', { text: 'tıkla künyeyi aç · Ctrl+tıkla çoklu seç · çift tıkla ikize git' })));
  }

  /** Sağ sütun tek seferde TEK kipte ve sütunun tamamını kaplar. */
  function cizSag() {
    const secVar = secililer.size > 0;
    detayCard.classList.toggle('hidden', !secVar);
    tblCard.classList.toggle('hidden', secVar);
    if (secVar) cizDetay(); else cizTablo();
  }

  // ================================================================= update ==

  function update(state) {
    const panels = (state.fleet && state.fleet.panels) || [];
    lastPanels = panels;

    // Üst şeritteki pano seçicisi de bu ekranı sürer.
    let odaklan = false;
    if (state.panelKey !== sonPanelKey) {
      sonPanelKey = state.panelKey;
      if (state.panelKey) {
        secililer.clear();
        secililer.add(state.panelKey);
        birincil = state.panelKey;
        detaySig = ''; tabloSig = '';
        odaklan = true;
      }
    }

    cizOkumalar(state.fleet);
    if (!filtreBar.childNodes.length) cizFiltre(); else tazeleFiltre();

    if (panels.length) {
      kurHarita().setPanels(panels, secililer, gorunurKume());
      // Kaydırma harita filo bölgesine oturduktan SONRA yapılır: ters sırada
      // "mevcut ölçeği koru" kuralı henüz kurulmamış bir ölçeği korur.
      if (odaklan && birincil) map.gotoPanel(birincil, false);
    } else if (!mapReady) {
      mount(mapSlot,
        h('header', h('h2', { text: 'Coğrafi görünüm' })),
        h('div.pad', empty('Filo verisi yok', 'API bağlantısı kurulunca panolar burada belirir')));
    }
    cizSag();
  }

  return {
    el,
    update,
    destroy() {
      document.removeEventListener('fullscreenchange', fsSenkron);
      if (isFullscreen(el)) exitFullscreen();
      if (map) map.destroy();
      map = null;
    },
  };
}

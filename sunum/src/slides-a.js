/* ======================================================================
   SLAYTLAR 1–7 · açılış, problem, fikir, donanım, mimari
   ----------------------------------------------------------------------
   Her slayt: title, section, time, html(), notes (konuşma metni),
   use (sunucuya ipucu), scene(el) (isteğe bağlı canlı animasyon).
   ====================================================================== */

/* ---- TAKIM · photo: sunum/assets/foto_*.jpg dosyasının adı (A.foto_melih) ya da bir URL ---- */
const TEAM = {
  name: 'Büke',
  no: '',
  members: [
    { name: 'Melih Ekizce', uni: 'İzmir Yüksek Teknoloji Enstitüsü', dept: 'Bilgisayar Mühendisliği', degree: 'Yüksek Lisans · devam ediyor', on: true, photo: 'foto_melih' },
    { name: 'Mustafa Eren Işıktaşlı', uni: 'Yıldız Teknik Üniversitesi', dept: 'Bilgisayar Mühendisliği', degree: 'Yüksek Lisans · devam ediyor', on: true, photo: 'foto_eren' },
    { name: 'Serhat Özdemir', uni: 'Dokuz Eylül Üniversitesi', dept: 'Bilgisayar Mühendisliği', degree: 'Lisans', photo: 'foto_serhat' },
    { name: 'Mert Arı', uni: 'Bursa Uludağ Üniversitesi', dept: 'Bilgisayar Mühendisliği', degree: 'Lisans', photo: 'foto_mert' },
  ],
};
const photoSrc = p => (p ? (A[p] || p) : '');

const SL = [];
const add = o => SL.push(o);
const HD = (k, t, lead) => `<header class="hd"><p class="kicker" data-a="fade">${k}</p><h2 data-a="up" style="--d:.06s">${t}</h2>${lead ? `<p class="lead" data-a="up" style="--d:.16s">${lead}</p>` : ''}</header>`;

/* ===================================================================== */
/* 1 · KAPAK                                                              */
/* ===================================================================== */
function coverSVG(p = 'cv') {
  /* Filtre yok: parıltılar radyal, kablo ısısı doğrusal gradyan. İkisi de vektördür; her
     büyütmede ve PDF'te keskin kalır (feGaussianBlur tarayıcıda ve baskıda piksele döner). */
  const cx = k => 52 + k * 41, LY = 232, OFF = [-11, -4, 4, 11];
  const CAB = ['var(--l1)', 'var(--l2)', 'var(--l3)', 'var(--nn)'];
  const HI = ['#d6dbe1', '#6b7380', '#c58a5f', '#b5dcff'];
  const rnd = H.rng(7);
  let defs = '', base = '', therm = '';
  for (let k = 0; k < 12; k++) {
    const x = cx(k), spare = k >= 10;
    base += `<text x="${x}" y="60" text-anchor="middle" class="mono" font-size="10" fill="var(--dim)">${spare ? 'Y' + (k - 9) : 'Ç' + (k + 1)}</text>`;
    if (spare) { base += `<rect x="${x - 15}" y="70" width="30" height="126" rx="3" fill="url(#${p}h)" stroke="var(--line2)"/>`; continue; }
    /* NH sigortalı yük ayırıcı: kapak, kol, üç sigorta penceresi, etiket */
    base += `<rect x="${x - 15}" y="70" width="30" height="126" rx="3" fill="#0d131b" stroke="#3a4a5a" stroke-width=".9"/>
      <rect x="${x - 11}" y="75" width="22" height="9" rx="2" fill="#1d2733" stroke="#2f3d4b" stroke-width=".6"/>
      <rect x="${x - 6}" y="78" width="12" height="3" rx="1.5" fill="#5d6b7a"/>
      ${[-9, -2, 5].map(o => `<rect x="${x + o}" y="96" width="5" height="76" rx="1.6" fill="#141c26" stroke="#334354" stroke-width=".7"/>
        <rect x="${x + o + 1.2}" y="100" width="2.6" height="12" rx="1" fill="#2a3644"/>
        <rect x="${x + o + 1.2}" y="156" width="2.6" height="12" rx="1" fill="#2a3644"/>`).join('')}
      <rect x="${x - 9}" y="180" width="18" height="8" rx="1.5" fill="#1a232e" stroke="#2c3a48" stroke-width=".6"/>`;
    OFF.forEach((o, j) => {
      const X = x + o;
      base += `<line x1="${X}" y1="${LY + 6}" x2="${X}" y2="470" stroke="${CAB[j]}" stroke-width="3.4"/>
        <line x1="${X - .8}" y1="${LY + 8}" x2="${X - .8}" y2="470" stroke="${HI[j]}" stroke-width=".7" stroke-opacity=".45"/>
        <rect x="${X - 3.2}" y="${LY - 2}" width="6.4" height="11" rx="1.6" fill="#aab4bf" stroke="#0b0f14" stroke-width=".6"/>
        <circle cx="${X}" cy="${LY}" r="3.1" fill="#dfe5eb" stroke="#0b0f14" stroke-width=".7"/>
        <circle cx="${X}" cy="${LY}" r="1.1" fill="#7d8894"/>`;
      const hot = k === 6 && j === 1;
      const t = hot ? 1 : (j === 3 ? .4 : .5) + rnd() * .1 + (k === 5 || k === 6 ? .06 : 0);
      const id = `${p}${k}_${j}`;
      defs += `<radialGradient id="${id}g"><stop offset="0" stop-color="${H.heat(Math.min(1, t + .12))}"/><stop offset=".38" stop-color="${H.heat(t)}" stop-opacity=".8"/><stop offset="1" stop-color="${H.heat(t)}" stop-opacity="0"/></radialGradient>
        <linearGradient id="${id}c" gradientUnits="userSpaceOnUse" x1="0" y1="${LY}" x2="0" y2="470"><stop offset="0" stop-color="${H.heat(t * .92)}"/><stop offset="${hot ? .42 : .2}" stop-color="${H.heat(t * .64)}"/><stop offset="1" stop-color="${H.heat(.3)}"/></linearGradient>`;
      therm += `<line x1="${X}" y1="${LY}" x2="${X}" y2="470" stroke="url(#${id}c)" stroke-width="${hot ? 11 : 8}" stroke-opacity=".28"/>
        <line x1="${X}" y1="${LY}" x2="${X}" y2="470" stroke="url(#${id}c)" stroke-width="${hot ? 4.6 : 3.4}" stroke-linecap="round"/>
        <circle cx="${X}" cy="${LY}" r="${hot ? 36 : 13}" fill="url(#${id}g)"/>
        <circle cx="${X}" cy="${LY}" r="${hot ? 5.5 : 3.2}" fill="${hot ? '#fffbd0' : H.heat(Math.min(1, t + .16))}"/>`;
    });
    const warm = k === 5 || k === 6 ? .04 : 0;
    therm += `<rect x="${x - 15}" y="70" width="30" height="126" rx="3" fill="${H.heat(.22 + warm + rnd() * .05)}" stroke="${H.heat(.3)}" stroke-width=".8"/>
      <rect x="${x - 11}" y="75" width="22" height="9" rx="2" fill="${H.heat(.27 + warm)}"/>
      <rect x="${x - 6}" y="78" width="12" height="3" rx="1.5" fill="${H.heat(.4 + warm)}"/>
      ${[-9, -2, 5].map(o => `<rect x="${x + o}" y="96" width="5" height="76" rx="1.6" fill="${H.heat(.32 + warm + rnd() * .06)}"/>
        <rect x="${x + o + 1.2}" y="104" width="2.6" height="60" rx="1.2" fill="${H.heat(.42 + warm + rnd() * .05)}"/>`).join('')}
      <rect x="${x - 9}" y="180" width="18" height="8" rx="1.5" fill="${H.heat(.28 + warm)}"/>
      ${OFF.map(o => `<rect x="${x + o - 3.2}" y="${LY - 2}" width="6.4" height="11" rx="1.6" fill="none" stroke="${H.heat(.62 + warm)}" stroke-width=".7" stroke-opacity=".8"/>`).join('')}`;
  }
  const HX = cx(6) + OFF[1];
  const tc = [5, 6].map(k => [0, 1, 2].map(j => `<rect x="${cx(k) + OFF[j] - 3.6}" y="268" width="7.2" height="16" rx="2" fill="var(--brand)" stroke="#ffd2a6" stroke-width=".6"/>`).join('')).join('');
  const scale = Array.from({ length: 11 }, (_, i) => `<stop offset="${i / 10}" stop-color="${H.heat(1 - i / 10)}"/>`).join('');
  const bracket = (x, y, r, l) => `M${x - r},${y - r + l}V${y - r}H${x - r + l}M${x + r - l},${y - r}H${x + r}V${y - r + l}M${x + r},${y + r - l}V${y + r}H${x + r - l}M${x - r + l},${y + r}H${x - r}V${y + r - l}`;
  return `<svg viewBox="0 0 560 520" class="cvsvg" aria-label="Alt kablo bölmesi, termal tarama">
  <defs>
    <pattern id="${p}h" width="7" height="7" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="7" stroke="#26313d" stroke-width="2"/></pattern>
    <linearGradient id="${p}trail" x1="1" x2="0"><stop offset="0" stop-color="#ffb066" stop-opacity=".35"/><stop offset="1" stop-color="#ffb066" stop-opacity="0"/></linearGradient>
    <linearGradient id="${p}fov" x1="0" y1="1" x2="0" y2="0"><stop offset="0" stop-color="#f78320" stop-opacity=".22"/><stop offset="1" stop-color="#f78320" stop-opacity="0"/></linearGradient>
    <linearGradient id="${p}sc" x1="0" y1="0" x2="0" y2="1">${scale}</linearGradient>
    <radialGradient id="${p}bg" cx="${HX / 560}" cy="${LY / 520}" r=".9"><stop offset="0" stop-color="#3b0d5e"/><stop offset=".5" stop-color="#1a0838"/><stop offset="1" stop-color="#0a0418"/></radialGradient>
    ${defs}
    <clipPath id="${p}clip"><rect id="${p}cr" x="0" y="0" width="0" height="520"/></clipPath>
  </defs>
  <rect x="14" y="20" width="532" height="486" rx="12" fill="#080b10" stroke="var(--line2)"/>
  <text x="28" y="40" class="mono" font-size="10.5" fill="var(--dim)">alt kablo bölmesi · 48 kablo bağlantısı</text>
  ${base}${tc}
  <polygon points="270,486 44,${LY} 500,${LY}" fill="url(#${p}fov)"/>
  <rect x="252" y="484" width="36" height="14" rx="3" fill="#1c2632" stroke="var(--brand)"/>
  <circle cx="270" cy="491" r="3.4" fill="#0b0f14" stroke="var(--brand2)" stroke-width="1"/>
  <text x="296" y="495" class="mono" font-size="9.5" fill="var(--muted)">termal kamera</text>
  <g id="${p}th" clip-path="url(#${p}clip)">
    <rect x="15" y="21" width="530" height="484" rx="12" fill="url(#${p}bg)"/>
    ${therm}
    <circle cx="${HX}" cy="${LY}" r="12" fill="none" stroke="#fcd34d" stroke-width="2"><animate attributeName="r" values="10;28" dur="1.6s" repeatCount="indefinite"/><animate attributeName="opacity" values="1;0" dur="1.6s" repeatCount="indefinite"/></circle>
    <path d="${bracket(HX, LY, 19, 7)}" fill="none" stroke="#fff" stroke-width="1.6" stroke-opacity=".9"/>
    <path d="M${HX - 26},${LY}h6M${HX + 20},${LY}h6M${HX},${LY - 26}v6M${HX},${LY + 20}v6" stroke="#fff" stroke-width="1.2" stroke-opacity=".75"/>
    <rect x="${HX + 22}" y="${LY - 35}" width="30" height="13" rx="2.5" fill="#fff"/>
    <text x="${HX + 37}" y="${LY - 25.5}" text-anchor="middle" class="mono" font-size="8.5" font-weight="700" fill="#1a0838">MAX</text>
    <rect x="525" y="74" width="8" height="150" rx="2" fill="url(#${p}sc)" stroke="#ffffff33" stroke-width=".6"/>
    <text x="529" y="68" text-anchor="middle" font-size="8.5" fill="#f5e6c8">sıcak</text>
    <text x="529" y="236" text-anchor="middle" font-size="8.5" fill="#c9b8ff">soğuk</text>
    <text x="28" y="40" class="mono" font-size="10.5" fill="#c9b8ff">termal görünüm · faz karşılaştırması</text>
  </g>
  <g id="${p}scan" style="opacity:0"><rect x="-46" y="21" width="46" height="484" fill="url(#${p}trail)"/><line x1="0" y1="21" x2="0" y2="505" stroke="#ffb066" stroke-width="2"/></g>
  <g id="${p}call" style="opacity:0;transition:opacity .5s">
    <path d="M${HX},${LY + 20} L318,318" stroke="var(--kritik)" stroke-width="1.5" fill="none"/>
    <rect x="308" y="300" width="230" height="100" rx="10" fill="rgba(6,8,12,.95)" stroke="var(--kritik)"/>
    <text x="324" y="323" font-size="12" fill="var(--muted)">Ç7 · L2 · çıkış pabucu</text>
    <rect x="462" y="309" width="62" height="21" rx="10.5" fill="rgba(255,107,61,.14)" stroke="var(--kritik)"/>
    <text x="493" y="323.5" text-anchor="middle" class="mono" font-size="11" font-weight="700" fill="var(--kritik)">Kritik</text>
    <text x="324" y="360" font-size="26" font-weight="700" fill="var(--olcum)">Fazla ısınıyor</text>
    <text x="324" y="386" font-size="12" fill="var(--muted)">haftalar önce fark edildi</text>
  </g>
</svg>`;
}
add({
  title: 'Kapak', noCorner: true, noFoot: true, time: '30 sn',
  html: () => `
<div class="cover">
  <div class="cv-l">
    <div class="cv-top" data-a="fade"><img class="gu" src="${A.gridup}" alt="Grid Up"><div><p class="kicker" style="margin:0 0 7px">GRID UP HACKATHON · FİNAL</p><p class="sub">ADM &amp; GDZ Elektrik · Pano/hücre içi anomali erken uyarı sistemi</p></div></div>
    <h1 class="cv-title" data-a="up" style="--d:.12s">PANO GÖZ</h1>
    <p class="lead" data-a="up" style="--d:.26s">1600 kVA AG dağıtım panosunda gevşeyen bağlantıyı, ısınan nötrü, nemi ve ark korumasının sağlığını; arıza olmadan, haftalar önce haber veren uçtan uca izleme sistemi.</p>
    <p class="cv-thesis" data-a="up" style="--d:.4s">Arıza önce ısınır. PANO GÖZ onu ısınırken görür.</p>
    <div class="cv-logos" data-a="fade" style="--d:.6s"><img src="${A.adm}" alt="ADM Elektrik Dağıtım"><i></i><img src="${A.gdz}" alt="GDZ Elektrik Dağıtım"></div>
    <p class="sub cv-team" data-a="fade" style="--d:.7s">Takım ${TEAM.name}${TEAM.no ? ' · Takım No ' + TEAM.no : ''}</p>
  </div>
  <div class="cv-r" data-a="blur" style="--d:.15s">${coverSVG()}</div>
</div>`,
  scene(el, { REDUCED }, p = 'cv') {
    const cr = el.querySelector('#' + p + 'cr'), scan = el.querySelector('#' + p + 'scan'), call = el.querySelector('#' + p + 'call'), th = el.querySelector('#' + p + 'th');
    const XH = 52 + 6 * 41 - 4; // sıcak pabuç: Ç7 · L2
    if (REDUCED) { cr.setAttribute('width', 560); call.style.opacity = 1; return null; }
    let raf, t0 = performance.now();
    const loop = t => {
      const T = ((t - t0) / 1000) % 10;
      const p = H.ease((T - .8) / 3.6), x = p * 560;
      cr.setAttribute('width', x.toFixed(1));
      scan.setAttribute('transform', `translate(${x.toFixed(1)},0)`);
      scan.style.opacity = p > 0 && p < 1 ? 1 : 0;
      call.style.opacity = x > XH + 8 && T < 9.4 ? 1 : 0;
      th.style.opacity = T > 9.4 ? Math.max(0, 1 - (T - 9.4) / .5) : 1;
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return { stop() { cancelAnimationFrame(raf); } };
  },
  notes: `Merhaba, biz Takım ${TEAM.name}. ADM ve GDZ Elektrik'in Grid Up hackathon'unda "Pano/Hücre İçi Anomali Erken Uyarı Sistemi" problemini çalıştık. Ürünümüzün adı PANO GÖZ.

Sağda bir alçak gerilim dağıtım panosunun alt kablo bölmesini görüyorsunuz: kabloların panoya bağlandığı yer. Termal kamera soldan sağa geçtiğinde bağlantıların hepsi birbirine benziyor — biri hariç. Çıkış 7'nin L2 bağlantısı.

Bu bağlantı bugün yanmıyor, arıza da yok. Ama aynı çıkışın diğer iki fazından belirgin biçimde sıcak ve bu gidişle birkaç hafta içinde ciddi bir soruna dönüşecek.

PANO GÖZ'ün işi tam olarak bu. Arıza önce ısınır; biz onu ısınırken görüyoruz — yanmadan, haftalar önce — ve doğru kişiye haber veriyoruz.`,
  use: `<b>Kullan:</b> Açılış — 30 saniyeyi geçmeyin. Tarama bitip etiket çıktığında "biri hariç" cümlesini söyleyin. <b>Kısayollar:</b> N konuşma metni · S konuşmacı ekranı · O slayt haritası · Q jüri soruları · B kararart · F tam ekran · P metni yazdır.`,
});

/* ===================================================================== */
/* 2 · TAKIM                                                              */
/* ===================================================================== */
add({
  title: 'Takım', section: 'Takım', time: '15 sn',
  html: () => `
<p class="kicker" style="text-align:center;margin-bottom:10px" data-a="fade">Takım</p>
<h2 style="text-align:center;font-size:46px;margin:0 auto 4px" data-a="up">${TEAM.name}</h2>
<div class="body">
  <div class="team">${TEAM.members.map((m, i) => `
    <div class="card mem" data-a="up" style="--d:${.15 + i * .1}s">
      <div class="ph">${m.photo ? `<img src="${photoSrc(m.photo)}" alt="${m.name}">` : IC.user}</div>
      <div class="nm">${m.name}</div><div class="un">${m.uni}</div><div class="dp">${m.dept}</div>
      <div class="deg${m.on ? ' on' : ''}"><i></i>${m.degree}</div>
    </div>`).join('')}
  </div>
  <div class="card tight" style="flex:0 0 auto;--d:.6s" data-a="fade"><p class="sub" style="text-align:center">ADM &amp; GDZ Elektrik · Grid Up Hackathon · Pano/Hücre İçi Anomali Erken Uyarı Sistemi${TEAM.no ? ` · <b>Takım No ${TEAM.no}</b>` : ''}</p></div>
</div>`,
  notes: `Takım ${TEAM.name} olarak dört kişiyiz ve dördümüz de Bilgisayar Mühendisliği okuyoruz.

${TEAM.members.map(m => `${m.name} — ${m.uni}, ${m.degree.includes('devam') ? 'yüksek lisans devam ediyor' : 'lisans'}.`).join('\n')}

İşi dört paralel pakete böldük: panoya takılan donanım; sunucu ve entegrasyon; izleme ekranları; bildirim ve doğrulama. Hemen problemin kendisine geçiyorum.`,
  use: `<b>Kullan:</b> 15 saniyeyi geçmeyin; isimleri soldan sağa okuyup geçin. <b>Not:</b> turuncu rozet yüksek lisansın hâlen sürdüğünü gösterir; sorulursa tek cümlede geçin. <b>Değiştirmek için:</b> slides-a.js başındaki <b>TEAM</b> bloğu; fotoğraflar sunum/assets/foto_*.jpg.`,
});

/* ===================================================================== */
/* 3 · PROBLEM                                                            */
/* ===================================================================== */
function problemSVG() {
  const X = t => 40 + t * 1080, Y = t => 330 - (12 + 46 * t + 252 * Math.pow(t, 6));
  const pts = []; for (let t = 0; t <= 1.0001; t += .02) pts.push([X(t), Y(t)]);
  const d = H.smooth(pts);
  const st = [[.08, 'Cıvata gevşer', 'temas direnci artar'], [.37, 'Bağlantı ısınır', 'birkaç kelvin, kimse görmez'], [.65, 'Oksitlenir', 'direnç kendini besler'], [.9, 'Ark, yangın, kesinti', 'artık herkes görür']];
  return `<svg viewBox="0 0 1160 420" class="probsvg">
  <defs><linearGradient id="pbf" x1="0" x2="1"><stop offset="0" stop-color="#4aa3ff" stop-opacity=".16"/><stop offset=".55" stop-color="#f4b13a" stop-opacity=".18"/><stop offset="1" stop-color="#ff2f79" stop-opacity=".38"/></linearGradient>
  <linearGradient id="pbs" x1="0" x2="1"><stop offset="0" stop-color="#4aa3ff"/><stop offset=".55" stop-color="#f4b13a"/><stop offset=".85" stop-color="#ff6b3d"/><stop offset="1" stop-color="#ff2f79"/></linearGradient></defs>
  <line x1="40" y1="330" x2="1124" y2="330" stroke="var(--line2)"/>
  <text x="1124" y="350" text-anchor="end" class="mono" font-size="12" fill="var(--dim)">zaman →</text>
  <text x="40" y="22" class="mono" font-size="12" fill="var(--dim)">bağlantı sıcaklığı</text>
  <path d="${d} L1120,330 L40,330 Z" fill="url(#pbf)" data-a="fade" style="--d:.9s"/>
  <path d="${d}" fill="none" stroke="url(#pbs)" stroke-width="4" stroke-linecap="round" data-a="draw" style="--d:.2s;--dur:2s"/>
  ${st.map(([t, a, b], i) => `<g data-a="up" style="--d:${.6 + i * .35}s"><circle cx="${X(t)}" cy="${Y(t)}" r="6" fill="var(--bg)" stroke="${['#4aa3ff', '#f4b13a', '#ff6b3d', '#ff2f79'][i]}" stroke-width="3"/>
    <text x="${X(t)}" y="372" text-anchor="middle" font-size="16" font-weight="600" fill="var(--ink)">${a}</text>
    <text x="${X(t)}" y="394" text-anchor="middle" font-size="13" fill="var(--muted)">${b}</text></g>`).join('')}
  <g data-step="1"><line x1="${X(.93)}" y1="40" x2="${X(.93)}" y2="330" stroke="var(--kritik)" stroke-width="2" stroke-dasharray="5 5"/>
    <rect x="${X(.93) - 236}" y="40" width="226" height="56" rx="10" fill="rgba(255,107,61,.1)" stroke="var(--kritik)"/>
    <text x="${X(.93) - 222}" y="63" font-size="15" font-weight="700" fill="var(--kritik)">Bugün fark edilen an</text>
    <text x="${X(.93) - 222}" y="84" font-size="13" fill="var(--muted)">ekipman arızası, kesinti, yangın</text></g>
  <g data-step="2"><line x1="${X(.24)}" y1="40" x2="${X(.24)}" y2="330" stroke="var(--brand)" stroke-width="2" stroke-dasharray="5 5"/>
    <rect x="${X(.24) + 10}" y="40" width="248" height="56" rx="10" fill="var(--brand-soft)" stroke="var(--brand)"/>
    <text x="${X(.24) + 24}" y="63" font-size="15" font-weight="700" fill="var(--brand)">PANO GÖZ'ün gördüğü an</text>
    <text x="${X(.24) + 24}" y="84" font-size="13" fill="var(--muted)">diğer fazlardan ayrışmaya başlar</text>
    <line x1="${X(.24) + 6}" y1="130" x2="${X(.93) - 6}" y2="130" stroke="var(--brand2)" stroke-width="2" marker-end="url(#ar)" marker-start="url(#al)"/>
    <defs><marker id="ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="var(--brand2)"/></marker>
    <marker id="al" viewBox="0 0 10 10" refX="1" refY="5" markerWidth="8" markerHeight="8" orient="auto"><path d="M10,0 L0,5 L10,10 z" fill="var(--brand2)"/></marker></defs>
    <rect x="${(X(.24) + X(.93)) / 2 - 80}" y="116" width="160" height="28" rx="14" fill="var(--bg)"/>
    <text x="${(X(.24) + X(.93)) / 2}" y="135" text-anchor="middle" font-size="16" font-weight="700" fill="var(--brand2)">haftalar önce</text></g>
</svg>`;
}
add({
  title: 'Problem: arıza önce ısınır', section: 'Problem', time: '45 sn',
  html: () => `${HD('01 · Problem', 'Arıza önce ısınır, sonra yanar.', 'Gevşek bir cıvata, nemli bir kablo kanalı, yıpranan bir yalıtım: hepsi kritik andan haftalar önce sinyal verir. Bugün çoğu, iş işten geçince fark ediliyor.')}
<div class="body"><div class="grow center">${problemSVG()}</div></div>`,
  notes: `Problemi şartnamenin kendi cümlesiyle başlatalım: OG hücre ve AG panolardaki arızaların önemli bir kısmı kritik andan önce sinyal veriyor — sıcaklık artışı, nem, aşırı akım, kısmi deşarj. Ama bu sinyaller birlikte ve sürekli izlenmiyor.

En sık senaryo şu eğri: bir cıvatalı bağlantı gevşer, temas direnci artar. Bağlantı birkaç kelvin ısınır; kimse görmez. Isındıkça oksitlenir, oksitlendikçe direnci artar — süreç kendini besler. Sonunda ark, yangın, kesinti.

[→] Bugün bu sürecin farkına buradan varılıyor: arıza olduğunda, müşteri karanlıkta kaldığında, bazen pano yandığında.

[→] PANO GÖZ'ün hedefi ise eğrinin başı. Sıcaklık henüz tehlikeli değilken, sadece "diğer fazlardan farklı" olduğu anda. Aradaki fark haftalar — ve o haftalar, gece çıkan bir arıza ekibi ile önceden planlanmış bir bakım ziyareti arasındaki fark.`,
  use: `<b>Kullan:</b> İki adım: önce kırmızı "bugün", sonra turuncu "PANO GÖZ" işareti. Kırmızıyı gösterirken durun, jüri kendi sahasını düşünsün. <b>Kaynak:</b> şartname "Problem" bölümü, ilk iki paragraf. <b>Akılda tutun:</b> süreç kendini besler — ısınma oksitlenmeyi, oksitlenme ısınmayı artırır.`,
});

/* ===================================================================== */
/* 4 · SABİT EŞİK NEDEN ÇALIŞMAZ                                          */
/* ===================================================================== */
function thermo(v, col, d) {
  const top = 14, bot = 176, lvl = bot - v / 100 * (bot - top);
  return `<svg viewBox="0 0 80 220" class="thermo">
   <rect x="24" y="8" width="22" height="182" rx="11" fill="#0b1018" stroke="var(--line2)" stroke-width="2"/>
   ${[0, 20, 40, 60, 80, 100].map(t => `<line x1="48" x2="56" y1="${bot - t / 100 * (bot - top)}" y2="${bot - t / 100 * (bot - top)}" stroke="var(--dim)"/><text x="58" y="${bot - t / 100 * (bot - top) + 4}" font-size="9" class="mono" fill="var(--dim)">${t}</text>`).join('')}
   <rect x="30" y="${lvl}" width="10" height="${bot - lvl + 12}" rx="5" fill="${col}" data-a="grow-y" style="--d:${d}s;animation-duration:1.4s"/>
   <circle cx="35" cy="196" r="17" fill="${col}"/>
  </svg>`;
}
function yearSVG() {
  const X = H.sc(0, 11, 60, 610), Y = H.sc(20, 100, 300, 24);
  const h = m => 49 + 13 * Math.cos(2 * Math.PI * (m - 7) / 12), f = m => h(m) + 26;
  const P = fn => { const p = []; for (let m = 0; m <= 11.001; m += .25) p.push([X(m), Y(fn(m))]); return H.smooth(p); };
  const AY = ['Oca', 'Şub', 'Mar', 'Nis', 'May', 'Haz', 'Tem', 'Ağu', 'Eyl', 'Eki', 'Kas', 'Ara'];
  return `<svg viewBox="0 0 640 340" class="yearsvg">
   ${[20, 40, 60, 80, 100].map(t => `<line x1="60" x2="610" y1="${Y(t)}" y2="${Y(t)}" stroke="var(--line)"/><text x="50" y="${Y(t) + 4}" text-anchor="end" class="mono" font-size="11" fill="var(--dim)">${t}</text>`).join('')}
   ${AY.map((a, m) => `<text x="${X(m)}" y="322" text-anchor="middle" font-size="11" fill="${m === 1 || m === 7 ? 'var(--ink)' : 'var(--dim)'}">${a}</text>`).join('')}
   <g data-step="2"><rect x="${X(0)}" y="24" width="${X(3.45) - X(0)}" height="276" fill="rgba(255,107,61,.10)"/><rect x="${X(10.55)}" y="24" width="${X(11) - X(10.55) + 1}" height="276" fill="rgba(255,107,61,.10)"/>
     <text x="${X(1.7)}" y="44" text-anchor="middle" font-size="13" font-weight="700" fill="var(--kritik)">kör bölge</text></g>
   <path d="${P(h)}" fill="none" stroke="var(--ok)" stroke-width="3" data-a="draw" style="--d:.3s"/>
   <path d="${P(f)}" fill="none" stroke="var(--kritik)" stroke-width="3" stroke-dasharray="0" data-a="draw" style="--d:.6s"/>
   <line x1="60" x2="610" y1="${Y(72)}" y2="${Y(72)}" stroke="var(--uyari)" stroke-width="2" stroke-dasharray="8 6" data-a="grow-x" style="--d:1.2s"/>
   <text x="${X(5.5)}" y="${Y(72) - 8}" text-anchor="middle" font-size="12" font-weight="600" fill="var(--uyari)" data-a="fade" style="--d:1.4s">sabit eşik 72 °C</text>
   <text x="${X(9.7)}" y="${Y(h(9.7)) + 24}" text-anchor="middle" font-size="12" fill="var(--ok)" data-a="fade" style="--d:1s">sağlam pabuç</text>
   <text x="${X(7)}" y="${Y(f(7)) - 12}" text-anchor="middle" font-size="12" fill="var(--kritik)" data-a="fade" style="--d:1.2s">kusurlu pabuç</text>
   <circle cx="${X(1)}" cy="${Y(62)}" r="6" fill="var(--kritik)" data-a="pop" style="--d:1.6s"/><circle cx="${X(7)}" cy="${Y(62)}" r="6" fill="var(--ok)" data-a="pop" style="--d:1.7s"/>
   <text x="${X(1) + 10}" y="${Y(62) - 10}" font-size="12" class="mono" fill="var(--ink)" data-a="fade" style="--d:1.7s">62 °C</text>
   <text x="${X(7)}" y="${Y(62) - 12}" text-anchor="middle" font-size="12" class="mono" fill="var(--ink)" data-a="fade" style="--d:1.8s">62 °C</text>
  </svg>`;
}
add({
  title: 'Sabit eşik neden çalışmaz', section: 'Problem', time: '45 sn',
  html: () => `${HD('01 · Problem', 'Aynı 62 °C, iki ayrı hüküm.')}
<div class="body"><div class="row grow">
  <div class="col" style="width:420px">
    <div class="card tcard" data-a="up" style="--d:.15s">${thermo(62, 'var(--kritik)', .35)}<div><p class="cap">Şubat · 09:00 · yük %35</p><div class="tv"><span data-count="62" data-dur="1.4" style="--d:.35s">0</span> °C</div><span class="chip kritik" data-a="pop" style="--d:1.6s"><i></i>Kusurlu</span></div></div>
    <div class="card tcard" data-a="up" style="--d:.3s">${thermo(62, 'var(--ok)', .5)}<div><p class="cap">Ağustos · 15:00 · yük %95</p><div class="tv"><span data-count="62" data-dur="1.4" style="--d:.5s">0</span> °C</div><span class="chip ok" data-a="pop" style="--d:1.8s"><i></i>Normal</span></div></div>
  </div>
  <div class="col grow" data-step="1">
    <div class="card grow" style="display:flex;flex-direction:column"><p class="cap">Bir yıl, aynı pano, aynı pabuç sırası</p>${yearSVG()}</div>
    <p class="lead" data-show-at="2" style="transition:opacity .4s">Eşik ağustosu atlatacak kadar yüksek kurulmak zorunda. O yüzden kasımdan nisana kusurlu pabuç eşiğin altında kalır ve sistem kördür.</p>
  </div>
</div></div>`,
  notes: `Her yarışmacının ilk aklına gelen çözüm: panoya bir termometre koy, bir eşiğin üstünde alarm ver. Bu sahada çalışmaz. Nedeni şu iki termometrede.

Şubat sabahı dokuzda, yüzde otuz beş yükte 62 derece okuyan bir pabuç kusurludur. Ağustos öğleden sonra, tam yükte okunan aynı 62 derece ise tamamen normaldir. Bir bağlantının sıcaklığını durumu değil, yükü ve mevsimi belirliyor.

[→] Bir yıl boyunca aynı panoya bakalım. Yeşil sağlam pabuç, kırmızı kusurlu pabuç. Sabit eşiği ağustosta yanlış alarm üretmeyecek kadar yükseğe kurmak zorundasınız.

[→] Sonuç: kasımdan nisana kadar kusurlu pabuç eşiğin altında kalıyor. Yılın neredeyse yarısında sistem kör. Eşiği düşürürseniz bu kez her yaz yüzlerce yanlış alarm gelir ve operatör sistemi üçüncü ayda kapatır.

Yani sorulması gereken soru "kaç derece?" değil, "neye göre sıcak?"`,
  use: `<b>Kullan:</b> Önce iki termometre (aynı sayı, zıt hüküm), sonra yıl grafiği, sonra kör bölge. <b>Not:</b> grafik açıklayıcıdır (şematik), ölçüm değildir; sorulursa "fiziği anlatan bir çizim" deyin. <b>Akılda tutun:</b> "Eşik ağustosa göre kurulur, şubatta kördür."`,
});

/* ===================================================================== */
/* 5 · FİKİR — KARDEŞE GÖRE FARK                                              */
/* ===================================================================== */
function thetaSVG() {
  const C = [120, 260, 400], N = ['L1', 'L2', 'L3'], K = ['gri', 'siyah', 'kahverengi'], CC = ['var(--l1)', 'var(--l2)', 'var(--l3)'];
  return `<svg viewBox="0 0 520 430" class="thsvg">
   ${[30, 50, 70, 90].map(t => { const y = 352 - (t - 20) / 80 * 284; return `<line x1="60" x2="470" y1="${y}" y2="${y}" stroke="var(--line)"/><text x="52" y="${y + 4}" text-anchor="end" class="mono" font-size="11" fill="var(--dim)">${t}°</text>`; }).join('')}
   ${C.map((x, i) => `
     <rect x="${x - 34}" y="62" width="68" height="296" rx="16" fill="#0a0f16" stroke="${i === 1 ? '#5b6573' : 'var(--line2)'}" stroke-width="2"/>
     <rect id="thf${i}" x="${x - 27}" y="200" width="54" height="152" rx="11" fill="#a3381e"/>
     <text id="tht${i}" x="${x}" y="46" text-anchor="middle" class="mono" font-size="17" font-weight="600" fill="var(--ink)">—</text>
     <rect x="${x - 26}" y="378" width="16" height="7" rx="2" fill="${CC[i]}" stroke="${i === 1 ? '#6b7380' : 'none'}"/>
     <text x="${x - 4}" y="386" font-size="15" font-weight="700" fill="var(--ink)">${N[i]}</text>
     <text x="${x}" y="408" text-anchor="middle" font-size="12" fill="var(--dim)">${K[i]}</text>`).join('')}
   <line id="thmed" x1="76" x2="444" y1="200" y2="200" stroke="var(--izle)" stroke-width="2" stroke-dasharray="6 5"/>
   <text id="thmedt" x="448" y="196" font-size="11" fill="var(--izle)">diğer</text><text id="thmedt2" x="448" y="209" font-size="11" fill="var(--izle)">fazlar</text>
   <g id="thdel" style="opacity:0"><line id="thdl" x1="${C[1] + 44}" x2="${C[1] + 44}" y1="200" y2="180" stroke="var(--olcum)" stroke-width="2"/>
     <text id="thdt" x="${C[1] + 50}" y="194" font-size="12" font-weight="600" fill="var(--olcum)">fark</text></g>
  </svg>`;
}
add({
  title: 'Fikir: faz karşılaştırması', section: 'Fikir', time: '60 sn',
  html: () => `${HD('02 · Fikir', 'Her bağlantıyı aynı çıkışın diğer fazlarıyla karşılaştırırız.')}
<div class="body"><div class="row grow">
  <div class="card" style="width:540px;padding:8px 10px;--d:.2s" data-a="blur">${thetaSVG()}</div>
  <div class="col grow">
    <div class="card" data-a="up" style="--d:.2s"><p class="cap">Neden fazlar?</p><p class="th-def">Aynı çıkışın üç fazı: aynı akımı taşır, aynı havayı solur, aynı yaştadır. Sağlıklıyken üçü aynı sıcaklıktadır. Biri ayrışırsa sorun odur.</p></div>
    <div class="g2" data-a="up" style="--d:.3s">
      <div class="card tight"><p class="cap">Ortam</p><div class="mini-v"><span id="thamb">30,0</span> °C</div></div>
      <div class="card tight"><p class="cap">Yük</p><div class="mini-v">%<span id="thf">67</span></div><div class="fbar"><i id="thfb"></i></div></div>
    </div>
    <div class="card th-read" data-a="up" style="--d:.4s"><div><p class="cap">L2 · fazlar arası fark</p><div class="big"><span id="thv">0,0</span><small> K</small></div></div><span id="thsev" class="chip"><i></i>Bilgi</span></div>
    <p class="th-cap" id="thcap" data-a="fade" style="--d:.5s">—</p>
  </div>
</div>
<div class="row th-chips" data-a="up" style="--d:.7s">
  <span class="chip ok">${IC.check} Hava ısınır → fark değişmez</span><span class="chip ok">${IC.check} Yük artar → fark değişmez</span><span class="chip brand">Montaj günü çalışır · geçmiş veri gerekmez</span>
</div></div>`,
  scene(el, { REDUCED }) {
    const q = s => el.querySelector(s);
    const fill = [0, 1, 2].map(i => q('#thf' + i)), txt = [0, 1, 2].map(i => q('#tht' + i));
    const BASE = [20.944, 21.094, 21.244]; // ortam 30 °C, k = 40, f = 0,67 → 68,90 / 69,05 / 69,20 °C (docs/08 §2)
    const Y = T => 352 - (T - 20) / 80 * 284;
    const set = (amb, f, R) => {
      const T = BASE.map((c, i) => amb + c + 40 * f * f + (i === 1 ? R * f * f : 0));
      T.forEach((t, i) => {
        const y = Y(t); fill[i].setAttribute('y', y.toFixed(1)); fill[i].setAttribute('height', (352 - y).toFixed(1));
        fill[i].setAttribute('fill', H.heat(.42 + (t - 55) / 60)); txt[i].textContent = fmt(t, 1) + '°';
      });
      const med = (T[0] + T[2]) / 2, dT = T[1] - med, th = dT / (f * f);
      const ym = Y(med), y2 = Y(T[1]);
      q('#thmed').setAttribute('y1', ym); q('#thmed').setAttribute('y2', ym);
      q('#thmedt').setAttribute('y', ym - 4); q('#thmedt2').setAttribute('y', ym + 9);
      q('#thdl').setAttribute('y1', ym); q('#thdl').setAttribute('y2', y2); q('#thdt').setAttribute('y', (ym + y2) / 2 + 4);
      q('#thdel').style.opacity = dT > .3 ? 1 : 0;
      q('#thamb').textContent = fmt(amb, 1); q('#thf').textContent = fmt(f * 100, 0); q('#thfb').style.width = (f * 100) + '%';
      const v = Math.abs(th) < .005 ? 0 : th;
      q('#thv').textContent = fmt(v, 1);
      const [lab, cls] = H.sev(v); const s = q('#thsev'); s.className = 'chip ' + cls; s.innerHTML = '<i></i>' + lab;
    };
    const CAP = [
      [0, 'Montaj günü: üç faz aynı sıcaklıkta. Karşılaştırma hemen başlar.'],
      [2, 'Sıcak hava: üçü birden ısınır. Fark değişmez, alarm yok.'],
      [6, 'Yük artıyor: üçü birden ısınır. Fark yine değişmez.'],
      [10, 'Yalnız L2 ısınıyor: gevşek bağlantı. Fark büyür.'],
      [13.4, 'Yük inip çıksa da fark aynı kalır: ölçtüğümüz yük değil, bağlantının kendisi.'],
    ];
    const seg = (t, a, b, v0, v1) => v0 + (v1 - v0) * H.ease((t - a) / (b - a));
    const at = t => {
      let amb = 30, f = .67, R = 0;
      if (t >= 2 && t < 5.4) amb = seg(t, 2, 3.4, 30, 36.1); else if (t >= 5.4 && t < 6) amb = seg(t, 5.4, 6, 36.1, 30);
      if (t >= 6 && t < 9.4) f = seg(t, 6, 7.4, .67, .95); else if (t >= 9.4 && t < 10) f = seg(t, 9.4, 10, .95, .67);
      if (t >= 10) R = seg(t, 10, 12.4, 0, 6.349);
      if (t >= 13.4 && t < 14.6) f = seg(t, 13.4, 14.4, .67, .40);
      else if (t >= 14.6 && t < 16.4) f = seg(t, 14.6, 16, .40, .95);
      else if (t >= 16.4 && t < 17.4) f = seg(t, 16.4, 17.2, .95, .67);
      if (t >= 18.2) R = seg(t, 18.2, 19, 6.349, 0);
      set(amb, f, R);
      let c = CAP[0][1]; for (const [s, x] of CAP) if (t >= s) c = x;
      const cp = q('#thcap'); if (cp.textContent !== c) cp.textContent = c;
    };
    if (REDUCED) { at(12.5); return null; }
    let raf, t0 = performance.now();
    const loop = now => { at(((now - t0) / 1000) % 19.2); raf = requestAnimationFrame(loop); };
    raf = requestAnimationFrame(loop);
    return { stop() { cancelAnimationFrame(raf); } };
  },
  notes: `Bizim cevabımız çok basit bir fikir: bir bağlantıyı aynı çıkışın diğer fazlarıyla karşılaştırmak. Buna faz karşılaştırması diyoruz.

Neden fazlar? Çünkü aynı çıkışın üç fazı aynı akımı taşıyor, aynı havayı soluyorlar, yan yana duruyorlar, aynı gün takıldılar. Sağlıklıyken üçü aynı sıcaklıkta. Biri ayrışırsa, sorun odur.

Animasyonu izleyelim:
— Sıcak hava geliyor: üç faz birden ısınıyor. Sabit eşikli bir sistem burada alarm verirdi. Bizim ölçtüğümüz fark ise kıpırdamıyor; çünkü hava üçüne birden aynı şeyi yapıyor.
— Yük artıyor: yine üçü birden ısınıyor. Farkı yüke göre düzelttiğimiz için bu da alarm üretmiyor.
— Şimdi yalnız L2 ısınıyor. Gevşek bağlantı tam olarak budur. Fark büyüyor ve sistem "Uyarı" diyor.
— Ve en önemlisi: yük düşse de artsa da fark aynı kalıyor. Yani ölçtüğümüz şey yük ya da hava değil, bağlantının kendisi.

Bu farka sistemde θ — teta — diyoruz; ekranlarda bu harfi göreceksiniz. İki büyük avantajı var: hava ve yük etkisini kendiliğinden ayıklıyor ve geçmiş veri istemiyor. Montaj günü üç faz zaten birbirinin referansı. Bu yeni bir icat da değil: termografi uzmanları sahada zaten "benzer bileşeni benzer yük altında karşılaştır" der. Fark şu: yılda bir kez değil, dakikada bir ölçüyoruz.`,
  use: `<b>Kullan:</b> Animasyon kendini döndürür (≈19 sn). Bir tur izletin; anlatımı alttaki cümleye göre senkronlayın. <b>Jüri sorarsa — "Kalibrasyon?":</b> Bu bir fark; iki sensörün ortak hatası birbirini götürür. <b>"Üç faz birden bozulursa?":</b> Fark bunu göremez; o durumu her zaman açık olan mutlak sıcaklık sınırları yakalar.`,
});

/* ===================================================================== */
/* 6 · DONANIM — 9 CİHAZ                                                  */
/* ===================================================================== */
function panelSVG() {
  const Y = y => 1500 - y, cx = k => 72 + k * 105, OFF = [-30, -10, 10, 30];
  const CAB = ['var(--l1)', 'var(--l2)', 'var(--l3)', 'var(--nn)'];
  let s = `<svg viewBox="-20 -20 1640 1540" class="pnsvg">
  <defs><pattern id="pnh" width="26" height="26" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="26" stroke="#1f2933" stroke-width="9"/></pattern>
  <linearGradient id="pnfov" x1="0" y1="1" x2="0" y2="0"><stop offset="0" stop-color="#f78320" stop-opacity=".38"/><stop offset="1" stop-color="#f78320" stop-opacity=".03"/></linearGradient></defs>
  <rect x="0" y="0" width="1600" height="1500" rx="14" fill="#090d13" stroke="#55707f" stroke-width="5"/>
  <rect x="0" y="0" width="1600" height="60" fill="#0f151d" stroke="#2f4149" stroke-width="3"/>
  ${[485, 610, 735, 860].map((x, j) => `<rect x="${x - 24}" y="6" width="48" height="50" rx="5" fill="${CAB[j]}" opacity=".75"/>`).join('')}
  <text x="20" y="40" font-size="30" fill="var(--dim)">çatı · giriş</text>
  <rect x="0" y="60" width="1300" height="340" fill="url(#pnh)" stroke="#2f4149" stroke-width="3"/>
  ${[0, 1, 2, 3].map(j => `<rect x="40" y="${115 + j * 70}" width="1220" height="${j === 3 ? 22 : 30}" rx="4" fill="${CAB[j]}" opacity=".55"/>`).join('')}
  <rect x="300" y="168" width="700" height="132" rx="14" fill="rgba(6,8,12,.9)" stroke="var(--kritik)" stroke-width="3"/>
  <text x="650" y="222" text-anchor="middle" font-size="42" font-weight="700" fill="var(--kritik)">Bara bölmesi: girilmez</text>
  <text x="650" y="270" text-anchor="middle" font-size="28" fill="var(--muted)">enerji kesilmeden güvenle açılamaz</text>
  <rect x="0" y="400" width="1300" height="400" fill="#0b1118" stroke="#2f4149" stroke-width="3"/>`;
  for (let k = 0; k < 12; k++) {
    const x = cx(k) - 42, spare = k >= 10;
    s += `<rect x="${x}" y="420" width="84" height="360" rx="6" fill="${spare ? 'url(#pnh)' : '#121a24'}" stroke="#415a68" stroke-width="3"/>
    <text x="${cx(k)}" y="${spare ? 610 : 770}" text-anchor="middle" font-size="26" fill="var(--dim)">${spare ? 'yedek' : 'Ç' + (k + 1)}</text>`;
    if (!spare) s += [-24, 0, 24].map(o => `<rect x="${cx(k) + o - 8}" y="470" width="16" height="240" rx="6" fill="#1a2430" stroke="#2f4149" stroke-width="2"/>`).join('');
  }
  // sağ kolon
  const boxes = [[80, 200, 'Ark rölesi', 'id="pntv"'], [215, 335, 'Enerji analizörü', 'id="pnmp"'], [350, 440, 'Sayaç', ''], [455, 600, 'Modem bölmesi', ''], [615, 790, 'Priz', '']];
  s += `<rect x="1300" y="60" width="300" height="740" fill="#0d131b" stroke="#2f4149" stroke-width="3"/>`;
  s += boxes.map(([a, b, t, id], i) => `<rect ${id} x="1316" y="${a}" width="268" height="${b - a}" rx="8" fill="#121a24" stroke="#415a68" stroke-width="3"/><text x="1450" y="${i === 3 ? a + 34 : i === 4 ? b - 22 : (a + b) / 2 + 10}" text-anchor="middle" font-size="27" fill="var(--muted)">${t}</text>`).join('');
  // alt kablo bölmesi
  s += `<rect x="0" y="800" width="1600" height="700" fill="#080c11" stroke="#2f4149" stroke-width="3"/>
  <text x="24" y="852" font-size="32" fill="var(--dim)">alt kablo bölmesi · kitin tamamı burada</text>`;
  for (let k = 0; k < 12; k++) OFF.forEach((o, j) => {
    const x = cx(k) + o;
    if (k >= 10) { s += `<circle cx="${x}" cy="${Y(500)}" r="9" fill="none" stroke="#33414f" stroke-width="3" stroke-dasharray="4 4"/>`; return; }
    s += `<line x1="${x}" y1="${Y(500) + 10}" x2="${x}" y2="1500" stroke="${CAB[j]}" stroke-width="9"/>
      <circle cx="${x}" cy="${Y(500)}" r="11" fill="#cfd6de" stroke="#0b0f14" stroke-width="3" ${k === 6 && j === 1 ? 'id="pnhot"' : ''}/>`;
  });
  s += `<line x1="80" x2="1540" y1="${Y(230)}" y2="${Y(230)}" stroke="#35c07a" stroke-width="16"/><line x1="80" x2="1540" y1="${Y(230)}" y2="${Y(230)}" stroke="#f4d13a" stroke-width="16" stroke-dasharray="30 30"/>
  <text x="1560" y="${Y(230) - 24}" text-anchor="end" font-size="30" fill="var(--dim)">topraklama barası</text>`;
  // adım 1: 6 × TC
  s += `<g data-step="1">${[5, 6].map(k => [0, 1, 2].map(j => `<rect x="${cx(k) + OFF[j] - 13}" y="${Y(430) - 26}" width="26" height="52" rx="6" fill="var(--brand)" stroke="#fff3" stroke-width="2"/>`).join('')).join('')}
    <path d="M${cx(6) + 30},${Y(430)} L1090,${Y(430) + 10}" stroke="var(--brand)" stroke-width="3" fill="none"/>
    <rect x="1090" y="${Y(430) - 22}" width="420" height="64" rx="12" fill="rgba(6,8,12,.94)" stroke="var(--brand)" stroke-width="3"/>
    <text x="1112" y="${Y(430) + 21}" font-size="36" font-weight="700" fill="var(--brand)">6 ısıl kelepçe</text></g>`;
  // adım 2: TN-IR
  s += `<g data-step="2"><polygon points="640,${Y(160)} 140,${Y(500)} 1140,${Y(500)}" fill="url(#pnfov)"/>
    <rect x="600" y="${Y(150) - 18}" width="80" height="36" rx="7" fill="#1c2632" stroke="var(--brand)" stroke-width="4"/>
    <path d="M680,${Y(150)} L1090,${Y(150) + 82}" stroke="var(--brand)" stroke-width="3" fill="none"/>
    <rect x="1090" y="${Y(150) + 50}" width="380" height="64" rx="12" fill="rgba(6,8,12,.94)" stroke="var(--brand)" stroke-width="3"/>
    <text x="1112" y="${Y(150) + 93}" font-size="36" font-weight="700" fill="var(--brand)">Termal kamera</text></g>`;
  // adım 3: PD-01
  s += `<g data-step="3"><circle cx="1290" cy="${Y(230)}" r="34" fill="#1c2632" stroke="var(--brand)" stroke-width="5"/><circle cx="1290" cy="${Y(230)}" r="10" fill="var(--brand)"/>
    <rect x="1090" y="${Y(230) + 44}" width="380" height="64" rx="12" fill="rgba(6,8,12,.94)" stroke="var(--brand)" stroke-width="3"/>
    <text x="1112" y="${Y(230) + 87}" font-size="36" font-weight="700" fill="var(--brand)">Ortam düğümü</text></g>`;
  // adım 4: GW-01 + radyo + RS-485
  const gx = 1450, gy = Y(980) + 10;
  s += `<g data-step="4"><rect x="${gx - 74}" y="${gy - 28}" width="148" height="64" rx="9" fill="#1c2632" stroke="var(--brand)" stroke-width="5"/>
    <text x="${gx}" y="${gy + 13}" text-anchor="middle" font-size="25" font-weight="700" fill="var(--brand)">Ağ geçidi</text>
    <path d="M${gx + 70},${gy - 20} h60 v-60" stroke="var(--brand)" stroke-width="5" fill="none"/><circle cx="${gx + 130}" cy="${gy - 86}" r="7" fill="var(--brand)"/>
    ${[[cx(5), Y(430)], [cx(6), Y(430)], [640, Y(150)], [1290, Y(230)]].map(([x, y]) => `<path class="rf" d="M${x},${y} Q${(x + gx) / 2 + 120},${(y + gy) / 2 + 60} ${gx},${gy + 36}" stroke="var(--izle)" stroke-width="5" fill="none"/>`).join('')}
    <path d="M${gx},${gy - 36} V200" stroke="var(--brand2)" stroke-width="6"/><path d="M${gx - 40},${gy - 36} V335" stroke="var(--brand2)" stroke-width="6" stroke-dasharray="14 8"/>
    <rect x="1322" y="${gy + 44}" width="256" height="42" rx="8" fill="rgba(6,8,12,.94)"/><text x="1450" y="${gy + 74}" text-anchor="middle" font-size="25" fill="var(--izle)">kablosuz toplar</text></g>`;
  s += `<circle cx="${cx(6) - 10}" cy="${Y(500)}" r="22" fill="none" stroke="var(--kritik)" stroke-width="5" class="pulse"/>`;
  return s + '</svg>';
}
add({
  title: 'Çözüm: panoya ne takıyoruz', section: 'Çözüm', time: '50 sn',
  html: () => `${HD('03 · Çözüm', 'Bir pano, dokuz küçük cihaz. Hiçbir şey sökülmez.', '')}
<div class="body"><div class="row grow">
  <div class="card center" style="width:570px;padding:8px;--d:.15s" data-a="blur">${panelSVG()}</div>
  <div class="col grow kit">
    <div class="card tight kitrow" data-a="up" style="--d:.25s"><span class="kn">0</span><div><h3>Tek kural</h3><p class="sub">Delik delinmez, mevcut parça değişmez, enerjili bara bölmesine girilmez. Kit yalnız kablo bölmesine ve ölçü kolonuna takılır.</p></div></div>
    <div class="card tight kitrow" data-step="1"><span class="kn">6</span><div><h3>Isıl kelepçe</h3><p class="sub">Çıkış kablolarına geçer; hem sıcaklığı hem akımı ölçer. Üçlü takılır, böylece her faz diğer ikisiyle karşılaştırılır.</p></div></div>
    <div class="card tight kitrow" data-step="2"><span class="kn">1</span><div><h3>Termal kamera</h3><p class="sub">Bölme tabanına mıknatısla oturur, yukarı bakar. Kelepçe takılmayan bütün bağlantıları görür.</p></div></div>
    <div class="card tight kitrow" data-step="3"><span class="kn">1</span><div><h3>Ortam düğümü</h3><p class="sub">Nemi ve yoğuşma riskini ölçer; yalıtım bozulmasının ve gevşek temasın elektriksel izlerini dinler.</p></div></div>
    <div class="card tight kitrow" data-step="4"><span class="kn">1</span><div><h3>Ağ geçidi</h3><p class="sub">Sensörlerden kablosuz veri toplar; panoda zaten bulunan ark rölesini ve enerji analizörünü de okur, sunucuya iletir.</p></div></div>
  </div>
</div></div>`,
  notes: `Panoya ne takıyoruz? Bir modül, bir pano demek ve dokuz küçük cihazdan oluşuyor.

Önce tek kural: hiçbir delik delinmiyor, mevcut hiçbir parça değişmiyor ve bara bölmesine girilmiyor. Çünkü o bölmeyi açmak için bütün dağıtım merkezinin enerjisini kesmek gerekir. O yüzden kitin tamamı alt kablo bölmesine ve ölçü kolonuna takılıyor; kurulum için kesinti gerekmiyor.

[→] Altı ısıl kelepçe: iki çıkışın üç fazına. Kablonun üzerine geçiyor, hem sıcaklığı hem akımı ölçüyor. Üçlü takılmalarının sebebi az önceki fikir: her fazı diğer ikisiyle karşılaştırabilmek.

[→] Bir termal kamera: bölme tabanına mıknatısla oturuyor ve yukarı bakıyor. Kelepçe takılmayan bütün bağlantıları görüyor.

[→] Bir ortam düğümü: nemi ve yoğuşma riskini ölçüyor; ayrıca yalıtım bozulmasının ve gevşek temasın yaydığı elektriksel izleri dinliyor.

[→] Ve ağ geçidi: sensörlerden kablosuz veri topluyor, panoda zaten bulunan ark rölesini ve enerji analizörünü de okuyor ve her şeyi sunucuya iletiyor.

Sensörler pille çalışıyor ve yıllarca dayanacak şekilde tasarlandı. Ağ geçidi, sunucuyla bağlantı koparsa veriyi saklıyor; bağlantı gelince kaldığı yerden gönderiyor.

Kırmızı halka, kapaktaki o bağlantı: Çıkış 7, L2.`,
  use: `<b>Kullan:</b> 4 adım: kelepçeler → termal kamera → ortam düğümü → ağ geçidi. Her adımda sağdaki satır açılır. <b>Jüri sorarsa — "Neden bara bölmesine koymuyorsunuz?":</b> Panoda AG giriş kesicisi yok; o bölmeyi enerjisiz yapmak bütün dağıtım merkezini karartmak demek. Orası periyodik termografiyle izlenmeye devam eder. <b>"Yükü nereden biliyorsunuz?":</b> her kelepçe kendi akım sensörünü taşır; diğer bağlantılarda yük analizörden kestirilir ve ekranda öyle yazar.`,
});

/* ===================================================================== */
/* 7 · UÇTAN UCA MİMARİ                                                   */
/* ===================================================================== */
function archSVG() {
  const box = (x, y, w, h, t, sub, col = 'var(--line2)', extra = '') => `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="12" fill="#0d131b" stroke="${col}" stroke-width="1.6" ${extra}/>
    <text x="${x + 14}" y="${y + 24}" font-size="14.5" font-weight="700" fill="var(--ink)">${t}</text>${sub ? `<text x="${x + 14}" y="${y + 43}" font-size="11.5" fill="var(--muted)">${sub}</text>` : ''}`;
  const pk = (id, d, dur, n, col) => `<path id="${id}" d="${d}" fill="none" stroke="${col}" stroke-opacity=".45" stroke-width="2"/>` +
    Array.from({ length: n }, (_, i) => `<circle r="4" fill="${col}"><animateMotion dur="${dur}s" begin="-${(i * dur / n).toFixed(2)}s" repeatCount="indefinite"><mpath href="#${id}"/></animateMotion></circle>`).join('');
  const dev = [['6 ısıl kelepçe', 'kablosuz'], ['Termal kamera', 'kablosuz'], ['Ortam düğümü', 'kablosuz'], ['Ark rölesi', 'kablolu · panoda mevcut'], ['Enerji analizörü', 'kablolu · panoda mevcut']];
  const srv = [['Veri toplama', 'bütün panolardan, tek yerde'], ['Kayıt', 'geçmiş korunur'], ['Analiz', 'faz karşılaştırması · gün gün eğilim'], ['Karar', 'gereksiz alarmı ayıkla · haber ver']];
  return `<svg viewBox="0 0 1160 470" class="archsvg">
  <g data-step="0">
    <rect x="0" y="16" width="214" height="446" rx="14" fill="none" stroke="var(--line2)" stroke-dasharray="5 5"/>
    <text x="14" y="40" class="mono" font-size="11" fill="var(--brand)">PANO · 1 MODÜL</text>
    ${dev.map(([a, b], i) => `<rect x="12" y="${56 + i * 80}" width="190" height="62" rx="10" fill="#0d131b" stroke="${i < 3 ? 'var(--brand)' : 'var(--line2)'}"/>
      <text x="26" y="${82 + i * 80}" font-size="14" font-weight="600" fill="var(--ink)">${a}</text><text x="26" y="${102 + i * 80}" class="mono" font-size="11" fill="var(--muted)">${b}</text>`).join('')}
    ${dev.map((_, i) => pk('ap' + i, `M202,${87 + i * 80} C250,${87 + i * 80} 250,240 292,240`, 2.2 + i * .25, 2, i < 3 ? 'var(--izle)' : 'var(--brand2)')).join('')}
    ${box(292, 168, 168, 148, 'Ağ geçidi', 'panodaki toplayıcı', 'var(--brand)')}
    <text x="306" y="236" font-size="11.5" fill="var(--muted)">bağlantı koparsa</text>
    <text x="306" y="254" font-size="12" fill="var(--ink)">veriyi saklar</text>
    <text x="306" y="278" font-size="11.5" fill="var(--muted)">aşırı sıcakta, arkta</text>
    <text x="306" y="296" font-size="12" fill="var(--ink)">kendisi alarm verir</text>
  </g>
  <g data-step="1">
    ${pk('bp', 'M460,242 L548,242', 1.4, 3, 'var(--brand)')}
    <text x="504" y="228" text-anchor="middle" font-size="11.5" fill="var(--brand2)">şifreli</text><text x="504" y="266" text-anchor="middle" font-size="11.5" fill="var(--brand2)">kayıpsız</text>
    <rect x="548" y="16" width="330" height="446" rx="14" fill="rgba(74,163,255,.04)" stroke="var(--izle)" stroke-dasharray="6 5"/>
    <text x="564" y="40" class="mono" font-size="11" fill="var(--izle)">DAĞITIM ŞİRKETİNİN KENDİ SUNUCUSU</text>
    <g transform="translate(846,22)" color="var(--ok)">${IC.cloudx.replace('class="ic"', 'width="22" height="22"')}</g>
    ${srv.map(([a, b], i) => `${box(566, 60 + i * 100, 294, 64, a, b)}${i < 3 ? `<path d="M713,${128 + i * 100} v24" stroke="var(--izle)" stroke-width="2" marker-end="url(#aa)"/>` : ''}`).join('')}
    <defs><marker id="aa" viewBox="0 0 10 10" refX="5" refY="8" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,0 L5,9 z" fill="var(--izle)" transform="rotate(-90 5 5)"/></marker></defs>
  </g>
  <g data-step="2">
    ${pk('o1', 'M878,392 C910,392 910,90 950,90', 2.4, 2, 'var(--ok)')}
    ${pk('o2', 'M878,392 C915,392 915,240 950,240', 2, 2, 'var(--ok)')}
    ${pk('o3', 'M878,392 C920,392 920,390 950,390', 1.6, 2, 'var(--kritik)')}
    ${box(950, 46, 210, 92, 'İzleme ekranları', 'harita · pano ikizi · kanıt', 'var(--ok)')}<text x="964" y="124" font-size="11.5" fill="var(--muted)">operatör ve bakım ekibi için</text>
    ${box(950, 196, 210, 92, 'SCADA', 'mevcut sisteme veri', 'var(--ok)')}<text x="964" y="274" font-size="11.5" fill="var(--muted)">yalnız okunur, komut almaz</text>
    ${box(950, 346, 210, 92, 'Bildirim', 'SMS + sesli arama', 'var(--kritik)')}<text x="964" y="424" font-size="11.5" fill="var(--muted)">en yakın ekibe · konumuyla</text>
  </g>
</svg>`;
}
add({
  title: 'Çözüm: veri nasıl akıyor', section: 'Çözüm', time: '40 sn',
  html: () => `${HD('03 · Çözüm', 'Veri panodan ekrana nasıl gidiyor?')}
<div class="body"><div class="grow center">${archSVG()}</div>
<div class="row" style="gap:10px" data-step="2"><span class="chip ok">${IC.lock} Tek yön: sistem panoya komut veremez</span><span class="chip">Bulut yok: her şey kurum içinde</span><span class="chip">Tek komutla kurulur · internet gerekmez</span></div></div>`,
  notes: `Verinin yolculuğu soldan sağa.

Panoda dokuz cihaz. Kelepçeler, termal kamera ve ortam düğümü ağ geçidine kablosuz konuşuyor. Panoda zaten bulunan ark rölesi ve enerji analizörü ise kabloyla okunuyor. Ağ geçidi yalnız bir köprü değil: sunucuyla bağlantı koparsa veriyi saklıyor, aşırı sıcaklık ya da ark gibi acil durumlarda alarmı kendisi veriyor.

[→] Ağ geçidinden sunucuya şifreli ve kayıpsız bir bağlantı var. Sunucu dağıtım şirketinin kendi sunucu odasında; kamu bulutu yok. İçeride sıra sabit: veriyi topla, kaydet, analiz et, karar ver.

[→] Üç çıkış var. Operatörün ve bakım ekibinin izleme ekranları. Mevcut SCADA sistemine giden veri. Ve panoya en yakın nöbetçi ekibe, konumuyla birlikte SMS ve sesli arama.

Bir de önemli bir güvenlik ilkesi: akış tek yönlü. Sistemin hiçbir yerinde panoya komut veren bir yol yok.`,
  use: `<b>Kullan:</b> 3 adım: pano + ağ geçidi → sunucu → çıkışlar. <b>Jüri sorarsa — "Hangi protokol?":</b> Ağ geçidi → sunucu MQTT (TLS, onaylı teslim); SCADA tarafı Modbus TCP. <b>"Neden bulut yok?":</b> şebeke ve arıza verisi kritik altyapı verisi; teknik olarak da gerekmiyor, 1000 pano sıradan bir sunucuda çalışır.`,
});

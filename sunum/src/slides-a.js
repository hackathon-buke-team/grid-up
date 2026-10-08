/* ======================================================================
   SLAYTLAR 1–8 · açılış, problem, fikir, donanım, mimari
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
  const cx = k => 52 + k * 41, LY = 232, OFF = [-11, -4, 4, 11];
  const CAB = ['var(--l1)', 'var(--l2)', 'var(--l3)', 'var(--nn)'];
  const rnd = H.rng(7);
  let base = '', therm = '';
  for (let k = 0; k < 12; k++) {
    const x = cx(k), spare = k >= 10;
    base += `<text x="${x}" y="60" text-anchor="middle" class="mono" font-size="10" fill="var(--dim)">${spare ? 'Y' + (k - 9) : 'Ç' + (k + 1)}</text>`;
    if (spare) { base += `<rect x="${x - 15}" y="70" width="30" height="126" rx="3" fill="url(#${p}h)" stroke="var(--line2)"/>`; continue; }
    base += `<rect x="${x - 15}" y="70" width="30" height="126" rx="3" fill="#0d131b" stroke="#33414f"/>
      <rect x="${x - 11}" y="76" width="22" height="10" rx="2" fill="#1a2330"/>
      ${[-9, -2, 5].map(o => `<rect x="${x + o}" y="98" width="5" height="72" rx="2" fill="#18212c" stroke="#2c3a48"/>`).join('')}`;
    OFF.forEach((o, j) => {
      base += `<line x1="${x + o}" y1="${LY + 4}" x2="${x + o}" y2="470" stroke="${CAB[j]}" stroke-width="3.2" ${j === 1 ? 'stroke-opacity=".95"' : ''}/>
        <circle cx="${x + o}" cy="${LY}" r="3.4" fill="#cfd6de" stroke="#0b0f14"/>`;
      const hot = k === 6 && j === 1;
      const t = hot ? 1 : (j === 3 ? .4 : .5) + rnd() * .1 + (k === 5 || k === 6 ? .06 : 0);
      therm += `<line x1="${x + o}" y1="${LY}" x2="${x + o}" y2="470" stroke="${H.heat(t * (hot ? .8 : .62))}" stroke-width="${hot ? 7 : 5}" stroke-opacity=".75" filter="url(#${p}b)"/>
        <line x1="${x + o}" y1="${LY}" x2="${x + o}" y2="${LY + (hot ? 110 : 40)}" stroke="${H.heat(t * .9)}" stroke-width="${hot ? 5 : 3}" stroke-linecap="round"/>
        <circle cx="${x + o}" cy="${LY}" r="${hot ? 24 : 10}" fill="${H.heat(t)}" filter="url(#${p}b)"/>
        <circle cx="${x + o}" cy="${LY}" r="${hot ? 6 : 3.8}" fill="${hot ? '#fffbd0' : H.heat(Math.min(1, t + .14))}"/>`;
    });
    therm += `<rect x="${x - 15}" y="70" width="30" height="126" rx="3" fill="${H.heat(.24 + rnd() * .05)}"/>
      ${[-9, -2, 5].map(o => `<rect x="${x + o}" y="98" width="5" height="72" rx="2" fill="${H.heat(.34 + rnd() * .06)}"/>`).join('')}`;
  }
  const tc = [5, 6].map(k => [0, 1, 2].map(j => `<rect x="${cx(k) + OFF[j] - 3.5}" y="268" width="7" height="15" rx="2" fill="var(--brand)"/>`).join('')).join('');
  return `<svg viewBox="0 0 560 520" class="cvsvg" aria-label="Alt kablo bölmesi, termal tarama">
  <defs>
    <pattern id="${p}h" width="7" height="7" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="7" stroke="#26313d" stroke-width="2"/></pattern>
    <filter id="${p}b" x="-2" y="-2" width="5" height="5"><feGaussianBlur stdDeviation="3.6"/></filter>
    <linearGradient id="${p}trail" x1="1" x2="0"><stop offset="0" stop-color="#ffb066" stop-opacity=".35"/><stop offset="1" stop-color="#ffb066" stop-opacity="0"/></linearGradient>
    <linearGradient id="${p}fov" x1="0" y1="1" x2="0" y2="0"><stop offset="0" stop-color="#f78320" stop-opacity=".22"/><stop offset="1" stop-color="#f78320" stop-opacity="0"/></linearGradient>
    <radialGradient id="${p}bg" cx="${(cx(6) - 4) / 560}" cy="${LY / 520}" r=".9"><stop offset="0" stop-color="#3b0d5e"/><stop offset=".5" stop-color="#1a0838"/><stop offset="1" stop-color="#0a0418"/></radialGradient>
    <clipPath id="${p}clip"><rect id="${p}cr" x="0" y="0" width="0" height="520"/></clipPath>
  </defs>
  <rect x="14" y="20" width="532" height="486" rx="12" fill="#080b10" stroke="var(--line2)"/>
  <text x="28" y="40" class="mono" font-size="10.5" fill="var(--dim)">EK-II/14 · alt kablo bölmesi · 48 pabuç pozisyonu</text>
  ${base}${tc}
  <polygon points="270,486 44,${LY} 500,${LY}" fill="url(#${p}fov)"/>
  <rect x="252" y="484" width="36" height="14" rx="3" fill="#1c2632" stroke="var(--brand)"/>
  <text x="296" y="495" class="mono" font-size="9.5" fill="var(--muted)">TN-IR 32×24</text>
  <g id="${p}th" clip-path="url(#${p}clip)">
    <rect x="15" y="21" width="530" height="484" rx="12" fill="url(#${p}bg)"/>
    ${therm}
    <circle cx="${cx(6) - 4}" cy="${LY}" r="12" fill="none" stroke="#fcd34d" stroke-width="2"><animate attributeName="r" values="10;26" dur="1.6s" repeatCount="indefinite"/><animate attributeName="opacity" values="1;0" dur="1.6s" repeatCount="indefinite"/></circle>
    <text x="28" y="40" class="mono" font-size="10.5" fill="#c9b8ff">termal görünüm · kardeş farkı</text>
  </g>
  <g id="${p}scan" style="opacity:0"><rect x="-46" y="21" width="46" height="484" fill="url(#${p}trail)"/><line x1="0" y1="21" x2="0" y2="505" stroke="#ffb066" stroke-width="2"/></g>
  <g id="${p}call" style="opacity:0;transition:opacity .5s">
    <path d="M${cx(6) - 4},${LY + 16} L318,318" stroke="var(--kritik)" stroke-width="1.5" fill="none"/>
    <rect x="308" y="300" width="230" height="100" rx="10" fill="rgba(6,8,12,.95)" stroke="var(--kritik)"/>
    <text x="324" y="323" font-size="12" fill="var(--muted)">Ç7 · L2 · çıkış pabucu</text>
    <rect x="462" y="309" width="62" height="21" rx="10.5" fill="rgba(255,107,61,.14)" stroke="var(--kritik)"/>
    <text x="493" y="323.5" text-anchor="middle" class="mono" font-size="11" font-weight="700" fill="var(--kritik)">Kritik</text>
    <text x="324" y="360" font-size="29" font-weight="700" fill="var(--olcum)">θ = 17,6 K</text>
    <text x="324" y="386" class="mono" font-size="11" fill="var(--muted)">ACİL eşiğine ~15 gün (13–19)</text>
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
    <p class="cv-thesis" data-a="up" style="--d:.4s">Sıcaklığa değil, kardeşine göre farka bakar.</p>
    <div class="cv-logos" data-a="fade" style="--d:.6s"><img src="${A.adm}" alt="ADM Elektrik Dağıtım"><i></i><img src="${A.gdz}" alt="GDZ Elektrik Dağıtım"></div>
    <p class="sub cv-team" data-a="fade" style="--d:.7s">Takım ${TEAM.name}${TEAM.no ? ' · Takım No ' + TEAM.no : ''}</p>
  </div>
  <div class="cv-r" data-a="blur" style="--d:.15s">${coverSVG()}</div>
</div>`,
  scene(el, { REDUCED }, p = 'cv') {
    const cr = el.querySelector('#' + p + 'cr'), scan = el.querySelector('#' + p + 'scan'), call = el.querySelector('#' + p + 'call'), th = el.querySelector('#' + p + 'th');
    const XH = 52 + 6 * 41 - 4;
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

Sağda gördüğünüz, 1600 kVA'lık bir TEDAŞ alçak gerilim dağıtım panosunun alt kablo bölmesi: on fider, kırk sekiz pabuç pozisyonu. Termal göz soldan sağa geçtiğinde pabuçların hepsi birbirine benziyor — biri hariç. Çıkış 7'nin L2 pabucu.

Bu pabuç bugün yanmıyor. Ama kendi kardeş fazlarına göre, yüke göre düzeltildiğinde, 17,6 kelvin daha sıcak. Ve bu gidişle ACİL seviyesine yaklaşık on beş günü var.

PANO GÖZ'ün işi tam olarak bu: arıza olmadan, haftalar önce o bağlantıyı bulmak, bozulmanın ne zaman başladığını ve ne kadar vaktimiz kaldığını söylemek. Tek cümlelik farkımız da şu: sıcaklığa değil, kardeşine göre farka bakıyoruz. Önümüzdeki dakikalarda bunun neden önemli olduğunu, nasıl kurulduğunu ve sahada nasıl işletileceğini göstereceğiz.`,
  use: `<b>Kullan:</b> Açılış — 30 saniyeyi geçmeyin. Tarama bitip etiket çıktığında "biri hariç" cümlesini söyleyin. <b>Ezberlenecek:</b> 1600 kVA · TEDAŞ-MLZ/2003-06.B · 48 pabuç pozisyonu · Ç7-L2. <b>Dikkat:</b> 17,6 K ve "~15 gün (13–19)" 3 Ekim demo koşusundan (24 pano, 45 gün geçmiş) alındı; provada kullanacağınız koşunun sayısıyla değiştirin. <b>Kısayollar:</b> N konuşma metni · S konuşmacı ekranı · O slayt haritası · Q jüri soruları · B kararart · F tam ekran · P metni yazdır.`,
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

İşi dört paralel pakete böldük: donanım ve uç düğüm; sunucu, entegrasyon ve ölçek; izleme ekranları ve operasyon deneyimi; bildirim, doğrulama ve sunum. Bu slaytta uzun durmayacağım; hemen problemin kendisine geçiyorum.`,
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
    <text x="${X(.24) + 24}" y="84" font-size="13" fill="var(--muted)">θ yükselir, CUSUM birikir</text>
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

[→] PANO GÖZ'ün hedefi ise eğrinin başı. Sıcaklık henüz tehlikeli değilken, sadece "kardeşlerinden farklı" olduğu anda. Aradaki fark haftalar — ve o haftalar bir arıza ekibi ile planlı bir tork iş emri arasındaki fark.`,
  use: `<b>Kullan:</b> İki adım: önce kırmızı "bugün", sonra turuncu "PANO GÖZ" işareti. Kırmızıyı gösterirken durun, jüri kendi sahasını düşünsün. <b>Kaynak:</b> şartname "Problem" bölümü, ilk iki paragraf. <b>Ezberlenecek:</b> pozitif geri besleme — ısınma oksidasyonu, oksidasyon direnci artırır.`,
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

[→] Sonuç: kasımdan nisana kadar kusurlu pabuç eşiğin altında kalıyor. Yılın neredeyse yarısında sistem kör. Eşiği düşürürseniz bu kez her yaz yüzlerce yanlış alarm gelir ve operatör sistemi üçüncü ayda kapatır.`,
  use: `<b>Kullan:</b> Önce iki termometre (aynı sayı, zıt hüküm), sonra yıl grafiği, sonra kör bölge. <b>Not:</b> grafik açıklayıcıdır (şematik), ölçüm değildir; sorulursa "fiziği anlatan bir çizim" deyin. <b>Ezberlenecek:</b> "Eşik ağustosa göre kurulur, şubatta kördür." <b>Kaynak:</b> README §1, docs/04 §11.1.`,
});

/* ===================================================================== */
/* 5 · θ — KARDEŞE GÖRE FARK                                              */
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
   <text id="thmedt" x="448" y="196" font-size="11" fill="var(--izle)">kardeş</text><text id="thmedt2" x="448" y="209" font-size="11" fill="var(--izle)">medyanı</text>
   <g id="thdel" style="opacity:0"><line id="thdl" x1="${C[1] + 44}" x2="${C[1] + 44}" y1="200" y2="180" stroke="var(--olcum)" stroke-width="2"/>
     <text id="thdt" x="${C[1] + 50}" y="194" class="mono" font-size="12" fill="var(--olcum)">ΔT</text></g>
  </svg>`;
}
add({
  title: 'θ: kardeşine göre fark', section: 'Fikir', time: '70 sn',
  html: () => `${HD('02 · Fikir', 'θ: bir bağlantının, kendi kardeş fazlarına göre fazla ısısı.')}
<div class="body"><div class="row grow">
  <div class="card" style="width:540px;padding:8px 10px;--d:.2s" data-a="blur">${thetaSVG()}</div>
  <div class="col grow">
    <div class="card" data-a="up" style="--d:.2s"><div class="formula">θ = <span class="frac"><span>T − medyan(kardeşler)</span><span>(I / I<sub>ref</sub>)²</span></span><span class="unit">K</span></div></div>
    <div class="g2" data-a="up" style="--d:.3s">
      <div class="card tight"><p class="cap">Ortam</p><div class="mini-v"><span id="thamb">30,0</span> °C</div></div>
      <div class="card tight"><p class="cap">Yük · I / I<sub>ref</sub></p><div class="mini-v" id="thf">0,67</div><div class="fbar"><i id="thfb"></i></div></div>
    </div>
    <div class="card th-read" data-a="up" style="--d:.4s"><div><p class="cap">θ · L2 pabucu</p><div class="big"><span id="thv">0,00</span><small> K</small></div></div><span id="thsev" class="chip"><i></i>Bilgi</span></div>
    <p class="mono th-sub" id="thsub" data-a="fade" style="--d:.5s">—</p>
    <p class="th-cap" id="thcap" data-a="fade" style="--d:.5s">—</p>
  </div>
</div>
<div class="row th-chips" data-a="up" style="--d:.7s">
  <span class="chip ok">${IC.check} Yük sadeleşir · I² paydada</span><span class="chip ok">${IC.check} Mevsim ve güneş sadeleşir · aynı hava</span><span class="chip ok">${IC.check} Yayıcılık sadeleşir · aynı yüzey</span><span class="chip brand">Geçmiş gerekmez · montaj günü referans</span>
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
      q('#thamb').textContent = fmt(amb, 1); q('#thf').textContent = fmt(f, 2); q('#thfb').style.width = (f * 100) + '%';
      const v = Math.abs(th) < .005 ? 0 : th;
      q('#thv').textContent = fmt(v, 2);
      const [lab, cls] = H.sev(v); const s = q('#thsev'); s.className = 'chip ' + cls; s.innerHTML = '<i></i>' + lab;
      q('#thsub').textContent = `(${fmt(T[1], 2)} − ${fmt(med, 2)}) / ${fmt(f, 2)}² = ${fmt(v, 2)} K`;
    };
    const CAP = [
      [0, 'Montaj günü: üç kardeş aynı. Referans hazır; geçmiş gerekmez.'],
      [2, 'Sıcak hava dalgası: üçü birden +6,1 K. θ değişimi: sıfır.'],
      [6, 'Yük %67 → %95: Joule ısısı üçünde de I² ile artar, paydada sadeleşir.'],
      [10, 'Yalnız L2 ısınıyor: gevşek bağlantı. θ yükselir.'],
      [13.4, 'Yük değişse de θ aynı kalır: ΔT değişir, θ değişmez.'],
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
  notes: `Bizim cevabımız θ. Formül üstte: bir bağlantının sıcaklığından, kendi kardeşlerinin medyanını çıkarıyoruz ve sonucu anma akımına göre normalize ediyoruz — yani (I bölü I_ref) karesine bölüyoruz. Birimi kelvin: "bu bağlantı anma akımını taşısaydı, kardeşlerinden ne kadar sıcak olurdu?"

Kardeş ne demek? Aynı fiderin üç fazı: aynı akımı taşıyorlar, aynı havayı soluyorlar, yirmi milimetre arayla duruyorlar, aynı yaştalar. Renkler TEDAŞ'ın kablo renkleri: L1 gri, L2 siyah, L3 kahverengi.

Animasyonu izleyelim:
— Sıcak hava dalgası geliyor: üç faz birden 6,1 kelvin ısınıyor. Eşik sistemi burada alarm verirdi. θ ise kıpırdamıyor; çünkü hava üçüne birden aynı şeyi yapıyor ve fark sıfır kalıyor.
— Yük artıyor: Joule ısısı üçünde de akımın karesiyle artıyor. Paydaya I² koyduğumuz için bu da sadeleşiyor.
— Şimdi yalnız L2 ısınıyor. Gevşek bağlantı tam olarak budur: tek fazda fazla temas direnci. θ altı virgül otuz beş kelvine çıkıyor, Uyarı seviyesi.
— Ve en önemlisi: yük düşse de artsa da θ aynı kalıyor. Ham sıcaklık farkı değişiyor, θ değişmiyor. Ölçtüğümüz şey yük değil, bağlantının kendisi.

Üç şey sadeleşiyor: yük, mevsim ve güneş, IR tarafında yayıcılık. Ve geçmiş gerektirmiyor: montaj günü üç kardeş zaten birbirinin referansı. Bu yeni bir icat değil — termografi pratiğinin "benzer bileşene göre benzer yük altında ΔT" ölçütü. Fark şu: yılda bir müteahhit değil, dakikada bir sistem ölçüyor.`,
  use: `<b>Kullan:</b> Animasyon kendini döndürür (≈19 sn). Bir tur izletin; anlatımı alttaki başlığa göre senkronlayın. <b>Ezberlenecek:</b> (71,90 − 69,05) / 0,67² = 6,35 K · hava dalgasında ölçülen θ kayması 0,0000 K. <b>Jüri sorarsa — "Kalibrasyon?":</b> θ bir farktır; iki sensörün ortak sapması çıkar. Mutlak doğruluk yalnız 110/130 °C limitleri için gerekir, TMP117 fabrikada ±0,1 °C. <b>Dürüst sınır:</b> kabin havalandırması tıkanırsa kardeşler arasında tam sadeleşmez (ölçülen kayma ≤ 2,9 K); ayırt edici işaret her bağlantının birlikte yükselmesidir.`,
});

/* ===================================================================== */
/* 6 · DONANIM KİTİ — 9 CİHAZ                                             */
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
  <text x="20" y="40" font-size="30" fill="var(--dim)">çatı · 4 giriş sapması</text>
  <rect x="0" y="60" width="1300" height="340" fill="url(#pnh)" stroke="#2f4149" stroke-width="3"/>
  ${[0, 1, 2, 3].map(j => `<rect x="40" y="${115 + j * 70}" width="1220" height="${j === 3 ? 22 : 30}" rx="4" fill="${CAB[j]}" opacity=".55"/>`).join('')}
  <rect x="300" y="168" width="700" height="132" rx="14" fill="rgba(6,8,12,.9)" stroke="var(--kritik)" stroke-width="3"/>
  <text x="650" y="222" text-anchor="middle" font-size="42" font-weight="700" fill="var(--kritik)">Bara bölmesi: girilmez</text>
  <text x="650" y="270" text-anchor="middle" font-size="28" fill="var(--muted)">AG giriş kesicisi yok · Madde 2.2.10.2.vi</text>
  <rect x="0" y="400" width="1300" height="400" fill="#0b1118" stroke="#2f4149" stroke-width="3"/>`;
  for (let k = 0; k < 12; k++) {
    const x = cx(k) - 42, spare = k >= 10;
    s += `<rect x="${x}" y="420" width="84" height="360" rx="6" fill="${spare ? 'url(#pnh)' : '#121a24'}" stroke="#415a68" stroke-width="3"/>
    <text x="${cx(k)}" y="${spare ? 610 : 770}" text-anchor="middle" font-size="26" fill="var(--dim)">${spare ? 'yedek' : 'Ç' + (k + 1)}</text>`;
    if (!spare) s += [-24, 0, 24].map(o => `<rect x="${cx(k) + o - 8}" y="470" width="16" height="240" rx="6" fill="#1a2430" stroke="#2f4149" stroke-width="2"/>`).join('');
  }
  // sağ kolon
  const boxes = [[80, 200, 'TVOC-2 ark rölesi', 'id="pntv"'], [215, 335, 'MPR-53CS analizör', 'id="pnmp"'], [350, 440, 'Sayaç · CT 2500/5', ''], [455, 600, 'Modem bölmesi', ''], [615, 790, 'İç ihtiyaç · 10 A priz', '']];
  s += `<rect x="1300" y="60" width="300" height="740" fill="#0d131b" stroke="#2f4149" stroke-width="3"/>`;
  s += boxes.map(([a, b, t, id], i) => `<rect ${id} x="1316" y="${a}" width="268" height="${b - a}" rx="8" fill="#121a24" stroke="#415a68" stroke-width="3"/><text x="1450" y="${i === 3 ? a + 34 : i === 4 ? b - 22 : (a + b) / 2 + 10}" text-anchor="middle" font-size="27" fill="var(--muted)">${t}</text>`).join('');
  // alt kablo bölmesi
  s += `<rect x="0" y="800" width="1600" height="700" fill="#080c11" stroke="#2f4149" stroke-width="3"/>
  <text x="24" y="852" font-size="32" fill="var(--dim)">alt kablo bölmesi · en az 400 mm · taban açık</text>`;
  for (let k = 0; k < 12; k++) OFF.forEach((o, j) => {
    const x = cx(k) + o;
    if (k >= 10) { s += `<circle cx="${x}" cy="${Y(500)}" r="9" fill="none" stroke="#33414f" stroke-width="3" stroke-dasharray="4 4"/>`; return; }
    s += `<line x1="${x}" y1="${Y(500) + 10}" x2="${x}" y2="1500" stroke="${CAB[j]}" stroke-width="9"/>
      <circle cx="${x}" cy="${Y(500)}" r="11" fill="#cfd6de" stroke="#0b0f14" stroke-width="3" ${k === 6 && j === 1 ? 'id="pnhot"' : ''}/>`;
  });
  s += `<line x1="80" x2="1540" y1="${Y(230)}" y2="${Y(230)}" stroke="#35c07a" stroke-width="16"/><line x1="80" x2="1540" y1="${Y(230)}" y2="${Y(230)}" stroke="#f4d13a" stroke-width="16" stroke-dasharray="30 30"/>
  <text x="1560" y="${Y(230) - 24}" text-anchor="end" font-size="30" fill="var(--dim)">PE barası · M12</text>`;
  // adım 1: 6 × TC
  s += `<g data-step="1">${[5, 6].map(k => [0, 1, 2].map(j => `<rect x="${cx(k) + OFF[j] - 13}" y="${Y(430) - 26}" width="26" height="52" rx="6" fill="var(--brand)" stroke="#fff3" stroke-width="2"/>`).join('')).join('')}
    <path d="M${cx(6) + 30},${Y(430)} L1090,${Y(430) + 10}" stroke="var(--brand)" stroke-width="3" fill="none"/>
    <rect x="1090" y="${Y(430) - 22}" width="420" height="64" rx="12" fill="rgba(6,8,12,.94)" stroke="var(--brand)" stroke-width="3"/>
    <text x="1112" y="${Y(430) + 21}" font-size="36" font-weight="700" fill="var(--brand)">6 × TC ısıl kelepçe</text></g>`;
  // adım 2: TN-IR
  s += `<g data-step="2"><polygon points="640,${Y(160)} 140,${Y(500)} 1140,${Y(500)}" fill="url(#pnfov)"/>
    <rect x="600" y="${Y(150) - 18}" width="80" height="36" rx="7" fill="#1c2632" stroke="var(--brand)" stroke-width="4"/>
    <path d="M680,${Y(150)} L1090,${Y(150) + 82}" stroke="var(--brand)" stroke-width="3" fill="none"/>
    <rect x="1090" y="${Y(150) + 50}" width="380" height="64" rx="12" fill="rgba(6,8,12,.94)" stroke="var(--brand)" stroke-width="3"/>
    <text x="1112" y="${Y(150) + 93}" font-size="36" font-weight="700" fill="var(--brand)">TN-IR termal dizi</text></g>`;
  // adım 3: PD-01
  s += `<g data-step="3"><circle cx="1290" cy="${Y(230)}" r="34" fill="#1c2632" stroke="var(--brand)" stroke-width="5"/><circle cx="1290" cy="${Y(230)}" r="10" fill="var(--brand)"/>
    <rect x="1090" y="${Y(230) + 44}" width="380" height="64" rx="12" fill="rgba(6,8,12,.94)" stroke="var(--brand)" stroke-width="3"/>
    <text x="1112" y="${Y(230) + 87}" font-size="36" font-weight="700" fill="var(--brand)">PD-01 RF + ortam</text></g>`;
  // adım 4: GW-01 + radyo + RS-485
  const gx = 1450, gy = Y(980) + 10;
  s += `<g data-step="4"><rect x="${gx - 74}" y="${gy - 28}" width="148" height="64" rx="9" fill="#1c2632" stroke="var(--brand)" stroke-width="5"/>
    <text x="${gx}" y="${gy + 14}" text-anchor="middle" font-size="30" font-weight="700" fill="var(--brand)">GW-01</text>
    <path d="M${gx + 70},${gy - 20} h60 v-60" stroke="var(--brand)" stroke-width="5" fill="none"/><circle cx="${gx + 130}" cy="${gy - 86}" r="7" fill="var(--brand)"/>
    ${[[cx(5), Y(430)], [cx(6), Y(430)], [640, Y(150)], [1290, Y(230)]].map(([x, y]) => `<path class="rf" d="M${x},${y} Q${(x + gx) / 2 + 120},${(y + gy) / 2 + 60} ${gx},${gy + 36}" stroke="var(--izle)" stroke-width="5" fill="none"/>`).join('')}
    <path d="M${gx},${gy - 36} V200" stroke="var(--brand2)" stroke-width="6"/><path d="M${gx - 40},${gy - 36} V335" stroke="var(--brand2)" stroke-width="6" stroke-dasharray="14 8"/>
    <rect x="1322" y="${gy + 44}" width="256" height="42" rx="8" fill="rgba(6,8,12,.94)"/><text x="1450" y="${gy + 74}" text-anchor="middle" font-size="25" fill="var(--izle)">868 MHz · RS-485 ×2</text></g>`;
  s += `<circle cx="${cx(6) - 10}" cy="${Y(500)}" r="22" fill="none" stroke="var(--kritik)" stroke-width="5" class="pulse"/>`;
  return s + '</svg>';
}
add({
  title: 'Donanım: 9 cihazlık kit', section: 'Donanım', time: '60 sn',
  html: () => `${HD('03 · Donanım', 'Bir modül = bir pano = 9 cihaz.', '')}
<div class="body"><div class="row grow">
  <div class="card center" style="width:570px;padding:8px;--d:.15s" data-a="blur">${panelSVG()}</div>
  <div class="col grow kit">
    <div class="card tight kitrow" data-a="up" style="--d:.25s"><span class="kn">0</span><div><h3>Tek kural</h3><p class="sub">Delik delinmez, tip testli parça değişmez, bara bölmesine girilmez. Her montaj yüzeyini şartname zaten zorunlu kılıyor.</p></div></div>
    <div class="card tight kitrow" data-step="1"><span class="kn">6</span><div><h3>TC ısıl kelepçe · Ç6 ve Ç7</h3><p class="sub">TMP117 ±0,1 °C + kendi split-core CT'si. Kablo kılıfına geçer, iki üçlü = iki kardeş kümesi.</p></div></div>
    <div class="card tight kitrow" data-step="2"><span class="kn">1</span><div><h3>TN-IR termal dizi</h3><p class="sub">MLX90640 32×24, 110° lens, mıknatıs kaide. Kalan 34 pabucu yukarıdan görür. Madde 2.2.1.vi: galvaniz sac, mıknatıs tutar.</p></div></div>
    <div class="card tight kitrow" data-step="3"><span class="kn">1</span><div><h3>PD-01 RF ve ortam düğümü</h3><p class="sub">HFCT (yalnız PE'ye) + TEV + 40 kHz ultrasonik + SHT41 nem. Madde 2.2.6.2.iii'nin M12 saplamasına.</p></div></div>
    <div class="card tight kitrow" data-step="4"><span class="kn">1</span><div><h3>GW-01 ağ geçidi</h3><p class="sub">Ölçü kolonunda DIN ray, mevcut 10 A prizden beslenir. TVOC-2 ve MPR-53CS'i iki ayrı RS-485 hattından okur.</p></div></div>
  </div>
</div></div>`,
  notes: `"En az 100 modül" ifadesini şartname tanımlamıyor; biz tanımladık: bir modül, bir enstrümante edilmiş pano demek ve dokuz cihazdan oluşuyor. Bu sayı kodda sabit; dijital ikizde nokta sayan jüri üyesi ile malzeme listesinde satır sayan satın almacı aynı sayıyı bulur.

Önce tek kural: hiçbir delik delinmiyor, tip testli hiçbir parça değişmiyor ve bara bölmesine girilmiyor. Neden? Bu panoda AG giriş kesicisi yok. Bara bölmesini enerjisiz yapmak, bütün dağıtım merkezini OG tarafından karartmak demek. O yüzden kit yalnız alt kablo bölmesine, ölçü kolonuna ve mevcut prize dokunuyor.

[→] Altı ısıl kelepçe: Çıkış 6 ve 7'nin üç fazına. Her biri TMP117 sıcaklık sensörü ve kendi ayrılabilir akım trafosunu taşıyor — çünkü çıkışlarda dağıtım şirketinin CT'si yok. İkişer üçlü olmalarının sebebi θ: medyan alabilmek için en az üç kardeş gerekiyor.

[→] Bir termal dizi: bölme tabanına mıknatısla oturuyor ve yukarı bakıyor. Kalan otuz dört pabucu görüyor. Mıknatıs tutuyor çünkü şartname pano içinin boyasız galvaniz sac olmasını zorunlu kılıyor.

[→] RF ve ortam düğümü: şartnamenin zorunlu kıldığı M12 topraklama saplamasında. Kısmi deşarj göstergesi ve nemi ölçüyor. HFCT asla faz iletkenine değil, yalnız koruma iletkenine takılıyor.

[→] Ve ağ geçidi: ölçü kolonunda DIN rayda, şartnamenin zaten istediği 10 amperlik prizden besleniyor. Panoda zaten bulunan ABB TVOC-2 ark rölesini ve Entes MPR-53CS analizörünü iki ayrı RS-485 hattından okuyor, sensörlerden 868 MHz ile veri topluyor.

Kırmızı halka, kapaktaki o pabuç: Çıkış 7, L2.`,
  use: `<b>Kullan:</b> 4 adım: kelepçeler → termal dizi → PD-01 → ağ geçidi. Her adımda sağdaki satır açılır. <b>Ezberlenecek:</b> 9 cihaz · 74 cıvatalı bağlantı modellendi · 40'ı ölçülüyor · 34 pabuç yalnız IR ile · bara bölmesinin 30 + çatının 4 bağlantısı izlenmez ve ekranda gri. <b>Jüri sorarsa — "Neden bara bölmesine koymuyorsunuz?":</b> AG giriş kesicisi yok (Madde 2.2.10.2.vi); enerjisiz yapmak dağıtım merkezini karartmak demek. <b>"Yükü nereden biliyorsunuz?":</b> her kelepçe kendi CT'sini taşır; 34 IR-only pabuçta yük analizörden orantısal pay ile kestirilir ve ekranda öyle etiketlenir.`,
});

/* ===================================================================== */
/* 7 · ELEKTRONİK VE FİRMWARE                                             */
/* ===================================================================== */
function fwSVG() {
  const cx = 190, cy = 190, r = 118;
  const loop = ['SAMPLE', 'AGGREGATE', 'TX', 'SLEEP'];
  const pos = i => { const a = -Math.PI / 2 + i * Math.PI / 2; return [cx + r * Math.cos(a), cy + r * Math.sin(a)]; };
  return `<svg viewBox="0 36 380 356" class="fwsvg">
   <circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="var(--line2)" stroke-width="2" stroke-dasharray="4 6"/>
   <path id="fwp" d="M${cx},${cy - r} a${r},${r} 0 1,1 -0.01,0" fill="none"/>
   <circle r="7" fill="var(--brand)"><animateMotion dur="6s" repeatCount="indefinite" rotate="auto"><mpath href="#fwp"/></animateMotion></circle>
   ${loop.map((n, i) => { const [x, y] = pos(i); return `<g class="fwst" style="--i:${i}"><rect x="${x - 52}" y="${y - 17}" width="104" height="34" rx="17" fill="#0e141c" stroke="var(--line2)" stroke-width="1.5"/><text x="${x}" y="${y + 5}" text-anchor="middle" class="mono" font-size="12.5" font-weight="600" fill="var(--ink)">${n}</text></g>`; }).join('')}
   <text x="${cx}" y="${cy - 8}" text-anchor="middle" font-size="14" font-weight="700" fill="var(--ink)">C99 · STM32WLE5</text>
   <text x="${cx}" y="${cy + 14}" text-anchor="middle" font-size="12.5" fill="var(--muted)">float yok · malloc yok</text>
   <text x="${cx}" y="${cy + 32}" text-anchor="middle" font-size="12.5" fill="var(--muted)">θ uçta, sabit noktada</text>
   <text x="10" y="356" class="mono" font-size="11" fill="var(--dim)">COLD_START → SELF_TEST → PROVISION → döngü</text>
   <text x="10" y="380" class="mono" font-size="11" fill="var(--uyari)">DE_ENERGISED · LOW_BATTERY birinci sınıf durum</text>
  </svg>`;
}
const BOARD = (code, n, ttl, rows, d) => `<div class="card tight board" data-a="up" style="--d:${d}s">
  <div class="bh"><span class="mono bc">${code}</span><span class="chip brand">×${n}</span></div><h3>${ttl}</h3>
  <ul>${rows.map(r => `<li>${r}</li>`).join('')}</ul></div>`;
add({
  title: 'Elektronik ve firmware', section: 'Donanım', time: '40 sn',
  html: () => `${HD('03 · Donanım', 'Dört kart, tek firmware.')}
<div class="body"><div class="row grow">
  <div class="col grow"><div class="g2" style="align-content:start">
    ${BOARD('PANOGOZ-TC-A1', 6, 'Isıl kelepçe', ['STM32WLE5CC · 868 MHz', 'TMP117 ±0,1 °C, ısıl ada', 'Split-core CT 3000:1 (400 A)', 'ER14250 + HLC1550 pil'], .15)}
    ${BOARD('PANOGOZ-IR-A1', 1, 'Termal dizi', ['MLX90640 32×24, 110° lens', 'SHT41 bölme havası ve nem', 'Nişan kilidi: 3 referans vida', 'ER14505 Li-SOCl₂'], .25)}
    ${BOARD('PANOGOZ-PD-A1', 1, 'RF ve ortam', ['HFCT yalnız PE · 1–3 MHz YGF', 'TEV plakası + 40 kHz alıcı', 'SHT41 · çiy noktası payı', 'pC eşdeğeri; IEC 60270 değil'], .35)}
    ${BOARD('PANOGOZ-GW-A1', 1, 'Ağ geçidi', ['STM32H563 · SX1262 · EC21-E LTE', '2 × izole RS-485 (ADM2587E)', '20 000 çerçeve QSPI tampon', '2 × 10 F süperkap: 8 sn son nefes'], .45)}
  </div>
  <div class="card tight grow cadc" data-a="up" style="--d:.6s"><p class="cap">Isıl kelepçe pil bütçesi · ER14250 · hesap, tezgâh ölçümü değil</p>
    <div class="cad">
      <div><span>IDLE · 900 s</span><b>6,89 µA</b><small>16,9 yıl</small></div>
      <div><span>WATCH · 60 s</span><b>42,15 µA</b><small>2,8 yıl</small></div>
      <div><span>BURST · 10 s</span><b>231 µA</b><small>0,5 yıl</small></div>
      <div class="mix"><span>Görev karması %97 / 2,5 / 0,5</span><b>8,89 µA → 13,1 yıl</b><small>öz deşarj dahil · en kısası PD-01: ≈ 8,4 yıl</small></div>
    </div></div></div>
  <div class="col" style="width:380px">
    <div class="card" style="padding:6px 8px;--d:.3s" data-a="blur">${fwSVG()}</div>
    <div class="card tight" data-a="up" style="--d:.55s"><p class="cap">Modül donanımı</p><div class="bom"><div><b data-count="470.59" data-dec="2" data-pre="€" style="--d:.7s">€0</b><span>1000 adet</span></div><div><b data-count="660.91" data-dec="2" data-pre="€" style="--d:.8s">€0</b><span>100 adet</span></div></div>
      <div class="row" style="gap:6px;flex-wrap:wrap;margin-top:10px"><span class="chip">−25…+70 °C</span><span class="chip">IP65</span><span class="chip">yoğuşmalı nem</span><span class="chip">IPC-CC-830B</span></div></div>
  </div>
</div></div>`,
  notes: `Dört kart tasarladık. Altı adet ısıl kelepçe, bir termal dizi, bir RF ve ortam düğümü, bir ağ geçidi. Sensör düğümleri STM32WLE5 üzerinde: mikrodenetleyici ile 868 MHz radyo aynı yongada, tek pille yıllarca çalışacak şekilde.

Ağ geçidi STM32H563 tabanlı: sensörleri radyodan topluyor, panodaki ark rölesini ve analizörü iki ayrı izole RS-485 hattından okuyor, LTE ile sunucuya çıkıyor. Bağlantı koparsa yirmi bin çerçeveyi tamponda tutuyor; elektrik kesilirse süperkapasitörle sekiz saniyelik bir "son nefes" bütçesi var — son mesajı gönderip düzgün kapanmak için.

Firmware C99 ile yazıldı: tek bir float yok, malloc yok. θ'nın kestiricisi uç düğümde sabit noktada çalışıyor. Ve önemli bir tasarım kararı: "pano enerjisiz" ve "pil zayıf" hata yolu değil, birinci sınıf durumlar. Enerjisiz bir panoda soğuk bir okumayı "her şey yolunda" gibi yayınlamak yerine düğüm durumu söylüyor.

Alttaki şerit kelepçenin pil bütçesi, firmware'in kendi güç tablosundan. Sağlıklı panoda düğüm on beş dakikada bir uyanıyor, şüphede dakikada bir, olay anında on saniyede bir. Bu karışımla ortalama 8,89 mikroamper, öz deşarj dahil 13,1 yıl. Bandı saklamıyoruz: gerçekten bozulan bir bağlantıyı aylarca izleyen düğüm üç yıl dolmadan biter — o bağlantıyla birlikte zaten değişir. Filoda en kısa ömürlü düğüm PD-01, yaklaşık 8,4 yıl. Hepsi hesap; tezgâhta ölçülmedi.

Çevresel zarfı şartnamenin −5/+40'ına değil, sahanın gerçeğine göre kurduk: −25 ile +70 derece, IP65 gövde, yoğuşmalı nem için koruyucu kaplama. Bara yüzeyindeki 14,5 militeslalık manyetik alanı hesapladık; kitin hiçbir parçası orada değil.

Modül donanımı bin adette 470 euro, yüz adette 660 euro.`,
  use: `<b>Kullan:</b> Kartlar sırayla açılır; firmware halkası sürekli döner. <b>Dürüst sınır:</b> KiCad şematik/PCB <b>çizilmedi</b>; blok şema, I/O tablosu, pin dizilimi, katman yığını ve BOM düzeyinde belgelendi (docs/03). Sorulursa saklamayın. Pil ömrü 8,4–16 yıl <b>hesaplandı, tezgâhta ölçülmedi</b>. <b>Jüri sorarsa — "Manyetik alan?":</b> bara yüzeyi ~14,5 mT, kelepçenin kendi damarı 5,3 mT, diğer cihazlar < 0,25 mT; NdFeB kaide etkilenmez, HFCT faz iletkenine takılmaz (6 mV/A kaçak).`,
});

/* ===================================================================== */
/* 8 · UÇTAN UCA MİMARİ                                                   */
/* ===================================================================== */
function archSVG() {
  const box = (x, y, w, h, t, sub, col = 'var(--line2)', extra = '') => `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="12" fill="#0d131b" stroke="${col}" stroke-width="1.6" ${extra}/>
    <text x="${x + 14}" y="${y + 24}" font-size="14.5" font-weight="700" fill="var(--ink)">${t}</text>${sub ? `<text x="${x + 14}" y="${y + 43}" font-size="11.5" fill="var(--muted)">${sub}</text>` : ''}`;
  const pk = (id, d, dur, n, col) => `<path id="${id}" d="${d}" fill="none" stroke="${col}" stroke-opacity=".45" stroke-width="2"/>` +
    Array.from({ length: n }, (_, i) => `<circle r="4" fill="${col}"><animateMotion dur="${dur}s" begin="-${(i * dur / n).toFixed(2)}s" repeatCount="indefinite"><mpath href="#${id}"/></animateMotion></circle>`).join('');
  const dev = [['6 × TC kelepçe', '868 MHz'], ['TN-IR dizi', '868 MHz'], ['PD-01 RF/ortam', '868 MHz'], ['TVOC-2 ark rölesi', 'RS-485 · mevcut'], ['MPR-53CS analizör', 'RS-485 · mevcut']];
  const srv = [['Mesaj yolu', 'Mosquitto · süreç-içi bus'], ['Toplama', 'zarf, sıra boşluğu, aralık'], ['Depo', 'SQLite · taşınabilir şema'], ['Dedektör', 'θ · RLS · CUSUM · değişim noktası'], ['Kurallar', 'bastırma → füzyon → alarm']];
  return `<svg viewBox="0 0 1160 470" class="archsvg">
  <g data-step="0">
    <rect x="0" y="16" width="214" height="446" rx="14" fill="none" stroke="var(--line2)" stroke-dasharray="5 5"/>
    <text x="14" y="40" class="mono" font-size="11" fill="var(--brand)">PANO · 1 MODÜL</text>
    ${dev.map(([a, b], i) => `<rect x="12" y="${56 + i * 80}" width="190" height="62" rx="10" fill="#0d131b" stroke="${i < 3 ? 'var(--brand)' : 'var(--line2)'}"/>
      <text x="26" y="${82 + i * 80}" font-size="14" font-weight="600" fill="var(--ink)">${a}</text><text x="26" y="${102 + i * 80}" class="mono" font-size="11" fill="var(--muted)">${b}</text>`).join('')}
    ${dev.map((_, i) => pk('ap' + i, `M202,${87 + i * 80} C250,${87 + i * 80} 250,240 292,240`, 2.2 + i * .25, 2, i < 3 ? 'var(--izle)' : 'var(--brand2)')).join('')}
    ${box(292, 168, 168, 148, 'GW-01', 'ağ geçidi · DIN ray', 'var(--brand)')}
    <text x="306" y="234" font-size="11.5" fill="var(--muted)">yerel kurallar:</text>
    <text x="306" y="252" class="mono" font-size="10.5" fill="var(--ink)">≥90 °C · Δ≥20 K · ark</text>
    <text x="306" y="276" font-size="11.5" fill="var(--muted)">bağlantı koparsa:</text>
    <text x="306" y="294" class="mono" font-size="11" fill="var(--ink)">20 000 çerçeve tampon</text>
  </g>
  <g data-step="1">
    ${pk('bp', 'M460,242 L548,242', 1.4, 3, 'var(--brand)')}
    <text x="504" y="228" text-anchor="middle" class="mono" font-size="10.5" fill="var(--brand2)">MQTT 5 · TLS</text><text x="504" y="266" text-anchor="middle" class="mono" font-size="10.5" fill="var(--brand2)">QoS 1 · S&amp;F</text>
    <rect x="548" y="16" width="330" height="446" rx="14" fill="rgba(74,163,255,.04)" stroke="var(--izle)" stroke-dasharray="6 5"/>
    <text x="564" y="40" class="mono" font-size="11" fill="var(--izle)">DAĞITIM ŞİRKETİ SUNUCU ODASI</text>
    <g transform="translate(838,22)" color="var(--ok)">${IC.cloudx.replace('class="ic"', 'width="22" height="22"')}</g>
    ${srv.map(([a, b], i) => `${box(566, 54 + i * 80, 294, 60, a, b)}${i < 4 ? `<path d="M713,${114 + i * 80} v20" stroke="var(--izle)" stroke-width="2" marker-end="url(#aa)"/>` : ''}`).join('')}
    <defs><marker id="aa" viewBox="0 0 10 10" refX="5" refY="8" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,0 L5,9 z" fill="var(--izle)" transform="rotate(-90 5 5)"/></marker></defs>
  </g>
  <g data-step="2">
    ${pk('o1', 'M878,392 C910,392 910,90 950,90', 2.4, 2, 'var(--ok)')}
    ${pk('o2', 'M878,392 C915,392 915,240 950,240', 2, 2, 'var(--ok)')}
    ${pk('o3', 'M878,392 C920,392 920,390 950,390', 1.6, 2, 'var(--kritik)')}
    ${box(950, 46, 210, 92, 'İzleme arayüzü', 'REST + WebSocket · 1 Hz', 'var(--ok)')}<text x="964" y="124" font-size="11.5" fill="var(--muted)">dijital ikiz, kanıt, bastırılanlar</text>
    ${box(950, 196, 210, 92, 'SCADA / DMS', 'Modbus TCP · salt okunur', 'var(--ok)')}<text x="964" y="274" font-size="11.5" fill="var(--muted)">48 register / pano · ICD v2.0</text>
    ${box(950, 346, 210, 92, 'Bildirim', 'SMS (UCS-2) + sesli arama', 'var(--kritik)')}<text x="964" y="424" font-size="11.5" fill="var(--muted)">vardiya merdiveni · onay kodu</text>
  </g>
</svg>`;
}
add({
  title: 'Uçtan uca mimari', section: 'Mimari', time: '50 sn',
  html: () => `${HD('04 · Mimari', 'Sensörden SCADA register\'ına tek zincir. Kamu bulutu yok.')}
<div class="body"><div class="grow center">${archSVG()}</div>
<div class="row" style="gap:10px" data-step="2"><span class="chip ok">${IC.lock} Tek yön: panoya komut veren hiçbir yol yok</span><span class="chip">Her sayı tek yerde tanımlı: ekran = register</span><span class="chip">Tek komutla çalışır · internet gerekmez</span></div></div>`,
  notes: `Uçtan uca mimari. Soldan başlayalım.

Panoda dokuz cihaz. Kelepçeler, termal dizi ve RF düğümü 868 MHz ile ağ geçidine konuşuyor. Panoda zaten bulunan ark rölesi ve analizör ise RS-485 Modbus ile okunuyor. Ağ geçidi aptal bir köprü değil: sunucuya giden yol kopsa bile üç kural yerelde çalışıyor — herhangi bir bağlantı 90 dereceyi geçerse, kardeş farkı 20 kelvini geçerse ve ark açması olursa. Bağlantı yokken yirmi bin çerçeveyi tamponda tutuyor ve sessizce kaybetmiyor.

[→] Ağ geçidinden sunucuya MQTT 5, TLS, QoS 1 ve store-and-forward. Bir çerçeve, broker'dan onay gelene kadar tampondan silinmiyor. Sunucu dağıtım şirketinin kendi sunucu odasında: kamu bulutu yok — ne hesaplama, ne depolama, ne bildirim. İçeride sıra sabit: toplama, depo, dedektör, kurallar.

[→] Üç çıkış. İzleme arayüzü. SCADA için Modbus TCP — istisnasız salt okunur. Ve bildirim: SMS ve sesli arama, onay koduyla.

Mimarinin taşıyıcı fikri: her sayı tek bir yerde tanımlı. Ekranda gördüğünüz değer ile SCADA register'ındaki değer aynı nesneden üretiliyor, dolayısıyla çelişemezler. Ve akış tek yönlü: sistemin hiçbir yerinde panoya komut veren bir yol yok.`,
  use: `<b>Kullan:</b> 3 adım: pano + ağ geçidi → sunucu odası → çıkışlar. <b>Neden Sparkplug B değil? (sorulursa):</b> Sparkplug 3.0 DDATA için QoS 0'ı zorunlu kılar; bizim dayanıklılığımız PUBACK ile ilerleyen tampon filigranına dayanır. Doğum/vasiyet/sıra numarası fikirlerini aldık, markayı bıraktık. <b>Dürüst sınır:</b> demo süreç-içi bus ve SQLite ile çalışır; TimescaleDB hedeflenen üretim yoludur ve <b>yazılmadı</b>. mTLS/ACL tasarlandı, saha sertifikalarıyla denenmedi. <b>Ezberlenecek:</b> 100 pano = 15 zarf/s · 200 nokta/s · ≈ 18 GB kararlı disk.`,
});

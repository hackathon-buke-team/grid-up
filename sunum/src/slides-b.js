/* ======================================================================
   SLAYTLAR 9–16 · yöntem, alarm, entegrasyon, canlı demo
   ====================================================================== */

/* ===================================================================== */
/* 9 · TESPİT ZİNCİRİ                                                     */
/* ===================================================================== */
function chainSVG() {
  const N = [
    ['Ölçüm', 'T · TMP117 / IR', 'I · kelepçe CT'],
    ['Kardeş farkı', 'T − medyan', 'kendisi hariç'],
    ['θ kestirimi', 'RLS, ileri model', 'dekonvolüsyon yok'],
    ['Günlük medyan', '', ''],
    ['Bastırma', 'şebeke · hava · yük', 'cihaz · öğrenme'],
    ['Füzyon', '26 kanıt, 6 aile', '7 arıza modu'],
    ['Alarm', '3/5 gün · %40 hist.', '2 aile = ekip'],
  ];
  const w = 140, g = 23, y = 40, h = 104;
  const x = i => 4 + i * (w + g);
  return `<svg viewBox="0 0 1160 190" class="chainsvg">
   <path id="chp" d="M${x(0) + 10},${y + h / 2} H${x(6) + w - 10}" stroke="var(--line2)" stroke-width="2" fill="none"/>
   ${[0, 1, 2].map(k => `<circle r="5" fill="var(--brand)" filter="drop-shadow(0 0 6px #f78320)"><animateMotion dur="4.5s" begin="-${k * 1.5}s" repeatCount="indefinite"><mpath href="#chp"/></animateMotion></circle>`).join('')}
   ${N.map(([a, b, c], i) => `<g class="chn" style="--i:${i};--d:${.1 + i * .08}s" data-a="up">
     <rect x="${x(i)}" y="${y}" width="${w}" height="${h}" rx="12" fill="#0d131b" stroke="${i === 2 ? 'var(--olcum)' : i === 4 ? 'var(--izle)' : i === 6 ? 'var(--kritik)' : 'var(--line2)'}" stroke-width="1.6"/>
     <text x="${x(i) + 14}" y="${y + 28}" font-size="15" font-weight="700" fill="var(--ink)">${a}</text>
     ${i === 3 ? ['CUSUM · h = 8', 'Değişim noktası', 'Theil-Sen eğim'].map((t, j) => `<rect x="${x(i) + 10}" y="${y + 40 + j * 20}" width="${w - 20}" height="16" rx="8" fill="rgba(255,234,70,.08)" stroke="rgba(255,234,70,.3)"/><text x="${x(i) + 18}" y="${y + 52 + j * 20}" class="mono" font-size="9.5" fill="var(--olcum)">${t}</text>`).join('')
      : `<text x="${x(i) + 14}" y="${y + 56}" font-size="12" fill="var(--muted)">${b}</text><text x="${x(i) + 14}" y="${y + 75}" font-size="12" fill="var(--muted)">${c}</text>`}
     <text x="${x(i) + 14}" y="${y + h + 22}" class="mono" font-size="10.5" fill="var(--dim)">${['dakikada bir', 'fider içinde', 'K, anma akımında', 'gün ölçeği', 'Türkçe gerekçe', 'tavanlı LLR', 'SMS · SCADA'][i]}</text>
   </g>`).join('')}
  </svg>`;
}
const MODES = [['Gevşek bağlantı', .30, 'tork anahtarıyla yeniden sık'], ['Aşırı yük', .15, 'yük profili, fider dengeleme'], ['Ark koruma bütünlüğü', .15, 'dedektör ve otokontrol'], ['Isıl kaçış / soğutma', .10, 'menfez ve filtreler'], ['Harmonik nötr', .10, '3. harmoniği ölç'], ['Nem / yoğuşma', .10, 'kanal sızdırmazlığı'], ['Yalıtım zayıflaması', .10, 'PD trendi, planlı ölçüm']];
add({
  title: 'Tespit zinciri', section: 'Yöntem', time: '50 sn',
  html: () => `${HD('05 · Yöntem', 'Her kutunun bir birimi var; hiçbiri eğitim verisi istemez.')}
<div class="body">
  ${chainSVG()}
  <div class="row grow">
    <div class="card grow" data-step="1"><p class="cap">7 arıza modu · sağlık endeksi tam ayrışır</p>
      <div class="modes">${MODES.map(([n, w, a], i) => `<div class="md"><span class="mn">${n}</span><span class="mb"><i style="width:${w / .3 * 100}%;--d:${.1 + i * .07}s" data-a="grow-x"></i></span><span class="mono mw">${fmt(w, 2)}</span><span class="ma">${a}</span></div>`).join('')}</div>
      <p class="mono hi">HI = 100 · Π (1 − r<sub>m</sub>)<sup>w<sub>m</sub></sup> → ln(HI/100) = Σ w<sub>m</sub> · ln(1 − r<sub>m</sub>)</p></div>
    <div class="card" style="width:420px" data-step="2"><p class="cap">Bilerek kullanmadıklarımız</p>
      <div class="rej">
        <div>${IC.x}<span><b>Pano başına LSTM / otokodlayıcı</b> Kayan pencerede 0,2 K/hafta sürüklenmeyi normal diye öğrenir: yapısal körlük.</span></div>
        <div>${IC.x}<span><b>One-class SVM</b> Kalibre skor yok; "−0,37" bir bakım mühendisine bir şey söylemez.</span></div>
        <div>${IC.x}<span><b>Ham sıcaklıkta kümeleme</b> Denedik: kümeler mevsimi buldu, arızayı değil.</span></div>
        <div>${IC.x}<span><b>Tek karar olarak sabit eşik</b> Mutlak limitler kalır (90/110/130 °C), tek karar olmaz.</span></div>
      </div></div>
  </div>
</div>`,
  notes: `Tespit zinciri soldan sağa. Ölçüm dakikada bir geliyor: sıcaklık ve akım. Kardeş farkını alıyoruz — kritik bir ayrıntı: medyan bağlantının kendisi hariç, yalnız kardeşleri üzerinden alınıyor. Kendini de içeren bir medyan, kusurlu faz bir kardeşini geçtiği anda sessizce ona atlar ve sinyalin yüzde kırkını yer.

θ'yı bir ileri modelin içinden, özyinelemeli en küçük kareler ile kestiriyoruz; çünkü bir bağlantı bir direnç değil, ısıl bir kütle — yük değiştiğinde sıcaklığı dakikalar sonra yetişir. Dekonvolüsyon gürültüyü büyütür; o yüzden yapmıyoruz.

Sonra zaman ölçeği değişiyor: günlük medyanlar. Avladığımız sinyal haftada 0,2 kelvin; doğru örnekleme adımı gün. Üzerinde üç araç: CUSUM sürüklenmeyi, değişim noktası başlangıç tarihini, Theil-Sen eğimi veriyor.

Sonra bastırma, sonra füzyon, sonra alarm. Sıra sabit: açıklanabilen kanıt hiç olasılığa girmiyor.

[→] Füzyon yedi arıza moduna risk veriyor ve sağlık endeksi bu risklerin ağırlıklı çarpımı. Logaritmasını aldığınızda tam ayrışıyor: "sağlık 67" dediğimizde, eksik 33 puanın hangi moddan geldiğini sezgisel bir atıf olmadan söyleyebiliyoruz.

[→] Ve bilerek kullanmadıklarımız. En çok sorulan: "Yapay zekâ nerede?" Kayan pencerede eğitilen bir otokodlayıcı, haftada 0,2 kelvinlik yavaş sürüklenmeyi normalin parçası olarak öğrenir ve yeniden üretir. Yani tam avladığımız sinyale yapısal olarak kördür. Üstelik aylarca temiz geçmiş ister — elimizde yok — ve yüz panoya yüz model demek. Bizim yöntemimizin her çıktısının birimi var: kelvin, mikroohm, gün.`,
  use: `<b>Kullan:</b> Adım 1: yedi mod; adım 2: reddedilen yöntemler. Akış çizgisindeki turuncu nokta zinciri dolaşır. <b>Ezberlenecek:</b> CUSUM k = 0,5 · h = 8 (otokorelasyon cezası yüzünden 4–5 değil) · ARL0 ≈ 19 112 gün = bağlantı başına 52,3 yıl · filo: 100 pano × 40 bağlantıda 4,8 günde bir yanlış CUSUM geçişi — ama alarm üç şartı birden ister (CUSUM > 8 VE θ ≥ 5 K VE son 5 günün 3'ü). <b>Dürüst sınır:</b> Naive Bayes ilişkili kanıtı fazla sayar; aile tavanı tek sensörlü bulguyu Uyarı'da tutar, ekip yönlendirmez.`,
});

/* ===================================================================== */
/* 10 · HAFTALAR ÖNCE: TARİH VE UFUK                                      */
/* ===================================================================== */
function trendSVG() {
  const X = H.sc(-45, 20, 70, 1130), Y = H.sc(0, 28, 330, 24);
  const r = H.rng(11), pts = [];
  for (let d = -45; d <= 0; d++) {
    const th = d < -22 ? 2 + (d + 45) * .2 : 6.6 + (d + 22) * .5;
    pts.push([X(d), Y(Math.max(.4, th + (r() - .5) * .9))]);
  }
  const TH = [[2, 'İzle', 'izle'], [5, 'Uyarı', 'uyari'], [12, 'Kritik', 'kritik'], [25, 'Acil', 'acil']];
  const days = [[-45, '19 Ağu'], [-30, '3 Eyl'], [-22, '11 Eyl'], [-11, '22 Eyl'], [0, 'bugün'], [15, '18 Eki']];
  const fan = `${X(0)},${Y(17.6)} ${X(20)},${Y(Math.min(28, 17.6 + 20 * .563))} ${X(20)},${Y(17.6 + 20 * .397)}`;
  return `<svg viewBox="0 0 1160 380" class="trsvg">
   ${TH.map(([v, l, c]) => `<line x1="70" x2="1130" y1="${Y(v)}" y2="${Y(v)}" stroke="var(--${c})" stroke-opacity=".55" stroke-dasharray="6 6"/><text x="64" y="${Y(v) + 4}" text-anchor="end" class="mono" font-size="11" fill="var(--${c})">${l} ${v}</text>`).join('')}
   <line x1="70" x2="1130" y1="${Y(0)}" y2="${Y(0)}" stroke="var(--line2)"/>
   ${days.map(([d, t]) => `<text x="${X(d)}" y="352" text-anchor="middle" class="mono" font-size="11" fill="${d === 0 ? 'var(--ink)' : 'var(--dim)'}">${t}</text>`).join('')}
   <line x1="${X(0)}" x2="${X(0)}" y1="20" y2="330" stroke="var(--line2)"/>
   <text x="${X(0) + 6}" y="34" font-size="11" fill="var(--muted)">bugün</text>
   <text x="70" y="14" class="mono" font-size="11" fill="var(--dim)">θ günlük medyan · K · SOKE-14 / Ç7-L2</text>
   <g data-step="2"><rect x="${X(-29)}" y="20" width="${X(-15) - X(-29)}" height="310" fill="rgba(255,47,121,.07)"/>
     <line x1="${X(-22)}" x2="${X(-22)}" y1="20" y2="330" stroke="var(--acil)" stroke-width="2" stroke-dasharray="5 4"/>
     <rect x="${X(-22) + 8}" y="40" width="226" height="48" rx="9" fill="rgba(6,8,12,.92)" stroke="var(--acil)"/>
     <text x="${X(-22) + 20}" y="60" font-size="13.5" font-weight="700" fill="var(--acil)">Değişim noktası · 11 Eylül</text>
     <text x="${X(-22) + 20}" y="78" font-size="11.5" fill="var(--muted)">ikili bölütleme + BIC · tarih bir aralık</text></g>
   <path d="${H.smooth(pts)}" fill="none" stroke="var(--olcum)" stroke-width="3.2" data-a="draw" style="--d:.3s;--dur:2.2s"/>
   <circle cx="${X(0)}" cy="${Y(17.6)}" r="6" fill="var(--olcum)" data-a="pop" style="--d:2.4s"/>
   <text x="${X(0) - 10}" y="${Y(17.6) - 12}" text-anchor="end" class="mono" font-size="13" font-weight="700" fill="var(--olcum)" data-a="fade" style="--d:2.5s">17,6 K</text>
   <g data-step="1">
     <circle cx="${X(-27)}" cy="${Y(5.6)}" r="7" fill="none" stroke="var(--uyari)" stroke-width="2.5"/>
     <rect x="${X(-27) - 100}" y="${Y(5.6) + 16}" width="200" height="44" rx="9" fill="rgba(6,8,12,.92)" stroke="var(--uyari)"/>
     <text x="${X(-27)}" y="${Y(5.6) + 35}" text-anchor="middle" font-size="12.5" font-weight="700" fill="var(--uyari)">Uyarı · iş emri açıldı</text>
     <text x="${X(-27)}" y="${Y(5.6) + 52}" text-anchor="middle" class="mono" font-size="10.5" fill="var(--muted)">CUSUM > 8 · θ ≥ 5 K · 3/5 gün</text>
     <circle cx="${X(-11)}" cy="${Y(12.1)}" r="7" fill="none" stroke="var(--kritik)" stroke-width="2.5"/>
     <rect x="${X(-11) - 96}" y="${Y(12.1) + 16}" width="192" height="44" rx="9" fill="rgba(6,8,12,.92)" stroke="var(--kritik)"/>
     <text x="${X(-11)}" y="${Y(12.1) + 35}" text-anchor="middle" font-size="12.5" font-weight="700" fill="var(--kritik)">Kritik · SMS nöbetçiye</text>
     <text x="${X(-11)}" y="${Y(12.1) + 52}" text-anchor="middle" class="mono" font-size="10.5" fill="var(--muted)">iki sensör ailesi hemfikir</text></g>
   <g data-step="3"><polygon points="${fan}" fill="rgba(255,47,121,.16)"/>
     <line x1="${X(0)}" y1="${Y(17.6)}" x2="${X(14.8)}" y2="${Y(25)}" stroke="var(--acil)" stroke-width="2.5" stroke-dasharray="7 5"/>
     <circle cx="${X(14.8)}" cy="${Y(25)}" r="6" fill="var(--acil)"/>
     <rect x="${X(1.5)}" y="${Y(17.6) + 26}" width="232" height="50" rx="10" fill="rgba(6,8,12,.94)" stroke="var(--acil)"/>
     <text x="${X(1.5) + 12}" y="${Y(17.6) + 48}" font-size="15" font-weight="700" fill="var(--acil)">ACİL'e ~15 gün (13–19)</text>
     <text x="${X(1.5) + 12}" y="${Y(17.6) + 67}" class="mono" font-size="10.5" fill="var(--muted)">+3,5 K/hf · %90 GA 2,8–3,9</text></g>
  </svg>`;
}
add({
  title: 'Haftalar önce: tarih ve ufuk', section: 'Yöntem', time: '60 sn',
  html: () => `${HD('05 · Yöntem', 'Ne zaman başladı, ne kadar vaktimiz var?')}
<div class="body"><div class="card grow" style="padding:10px 14px;--d:.1s" data-a="blur">${trendSVG()}</div>
<div class="row" style="gap:10px;flex-wrap:wrap">
  <span class="chip izle" data-step="1">Geriye bakan yol: CUSUM + 3/5 gün debounce</span>
  <span class="chip acil" data-step="2">Başlangıç tarihi: değişim noktası, aralıkla</span>
  <span class="chip brand" data-step="3">İleri yol: Theil-Sen + Sen (1968) güven aralığı</span>
  <span class="chip" data-step="3">21 günde en az 14 geçerli gün yoksa sayı yok: YETERSİZ_GEÇMİŞ</span>
</div></div>`,
  notes: `Ürünün haftalar önce haber veren yolu bu grafikte. Sarı çizgi, Çıkış 7 L2 pabucunun günlük θ medyanı.

[→] Geriye bakan yol: CUSUM birikiyor, θ beş kelvini geçiyor ve son beş günün üçünde geçiyor — üç şart birden olunca Uyarı açılıyor, iş emri yazılıyor. Telefon çalmıyor. On iki kelvini geçip ikinci bağımsız sensör ailesi de hemfikir olunca Kritik oluyor ve nöbetçiye SMS gidiyor.

[→] Ama asıl ikna edici cümle şu: bu bozulma 11 Eylül civarında hızlandı. Bunu CUSUM söylemiyor — CUSUM zaten gecikir. Tarihi, tüm seri üzerinde geriye dönük bir değişim noktası kestirimi veriyor. Ve tarihi bir aralık olarak veriyoruz; çünkü bozulma bir basamak değil bir rampa. Kesin tarih vermek sahte kesinlik olurdu: planlayıcı o günün manevra kaydını açar ve olmayan bir şeyi arar.

[→] Bakım planlayıcısının sorduğu soru ise ileriye dönük: bu pabuç ne zaman benim sorunum olacak? Bu gidişle ACİL seviyesine on beş gün; on üç ile on dokuz arası. Aralık uydurulmadı: eğimin kendi güven aralığı var ve gün sayısı o aralığın iki ucuna bölünerek çıkıyor.

Bu sayı bir iş emrinin bu haftaya mı gelecek aya mı yazılacağına karar vermeye yeter. Bir kesinti tarihini planlamaya yetmez — ve öyle sunmuyoruz. Ve yirmi bir günlük pencerede en az on dört geçerli gün yoksa sistem gün sayısı üretmiyor; "yetersiz geçmiş" yazıyor. Sayı üretmek kolaydı; üretmemek ürünün kendisi.`,
  use: `<b>Kullan:</b> 3 adım: alarm işaretleri → değişim noktası → projeksiyon yelpazesi. <b>Dikkat:</b> sayılar (17,6 K · 11 Eylül · 15 gün (13–19) · +3,5 K/hf, %90 GA 2,8–3,9 · 22 geçerli gün) 3 Ekim demo koşusundandır; prova koşusuyla tazeleyin. Grafik eğrisi şematiktir, işaretlerdeki sayılar ölçümdür. <b>Jüri sorarsa — "Bozulma hızlanırsa?":</b> Model doğrusal ve ekranda yazıyor. Isıl kaçış süper-doğrusaldır; o modda bu sayı <b>iyimserdir</b>, gerçek tarih daha erken olabilir. Kalibre edecek saha verisi olmadan süper-doğrusal model bir iddia olurdu. <b>Kapsama:</b> nominal %90 GA'nın simülasyonda ölçülen kapsaması %88–93.`,
});

/* ===================================================================== */
/* 11 · GÖRÜLEBİLİRLİK                                                    */
/* ===================================================================== */
function visSVG() {
  const X = H.sc(.1, 1, 70, 600), Y = H.sc(0, 30, 330, 20);
  const cur = s => { const p = []; for (let f = .1; f <= 1.0001; f += .01) { const v = 3 * s / (f * f); if (v <= 31) p.push([X(f), Y(v)]); } return H.smooth(p); };
  return `<svg viewBox="0 0 640 370" class="vissvg">
   <rect x="${X(.1)}" y="20" width="${X(.35) - X(.1)}" height="310" fill="rgba(74,163,255,.08)"/>
   <line x1="${X(.35)}" x2="${X(.35)}" y1="20" y2="330" stroke="var(--izle)" stroke-dasharray="5 4"/>
   <text x="${X(.225)}" y="318" text-anchor="middle" font-size="12" font-weight="700" fill="var(--izle)">görünürlük düşük</text>
   <text x="${X(.36)}" y="${Y(29)}" font-size="11" class="mono" fill="var(--izle)">f = 0,35</text>
   ${[0, 5, 10, 15, 20, 25, 30].map(v => `<line x1="70" x2="600" y1="${Y(v)}" y2="${Y(v)}" stroke="var(--line)"/><text x="62" y="${Y(v) + 4}" text-anchor="end" class="mono" font-size="11" fill="var(--dim)">${v}</text>`).join('')}
   ${[.2, .4, .6, .8, 1].map(f => `<text x="${X(f)}" y="352" text-anchor="middle" class="mono" font-size="11" fill="var(--dim)">${fmt(f, 1)}</text>`).join('')}
   <text x="600" y="366" text-anchor="end" font-size="11" fill="var(--dim)">yük faktörü f = I / I_ref</text>
   <text x="70" y="12" font-size="11" fill="var(--dim)">θ_min · görülebilen en küçük kusur (K)</text>
   <path d="${cur(.8)}" fill="none" stroke="var(--muted)" stroke-width="2.4" stroke-dasharray="6 5" data-a="draw" style="--d:.5s"/>
   <path d="${cur(.2)}" fill="none" stroke="var(--olcum)" stroke-width="3.2" data-a="draw" style="--d:.3s"/>
   <text x="${X(.62)}" y="${Y(3 * .8 / .3844) - 10}" font-size="12" fill="var(--muted)">IR dizi · σ = 0,8 K</text>
   <text x="${X(.56)}" y="${Y(3 * .2 / .3136) + 22}" font-size="12" fill="var(--olcum)">kelepçe · σ = 0,2 K</text>
   <line id="vsl" x1="0" x2="0" y1="20" y2="330" stroke="var(--ink)" stroke-opacity=".35"/>
   <circle id="vsd" r="8" fill="var(--olcum)" stroke="#000" stroke-width="2"/>
  </svg>`;
}
add({
  title: 'Kör olduğumuz yeri söyleriz', section: 'Yöntem', time: '35 sn',
  html: () => `${HD('05 · Yöntem', 'Kör olduğumuz yeri ekranda yazıyoruz.')}
<div class="body"><div class="row grow">
  <div class="card" style="width:680px;--d:.1s" data-a="blur">${visSVG()}</div>
  <div class="col grow">
    <div class="card" data-a="up" style="--d:.2s"><div class="formula" style="font-size:28px">θ<sub>min</sub> = <span class="frac"><span>3 σ</span><span>f²</span></span></div></div>
    <div class="card vis-read" data-a="up" style="--d:.3s">
      <div class="g2"><div><p class="cap">Saat</p><div class="mini-v mono" id="vst">03:00</div></div><div><p class="cap">Yük f</p><div class="mini-v" id="vsf">0,18</div></div></div>
      <p class="cap" style="margin-top:12px">Şu an görülebilen en küçük θ</p><div class="big"><span id="vsm">18,5</span><small> K</small></div>
      <span id="vss" class="chip izle"><i></i>Görünürlük düşük</span>
      <p class="vis-say" id="vsy">"Şu anda 18,5 K'nin altındaki bir kusuru göremiyorum."</p>
    </div>
    <div class="row" style="gap:8px;flex-wrap:wrap;--d:.5s" data-a="up"><span class="chip kritik">Mutlak limitler her zaman açık</span><span class="chip">90 · 110 · 130 °C</span></div>
  </div>
</div></div>`,
  scene(el, { REDUCED }) {
    const q = s => el.querySelector(s);
    const X = H.sc(.1, 1, 70, 600), Y = H.sc(0, 30, 330, 20);
    const put = hr => {
      const f = .55 - .37 * Math.cos(2 * Math.PI * (hr - 3) / 24);
      const m = 3 * .2 / (f * f);
      q('#vsd').setAttribute('cx', X(f)); q('#vsd').setAttribute('cy', Y(Math.min(30, m)));
      q('#vsl').setAttribute('x1', X(f)); q('#vsl').setAttribute('x2', X(f));
      q('#vst').textContent = String(Math.floor(hr) % 24).padStart(2, '0') + ':00';
      q('#vsf').textContent = fmt(f, 2); q('#vsm').textContent = fmt(m, 1);
      const low = f < .35, s = q('#vss');
      s.className = 'chip ' + (low ? 'izle' : 'ok'); s.innerHTML = '<i></i>' + (low ? 'Görünürlük düşük' : 'Tam görüş');
      q('#vsy').textContent = low ? `"Şu anda ${fmt(m, 1)} K'nin altındaki bir kusuru göremiyorum."` : `"${fmt(m, 1)} K ve üstündeki kusuru görüyorum."`;
    };
    if (REDUCED) { put(3); return null; }
    let raf, t0 = performance.now();
    const loop = t => { put((3 + ((t - t0) / 1000) * 2) % 24); raf = requestAnimationFrame(loop); };
    raf = requestAnimationFrame(loop);
    return { stop() { cancelAnimationFrame(raf); } };
  },
  notes: `Bir kusur, yük faktörü f'te gözlenen farkı yalnız θ çarpı f kare kadar büyütür. Yük düştükçe aynı kusuru görmek zorlaşır. Bunu saklamıyoruz, hesaplıyoruz: görülebilen en küçük θ, üç sigma bölü f kare.

Noktayı izleyin: günün saatine göre yük değişiyor. Öğleden sonra, tam yüke yakınken kelepçe yarım kelvinlik bir kusuru bile görüyor. Gece üçte, yüzde on sekiz yükte bu sayı on sekiz buçuk kelvine çıkıyor.

Rakip bir ürün gece yarısı "her şey normal" der. Biz "şu anda on sekiz buçuk kelvinin altındaki bir kusuru göremiyorum" diyoruz. İkincisi kullanılabilir bir bilgi. Bu bir arıza değil, bir görünürlük durumu: ayrı raporlanıyor, SCADA'da da ayrı bir bit.

Ve mutlak sıcaklık limitleri bu sırada da açık: yüz otuz derecedeki bir pabuç, yük ne olursa olsun yüz otuz derecedir. Kör olduğumuz yeri söylemek bir kusur değil, ürünün özelliği.`,
  use: `<b>Kullan:</b> Nokta 24 saati ≈ 12 sn'de döner. "Gece üç" anını yakalayıp konuşun. <b>Ezberlenecek:</b> f = 0,35 eşik · f = 0,18 → θ_min = 3 × 0,2 / 0,18² = 18,5 K · SCADA STATUS_WORD bit 2 = görünürlük düşük. <b>Dürüst not:</b> 110/130 °C bir standart alıntısı değil, <b>mühendislik çıkarımıdır</b> (TS EN 61439-1 bara cıvatalı bağlantısı için sayısal limit koymaz); gerçek Çizelge 8 değerleri gelince tek satırda değişir.`,
});

/* ===================================================================== */
/* 12 · BASTIRILMIŞ ALARMLAR                                              */
/* ===================================================================== */
add({
  title: 'Bastırılmış alarmlar', section: 'Alarm', time: '50 sn',
  html: () => `${HD('06 · Alarm', 'Ürettiğimiz değil, üretmediğimiz alarmlar.', '"78 °C okudun, neden bana söylemedin?" sorusunun cevabı ekranda, operatörün dilinde, sayılarıyla durur.')}
<div class="body"><div class="row grow">
  <div class="card col" style="width:560px;--d:.15s" data-a="up">
    <p class="cap">Sıcak hava dalgası · ortam 41,2 °C · 40 bağlantı</p>
    <div class="jgrid" id="sjg">${Array.from({ length: 40 }, (_, i) => `<i style="--k:${i}"></i>`).join('')}</div>
    <div class="g2" style="margin-top:6px">
      <div class="cnt bad"><span class="cl">Sabit eşikli sistem</span><b id="sc1">0</b><span class="cs">alarm</span></div>
      <div class="cnt good"><span class="cl">PANO GÖZ</span><b id="sc2">0</b><span class="cs">alarm · Δθ = <span class="mono" id="sdt">0,0000</span> K</span></div>
    </div>
    <p class="sub" id="scap" style="margin-top:8px">Tüm bağlantılar birlikte ısınıyor.</p>
  </div>
  <div class="col grow sup" data-step="1">
    ${[['GRID_THD_3PH', 'Üç fazın gerilim THD\'si birlikte yükseldi: pano bir yüktür, kaynak değil.'],
       ['GRID_THD_3PH_CANDIDATE', 'Isıl bulgu silinmez, bir kademe geriletilir; ekip vetolanmaz.'],
       ['LOAD_STEP · INRUSH', 'θ kararlı hâl içindir; 3τ boyunca askıya alınır.'],
       ['SENSITIVITY_LOW · STALE', 'Görünürlük ve bayat veri: pano arızası değil, durum.'],
       ['DEVICE_MOUNT_LOST · DRIFT', 'Cihaz iş emri açılır; sağlam bağlantı asla sıktırılmaz.'],
       ['LEARN_WEEK', 'İlk 7 gün taban toplanır; mutlak limitler yine açık.']].map(([c, t], i) =>
      `<div class="card tight suprow" data-a="left" style="--d:${.08 * i}s"><span class="mono">${c}</span><span>${t}</span></div>`).join('')}
    <p class="sub" style="margin-top:2px">100 panoda haftada ~20–60 satır. Bakım planlayıcı haftada bir okur.</p>
  </div>
</div></div>`,
  scene(el, { REDUCED }) {
    const q = s => el.querySelector(s);
    const cells = [...el.querySelectorAll('#sjg i')];
    const r = H.rng(3), base = cells.map(() => 48 + r() * 9), thr = 60;
    const draw = (rise, tt) => {
      let n = 0;
      cells.forEach((c, i) => { const T = base[i] + rise; c.style.background = H.heat(.3 + (T - 45) / 40); if (T >= thr) n++; });
      q('#sc1').textContent = n; q('#sc2').textContent = '0';
      q('#scap').textContent = tt;
    };
    if (REDUCED) { draw(6.1, 'Kırk bağlantının tamamı +6,1 K. Kardeşler aynı havada: θ değişimi tam sıfır.'); return null; }
    let raf, t0 = performance.now();
    const loop = t => {
      const T = ((t - t0) / 1000) % 9;
      const rise = T < 1 ? 0 : T < 4 ? 6.1 * H.ease((T - 1) / 3) : T < 7.4 ? 6.1 : 6.1 * (1 - H.ease((T - 7.4) / 1.4));
      draw(rise, T < 1 ? 'Normal bir öğleden sonra.' : T < 7.4 ? 'Kırk bağlantının tamamı +6,1 K. Kardeşler aynı havada: θ değişimi tam sıfır.' : 'Hava serinliyor.');
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return { stop() { cancelAnimationFrame(raf); } };
  },
  notes: `Şimdi ürünün bence en önemli parçası: ürettiğimiz alarmların değil, üretmediğimiz alarmların listesi. Gerekçeleriyle.

Solda bir sıcak hava dalgası. Ortam 41,2 derece — şartnamenin dahili maksimumu 40 derece, yani bu zaten hizmet zarfı dışı bir bulgu. Kırk bağlantının hepsi birden 6,1 kelvin ısınıyor. Sabit eşikli bir sistem burada kırk alarm üretirdi. θ'nın değişimi tam sıfır: sıfır virgül sıfır sıfır sıfır sıfır. Çünkü kardeşler aynı havayı soluyor. Bu pano hakkında değil, hava hakkında bir okuma.

[→] Sağda bastırma kurallarından bazıları. Her biri tek bir soruya cevap veriyor: bu okuma pano hakkında mı, yoksa şebeke, hava, yük ya da kendi cihazımız hakkında mı?

Üç fazın gerilim bozulması birlikte yükselirse: pano bir yüktür, kaynak değil; harmonik kanıtlı modlar kapanır. Ama dürüst olalım — aynı ölçümü tesisteki büyük bir sürücü ya da UPS de üretir. O yüzden ısıl bulguyu silmiyoruz, yalnız bir kademe geriletiyoruz ve ekibi vetolamıyoruz. Sıcak bir cıvata, gerilim bozunumu sürüyor diye bekletilmez.

Sensör kayarsa ya da kelepçe düşerse cihaz iş emri açılıyor — tork iş emri değil. Sapan bir sensör yüzünden bir ekibi sağlam bir bağlantıyı sıkmaya göndermek, sistemin güvenilirliğini bir seferde bitirir.

Bölgesel bir olay, yüz dürüst dedektörden yüz eşzamanlı alarm üretir ve sistem üçüncü ayda kapatılır. Bu liste bir hata ayıklama günlüğü değil; kendi ekranı olan bir ürün.`,
  use: `<b>Kullan:</b> ASLA KESİLMEZ (demo senaryosu §4). Animasyon 9 sn'de döner; sayaç 40'a ulaştığında "kırk alarm" deyin. Sonra → ile kural listesi. <b>Ezberlenecek:</b> ortam 41,2 °C · +6,1 K · Δθ = 0,0000 K (ölçülen) · THD: L1 %6,8 / L2 %7,1 / L3 %6,9, tabanlar %2,4 / 2,5 / 2,3. <b>Kapanış cümlesi:</b> "Bu bir hata ayıklama günlüğü değil — kendi ekranı olan bir üründür."`,
});

/* ===================================================================== */
/* 13 · ARK OLAYI                                                         */
/* ===================================================================== */
add({
  title: 'Ark olayı: koruma bizde değil', section: 'Alarm', time: '45 sn',
  html: () => `${HD('06 · Alarm', 'Ark oluştu. Biz açmadık; TVOC-2 açtı.')}
<div class="body"><div class="row grow">
  <div class="card col arc" style="width:400px;--d:.1s" data-a="up">
    <div class="flash"><i></i><i></i><i></i>${IC.flash}</div>
    <div class="arc-kv"><span>TVOC-2 reg 1300</span><b class="mono">0x0001 · aktif açma</b></div>
    <div class="arc-kv"><span>Gören dedektör</span><b class="mono">X2:3</b></div>
    <div class="arc-kv"><span>Açan röle</span><b class="mono">K5</b></div>
    <div class="arc-kv"><span>Işık → kontak</span><b class="mono">~1 ms · SIL-2</b></div>
    <div class="arc-kv"><span>Sağlam dedektör</span><b class="mono">10 / 10 <small class="uyari">X1 kapsam dışı</small></b></div>
    <p class="sub arc-note">Register 222/223 yalnız X2 ve X3 kartlarını kapsar. X1'deki dedektörleri göremiyoruz ve ekranda öyle yazıyor.</p>
  </div>
  <div class="col grow">
    <div class="card grow lat" data-a="up" style="--d:.25s"><p class="cap">Bildirim gecikmesi · tek temiz sayı değil, bir aralık</p>
      ${[['en iyi', [.001, .2, 1, .3, 2.5]], ['en kötü', [.001, 2, 1, 2, 8]]].map(([n, segs], r) => {
        let acc = 0;
        return `<div class="latrow"><span class="mono">${n}</span><div class="lbar">${segs.map((s, i) => { const x = acc; acc += s; return `<i class="s${i}" style="left:${x / 14 * 100}%;width:${Math.max(.4, s / 14 * 100)}%;--d:${.5 + r * .9 + i * .16}s" data-a="grow-x"></i>`; }).join('')}</div><b class="mono">${fmt(acc, 0)} sn</b></div>`;
      }).join('')}
      <div class="laxis">${[0, 2, 4, 6, 8, 10, 12, 14].map(v => `<span style="left:${v / 14 * 100}%">${v}</span>`).join('')}</div>
      <div class="lleg">${[['TVOC-2 ışık → kontak', '~1 ms', 'bizi beklemez'], ['Modbus görüntü yenileme', '0,2–2 s', 'ABB yazmıyor · modellendi'], ['Ağ geçidi taraması', '1 s', ''], ['Sunucu işleme', '0,3–2 s', ''], ['SMS yolu', '2,5–8 s', 'operatöre bağlı']].map(([a, b, c], i) => `<div><i class="s${i}"></i><span>${a}</span><b class="mono">${b}</b><em>${c}</em></div>`).join('')}</div>
    </div>
    <div class="row" style="gap:10px;--d:1.4s" data-a="up"><span class="chip kritik">Toplam 4–13 sn</span><span class="chip">Açmadan sonra pano enerjisiz: AG'de giriş kesicisi yok</span></div>
  </div>
</div></div>`,
  notes: `Ark oluştu. Biz açmadık. Panodaki ABB TVOC-2 rölesi açtı: ışıktan kontağa yaklaşık bir milisaniye, SIL-2 donanımda. PANO GÖZ koruma yapmıyor ve yapmaya çalışmıyor; koruma bizi beklemez.

Bizim işimiz ark olduktan sonra başlıyor: hangi dedektör gördü — X2:3. Hangi röle attı — K5. Ne zaman oldu. Ve nöbetçiye haber vermek.

Gecikmeyi tek bir temiz sayı olarak vermiyoruz: dört ile on üç saniye arası. Neden? Çünkü TVOC-2'nin Modbus görüntüsünün ne kadar sürede güncellendiğini ABB dokümante etmemiş. Beş saniye deseydik, ölçmediğimiz bir şeyi ölçmüş gibi göstermiş olurduk.

Bir şeye daha bakın: "sağlam dedektör 10/10" yazıyor; ama bu röleye yirmi dedektör bağlı olabilir. Register 222 ve 223 yalnız X2 ve X3 kartlarını kapsıyor. X1'deki dedektörlerin sağlığını göremiyoruz ve ekranda tam olarak öyle yazıyor. Görmediğimiz şeyi gördü gibi göstermek, en tehlikeli hatadır.`,
  use: `<b>Kullan:</b> ASLA KESİLMEZ (demo senaryosu §5). Canlı demoda "Ark olayı enjekte et" ile aynı kart açılır. <b>Ezberlenecek aritmetik:</b> reg 1300 bit0 = aktif açma · dedektör LOW kelimesi 0x1000 → bit 12 → X2:3 · röle bit alanı 0x0002 → bit1 = K5. En iyi 0,2 + 1 + 0,3 + 2,5 ≈ 4 s; en kötü 2 + 1 + 2 + 8 = 13 s. <b>Jüri sorarsa — "Otokontrolü uzaktan tetikleyebilir misiniz?":</b> Hayır, ne MQTT'den ne SCADA'dan ne API'den. Reg 213 otokontrol ve açma sıfırlama, ağ geçidinde operatör kimlik doğrulaması <b>ve</b> fiziksel anahtar (X4) arkasında.`,
});

/* ===================================================================== */
/* 14 · SEVİYE MERDİVENİ VE BİLDİRİM                                     */
/* ===================================================================== */
const SMS = 'PANO GÖZ KRİTİK · SOKE-14 · Ç7·L2·pabuç θ=17.6K · bağlantıyı torkla · ACİL\'e 15 g (13-19) · onay: TAMAM 1 0541';
add({
  title: 'Seviye merdiveni ve bildirim', section: 'Alarm', time: '50 sn',
  html: () => `${HD('06 · Alarm', 'Yalnız Kritik ve Acil bir telefonu çaldırır.')}
<div class="body"><div class="row grow">
  <div class="card ladder" style="width:400px;--d:.1s" data-a="up">
    ${[['Acil', 'acil', '≥ 25 K', 'derhal ekip · SMS + sesli', 1], ['Kritik', 'kritik', '≥ 12 K', '7 gün içinde ziyaret · SMS', 1], ['Uyarı', 'uyari', '≥ 5 K', 'iş emri · planlı ziyaret', 0], ['İzle', 'izle', '≥ 2 K', 'haftalık özet', 0], ['Bilgi', '', '< 2 K', 'kayıt', 0]].map(([n, c, t, a, ph], i) =>
      `<div class="lad ${c}" style="--w:${100 - i * 12}%;--d:${.2 + (4 - i) * .1}s" data-a="right"><span class="ln">${n}</span><span class="mono lt">${t}</span><span class="la">${a}</span>${ph ? `<span class="lp">${IC.phone}</span>` : ''}</div>`).join('')}
    <p class="sub" style="margin-top:10px">θ eşikleri IR termografi pratiğine dayanır; fark, yüke normalize edilmiş olması. Kapanma eşiği açılmanın %60'ı.</p>
  </div>
  <div class="phone" data-a="up" style="--d:.3s"><div class="pscr">
    <div class="ptop"><span>Nöbetçi tekniker</span><span class="mono">GSM · UCS-2</span></div>
    <div class="bub in" id="smsb"><span id="smst"></span><span class="blink">▍</span></div>
    <div class="bub out" data-step="1">TAMAM 1 0541</div>
    <div class="bub sys" data-step="1">Olay ONAYLANDI · Nöbetçi tekniker</div>
  </div></div>
  <div class="col grow esc">
    <div class="card tight escrow" data-a="left" style="--d:.5s"><span class="mono et">0 dk</span><div><h3>1. kademe · nöbetçi</h3><p class="sub">SMS, kişiye ve olaya bağlı 4 haneli onay kodu</p></div></div>
    <div class="card tight escrow" data-a="left" style="--d:.65s"><span class="mono et">15 / 45 dk</span><div><h3>2. kademe · şef + sesli arama</h3><p class="sub">Onay gelmezse: Acil 15 dk, Kritik 45 dk</p></div></div>
    <div class="card tight escrow" data-a="left" style="--d:.8s"><span class="mono et">sonra</span><div><h3>3. kademe · işletme müdürü</h3><p class="sub">Merdiven her adımı kayda yazar</p></div></div>
    <div class="row" style="gap:6px;flex-wrap:wrap;margin-top:2px;--d:1s" data-a="up"><span class="chip">2 bağımsız sensör ailesi</span><span class="chip">24 sa bekleme · Acil muaf</span><span class="chip">saatte 8 Kritik tavanı · Acil muaf</span></div>
  </div>
</div></div>`,
  scene(el, { REDUCED }) {
    const t = el.querySelector('#smst');
    if (REDUCED) { t.textContent = SMS; return null; }
    let i = 0, tm;
    const tick = () => { t.textContent = SMS.slice(0, i); i += 2; if (i <= SMS.length + 1) tm = setTimeout(tick, 28); };
    tm = setTimeout(tick, 900);
    return { stop() { clearTimeout(tm); } };
  },
  notes: `Seviye merdiveni beş basamak. Bilgi kayda geçer. İzle haftalık özete girer, ekip çıkmaz. Uyarı iş emri açar ve planlı bir ziyarette doğrulanır. Yalnızca Kritik ve Acil bir telefonu çaldırır. Bu tek kural, sistemin üçüncü aydan sonra da açık kalmasını sağlayan kural; bu yüzden bir ayar değil, kodda bir sözleşme.

Telefon çalmadan önce iki şart daha var: iki bağımsız sensör ailesi hemfikir olmalı — örneğin kelepçe ve termal dizi — ve Kritik için yirmi dört saat bekleme var; Acil bundan muaf.

Mesaja bakın: pano, bağlantı, θ, yapılacak iş, ACİL'e kalan gün ve onay kodu. Türkçe karakterler bozulmasın diye UCS-2 gidiyor; iki parçaya sığacak şekilde tasarlandı. Bütçe daralırsa ilk düşen şey ufuk satırı; "bağlantıyı torkla" demek, "15 gün" demekten değerli.

[→] Nöbetçi "TAMAM 1 0541" yazıyor ve olay onaylanıyor. Kod kişiye ve olaya bağlı: rotada olmayan biri ya da yanlış kod onaylayamaz.

Onay gelmezse merdiven yükseliyor: Acil'de on beş dakika, Kritik'te kırk beş dakika sonra şef ve sesli arama, ardından işletme müdürü. Bir de fırtına tavanı var: saatte en fazla sekiz Kritik — ama Acil muaf. Tavan bir Acil'i susturabilseydi tavan değil arıza olurdu.`,
  use: `<b>Kullan:</b> SMS kendini yazar; bitince → ile onay balonu. <b>Dürüst sınır:</b> GSM modem AT diyaloğu ve SMPP oturumu <b>simüle</b> edilir, transkript kaydedilir; gerçek bir kanaldan mesaj gitmedi. Sesli arama da simülasyon. WhatsApp yok. Sorulursa açıkça söyleyin. <b>Not:</b> mesaj biçimi panogoz/notify/escalation.py compose() ile aynıdır; θ ve gün değerleri demo koşusundandır.`,
});

/* ===================================================================== */
/* 15 · SCADA ENTEGRASYONU                                                */
/* ===================================================================== */
const REGS = [['+0', 'PANEL_ID', '14', '14'], ['+2', 'HEALTH_INDEX', '67', '67'], ['+6', 'THETA_MAX', '176', '17,6 K'], ['+7', 'THETA_MAX_JOINT', '25', 'Ç7-L2'], ['+8', 'THETA_SLOPE', '3013', '3,01 K/hf'], ['+9', 'SENSITIVITY_PCT', '100', '%100'], ['+45', 'DATA_AGE_S', '2', '2 sn']];
add({
  title: 'SCADA: Modbus haritalama', section: 'Entegrasyon', time: '40 sn',
  html: () => `${HD('07 · Entegrasyon', 'SCADA mühendisi tek blok tanımlar, yüz kez kopyalar.')}
<div class="body"><div class="row grow">
  <div class="col" style="width:520px">
    <div class="card" data-a="up" style="--d:.1s"><p class="cap">Pano n'in taban adresi</p>
      <div class="formula" style="font-size:26px">1000 + 48 × (n − 1)</div>
      <div class="formula" style="font-size:26px;margin-top:6px;color:var(--brand)">1000 + 48 × 13 = <span data-count="1624" data-from="1000" data-dur="1.6" data-plain="1" style="--d:.5s">1000</span></div>
    </div>
    <div class="card grow" data-a="up" style="--d:.2s"><p class="cap">SOKE-14 · 48 register · salt okunur</p>
      <div class="regs" id="rgg">${Array.from({ length: 48 }, (_, i) => `<i class="${[0, 2, 6, 7, 8, 9, 45].includes(i) ? 'k' : ''}" style="--k:${i}">${i}</i>`).join('')}</div>
      <p class="sub" style="margin-top:8px">Doldurulmamış pano bloğu sıfır okur ve DATA_VALID biti temizdir: tarama hatası ile boş pano ayırt edilir.</p></div>
  </div>
  <div class="col grow">
    <div class="card tight" data-a="up" style="--d:.3s"><table class="rt"><tr><th>ofset</th><th>register</th><th>ham</th><th>mühendislik</th></tr>
      ${REGS.map(([o, n, r, e], i) => `<tr data-a="fade" style="--d:${.5 + i * .1}s"><td class="mono">${o}</td><td class="mono">${n}</td><td class="mono">${r}</td><td class="mono b">${e}</td></tr>`).join('')}</table></div>
    <div class="term" data-step="1"><div><span class="pr">$</span> modpoll -m tcp -0 -r 1624 -p 5020 127.0.0.1 1</div><div class="err">Illegal Function exception response! (0x01)</div><div class="dimc">FC 05/06/15/16 istisnasız reddedilir</div></div>
    <div class="row" style="gap:8px;flex-wrap:wrap;--d:1.2s" data-a="up"><span class="chip ok">100 pano: 39 istek · 19 ms</span><span class="chip ok">SCADA 1 Hz: 2 istek · 0,72 ms</span><span class="chip">ICD v2.0 koddan üretilir</span><span class="chip uyari">IEC 104 / OPC UA: nokta listesi var, sunucu yok</span></div>
  </div>
</div></div>`,
  notes: `Şartname SCADA entegrasyonu için Modbus haritalaması istiyor. Çalışan bir Modbus TCP slave teslim ettik.

Her pano sabit adımlı, deliksiz bir bloğa sahip: bin artı kırk sekiz çarpı n eksi bir. On dört numaralı panonun adresi kafadan atılmadı: bin artı kırk sekiz çarpı on üç, bin altı yüz yirmi dört. SCADA mühendisi tek bir blok tanımlıyor ve yüz kez kopyalıyor.

Sağda bu bloktan birkaç register. THETA_MAX ham 176, ölçek 0,1: 17,6 kelvin. Bu sayı arayüzdeki sayıyla aynı nesneden geliyor; ikisi çelişemez. En değerli iki register ise kaynak cihazların üretemediği ikisi: ark rölesiyle bağın koptuğunu söyleyen durum biti ve bu bloğun ne kadar bayat olduğunu söyleyen veri yaşı. Klasik bir ağ geçidi son iyi değeri sonsuza dek sessizce yayınlar; bizimki kendi sağlığı hakkında doğruyu söyler.

[→] Ve yazmayı deneyin: exception sıfır bir, ILLEGAL FUNCTION. İstisnası yok. Modbus'ta kimlik doğrulama yok; ark rölesine otokontrol komutu verebilen bir sisteme kimliksiz yazma yolu açmak kabul edilemez.

Yüz panonun tamamını taramak dört bin sekiz yüz register ediyor; FC 03'ün 125 register sınırı yüzünden en az otuz dokuz istek gerekiyor — ölçtük, on dokuz milisaniye. "İki istekte olur" demiyoruz, çünkü olmuyor.`,
  use: `<b>Kullan:</b> → ile yazma denemesi. Canlı modpoll mümkünse terminalden gösterin (modpoll ikili dosyası depoda yok; jüri makinesinde kurulu olmalı, yoksa bu slayt yeterli). <b>Ezberlenecek:</b> pano bloğu 48 register · MAX_PANELS 200 (üst adres 10 599) · 1000+ panoda bölge başına slave ya da MAX_PANELS artırımı. <b>Dürüst sınır:</b> IEC 60870-5-104 ve OPC UA için nokta listesi ve IOA şeması yazıldı, sunucu kurulmadı. "Eşiğe kalan gün" için SCADA register'ı yok: blok dolu, büyütmek ICD v2.0'ı bozar; eklemeli ETA bloğu tarif edildi.`,
});

/* ===================================================================== */
/* 16 · CANLI DEMO / EKRANLAR                                             */
/* ===================================================================== */
const SCR = [['filo', 'Filo', 'Harita, seviye, Δ7 gün, eşiğe kalan gün'], ['ikiz', 'Dijital ikiz', 'EK-II/14 kesiti, 74 bağlantı, 9 cihaz'], ['kanit', 'Kanıt', 'Ham T, yük, θ, CUSUM; aynı eksen'], ['bastir', 'Bastırılanlar', 'Açılmayan alarmlar, gerekçeleriyle'], ['prpd', 'PRPD', 'Faz çözünürlüklü RF imzası'], ['scada', 'SCADA', 'Canlı register bloğu, salt okunur']];
add({
  title: 'Canlı demo: izleme ekranları', section: 'Demo', time: '5 dk demo',
  html: () => `${HD('08 · Demo', 'Operasyon ekibi ne görüyor?')}
<div class="body"><div class="row grow">
  <div class="frame grow" data-a="blur" style="--d:.1s"><div class="bar"><i></i><i></i><i></i><span id="scru">127.0.0.1:8080/#/filo</span></div>
    <div class="scr">${SCR.map(([k], i) => `<img src="${A['ekran_' + k]}" data-k="${k}" class="${i === 0 ? 'on' : ''}" alt="">`).join('')}</div></div>
  <div class="col scrl" style="width:300px">${SCR.map(([k, t, d], i) => `<button class="sci ${i === 0 ? 'on' : ''}" data-i="${i}" data-a="left" style="--d:${.2 + i * .07}s"><b>${t}</b><span>${d}</span><i></i></button>`).join('')}</div>
</div></div>`,
  /* PDF'te ekranlar dönemez: altısı tek sayfada, sunumda canlı gösterilir. */
  printHtml: () => `${HD('08 · Demo', 'Operasyon ekibi ne görüyor?')}
<div class="body"><div class="shots">${SCR.map(([k, t, d]) => `<figure class="shot"><img src="${A['ekran_' + k]}" alt="${t} ekranı"><figcaption><b>${t}</b>${d}</figcaption></figure>`).join('')}</div>
<p class="sub shots-note">Ekranlar sunumda canlı sistemden gösterilir · tek komut: <span class="mono">.\\baslat.ps1</span> → 127.0.0.1:8080 · internet gerekmez</p></div>`,
  scene(el) {
    const imgs = [...el.querySelectorAll('.scr img')], btn = [...el.querySelectorAll('.sci')], url = el.querySelector('#scru');
    const routes = ['#/filo', '#/pano/SOKE-14', '#/kanit/SOKE-14/C07-L2-PABUC', '#/alarm/bastirilan', '#/prpd/SOKE-14', '#/scada/SOKE-14'];
    let i = 0, tm;
    const show = k => {
      i = k; imgs.forEach((im, j) => { im.classList.toggle('on', j === k); if (j === k) { im.style.animation = 'none'; void im.offsetWidth; im.style.animation = ''; } });
      btn.forEach((b, j) => b.classList.toggle('on', j === k)); url.textContent = '127.0.0.1:8080/' + routes[k];
      clearTimeout(tm); tm = setTimeout(() => show((i + 1) % imgs.length), 6000);
    };
    btn.forEach((b, j) => b.onclick = e => { e.stopPropagation(); show(j); });
    tm = setTimeout(() => show(1), 6000);
    return { stop() { clearTimeout(tm); } };
  },
  notes: `Şimdi canlı sisteme geçiyoruz. [Tarayıcıya geç: http://127.0.0.1:8080 — sunumdan 2 dakika önce .\\baslat.ps1 ile başlatılmış olmalı. --no-backfill ile BAŞLATMAYIN.]

Demo akışı (5 dakika, docs/08):
1 · Tez (35 sn) — Filo haritası: 112 pano, Ege ve Güney Ege. "Her yarışmacı termometre koyar..." cümlesi ve θ formülü.
2 · Dijital ikiz (45 sn) — Haritada SOKE-14 → panoya gir. Dokuz cihaz, yetmiş dört bağlantı, kırkı ölçülüyor; gri olanlar bara bölmesi ve çatı: "Gri renk bir eksiklik değil, bir beyandır."
3 · Yavaş bozulma ve tarih (50 sn) — Ç7-L2 kanıt ekranı: θ, CUSUM, değişim noktası, projeksiyon kartı: "ACİL'e X gün (a–b)". Sonra filo tablosunda sayı vermeyen satırlar: "yetersiz geçmiş".
4 · Bastırılmış alarm (45 sn, ASLA KESİLMEZ) — Alarmlar → Bastırılan. Sıcak hava dalgası ve şebeke olayı satırları.
5 · Ark olayı (45 sn, ASLA KESİLMEZ) — Demo panelinden "ark olayı" enjekte et; X2:3, K5, 4–13 sn.
6 · SCADA kanıtı (40 sn) — modpoll ile 1624'ten 48 register; yazma → exception 0x01.
7 · Kör olduğumuz yer (25 sn) — gece, düşük yüklü bir pano: "görünürlük düşük".
8 · Kapanış (15 sn).

Canlı sistem açılmazsa: bu slayttaki ekranlar sırayla döner; sağdaki listeden tıklayarak anlatın.`,
  use: `<b>Kullan:</b> Ekranlar 6 sn'de bir değişir; sağdan tıklayıp sabitleyebilirsiniz. Bu slayt canlı demonun <b>yedeğidir</b>. <b>Süre daralırsa kesme sırası (docs/08 §9):</b> 1) canlı modpoll → ekran görüntüsü · 2) görünürlük beat'i → tek cümle · 3) sahte veri cümlesi · 4) CUSUM açıklaması · 5) 74/40 bağlantı açıklaması · 6) tezin ikinci paragrafı. Hepsi kesilirse demo 3 dk 28 sn; 4 ve 5 numaralı beat'ler tam kalır. <b>Senaryo uçları:</b> GET /api/scenarios · POST /api/scenario/{key} · POST /api/demo/reset.`,
});

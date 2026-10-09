/* ======================================================================
   SLAYTLAR 8–14 · karar, erken uyarı, alarm, entegrasyon, canlı demo
   ====================================================================== */

/* ===================================================================== */
/* 8 · SİSTEM NASIL KARAR VERİYOR                                         */
/* ===================================================================== */
function chainSVG() {
  const N = [
    ['Ölç', 'dakikada bir', 'sıcaklık ve akım', IC.therm],
    ['Karşılaştır', 'her bağlantıyı', 'diğer fazlarla', IC.grid],
    ['Eğilimi izle', 'tek ölçüme değil,', 'günlere bakar', IC.clock],
    ['Ayıkla', 'hava mı, yük mü,', 'sensör mü?', IC.eye],
    ['Haber ver', 'gerekçesiyle,', 'doğru kişiye', IC.bell],
  ];
  const w = 208, g = 30, y = 14, h = 118;
  const x = i => i * (w + g);
  const col = ['var(--line2)', 'var(--line2)', 'var(--olcum)', 'var(--izle)', 'var(--kritik)'];
  return `<svg viewBox="0 0 1160 140" class="chainsvg">
   <path id="chp" d="M${x(0) + 10},${y + h / 2} H${x(4) + w - 10}" stroke="var(--line2)" stroke-width="2" fill="none"/>
   ${[0, 1, 2].map(k => `<circle r="5" fill="var(--brand)" filter="drop-shadow(0 0 6px #f78320)"><animateMotion dur="4.5s" begin="-${k * 1.5}s" repeatCount="indefinite"><mpath href="#chp"/></animateMotion></circle>`).join('')}
   ${N.map(([a, b, c, ic], i) => `<g data-a="up" style="--d:${.1 + i * .1}s">
     <rect x="${x(i)}" y="${y}" width="${w}" height="${h}" rx="14" fill="#0d131b" stroke="${col[i]}" stroke-width="1.6"/>
     <g transform="translate(${x(i) + 18},${y + 18})" color="var(--brand)">${ic.replace('class="ic"', 'width="24" height="24"')}</g>
     <text x="${x(i) + 52}" y="${y + 37}" font-size="19" font-weight="700" fill="var(--ink)">${a}</text>
     <text x="${x(i) + 18}" y="${y + 74}" font-size="14" fill="var(--muted)">${b}</text>
     <text x="${x(i) + 18}" y="${y + 95}" font-size="14" fill="var(--muted)">${c}</text>
   </g>`).join('')}
  </svg>`;
}
const MODES = [['Gevşek bağlantı', 'bağlantı yeniden sıkılır'], ['Aşırı yük', 'yük dengelenir'], ['Ark korumasında arıza', 'dedektörler kontrol edilir'], ['Soğutma sorunu', 'menfez ve filtreler temizlenir'], ['Nötr iletkeni ısınması', 'harmonikler incelenir'], ['Nem ve yoğuşma', 'kanal sızdırmazlığı sağlanır'], ['Yalıtım zayıflaması', 'planlı ölçüm yapılır']];
add({
  title: 'Sistem nasıl karar veriyor', section: 'Çözüm', time: '45 sn',
  html: () => `${HD('03 · Çözüm', 'Sistem nasıl karar veriyor?')}
<div class="body">
  ${chainSVG()}
  <div class="row grow">
    <div class="card grow col" data-step="1"><p class="cap">Yakaladığı yedi sorun ve sahada ne yapılacağı</p>
      <div class="mlist">${MODES.map(([n, a]) => `<div><b>${n}</b><span>${a}</span></div>`).join('')}</div></div>
    <div class="card col" style="width:440px" data-step="2"><p class="cap">Neden "kara kutu" yapay zekâ değil?</p>
      <div class="rej">
        <div>${IC.x}<span><b>Yavaş bozulmayı "normal" sanabilir</b> Haftalarca süren ısınmayı öğrenip kabullenir; tam aradığımız şeye kör kalır.</span></div>
        <div>${IC.x}<span><b>Aylarca temiz veri ister</b> Elimizde yok; üstelik her pano için ayrı bir model gerekir.</span></div>
        <div>${IC.x}<span><b>Kararını açıklayamaz</b> Bizim sistemimiz her uyarının nedenini Türkçe ve sade yazar.</span></div>
      </div></div>
  </div>
</div>`,
  notes: `Sistem her pano için beş adımlık aynı zinciri işletiyor.

Ölç: dakikada bir sıcaklık ve akım. Karşılaştır: her bağlantıyı aynı çıkışın diğer fazlarıyla. Eğilimi izle: tek bir ölçüme değil, günlerin gidişatına bakıyoruz; çünkü gevşeyen bir bağlantı bir günde değil, haftalar içinde ısınır. Ayıkla: bu okuma gerçekten panoyla mı ilgili, yoksa hava, yük ya da kendi sensörümüz mü? Ve haber ver: gerekçesiyle, doğru kişiye.

[→] Bu zincir yalnız gevşek bağlantıyı değil, şartnamenin saydığı yedi sorunu izliyor: aşırı yük, ark korumasının sağlığı, soğutma, nötr ısınması, nem ve yalıtım zayıflaması. Her biri için ekrana "ne yapılmalı" da yazılıyor.

[→] En sık sorulan soru: "Yapay zekâ nerede?" Bilerek kara kutu bir model kullanmadık. Böyle bir model haftalarca süren yavaş ısınmayı normalin parçası olarak öğrenir — yani tam aradığımız şeye kör kalır. Aylarca temiz geçmiş veri ister; elimizde yok. Ve kararını açıklayamaz. Bizim sistemimiz her uyarının nedenini bakım ekibinin anlayacağı dilde yazıyor.`,
  use: `<b>Kullan:</b> Adım 1: yedi sorun; adım 2: neden kara kutu model değil. Akış çizgisindeki turuncu nokta zinciri dolaşır. <b>Jüri sorarsa — "Hangi yöntemler?":</b> fizik tabanlı kestirici + istatistiksel süreç kontrolü (CUSUM) + değişim noktası tespiti; hepsinin çıktısının bir birimi var (kelvin, gün). <b>Yanlış alarm?</b> Uyarı için üç şart birden gerekir: biriken sapma, yeterince büyük fark ve son beş günün en az üçünde tekrar.`,
});

/* ===================================================================== */
/* 9 · HAFTALAR ÖNCE: BAŞLANGIÇ VE KALAN SÜRE                             */
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
   ${TH.map(([v, l, c]) => `<line x1="70" x2="1130" y1="${Y(v)}" y2="${Y(v)}" stroke="var(--${c})" stroke-opacity=".55" stroke-dasharray="6 6"/><text x="64" y="${Y(v) + 4}" text-anchor="end" font-size="12" font-weight="600" fill="var(--${c})">${l}</text>`).join('')}
   <line x1="70" x2="1130" y1="${Y(0)}" y2="${Y(0)}" stroke="var(--line2)"/>
   ${days.map(([d, t]) => `<text x="${X(d)}" y="352" text-anchor="middle" class="mono" font-size="11" fill="${d === 0 ? 'var(--ink)' : 'var(--dim)'}">${t}</text>`).join('')}
   <line x1="${X(0)}" x2="${X(0)}" y1="20" y2="330" stroke="var(--line2)"/>
   <text x="${X(0) + 6}" y="34" font-size="11" fill="var(--muted)">bugün</text>
   <text x="70" y="14" font-size="11.5" fill="var(--dim)">Çıkış 7 · L2 · fazlar arası fark, gün gün</text>
   <g data-step="2"><rect x="${X(-29)}" y="20" width="${X(-15) - X(-29)}" height="310" fill="rgba(255,47,121,.07)"/>
     <line x1="${X(-22)}" x2="${X(-22)}" y1="20" y2="330" stroke="var(--acil)" stroke-width="2" stroke-dasharray="5 4"/>
     <rect x="${X(-22) + 8}" y="40" width="226" height="48" rx="9" fill="rgba(6,8,12,.92)" stroke="var(--acil)"/>
     <text x="${X(-22) + 20}" y="60" font-size="13.5" font-weight="700" fill="var(--acil)">Bozulma burada başladı</text>
     <text x="${X(-22) + 20}" y="78" font-size="11.5" fill="var(--muted)">geriye dönük bulunur · ~11 Eylül</text></g>
   <path d="${H.smooth(pts)}" fill="none" stroke="var(--olcum)" stroke-width="3.2" data-a="draw" style="--d:.3s;--dur:2.2s"/>
   <circle cx="${X(0)}" cy="${Y(17.6)}" r="6" fill="var(--olcum)" data-a="pop" style="--d:2.4s"/>
   <g data-step="1">
     <circle cx="${X(-27)}" cy="${Y(5.6)}" r="7" fill="none" stroke="var(--uyari)" stroke-width="2.5"/>
     <rect x="${X(-27) - 100}" y="${Y(5.6) + 16}" width="200" height="44" rx="9" fill="rgba(6,8,12,.92)" stroke="var(--uyari)"/>
     <text x="${X(-27)}" y="${Y(5.6) + 35}" text-anchor="middle" font-size="12.5" font-weight="700" fill="var(--uyari)">Uyarı · iş emri açıldı</text>
     <text x="${X(-27)}" y="${Y(5.6) + 52}" text-anchor="middle" font-size="11" fill="var(--muted)">birkaç gün üst üste yüksek</text>
     <circle cx="${X(-11)}" cy="${Y(12.1)}" r="7" fill="none" stroke="var(--kritik)" stroke-width="2.5"/>
     <rect x="${X(-11) - 96}" y="${Y(12.1) + 16}" width="192" height="44" rx="9" fill="rgba(6,8,12,.92)" stroke="var(--kritik)"/>
     <text x="${X(-11)}" y="${Y(12.1) + 35}" text-anchor="middle" font-size="12.5" font-weight="700" fill="var(--kritik)">Kritik · nöbetçiye SMS</text>
     <text x="${X(-11)}" y="${Y(12.1) + 52}" text-anchor="middle" font-size="11" fill="var(--muted)">iki ayrı sensör de doğruluyor</text></g>
   <g data-step="3"><polygon points="${fan}" fill="rgba(255,47,121,.16)"/>
     <line x1="${X(0)}" y1="${Y(17.6)}" x2="${X(14.8)}" y2="${Y(25)}" stroke="var(--acil)" stroke-width="2.5" stroke-dasharray="7 5"/>
     <circle cx="${X(14.8)}" cy="${Y(25)}" r="6" fill="var(--acil)"/>
     <rect x="${X(1.5)}" y="${Y(17.6) + 26}" width="236" height="50" rx="10" fill="rgba(6,8,12,.94)" stroke="var(--acil)"/>
     <text x="${X(1.5) + 12}" y="${Y(17.6) + 48}" font-size="15" font-weight="700" fill="var(--acil)">Acil seviyesine ~2 hafta</text>
     <text x="${X(1.5) + 12}" y="${Y(17.6) + 67}" font-size="11.5" fill="var(--muted)">bugünkü gidişe göre, bir aralıkla</text></g>
  </svg>`;
}
add({
  title: 'Haftalar önce: ne zaman başladı, ne kadar vakit var', section: 'Uyarı', time: '45 sn',
  html: () => `${HD('04 · Uyarı', 'Ne zaman başladı, ne kadar vaktimiz var?')}
<div class="body"><div class="card grow" style="padding:10px 14px;--d:.1s" data-a="blur">${trendSVG()}</div>
<div class="row" style="gap:10px;flex-wrap:wrap">
  <span class="chip uyari" data-step="1">Uyarı: birkaç gün üst üste görülünce</span>
  <span class="chip acil" data-step="2">Başlangıç: geriye dönük bulunur</span>
  <span class="chip brand" data-step="3">Kalan süre: bugünkü gidişe göre tahmin</span>
  <span class="chip" data-step="3">Veri yetersizse tahmin uydurmaz</span>
</div></div>`,
  notes: `Ürünün "haftalar önce" sözü bu grafikte. Sarı çizgi, kapaktaki bağlantının — Çıkış 7, L2 — diğer fazlara göre farkı, gün gün.

[→] Fark birkaç gün üst üste yüksek kalınca Uyarı açılıyor ve bakım için iş emri yazılıyor. Telefon çalmıyor. Fark büyümeye devam edip ikinci, bağımsız bir sensör de doğrulayınca Kritik oluyor ve nöbetçiye SMS gidiyor.

[→] Bakım ekibinin ilk sorusu: bu ne zaman başladı? Sistem geçmişe dönüp bozulmanın Eylül ortası civarında hızlandığını buluyor. Bunu tek bir gün olarak değil, bir aralık olarak veriyoruz; çünkü bozulma bir anda değil, yavaş yavaş olur.

[→] İkinci soru: ne kadar vaktimiz var? Bugünkü gidişle Acil seviyesine yaklaşık iki hafta. Bu da bir aralık. Bu bilgi bir iş emrinin bu haftaya mı gelecek aya mı yazılacağına karar vermeye yeter. Ve yeterli veri yoksa sistem sayı uydurmuyor, "yetersiz geçmiş" yazıyor.`,
  use: `<b>Kullan:</b> 3 adım: alarm işaretleri → başlangıç → kalan süre. <b>Not:</b> eğri şematiktir; tarihler 3 Ekim demo koşusundandır, prova koşusuyla tazeleyin. <b>Jüri sorarsa — "Bozulma hızlanırsa?":</b> Tahmin bugünkü gidişi uzatır; bozulma hızlanırsa gerçek tarih daha erken olabilir. Bunu ekranda da yazıyoruz.`,
});

/* ===================================================================== */
/* 10 · BASTIRILMIŞ ALARMLAR                                              */
/* ===================================================================== */
const SUP = [
  ['Hava ısındı', 'Bütün bağlantılar birlikte ısınıyorsa sorun pano değil, hava.'],
  ['Şebekeden gelen bozulma', 'Üç faz birden etkileniyorsa kaynak şebeke. Alarm silinmez, bir kademe düşürülür.'],
  ['Yük aniden değişti', 'Sıcaklık yeni yüke yetişene kadar beklenir.'],
  ['Gece, yük çok düşük', 'Küçük kusurlar görünmez; sistem "görünürlük düşük" der.'],
  ['Sensör düştü ya da kaydı', 'Cihaz için iş emri açılır; sağlam bağlantıya ekip gönderilmez.'],
  ['İlk hafta', 'Sistem panoyu tanır; bu sırada mutlak sıcaklık sınırları yine açık.'],
];
add({
  title: 'Bastırılmış alarmlar', section: 'Uyarı', time: '45 sn',
  html: () => `${HD('04 · Uyarı', 'Ürettiğimiz değil, üretmediğimiz alarmlar.')}
<div class="body"><div class="row grow">
  <div class="card col" style="width:560px;--d:.15s" data-a="up">
    <p class="cap">Sıcak hava dalgası · 40 bağlantı</p>
    <div class="jgrid" id="sjg">${Array.from({ length: 40 }, (_, i) => `<i style="--k:${i}"></i>`).join('')}</div>
    <div class="g2" style="margin-top:6px">
      <div class="cnt bad"><span class="cl">Sabit eşikli sistem</span><b id="sc1">0</b><span class="cs">alarm</span></div>
      <div class="cnt good"><span class="cl">PANO GÖZ</span><b id="sc2">0</b><span class="cs">alarm · fazlar arası fark değişmedi</span></div>
    </div>
    <p class="sub" id="scap" style="margin-top:8px">Tüm bağlantılar birlikte ısınıyor.</p>
  </div>
  <div class="col grow sup" data-step="1">
    ${SUP.map(([c, t], i) => `<div class="card tight suprow" data-a="left" style="--d:${.08 * i}s"><b>${c}</b><span>${t}</span></div>`).join('')}
    <p class="sub" style="margin-top:2px">Açılmayan her alarm, gerekçesiyle ayrı bir ekranda listelenir: "neden bana söylemedin?" sorusunun cevabı orada.</p>
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
    const HOT = 'Kırk bağlantının hepsi birlikte ısınıyor. Fazlar aynı havada: aralarındaki fark değişmedi.';
    if (REDUCED) { draw(6.1, HOT); return null; }
    let raf, t0 = performance.now();
    const loop = t => {
      const T = ((t - t0) / 1000) % 9;
      const rise = T < 1 ? 0 : T < 4 ? 6.1 * H.ease((T - 1) / 3) : T < 7.4 ? 6.1 : 6.1 * (1 - H.ease((T - 7.4) / 1.4));
      draw(rise, T < 1 ? 'Normal bir öğleden sonra.' : T < 7.4 ? HOT : 'Hava serinliyor.');
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return { stop() { cancelAnimationFrame(raf); } };
  },
  notes: `Şimdi ürünün bence en önemli parçası: ürettiğimiz değil, üretmediğimiz alarmlar.

Solda bir sıcak hava dalgası. Kırk bağlantının hepsi birden ısınıyor. Sabit eşikli bir sistem, eşiği geçen her bağlantı için ayrı bir alarm üretiyor — sayacı izleyin. Bizim sistemimiz sıfır alarm üretiyor; çünkü üç faz aynı havayı soluyor ve aralarındaki fark değişmiyor. Bu okuma pano hakkında değil, hava hakkında.

[→] Sağda bastırma kurallarından bazıları. Her biri tek bir soruya cevap veriyor: bu okuma gerçekten pano hakkında mı, yoksa hava, şebeke, yük ya da kendi cihazımız hakkında mı?

En önemlisi şu: bir sensör düşerse ya da kayarsa, sensör için iş emri açılıyor. Bozuk bir sensör yüzünden ekibi sağlam bir bağlantıyı sökmeye göndermek, sistemin güvenilirliğini tek seferde bitirir.

Yüz panoyu izleyen bir operatör, her sıcak günde yüz alarm alırsa sistemi üçüncü ayda kapatır. Bu liste o yüzden var ve her satırın gerekçesi ekranda yazıyor.`,
  use: `<b>Kullan:</b> ASLA KESİLMEZ. Animasyon 9 sn'de döner; sol sayaç eşiği geçen bağlantıları sayar ve tepe noktada 13'te durur. Sonra → ile kural listesi. <b>Kapanış cümlesi:</b> "Bu bir hata ayıklama günlüğü değil — kendi ekranı olan bir ürün."`,
});

/* ===================================================================== */
/* 11 · ARK OLAYI                                                         */
/* ===================================================================== */
add({
  title: 'Ark olayı: koruma bizde değil', section: 'Uyarı', time: '35 sn',
  html: () => `${HD('04 · Uyarı', 'Ark oluştu. Panoyu biz değil, ark rölesi açtı.')}
<div class="body"><div class="row grow">
  <div class="card col arc" style="width:420px;--d:.1s" data-a="up">
    <div class="flash"><i></i><i></i><i></i>${IC.flash}</div>
    <div class="arc-kv"><span>Panoyu kim açtı?</span><b>Ark rölesi · milisaniyede</b></div>
    <div class="arc-kv"><span>Işığı hangi dedektör gördü?</span><b class="mono">X2:3</b></div>
    <div class="arc-kv"><span>Hangi röle açtı?</span><b class="mono">K5</b></div>
    <div class="arc-kv"><span>Dedektörler sağlam mı?</span><b>görebildiklerimiz sağlam</b></div>
    <p class="sub arc-note">Göremediğimiz dedektörler varsa ekranda "kapsam dışı" diye yazar.</p>
  </div>
  <div class="col grow">
    <div class="card grow" data-a="up" style="display:flex;flex-direction:column;--d:.25s"><p class="cap">Olaydan nöbetçiye</p>
      <div class="tl">${[['Ark oluşur, röle panoyu açar', 'milisaniyeler içinde · bizi beklemez'], ['Ağ geçidi röleyi okur', 'olay kaydı alınır'], ['Sunucu olayı çözer', 'nerede, hangi dedektör, ne zaman'], ['En yakın ekibe SMS + konum', 'birkaç saniye içinde']].map(([t, d], i) =>
        `<div class="tli s${i}" data-a="left" style="--d:${.4 + i * .18}s"><span class="n">${i + 1}</span><div><h3>${t}</h3><p>${d}</p></div></div>`).join('')}</div>
    </div>
    <div class="row" style="gap:10px;--d:1.2s" data-a="up"><span class="chip kritik">Koruma rölenin işi; bizim işimiz haber vermek</span><span class="chip">Pano enerjisiz kaldı: ekip yönlendirilir</span></div>
  </div>
</div></div>`,
  notes: `Ark oluştu. Panoyu biz açmadık; panoda zaten bulunan ark rölesi açtı, milisaniyeler içinde. PANO GÖZ koruma yapmıyor ve yapmaya çalışmıyor; koruma bizi beklemez, beklememeli de.

Bizim işimiz ark olduktan sonra başlıyor: ışığı hangi dedektör gördü, hangi röle açtı, ne zaman oldu. Ve bunu birkaç saniye içinde, panonun konumuyla birlikte en yakın nöbetçi ekibe haber vermek.

Bir şeye daha dikkat edin: "görebildiklerimiz sağlam" yazıyor. Röleye bağlı bazı dedektörlerin durumunu okuyamıyoruz ve ekranda tam olarak öyle yazıyor. Görmediğimiz bir şeyi gördü gibi göstermek, en tehlikeli hatadır.`,
  use: `<b>Kullan:</b> ASLA KESİLMEZ. Canlı demoda "Ark olayı" senaryosu aynı kartı açar. <b>Jüri sorarsa — "Ne kadar sürede haber veriyorsunuz?":</b> 4–13 saniye; rölenin kendi veri yenileme süresi üretici tarafından belgelenmediği için tek sayı vermiyoruz. <b>"Röleyi uzaktan test edebilir misiniz?":</b> Hayır; yalnız sahada, yetkili kişi ve fiziksel anahtarla.`,
});

/* ===================================================================== */
/* 12 · ALARM: EN YAKIN EKİBE, KONUMUYLA                                  */
/* ===================================================================== */
/* Mesajlar sistemin ürettiğiyle aynıdır: compose() ve compose_location()
   (panogoz/notify/escalation.py); değerler demo koşusundandır. */
const SMS = 'PANO GÖZ KRİTİK · SOKE-14 · Ç7·L2·pabuç θ=17.6K · bağlantıyı torkla · ACİL\'e 15 g (13-19) · onay: TAMAM 1 0541';
const ROUTE = 'M44,88 C70,86 86,68 112,62 S176,50 206,42';
function alarmMapSVG() {
  return `<svg viewBox="0 0 260 112" class="mapsvg" aria-label="Pano konumu ve en yakın ekip">
   <rect width="260" height="112" fill="#111d18"/>
   <path d="M0,34 L260,62" stroke="#1b2a23" stroke-width="3"/>
   <path d="M34,0 L64,112" stroke="#1b2a23" stroke-width="4"/>
   <path d="M128,0 C138,40 172,72 184,112" stroke="#1b2a23" stroke-width="4" fill="none"/>
   <path d="M0,78 C60,74 92,44 150,46 S228,22 260,18" stroke="#26372f" stroke-width="7" fill="none"/>
   <path d="${ROUTE}" stroke="var(--brand)" stroke-width="2.6" stroke-dasharray="5 4" fill="none"/>
   <rect x="98" y="72" width="44" height="17" rx="8.5" fill="rgba(6,8,12,.9)" stroke="var(--brand)"/>
   <text x="120" y="84" text-anchor="middle" font-size="10" font-weight="700" fill="var(--brand2)">~3 km</text>
   <circle cx="44" cy="88" r="6" fill="var(--izle)" stroke="#0b0f15" stroke-width="2"/>
   <text x="54" y="104" font-size="10" fill="var(--muted)">Söke ekibi</text>
   <circle cx="206" cy="42" r="8" fill="none" stroke="var(--kritik)" stroke-width="2"><animate attributeName="r" values="6;18" dur="1.6s" repeatCount="indefinite"/><animate attributeName="opacity" values="1;0" dur="1.6s" repeatCount="indefinite"/></circle>
   <path d="M206,42 C200,33 198,30 198,26 a8,8 0 1,1 16,0 c0,4 -2,7 -8,16z" fill="var(--kritik)"/>
   <circle cx="206" cy="26" r="3" fill="#fff"/>
   <text x="194" y="22" text-anchor="end" font-size="10" font-weight="700" fill="var(--ink)">SOKE-14</text>
   <circle id="mcrew" r="5" fill="var(--brand)" stroke="#fff" stroke-width="1.5" opacity="0"><animateMotion id="mgo" dur="3.2s" begin="indefinite" fill="freeze" path="${ROUTE}"/></circle>
  </svg>`;
}
add({
  title: 'Alarm: en yakın ekibe, konumuyla', section: 'Uyarı', time: '45 sn',
  html: () => `${HD('04 · Uyarı', 'Alarm, konumuyla birlikte en yakın ekibe gider.')}
<div class="body"><div class="row grow">
  <div class="card ladder" style="width:350px;--d:.1s" data-a="up">
    <p class="cap">Seviye merdiveni</p>
    ${[['Acil', 'acil', 'derhal ekip · SMS + sesli arama', 1], ['Kritik', 'kritik', 'bir hafta içinde ziyaret · SMS', 1], ['Uyarı', 'uyari', 'iş emri · planlı ziyaret', 0], ['İzle', 'izle', 'haftalık özete girer', 0], ['Bilgi', '', 'yalnız kayıt', 0]].map(([n, c, a, ph], i) =>
      `<div class="lad ${c}" style="--w:${100 - i * 8}%;--d:${.2 + (4 - i) * .1}s" data-a="right"><span class="ln">${n}</span><span class="la">${a}</span>${ph ? `<span class="lp">${IC.phone}</span>` : ''}</div>`).join('')}
    <p class="sub" style="margin-top:8px">Yalnız Kritik ve Acil bir telefonu çaldırır. Gerisi iş emri ya da özet olur.</p>
  </div>
  <div class="phone alarm" data-a="up" style="--d:.25s"><div class="pscr">
    <div class="ptop"><span class="mono">GSM</span><span class="sig">${IC.antenna}${IC.battery}</span></div>
    <div class="pclock"><b>02:14</b><span>Perşembe · gece nöbeti</span></div>
    <div class="alm" data-a="pop" style="--d:.6s"><span class="ab">${IC.bell}</span><div><b>KRİTİK ALARM</b><small>PANO GÖZ · şimdi</small></div></div>
    <div class="ntf" data-a="up" style="--d:1s"><div class="nh"><span>Mesajlar · PANO GÖZ</span><em>şimdi</em></div><p>${SMS}</p></div>
    <div class="ntf" data-a="up" style="--d:1.5s"><div class="nh"><span>KONUM · SOKE-14</span><em>~3 km</em></div>${alarmMapSVG()}
      <div class="mp">${IC.pin}<span>Size en yakın nöbetçi ekip: <b>Söke</b></span></div></div>
    <div class="pack" data-step="1"><span class="bub out">TAMAM 1 0541</span><span class="okb">${IC.check} Onaylandı · Söke ekibi üstlendi</span></div>
  </div></div>
  <div class="col grow esc near">
    <div class="card tight escrow" data-a="left" style="--d:.5s"><span class="mono et">hemen</span><div><h3>1. kademe · en yakın nöbetçi ekip</h3><p class="sub">SMS + harita konumu · kişiye özel onay kodu</p></div></div>
    <div class="card tight escrow" data-a="left" style="--d:.65s"><span class="mono et">onay yoksa</span><div><h3>2. kademe · şef + sesli arama</h3><p class="sub">Acil'de daha kısa, Kritik'te daha uzun bekler</p></div></div>
    <div class="card tight escrow" data-a="left" style="--d:.8s"><span class="mono et">sonra</span><div><h3>3. kademe · işletme müdürü</h3><p class="sub">Her adım kayda geçer</p></div></div>
    <div class="card tight why" data-a="up" style="--d:.95s"><p class="cap">Neden en yakın ekip?</p><p class="sub">Altı ekibi birden uyandırmak yerine tek doğru ekip. Bergama'daki bir pano Söke'ye değil, Manisa'ya gider.</p><p class="sub" style="margin-top:6px">Tekrar SMS'leri ve sesli arama da aynı ekibe gider; konum bir kez gelir.</p></div>
    <div class="row" style="gap:6px;flex-wrap:wrap;--d:1.1s" data-a="up"><span class="chip">iki ayrı sensör doğrulamadan telefon çalmaz</span><span class="chip">Acil hiçbir koşulda susturulmaz</span></div>
  </div>
</div></div>`,
  scene(el, { REDUCED }) {
    const dot = el.querySelector('#mcrew'), go = el.querySelector('#mgo');
    return {
      step(n) {
        if (n < 1) { dot.setAttribute('opacity', 0); return; }
        dot.setAttribute('opacity', 1);
        if (REDUCED) { dot.setAttribute('cx', 206); dot.setAttribute('cy', 42); return; }
        try { go.beginElement(); } catch (e) { /* SMIL yoksa nokta varışta durur */ dot.setAttribute('cx', 206); dot.setAttribute('cy', 42); }
      },
      stop() {},
    };
  },
  notes: `Gece ikiyi on dört geçe. Nöbetçi teknikerin telefonu çalıyor.

Önce seviye merdiveni: Bilgi yalnız kayda geçer, İzle haftalık özete girer, Uyarı bir iş emri açar. Yalnızca Kritik ve Acil bir telefonu çaldırır. Bu tek kural, sistemin üçüncü aydan sonra da açık kalmasını sağlıyor.

Telefon çaldığında ilk mesaj neyin olduğunu söylüyor: hangi pano, hangi bağlantı, ne yapılmalı, ne kadar vakit var ve onay kodu. Hemen ardından ikinci mesaj geliyor: panonun haritadaki yeri. Ve bu mesaj herkese değil, panoya en yakın nöbetçi ekibe gidiyor. Söke'deki pano için Söke ekibi, üç kilometre. Bergama'daki bir pano için Söke değil, Manisa ekibi.

Neden? Altı ekibi birden uyandırırsanız, bir süre sonra hiçbiri telefona bakmaz. Yanlış ilçeden ekip gönderirseniz, Kritik bir olay yolda Acil'e dönüşür.

[→] Ekip kodu yazıp yanıtlıyor; olay onaylanıyor ve iş o ekibin üzerinde. Kod kişiye ve olaya özel; başkası ya da yanlış kod onaylayamaz.

Onay gelmezse merdiven yükseliyor: önce şef ve sesli arama, ardından işletme müdürü. Ve çok sayıda alarm aynı anda gelse bile Acil asla susturulmuyor.`,
  use: `<b>Kullan:</b> Bildirimler sırayla düşer; → ile onay gelir ve ekip haritada panoya ilerler. <b>Dürüst sınır:</b> SMS ve sesli arama <b>simüle</b> edilir, gerçek operatör hattından mesaj gitmedi. Mesafe ekibin <b>görev yerinden</b>, kuş uçuşu ölçülür; canlı konum yok (telefonda uygulama gerektirir). Harita bağlantısı yalnız SMS metnidir, sunucu dışarı istek atmaz; kurumun kendi CBS adresine tek satırda çevrilir. <b>Not:</b> iki mesaj da sistemin gerçekte ürettiği biçimdedir (Bildirimler sekmesinde görünür); değerler demo koşusundandır. Bekleme süreleri: Acil 15 dk, Kritik 45 dk.`,
});

/* ===================================================================== */
/* 13 · SCADA ENTEGRASYONU                                                */
/* ===================================================================== */
const REGS = [['Pano', 'SOKE-14'], ['Sağlık puanı', '67 / 100'], ['En çok ısınan bağlantı', 'Çıkış 7 · L2'], ['Isınma eğilimi', 'artıyor'], ['Görünürlük', 'tam'], ['Verinin tazeliği', '2 sn önce']];
add({
  title: 'SCADA entegrasyonu', section: 'Entegrasyon', time: '30 sn',
  html: () => `${HD('05 · Entegrasyon', 'Mevcut SCADA\'ya kendi dilinde bağlanır.')}
<div class="body"><div class="row grow">
  <div class="card col" style="width:500px;--d:.1s" data-a="up"><p class="cap">Her pano = SCADA'da hazır bir veri bloğu</p>
    <div class="regs">${Array.from({ length: 48 }, (_, i) => `<i class="${[0, 2, 6, 7, 8, 9, 45].includes(i) ? 'k' : ''}" style="--k:${i}"></i>`).join('')}</div>
    <p class="sub rg-leg"><i></i>Turuncu kareler: sağdaki bilgiler. Blok her panoda aynı düzende.</p>
    <p class="sub" style="margin-top:auto">SCADA mühendisi bloğu bir kez tanımlar, her pano için kopyalar. Standart Modbus TCP; ek yazılım gerekmez.</p></div>
  <div class="col grow">
    <div class="card tight" data-a="up" style="--d:.25s"><p class="cap">SCADA ne okur?</p><table class="rt">
      ${REGS.map(([n, e], i) => `<tr data-a="fade" style="--d:${.4 + i * .1}s"><td>${n}</td><td class="b">${e}</td></tr>`).join('')}</table></div>
    <div class="card tight deny" data-step="1"><span class="dn">${IC.lock}</span><div><h3>Yazma denemesi reddedilir</h3><p class="sub">SCADA veriyi okur ama panoya komut gönderemez. Ark rölesine kimliksiz bir erişim yolu açmıyoruz.</p></div></div>
    <div class="row" style="gap:8px;flex-wrap:wrap;--d:1.1s" data-a="up"><span class="chip ok">Ekrandaki sayı = SCADA'daki sayı</span><span class="chip uyari">IEC 104 / OPC UA: planlandı</span></div>
  </div>
</div></div>`,
  notes: `Şartname SCADA entegrasyonu istiyor. Çalışan bir Modbus bağlantısı teslim ettik; Modbus, SCADA dünyasının ortak dili.

Her panonun SCADA'da hazır bir veri bloğu var. SCADA mühendisi bu bloğu bir kez tanımlıyor ve her pano için kopyalıyor; yüz pano için yüz kez uğraşmıyor.

SCADA'nın okuduğu bilgiler sağda: hangi pano, sağlık puanı, en çok ısınan bağlantı, ısınmanın eğilimi, görünürlük ve verinin ne kadar taze olduğu. Ekranda gördüğünüz sayı ile SCADA'daki sayı aynı kaynaktan geliyor; ikisi çelişemez. Verinin tazeliği özellikle önemli: klasik bir sistem bağlantı koptuğunda son değeri sessizce göstermeye devam eder, bizimki "bu veri bayat" der.

[→] Ve SCADA'dan yazmayı denerseniz reddediliyor. Modbus'ta kimlik doğrulama yok; ark rölesine komut verebilen bir sisteme kimliksiz yazma yolu açmak kabul edilemez.`,
  use: `<b>Kullan:</b> → ile yazma reddi. Canlı gösterim gerekirse <span class="mono">python sunum/scada_kanit.py</span> pano bloğunu okur ve yazmanın reddedildiğini gösterir. <b>Jüri sorarsa — "Adresleme?":</b> pano n'in bloğu 1000 + 48 × (n − 1); SOKE-14 → 1624. <b>Dürüst sınır:</b> IEC 104 ve OPC UA için nokta listesi yazıldı, sunucu kurulmadı.`,
});

/* ===================================================================== */
/* 14 · CANLI DEMO / EKRANLAR                                             */
/* ===================================================================== */
const SCR = [['filo', 'Filo', 'Bütün panolar haritada, seviyeleriyle'], ['ikiz', 'Dijital ikiz', 'Panonun kesiti, her bağlantının durumu'], ['kanit', 'Kanıt', 'Bir uyarının arkasındaki veri'], ['bastir', 'Bastırılanlar', 'Açılmayan alarmlar, gerekçeleriyle'], ['prpd', 'Kısmi deşarj', 'Yalıtım bozulmasının elektriksel izi'], ['scada', 'SCADA', 'SCADA\'ya giden canlı veri']];
add({
  title: 'Canlı demo: izleme ekranları', section: 'Demo', time: '5 dk demo',
  html: () => `${HD('06 · Demo', 'Operasyon ekibi ne görüyor?')}
<div class="body"><div class="row grow">
  <div class="frame grow" data-a="blur" style="--d:.1s"><div class="bar"><i></i><i></i><i></i><span id="scru">127.0.0.1:8080/#/filo</span></div>
    <div class="scr">${SCR.map(([k], i) => `<img src="${A['ekran_' + k]}" data-k="${k}" class="${i === 0 ? 'on' : ''}" alt="">`).join('')}</div></div>
  <div class="col scrl" style="width:300px">${SCR.map(([k, t, d], i) => `<button class="sci ${i === 0 ? 'on' : ''}" data-i="${i}" data-a="left" style="--d:${.2 + i * .07}s"><b>${t}</b><span>${d}</span><i></i></button>`).join('')}</div>
</div></div>`,
  /* PDF'te ekranlar dönemez: altısı tek sayfada, sunumda canlı gösterilir. */
  printHtml: () => `${HD('06 · Demo', 'Operasyon ekibi ne görüyor?')}
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

Demo akışı (5 dakika):
1 · Filo (35 sn) — Haritada bütün panolar, seviyeleriyle. "Her pano bir nokta; renk, durumu."
2 · Dijital ikiz (45 sn) — SOKE-14'e gir. Panonun kesiti, her bağlantının durumu. Gri olanlar izlenmeyen bara bölmesi: "Gri bir eksiklik değil, bir beyan."
3 · Yavaş bozulma (50 sn) — Çıkış 7 L2'nin kanıt ekranı: farkın gün gün yükselişi, başlangıç tarihi ve kalan süre.
4 · Bastırılan alarmlar (45 sn, ASLA KESİLMEZ) — Alarmlar → Bastırılan. Sıcak hava ve şebeke olayı satırları, gerekçeleriyle.
5 · Ark olayı (45 sn, ASLA KESİLMEZ) — Demo panelinden "ark olayı" senaryosu: hangi dedektör, hangi röle, nöbetçiye bildirim.
6 · SCADA (40 sn) — Pano bloğunu oku; yazma denemesi reddedilir.
7 · Gece görünürlüğü (25 sn) — Düşük yüklü bir pano: "görünürlük düşük".
8 · Kapanış (15 sn).

Canlı sistem açılmazsa: bu slayttaki ekranlar sırayla döner; sağdaki listeden tıklayarak anlatın.`,
  use: `<b>Kullan:</b> Ekranlar 6 sn'de bir değişir; sağdan tıklayıp sabitleyebilirsiniz. Bu slayt canlı demonun <b>yedeğidir</b>. <b>Süre daralırsa kesme sırası:</b> 1) SCADA → tek cümle · 2) gece görünürlüğü → tek cümle · 3) dijital ikiz açıklaması kısalır. 4 ve 5 numaralı adımlar her durumda tam kalır. <b>Senaryo uçları:</b> GET /api/scenarios · POST /api/scenario/{key} · POST /api/demo/reset.`,
});

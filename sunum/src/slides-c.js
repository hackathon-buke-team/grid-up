/* ======================================================================
   SLAYTLAR 17–23 · saha, ölçek, maliyet, dürüstlük, kapanış · jüri soruları
   ====================================================================== */

/* ===================================================================== */
/* 17 · SAHA UYGULAMASI                                                   */
/* ===================================================================== */
add({
  title: 'Saha uygulaması', section: 'Saha', time: '45 sn',
  html: () => `${HD('09 · Saha', 'İki kişi, iki buçuk saat, kesinti yok.')}
<div class="body"><div class="row grow">
  <div class="card center" style="width:330px;--d:.1s" data-a="blur">
    <svg viewBox="0 0 260 260" class="clk">
      <circle cx="130" cy="130" r="104" fill="none" stroke="var(--line)" stroke-width="18"/>
      <circle cx="130" cy="130" r="104" fill="none" stroke="url(#clg)" stroke-width="18" stroke-linecap="round" transform="rotate(-90 130 130)" data-a="draw" style="--d:.3s;--dur:2.2s"/>
      <defs><linearGradient id="clg" x1="0" x2="1" y1="0" y2="1"><stop offset="0" stop-color="#f78320"/><stop offset="1" stop-color="#ffb066"/></linearGradient></defs>
      <text x="130" y="124" text-anchor="middle" font-size="40" font-weight="700" fill="var(--ink)">2:30</text>
      <text x="130" y="150" text-anchor="middle" font-size="13" fill="var(--muted)">saat · 2 kişi</text>
      <text x="130" y="170" text-anchor="middle" font-size="11.5" fill="var(--dim)">ilk 5 kurulum 3,5–4 sa</text>
    </svg>
  </div>
  <div class="col grow steps6">
    ${[[IC.camera, 'Güvenlik kapısı', 'Hiçbir şeye dokunmadan termal kamerayla tara. Bir pabuç 110 °C üstündeyse dur, montaj yapma, arıza bildir.', '10 dk', 'kritik'],
       [IC.therm, '6 kelepçe · Ç6 ve Ç7', 'Kablo kılıfı üzerine, pabuçtan 50–100 mm aşağı, çıplak metale ≥ 25 mm. Emniyet teli kablo kanalı askısına.', '30 dk', ''],
       [IC.eye, 'TN-IR nişan sihirbazı', 'Mıknatıs kaide, yukarı bakış; üç referans vida kilitlenene kadar bitmez.', '20 dk', ''],
       [IC.wave, 'PD-01 · M12 saplama', 'HFCT yalnız PE iletkenine. Faza takılırsa 400 A × 6 mV/A = 2,4 V: otomatik doğrulama yakalar.', '15 dk', ''],
       [IC.plug, 'GW-01 · DIN ray + 10 A priz', 'İki ayrı RS-485 hattı. DSO kuralı enerjili iletken indirmeye izin vermezse planlı kesintiye ertelenir.', '30 dk', 'uyari'],
       [IC.phone, 'Dizüstüsüz devreye alma', 'Telefonla etiket OCR → NFC dokunuş → çizimde parmakla işaretle → otomatik doğrulama → test SMS.', '35 dk', 'ok']].map(([ic, t, d, m, c], i) =>
      `<div class="card tight st6 ${c}" data-a="left" style="--d:${.15 + i * .09}s"><span class="si">${ic}</span><div><h3>${t}</h3><p class="sub">${d}</p></div><span class="mono sm">${m}</span></div>`).join('')}
  </div>
</div>
<div class="row" style="gap:10px;flex-wrap:wrap" data-step="1"><span class="chip brand">7 gün öğrenme: taban toplanır, mutlak limitler açık</span><span class="chip">PANO iş emri ≠ CİHAZ iş emri, asla karışmaz</span><span class="chip">100 modül = 25 ekip-günü</span><span class="chip">devreye alma paketi çevrimdışı da tamamlanır</span></div>
</div>`,
  notes: `Kurulum, şartnamenin en çok vurguladığı risk: kalabalık bir pano, hayati risk ve şebeke etkisi. Bu yüzden saha prosedürünü adım adım yazdık.

İki kişi, hedef iki buçuk saat; ilk beş kurulumda üç buçuk-dört saat bekliyoruz. Kesinti gerekmiyor, çünkü yalnız alt kablo bölmesine, ölçü kolonuna ve mevcut prize dokunuyoruz.

İlk adım bir güvenlik kapısı: hiçbir şeye dokunmadan termal kamerayla pabuç sırası taranıyor. Bir pabuç 110 derecenin üstündeyse ekip duruyor ve montaj yapmıyor; çünkü zaten bozulmuş bir bağlantının yanında çalışmak, ölçmek için değil onarmak için gidilecek bir durum.

Sonra kelepçeler, termal dizinin nişanı, RF düğümü ve ağ geçidi. Tek bir adımı dürüstçe işaretledik: RS-485 hattını indirmek enerjili bir panoda iletken çekmeyi gerektiriyor. Dağıtım şirketinin çalışma kuralları buna izin vermiyorsa bu adım planlı bir kesintiye ertelenir; sistem RS-485 olmadan da çalışır, yalnız analizör ve ark kanalları kapalı kalır.

Devreye alma dizüstü bilgisayarsız, telefonla: etiket kamerayla okunuyor, her cihaza NFC ile dokunuluyor, teknisyen cihazın yerini pano çizimi üzerinde parmağıyla işaretliyor. Elle yazılan pano numarası filo yönetiminde en sık görülen hata; onu ortadan kaldırıyoruz.

[→] Sonra yedi günlük öğrenme penceresi — mutlak limitler bu sırada da açık. Ve iki iş emri türü asla karışmıyor: pano iş emri elektrik işi, cihaz iş emri ise panoya dokunmadan sensörü düzeltmek.`,
  use: `<b>Kullan:</b> Liste sırayla gelir; → ile alt satır. <b>Ezberlenecek:</b> güvenlik kapısı > 110 °C → DUR · HFCT faza takılırsa 2,4 V_pp · ekip başına günde 2 modül → 100 modül = 25 ekip-günü; 1000 modül = 4 ekiple 3 ay. <b>Dürüst sınır:</b> NFC akışı tasarlandı, NFC yongası tezgâhta denenmedi. Enerjili RS-485 indirme izni açık soru (docs/11 S4). <b>Jüri sorarsa — "Kurulumda kesinti?":</b> Profil B kesinti istemez; RS-485 adımı DSO kuralına bağlı olarak planlı kesintiye ertelenebilir.`,
});

/* ===================================================================== */
/* 18 · ÖLÇEKLENEBİLİRLİK                                                 */
/* ===================================================================== */
const SCALE = [
  ['Zarf / sn', ['15', '150', '1 500'], [15, 150, 1500], 'izle'],
  ['Dedektör CPU', ['%2,2', '%21,6', '2,2 çekirdek'], [2.16, 21.6, 216], 'olcum'],
  ['Disk · kararlı hâl', ['18 GB', '180 GB', '1,8 TB'], [18, 180, 1800], 'brand'],
];
add({
  title: 'Ölçeklenebilirlik', section: 'Ölçek', time: '40 sn',
  html: () => `${HD('10 · Ölçek', '1000 panoda pahalı bir sunucu istemez.', 'Kaynak sayıları bu projenin kodu üzerinde ölçüldü; 10 000 pano kestirimdir.')}
<div class="body"><div class="row grow">
  <div class="card grow scl" data-a="up" style="--d:.15s">
    <div class="sch"><span></span><b>100 pano</b><b>1 000 pano</b><b>10 000 pano</b></div>
    ${SCALE.map(([n, lab, v, c], r) => `<div class="scr2"><span class="sn">${n}</span>${v.map((x, j) => `<div class="sb"><i class="${c}" data-a="grow-x" style="--d:${.4 + r * .25 + j * .12}s;width:${Math.max(3, Math.log10(x * 10) / Math.log10(v[2] * 10) * 100)}%"></i><span class="mono">${lab[j]}</span></div>`).join('')}</div>`).join('')}
    <div class="scr2 srv"><span class="sn">Sunucu</span><div class="mono">2 vCPU · 8 GB</div><div class="mono">4 vCPU · 16 GB</div><div class="mono">bölge başına 4 düğüm</div></div>
    <p class="sub" style="margin-top:6px">Çubuklar logaritmik. Ölçülen: RLS güncellemesi 2,67 µs · pano değerlendirmesi 12,95 ms · 112 panolu filo adımı 270 ms.</p>
  </div>
  <div class="col" style="width:400px">
    <div class="card" data-a="up" style="--d:.3s"><p class="cap">Paylaşılan seri hat yok</p>
      <svg viewBox="0 0 360 150" class="topo">${[0, 1, 2, 3].map(i => `<rect x="${8 + i * 88}" y="10" width="74" height="54" rx="8" fill="#0d131b" stroke="var(--line2)"/><text x="${45 + i * 88}" y="32" text-anchor="middle" font-size="11" fill="var(--muted)">${i === 3 ? 'Pano N' : 'Pano ' + (i + 1)}</text><rect x="${25 + i * 88}" y="40" width="40" height="16" rx="4" fill="var(--brand-soft)" stroke="var(--brand)"/><text x="${45 + i * 88}" y="52" text-anchor="middle" font-size="9" class="mono" fill="var(--brand)">GW</text>
        <path id="tp${i}" d="M${45 + i * 88},64 C${45 + i * 88},100 180,96 180,120" fill="none" stroke="var(--line2)"/><circle r="3" fill="var(--izle)"><animateMotion dur="${1.6 + i * .3}s" repeatCount="indefinite"><mpath href="#tp${i}"/></animateMotion></circle>`).join('')}
        <rect x="130" y="118" width="100" height="28" rx="8" fill="#0d131b" stroke="var(--izle)"/><text x="180" y="137" text-anchor="middle" font-size="12" fill="var(--izle)">Broker</text></svg>
      <p class="sub">Her panonun kendi kısa RS-485 hattı ve kendi master'ı var. 1000. pano, diğer 999'un hattına sıfır yük ekler.</p></div>
    <div class="card" data-step="1"><p class="cap">Asıl ölçek kısıtları</p>
      <p class="sub"><b class="muted">Operatörün dikkati:</b> 100 panoda haftada en fazla 3 telefon çaldıran alarm hedefi.</p>
      <p class="sub" style="margin-top:6px"><b class="muted">Kurulum kapasitesi:</b> yazılım değil, takvimi ekip-günü belirler.</p></div>
  </div>
</div></div>`,
  notes: `Şartname en az yüz modülü işleyebilecek bir tasarım ve kaynak değerlendirmesi istiyor. Sayıları kendi kodumuz üzerinde ölçtük.

Yüz panoda saniyede on beş zarf geliyor. Dedektör bir çekirdeğin yüzde ikisini kullanıyor; disk kararlı hâlde on sekiz gigabayt. Bin panoda dedektör bir çekirdeğin beşte birinden az, disk yüz seksen gigabayt. On bin panoda iki çekirdek ve bölge başına düğümler — bu kestirim, ölçülen en büyük filomuz 112 pano.

İnsanların "ölçeklenmez" diye korktuğu kısım, her bağlantı için çalışan kestiriciler; on bin panoda bile bir çekirdeğin yüzde 1,3'ü. Kısacası bu sistem bin panoda pahalı bir sunucu istemez; isterse o istek dedektörden değil veritabanından gelir.

Bir de klasik itiraz var: yüz cihazı tek bir 19200 baud RS-485 hattına koyarsanız tarama saniyeler sürer. İtiraz doğru — ve biz o hattı kurmuyoruz. Her panonun kendi kısa hattı ve kendi master'ı var. Ölçekleme seri hatta değil, broker'da oluyor.

[→] Gerçek ölçek kısıtları başka yerde: operatörün dikkati — bir nöbetçi günde beş-on gerçek alarmdan fazlasını işleyemez; bastırma ve seviye merdiveni tam bunun için var. Ve kurulum kapasitesi: yazılım değil, ekip-günü projenin takvimini belirler.`,
  use: `<b>Kullan:</b> Çubuklar logaritmik ölçekte; sayıları okuyun, çubuklara değil. → ile kısıtlar. <b>Dürüst sınır:</b> ölçülen en büyük filo 112 pano; 10 000 pano yük testi yapılmadı. SQLite yazma yolu hesabın 11 katı maliyetli; ~10 000 panoda biter, TimescaleDB sürücüsü <b>yazılmadı</b>. ICD MAX_PANELS = 200 bilinçli hackathon sınırı. <b>Ezberlenecek:</b> 100 pano = 4 841 zarf/s kapasiteye karşı 15 zarf/s · Mosquitto tek düğüm 1000 panoya yeter · 10 000'de bölge başına broker ve 0–300 sn jitter.`,
});

/* ===================================================================== */
/* 19 · MALİYET – FAYDA                                                   */
/* ===================================================================== */
function costSVG() {
  const X = H.sc(0, 5, 70, 690), Y = H.sc(-120, 160, 420, 24);
  const L = (capex, net) => [0, 1, 2, 3, 4, 5].map(t => [X(t), Y((-capex + net * t) / 1000)]);
  const uni = L(109591, 15885), dec = L(109591, 50540);
  return `<svg viewBox="0 0 720 460" class="costsvg">
   ${[-100, -50, 0, 50, 100, 150].map(v => `<line x1="70" x2="690" y1="${Y(v)}" y2="${Y(v)}" stroke="${v === 0 ? 'var(--muted)' : 'var(--line)'}" ${v === 0 ? 'stroke-width="1.5"' : ''}/><text x="62" y="${Y(v) + 4}" text-anchor="end" class="mono" font-size="11" fill="var(--dim)">${v > 0 ? '+' : ''}${v}k€</text>`).join('')}
   ${[0, 1, 2, 3, 4, 5].map(t => `<text x="${X(t)}" y="444" text-anchor="middle" class="mono" font-size="11" fill="var(--dim)">${t}. yıl</text>`).join('')}
   <text x="70" y="12" font-size="11" fill="var(--dim)">kümülatif net nakit · 100 modül</text>
   <path d="${H.line(uni)}" fill="none" stroke="var(--kritik)" stroke-width="3.2" data-a="draw" style="--d:.4s"/>
   <circle cx="${X(5)}" cy="${Y(-30.166)}" r="6" fill="var(--kritik)" data-a="pop" style="--d:2s"/>
   <text x="${X(5) - 10}" y="${Y(-30.166) - 16}" text-anchor="end" font-size="13" font-weight="700" fill="var(--kritik)" data-a="fade" style="--d:2s">tekdüze dağıtım: −€30 166</text>
   <g data-step="1"><path d="${H.line(dec)}" fill="none" stroke="var(--ok)" stroke-width="3.2" data-a="draw"/>
     <circle cx="${X(2.168)}" cy="${Y(0)}" r="7" fill="none" stroke="var(--ok)" stroke-width="2.5" data-a="pop" style="--d:1s"/>
     <text x="${X(2.168) + 12}" y="${Y(0) + 22}" font-size="12.5" font-weight="700" fill="var(--ok)" data-a="fade" style="--d:1.1s">2,2 yılda geri öder</text>
     <circle cx="${X(5)}" cy="${Y(143.109)}" r="6" fill="var(--ok)" data-a="pop" style="--d:1.5s"/>
     <text x="${X(5) - 10}" y="${Y(143.109) - 12}" text-anchor="end" font-size="13" font-weight="700" fill="var(--ok)" data-a="fade" style="--d:1.5s">en kötü ondalık: +€143 109</text></g>
  </svg>`;
}
add({
  title: 'Maliyet ve fayda', section: 'Maliyet', time: '55 sn',
  html: () => `${HD('11 · Maliyet', 'Önce kötü haber.')}
<div class="body"><div class="row grow">
  <div class="card" style="width:740px;--d:.1s" data-a="blur">${costSVG()}</div>
  <div class="col grow">
    <div class="card tight kpi" data-a="up" style="--d:.3s"><div class="v kritik">6,9 yıl</div><div class="l">100 pano, her panoya eşit: 5 yılda parasını geri ödemez. Başa baş 175 panoda.</div></div>
    <div class="card tight kpi" data-step="1"><div class="v ok">2,2 yıl</div><div class="l">Aynı 100 modül, filonun en kötü %10'una: arıza kaydı, yaş, yük ve son termografi ile seçilir.</div></div>
    <div class="card tight kpi" data-step="2"><div class="v izle">3,3 yıl</div><div class="l">1000 pano tekdüze: öğrenme eğrisi donanımı %28,8 ucuzlatır. Pano başına yıllık €184.</div></div>
    <div class="card tight" data-step="2" style="border-color:rgba(247,131,32,.4)"><p class="cap">Tespit oranından bağımsız fayda</p><p class="sub"><b class="brand">%43,5</b> · termografi ziyareti €130 → €21,7 / pano / yıl. Hiçbir kusur bulunmasa bile gerçekleşir.</p></div>
  </div>
</div></div>`,
  notes: `Maliyet–fayda bölümüne kötü haberle başlıyoruz, çünkü bir dağıtım şirketinin varlık yönetimi ekibi bu hesabı zaten kendisi yapacak.

Her panoya eşit dağıtılmış yüz modüllük bir pilot, beş yılda parasını geri ödemez. Beş yıllık toplam sahip olma maliyeti yüz elli dört bin euro, fayda yüz yirmi dört bin; net eksi otuz bin euro. Geri ödeme 6,9 yıl. Başa baş yüz yetmiş beş panoda geliyor.

[→] Ama çözüm daha fazla pano almak değil. Aynı yüz modülü filonun en kötü onda birine koyarsanız — dağıtım şirketi bu panoları zaten biliyor: arıza kaydı, yaş, yük faktörü, son termografi raporu — olay hızları ortalamanın dört katı ve geri ödeme 2,2 yıla iniyor. Beş yılda artı yüz kırk üç bin euro.

[→] Bin panoda tekdüze dağıtım da 3,3 yılda geri öder, çünkü öğrenme eğrisi donanımı yüzde 28,8 ucuzlatıyor ve sabit kalemler seyreliyor.

Ve faydanın en sağlam kalemi: yüzde 43,5'i hiçbir kusuru tespit etmesek bile gerçekleşiyor. Bugün bu panolara yılda iki kez termal kamerayla gidiliyor; PANO GÖZ ile bara bölmesi ve çatı için üç yılda bir ziyaret yeterli. Bu kalemi bir dağıtım şirketi bir öğleden sonra kendi bakım bütçesinden doğrulayabilir; bizim modelimize inanması gerekmez.

Soru kaç pano alacağınız değil, hangi panolara koyacağınız.`,
  use: `<b>Kullan:</b> 3 adım: kırmızı çizgi → yeşil çizgi → 1000 pano + F1. <b>Ezberlenecek:</b> modül €470,59 (1000 adet) / €660,91 (100 adet) · kurulum €150 · 100 pano 5 yıl TCO €154 591 · tip testleri €22 500 tek seferlik. <b>Dürüst sınır:</b> V9–V16 olay hızları ve maliyetleri DSO kayıtlarından <b>doğrulanmadı</b>; hepsi etiketli varsayım (docs/07 §1). En kırılgan varsayım arıza hızı V11 (%1,2/pano/yıl). Toplumsal maliyet (VoLL) bilinçli olarak nakit akışına katılmadı. <b>Not:</b> docs/07 §4.3'teki "+€142 109" toplamı yanlış; 5 × 50 540 − 109 591 = <b>+€143 109</b>. Belgeyi düzeltin.`,
});

/* ===================================================================== */
/* 20 · VERİ DÜRÜSTLÜĞÜ                                                   */
/* ===================================================================== */
function seriesSVG(kind) {
  const W = 520, Hh = 150, n = 152, r = H.rng(kind === 'real' ? 5 : 9), pts = [];
  for (let i = 0; i < n; i++) {
    const hr = (i * .25) % 24;
    let v = kind === 'real' ? 45 + 26 * Math.max(0, Math.sin((hr - 6) / 24 * 2 * Math.PI)) + 9 * Math.exp(-Math.pow(hr - 20, 2) / 6) + (r() - .5) * 3 : 15 + Math.floor(r() * 76);
    pts.push([10 + i / (n - 1) * (W - 20), Hh - 8 - (v - 10) / 85 * (Hh - 20)]);
  }
  return `<svg viewBox="0 0 ${W} ${Hh}" class="sersvg"><path d="${H.line(pts)}" fill="none" stroke="${kind === 'real' ? 'var(--ok)' : 'var(--kritik)'}" stroke-width="1.8" data-a="draw" style="--d:${kind === 'real' ? .3 : .6}s;--dur:2.2s"/></svg>`;
}
add({
  title: 'Verilen veri ve dijital ikiz', section: 'Dürüstlük', time: '35 sn',
  html: () => `${HD('12 · Dürüstlük', 'Verilen akım verisi sentetik; bunu ölçtük.')}
<div class="body"><div class="row grow">
  <div class="col" style="width:560px">
    <div class="card tight" data-a="up" style="--d:.1s"><p class="cap">Gerçek bir fider böyle görünür · dijital ikiz</p>${seriesSVG('real')}<p class="mono sub">lag-1 otokorelasyon &gt; 0,97 · günün saati akımı belirler</p></div>
    <div class="card tight" data-a="up" style="--d:.25s"><p class="cap">"Akım Sensörü" sayfası · 152 satır, 15 dk</p>${seriesSVG('given')}<p class="mono sub">=RASTGELEARADA(15;90) ile uyumlu düzgün gürültü</p></div>
  </div>
  <div class="col grow">
    <div class="tests">${[['Lag-1 otokorelasyon', '+0,0003', '> +0,97'], ['var(fark) / var(seri)', '2,0023', '≪ 2'], ['Fazlalık basıklık', '−1,2129', '≈ 0'], ['KS, U(14,5; 90,5)', 'D = 0,0526', '> 0,1101'], ['χ², 76 tam sayı', 'p = 0,446', 'reddedilmeli'], ['Gün-üstü şekil korelasyonu', 'r = +0,0596', '> 0,85']].map(([t, m, e], i) =>
      `<div class="card tight tst" data-a="pop" style="--d:${.4 + i * .1}s"><span class="tn">${t}</span><b class="mono kritik">${m}</b><span class="mono te">beklenen ${e}</span></div>`).join('')}</div>
    <div class="card" data-step="1" style="border-color:rgba(53,192,122,.4)"><p class="cap">Bu yüzden</p><p class="sub" style="color:var(--ink);font-size:15px">Modeli bu veriye uydurmadık. Fizikten türetilmiş bir dijital ikiz kurduk: 17 senaryo, 7'si negatif kontrol. Kabul kriterlerini ölçtük ve verilen kümeyi de aynı testlerden geçirdik.</p>
      <p class="sub" style="margin-top:8px">Paketteki hiçbir başarım sayısı saha verisiyle doğrulanmış değil. Gerçek yanlış alarm oranı yalnız etiketli bir pilot sahada ölçülebilir.</p></div>
  </div>
</div></div>`,
  notes: `Yarışmada bize bir akım verisi verildi. Önce onu analiz ettik ve şunu bulduk: veri sentetik. Bunu bir "yakaladık" gösterisi olarak değil, sonuçlarını hesaba katmak için söylüyoruz.

Üstte gerçek bir fiderin nasıl görünmesi gerektiği: sabah yükselen, öğleden sonra tepe yapan, akşam ikinci bir tepe yapan bir eğri. Komşu iki ölçüm neredeyse aynıdır; lag-1 otokorelasyonu 0,97'nin üstündedir.

Altta verilen veri: lag-1 otokorelasyonu artı sıfır virgül sıfır sıfır sıfır üç. Altı bağımsız test aynı şeyi söylüyor: bu, Excel'in RASTGELEARADA fonksiyonuyla on beş ile doksan arasında üretilmiş düzgün dağılımlı gürültüyle uyumlu. Ayrıca sıcaklık-nem sayfası tamamen boş, etiketli arıza geçmişi yok, kardeş fazı yok, anomali yok.

[→] Bu yüzden modelimizi bu veriye uydurmadık. Fizikten türetilmiş bir dijital ikiz kurduk: on yedi senaryo, bunların yedisi negatif kontrol — yani "alarm vermemesi gereken" durumlar. Ve dürüst olalım: bu paketteki hiçbir başarım sayısı saha verisiyle doğrulanmış değil. Gerçek yanlış alarm oranı ancak etiketli saha geçmişi olan bir pilot tesiste ölçülebilir. Bunu sizden saklamak yerine, pilotun ölçeceği ilk şey olarak öneriyoruz.`,
  use: `<b>Kullan:</b> Ton önemli: suçlama değil, sonuç. "Bunu ortaya çıkarmak bir başarı değil, sonuçlarını dikkate almak bir zorunluluk." <b>Ek bulgu (sorulursa):</b> sayfa başlığı "125 mA = 5 A" der (40:1), formül 600000/100 = 6,0 A/mA uygular; fark 3,33 kat. 125 mA × 6 = 750 A, belirtilen 600 A tam ölçek değil. <b>Ezberlenecek:</b> n = 152 · min 15 · maks 90 · ortalama 52,13 · saatlik ANOVA F(23,128) = 1,375, p = 0,135. <b>Kaynak:</b> README §6, docs/09, <span class="mono">python -m analysis.supplied_data</span>.`,
});

/* ===================================================================== */
/* 21 · YAPMADIKLARIMIZ                                                   */
/* ===================================================================== */
add({
  title: 'Yapmadıklarımız', section: 'Dürüstlük', time: '40 sn',
  html: () => `${HD('12 · Dürüstlük', 'Yapmadıklarımız da tasarımın parçası.')}
<div class="body"><div class="nogrid">
  ${[['Bara bölmesine sensör', 'AG giriş kesicisi yok. Enerjisiz yapmak dağıtım merkezini OG tarafından karartmak demek. Profili yazmadık, sildik.'],
     ['Enerji hasadı iddiası', 'Teorik olarak mümkün, ölçmedik. Ölçmediğimizi teklif etmeyiz: Li-SOCl₂ pil, 9–16 yıl tasarım ömrü.'],
     ['Pano başına derin öğrenme', 'Otokodlayıcı yavaş sürüklenmeyi öğrenir ve yeniden üretir; avladığımız 0,2 K/hafta sinyaline kör.'],
     ['SCADA\'dan yazma yolu', 'Modbus\'ta kimlik doğrulama yok. Ark rölesine komut verebilen sisteme kimliksiz yazma açılmaz.'],
     ['Sparkplug B rozeti', 'DDATA için QoS 0 zorunlu; bizim tamponumuz PUBACK ister. Fikirleri aldık, rozeti bıraktık.'],
     ['Tek başına PD ile ekip', '400 V\'ta klasik PD oluşmaz (Paschen minimumu 327 V). RF kanalı ısıl bulguyu yalnız destekler.']].map(([t, d], i) =>
    `<div class="card nog" data-a="pop" style="--d:${.15 + i * .1}s"><span class="nx">${IC.x}</span><h3>${t}</h3><p class="sub">${d}</p></div>`).join('')}
</div>
<div class="row" style="gap:10px;flex-wrap:wrap" data-step="1"><span class="chip uyari">Belgelendi, kodlanmadı: KiCad şematik/PCB · IEC 104 / OPC UA sunucusu · gerçek SMS gönderimi · TimescaleDB sürücüsü · OG hücre donanımı</span></div>
</div>`,
  notes: `Bir hackathon teslimi için bence en değerli bölüm: bilerek yapmadıklarımız.

Bara bölmesine sensör koymadık. Panoda AG giriş kesicisi yok; o bölmeye girmek ya dağıtım merkezini karartmak ya da 2312 amper taşıyan çıplak baranın kapağını enerjili açmak demek. Erken bir taslakta o profil vardı; sildik.

Enerji hasadı iddia etmiyoruz. Teorik olarak mümkün ama ölçmedik; ölçmediğimiz bir şeyi teklif etmiyoruz.

Pano başına derin öğrenme kullanmadık; çünkü tam aradığımız yavaş sürüklenmeye yapısal olarak kör.

SCADA'dan yazma yolu açmadık; Modbus'ta kimlik doğrulama yok.

Sparkplug B rozetini takmadık; çünkü spesifikasyon bizim dayanıklılık mekanizmamızı yasaklıyor. Rozeti takıp kuralı çiğnemek sahtekârlık olurdu.

Ve kısmi deşarj kanalını tek başına ekip yönlendirmek için kullanmıyoruz; 400 voltta klasik kısmi deşarj zaten oluşmaz. RF kanalı gevşek bağlantı mikro-arkını ölçüyor ve ısıl bulguyu destekliyor.

[→] Bir de "belgelendi ama kodlanmadı" listemiz var: KiCad çizimleri, IEC 104 sunucusu, gerçek SMS gönderimi, TimescaleDB sürücüsü ve OG hücre donanımı. Her belgemizin sonunda bu başlıkla bir liste var; jüri ne teslim edildiğini ve ne edilmediğini tek bakışta görebilsin diye.`,
  use: `<b>Kullan:</b> Kartlar sırayla açılır; her biri için tek cümle yeter. Süre daralırsa yalnız ilk üçünü söyleyin. <b>Jüri sorarsa — "OG hücreler?":</b> OG çizimi verilmedi; istedik, alınamadı. docs/10 jenerik 36 kV kablo bölmesi için konsept: HFCT kablo ekranı topraklamasında, TEV, ultrasonik, θ kablo başlıklarında; hücre başına donanım ~€502 (özel HFCT) / ~€2 656 (katalog HFCT50). Montaj zaten planlanmış bir bakım penceresine eklenir.`,
});

/* ===================================================================== */
/* 22 · ŞARTNAME KARŞILIĞI                                                */
/* ===================================================================== */
const REQ = [
  ['Kabin içi modül tasarımı', 'Kısmen', 'uyari', '9 cihaz, montaj yerleşimi, TEDAŞ madde eşlemesi, BOM. KiCad çizilmedi.'],
  ['Elektronik dokümantasyon', 'Kısmen', 'uyari', 'Blok şema, I/O, pin dizilimi, katman yığını, güç ağacı, derating.'],
  ['Yazılım mimarisi', 'Tamam', 'ok', 'C99 firmware + durum makinesi, Python sunucu, saf JS arayüz.'],
  ['Monitoring', 'Tamam', 'ok', 'Filo, dijital ikiz, kanıt, bastırılanlar, PRPD, SCADA ekranları.'],
  ['SCADA · Modbus haritalama', 'Tamam', 'ok', 'Çalışan TCP slave, ICD v2.0, salt okunur, nokta listesi CSV.'],
  ['On-premise, kamu bulutu yok', 'Tamam', 'ok', 'Tek komut, internet yok, dış servis çağrısı yok.'],
  ['SMS / anlık bildirim', 'Kısmen', 'uyari', 'Merdiven, onay kodu, fırtına tavanı çalışıyor; gönderim simüle.'],
  ['Ölçek · ≥ 100 modül', 'Tamam', 'ok', '112 pano ile ölçüldü; kaynak profili raporlandı.'],
];
add({
  title: 'Şartname karşılığı', section: 'Özet', time: '30 sn',
  html: () => `${HD('13 · Özet', 'Şartnamenin istedikleri, bugünkü durumuyla.')}
<div class="body"><div class="row grow">
  <div class="card grow reqs" data-a="up" style="--d:.1s">${REQ.map(([t, s, c, d], i) => `<div class="rq" data-a="left" style="--d:${.2 + i * .08}s"><span class="chip ${c}">${c === 'ok' ? IC.check : '◐'} ${s}</span><b>${t}</b><span class="sub">${d}</span></div>`).join('')}</div>
  <div class="col" style="width:330px">
    ${[['33 bin', 'satır Python · sunucu, dedektör, ikiz'], ['4,5 bin', 'satır C99 · uç düğüm firmware'], ['7,9 bin', 'satır arayüz · bağımlılıksız JS'], ['172', 'otomatik test · gerileme takımı'], ['11 + ICD', 'teknik belge · ≈ 5 800 satır']].map(([v, l], i) =>
      `<div class="card tight kpi mini" data-a="left" style="--d:${.4 + i * .1}s"><div class="v">${v}</div><div class="l">${l}</div></div>`).join('')}
  </div>
</div></div>`,
  notes: `Şartnamenin "beklenen teknik çıktılar" listesini bugünkü durumla eşledik ve renk yerine kelimeyle yazdık: Tamam ya da Kısmen.

Yazılım mimarisi, izleme ekranları, SCADA Modbus haritalaması, on-premise altyapı ve yüz modül ölçeği tamam. Modül tasarımı ve elektronik dokümantasyon kısmen: blok şema, I/O tabloları, pin dizilimleri, katman yığını ve BOM var; KiCad çizimleri yok. SMS kısmen: eskalasyon merdiveni, onay kodu ve fırtına tavanı çalışıyor; gönderim simüle ediliyor.

Arkasındaki iş: yaklaşık otuz üç bin satır Python, dört buçuk bin satır C99 firmware, sekiz bine yakın satır bağımlılıksız arayüz kodu, yüz yetmiş iki otomatik test ve on bir teknik belge artı SCADA arayüz dokümanı. Gerileme testleri daha önce gerçekten yaşadığımız hataları yeniden üretip kilitliyor — negatif kontrollerin gerçek boru hattında alarm üretmediğini ve aynı koşumda pozitif kontrolün ürettiğini doğrulayan test dahil.`,
  use: `<b>Kullan:</b> Hızlı geçin; jüri tabloyu okur. "Kısmen" satırlarını siz söyleyin, sorulmasını beklemeyin. <b>Sayılar:</b> 3 Ekim itibarıyla <span class="mono">panogoz/analysis/tests</span> Python 32 969 satır, <span class="mono">firmware</span> 4 487 satır, <span class="mono">frontend</span> 7 881 satır; <span class="mono">pytest --collect-only</span> 172 test. Teslim öncesi tekrar sayın.`,
});

/* ===================================================================== */
/* 23 · KAPANIŞ                                                           */
/* ===================================================================== */
add({
  title: 'Kapanış', section: 'Kapanış', noCorner: true, time: '30 sn',
  html: () => `
<div class="cover end">
  <div class="cv-l">
    <p class="kicker" data-a="fade">Kapanış</p>
    <h1 class="end-t" data-a="up" style="--d:.1s">Soru kaç pano değil, hangi pano.</h1>
    <div class="ends">
      <div data-a="up" style="--d:.3s"><b>θ</b><span>Yükten ve mevsimden bağımsız; montaj gününden itibaren çalışır.</span></div>
      <div data-a="up" style="--d:.42s"><b>Bastırma</b><span>Üretmediğimiz her alarmın Türkçe, sayılı bir gerekçesi var.</span></div>
      <div data-a="up" style="--d:.54s"><b>Dürüstlük</b><span>Kör olduğumuz yeri, aralığı ve bilmediğimizi ekranda söyleriz.</span></div>
    </div>
    <div class="cv-logos" data-a="fade" style="--d:.8s"><img src="${A.adm}" alt="ADM Elektrik Dağıtım"><i></i><img src="${A.gdz}" alt="GDZ Elektrik Dağıtım"><i></i><img src="${A.gridup}" alt="Grid Up" style="height:46px"></div>
    <p class="thanks" data-a="up" style="--d:.9s">Teşekkürler. Sorularınızı bekliyoruz.</p>
  </div>
  <div class="cv-r" data-a="blur" style="--d:.2s">${coverSVG('ed')}</div>
</div>`,
  scene(el, ctx) { return SL[0].scene(el, ctx, 'ed'); },
  notes: `Kapatırken üç şey.

Bir: θ. Yükten ve mevsimden bağımsız bir ölçü; geçmiş istemediği için montaj gününden itibaren çalışıyor ve haftalar önce, tarihiyle ve kalan süresiyle haber veriyor.

İki: bastırma. Yüz panoyu yönetilebilir kılan şey ürettiğimiz alarmlar değil, üretmediğimiz alarmların gerekçeli listesi.

Üç: dürüstlük. Kör olduğumuz yeri, gecikmenin bir aralık olduğunu ve verinin neyi ölçemediğini ekranda söylüyoruz. Bir dağıtım şirketi, ne zaman güvenmemesi gerektiğini söyleyen bir sisteme güvenir.

Ve son cümle: aynı yüz modülü filonun en kötü onda birine koyarsanız 2,2 yılda geri öder. Soru kaç pano alacağınız değil, hangi panolara koyacağınız.

Teşekkürler. Sorularınızı bekliyoruz.`,
  use: `<b>Kullan:</b> Son cümleden sonra susun ve bekleyin. Soru-cevap için <b>Q</b> tuşu hazır cevap panelini açar (arama kutulu). Belirli bir slayta dönmek için slayt numarasını yazıp Enter'a basın ya da <b>O</b> ile haritayı açın.`,
});

/* ===================================================================== */
/* JÜRİ SORULARI — hazır cevaplar (Q)                                    */
/* ===================================================================== */
const QA = [
  { q: 'Kalibrasyonu nasıl yapıyorsunuz?', a: 'θ bir <b>fark</b>tır; iki sensörün ortak sapması çıkar. Mutlak doğruluk yalnız 110/130 °C limitleri için gerekir ve TMP117 fabrikada ±0,1 °C\'dir. IR dizisinde kardeş-fark gürültüsü 0,8 K alınır.', ref: 'docs/04 §1' },
  { q: 'Yükü nereden biliyorsunuz? Çıkışlarda CT yok.', a: 'Doğru: dağıtım şirketinin CT\'si yalnız girişte (2500/5). Bu yüzden <b>her kelepçe kendi split-core CT\'sini</b> taşır. Kalan 34 pabuçta yük analizörün faz akımından orantısal pay ile <b>kestirilir</b> ve ekranda öyle etiketlenir.', ref: 'docs/02 §1.1' },
  { q: 'Neden bara bölmesine koymuyorsunuz?', a: 'Panoda <b>AG giriş kesicisi yok</b> (Madde 2.2.10.2.vi). Enerjisiz yapmak tüm dağıtım merkezini OG tarafından karartmak demek; enerjili açmak ise 2312 A\'lik çıplak bara üzerinde çalışmak. Bara bölmesinin 30 + çatının 4 bağlantısı için periyodik termografi devam eder, sıklığı düşer.', ref: 'docs/05 §1' },
  { q: 'Yapay zekâ nerede?', a: 'Kasıtlı olarak yok. Kayan pencerede eğitilen bir otokodlayıcı, avladığımız 0,2 K/hafta sürüklenmesini <b>öğrenir ve yeniden üretir</b>: yapısal körlük. Aylarca temiz geçmiş ister (yok), 100 panoya 100 model işletme yükü getirir. Kullandığımız: fizik tabanlı kestirici + istatistiksel süreç kontrolü + tavanlı olabilirlik füzyonu; hepsinin birimi var.', ref: 'docs/04 §11' },
  { q: 'PD ölçümünüz IEC 60270\'e göre mi?', a: '<b>Hayır ve iddia etmiyoruz.</b> 400 V\'ta klasik PD oluşmaz (Paschen minimumu 327 V). RF kanalı gevşek bağlantı mikro-arkını ölçer, pC <b>eşdeğeri</b> raporlar ve AG\'de tek başına ekip yönlendirmez.', ref: 'docs/04 §9.3' },
  { q: 'Yanlış alarm hızınız ne?', a: 'Analitik: 100 pano × 40 bağlantıda <b>4,8 günde bir yanlış CUSUM geçişi</b>. Ama geçiş alarm değildir; alarm üç şart ister (CUSUM > 8, θ ≥ 5 K, son 5 günün 3\'ü). Bu bir üst sınırdır. Gerçek oran ancak etiketli pilot sahada ölçülür.', ref: 'docs/04 §5.4' },
  { q: 'Standart hangi sıcaklığı yasaklıyor?', a: 'TS EN 61439-1, bara cıvatalı bağlantısı için sayısal limit koymaz. 110/130 °C bizim <b>mühendislik çıkarımımızdır</b> ve öyle etiketlidir (105 °C kablo yalıtımı, 120 °C üstü oksidasyon, kalayın 232 °C erimesi). Çizelge 8 değerleri gelirse tek satırda değişir.', ref: 'docs/04 §8.2' },
  { q: 'Pil ne kadar dayanır?', a: '<b>Hesaplandı, ölçülmedi:</b> 8,4–16 yıl; bağlayıcı düğüm PD-01. Tezgâh ölçümü açık sorular listemizde. 8. yıl toplu hücre değişimi gösterge olarak modül başına ~€18 + ziyaret.', ref: 'docs/02 §5' },
  { q: 'Bozulma hızlanırsa "eşiğe kalan gün" ne olur?', a: 'Model doğrusal ve ekranda yazıyor. Isıl kaçış süper-doğrusaldır; o modda sayı <b>iyimserdir</b>, gerçek tarih daha erken olabilir. 21 günde 14 geçerli gün yoksa sayı verilmez (YETERSİZ_GEÇMİŞ). Nominal %90 aralığın simülasyondaki kapsaması %88–93.', ref: 'docs/04 §6.1' },
  { q: 'Neden Sparkplug B değil?', a: 'Sparkplug 3.0 DDATA için <b>QoS 0 zorunlu</b> kılar; dayanıklılığımız PUBACK ile ilerleyen store-and-forward filigranına dayanır. Doğum/vasiyet/monoton sıra numarası fikirlerini aldık, rozeti bıraktık.', ref: 'docs/01 §6' },
  { q: 'Gerçekten SMS gidiyor mu? WhatsApp?', a: 'GSM modem AT diyaloğu ve SMPP oturumu <b>simüle</b> edilir, transkript kaydedilir; gerçek kanaldan mesaj gitmedi. Mesaj gövdesi, UCS-2 bütçesi, onay kodu, merdiven ve fırtına tavanı kodlu ve testli. WhatsApp için bulut tarafı gerektiğinden yalnız "pano + seviye + onay kodu" çıkan bir DMZ aynalama servisi önerildi, kurulmadı.', ref: 'notify/escalation.py' },
  { q: 'Neden bulut yok? Ölçek için gerekmez mi?', a: 'Gerekçe kurumsal: şebeke topolojisi ve arıza geçmişi kritik altyapı verisi. Teknik olarak da gerekmiyor: 100 pano ≈ 18 GB disk, 1000 pano tek çekirdeğin dörtte biri. 500 GB NVMe 100 panoda 25 kat baş boşluğu bırakır.', ref: 'docs/01 §4–5' },
  { q: '1000 / 10 000 panoda ne olur?', a: '1000 pano: 4 vCPU / 16 GB, tek Mosquitto. 10 000: bölge başına (ADM / GDZ, sonra il) yığın + federe salt okunur görünüm, bölge başına broker, ağ geçitlerinde 0–300 sn jitter. SQLite ~10 000\'de biter; TimescaleDB sürücüsü yazılmadı. ICD MAX_PANELS = 200.', ref: 'docs/06' },
  { q: 'Verilen veriyi neden kullanmadınız?', a: 'Sentetik: lag-1 otokorelasyon +0,0003 (gerçek fiderde > 0,97), altı bağımsız test. Sıcaklık-nem sayfası boş, etiketli arıza yok, kardeş yapısı yok. Fizikten türetilmiş dijital ikiz kurduk ve verilen kümeyi de aynı kabul testlerinden geçirdik.', ref: 'README §6 · docs/09' },
  { q: 'OG hücreler ne olacak?', a: 'OG çizimi verilmedi; istedik. docs/10 jenerik 36 kV kablo bölmesi için <b>konsept</b>: HFCT kablo ekranı topraklamasında, TEV, ultrasonik, kablo başlıklarında θ. Hücre başına ~€502 (özel HFCT). Montaj planlı bakım penceresine eklenir; ayrı kesinti istemez.', ref: 'docs/10' },
  { q: 'Kurulum için kesinti gerekir mi?', a: 'Hayır: kit yalnız alt kablo bölmesi, ölçü kolonu DIN rayı ve mevcut 10 A prize dokunur. Tek istisna RS-485\'in TVOC-2 ve MPR-53CS\'e indirilmesi: DSO kuralı enerjili iletken indirmeye izin vermezse planlı kesintiye ertelenir; sistem RS-485\'siz de çalışır.', ref: 'docs/05 §3' },
  { q: 'SCADA\'dan komut verebilir miyiz?', a: 'Hayır. Modbus slave istisnasız salt okunur; FC 05/06/15/16 exception 0x01 döner. TVOC-2 otokontrol ve açma sıfırlama yalnız ağ geçidinde, operatör kimlik doğrulaması <b>ve</b> fiziksel anahtar arkasında.', ref: 'docs/PANOGOZ-ICD-v2.0' },
  { q: 'Sensör arızası sağlam bir bağlantıyı sıktırır mı?', a: 'Hayır. DEVICE_MOUNT_LOST, AIM_SHIFTED, DRIFT, STUCK, CELL_LOW <b>cihaz iş emri</b> üretir, pano iş emri asla. Kelepçe düşerse okunan sıcaklık havanınkidir; tork iş emri yapısal olarak engellenir.', ref: 'docs/05 §8.2' },
  { q: 'Nem ve yoğuşmayı nasıl izliyorsunuz?', a: 'Su havadan değil, çiy noktasının altındaki <b>yüzeyde</b> yoğuşur. Duvar sıcaklığını havanın τ ≈ 90 dk gecikmesi olarak modelliyoruz, pay = T_duvar − T_çiy. Boolean değil pay raporlanır. Tek başına İzle/Uyarı; yükselen PD ile birlikte Kritik.', ref: 'docs/04 §9.2' },
  { q: 'Ağ geçidi ile sunucu bağlantısı koparsa?', a: 'Üç yerel kural çalışmaya devam eder (≥ 90 °C, Δ ≥ 20 K, ark). 20 000 çerçeve halka tamponda tutulur, PUBACK geldikçe filigran ilerler; ark olayı tamponun başına alınır. Tampon dolarsa en eskiler düşer ve düşen sayısı bir sağlık metriği olarak yayınlanır.', ref: 'docs/01 §2.1' },
  { q: 'Maliyeti ne, ne zaman geri öder?', a: 'Modül donanımı €470,59 (1000 adet) / €660,91 (100 adet), kurulum €150. 100 pano tekdüze: 6,9 yıl (5 yılda −€30 166). Aynı 100 modül en kötü ondalıkta: <b>2,2 yıl</b>. 1000 pano tekdüze: 3,3 yıl. Faydanın %43,5\'i tespit oranından bağımsız (termografi ziyareti).', ref: 'docs/07' },
  { q: 'Kardeş fazlardan ikisi birden bozulursa?', a: 'Medyan kendisi hariç iki kardeşten alınır, yani ikisinin ortalamasıdır. İki faz eşit bozulursa her birinin θ\'sı yaklaşık <b>yarıya iner ama görünür kalır</b>; sağlam üçüncü faz negatif θ gösterir. Üç faz birden ve aynı hızda bozulursa θ bunu <b>görmez</b>: bu yöntemin kör noktasıdır ve onu her koşulda açık olan mutlak limitler (90/110/130 °C) kapsar.', ref: 'formülden türetildi · belgede ayrıca yazılı değil, provada doğrulayın' },
];

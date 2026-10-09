/* ======================================================================
   SLAYTLAR 15–18 · saha, doğrulama, özet, kapanış · jüri soruları
   ====================================================================== */

/* ===================================================================== */
/* 15 · SAHA UYGULAMASI                                                   */
/* ===================================================================== */
add({
  title: 'Saha uygulaması', section: 'Saha', time: '35 sn',
  html: () => `${HD('07 · Saha', 'İki kişi, yaklaşık iki buçuk saat, kesinti yok.')}
<div class="body"><div class="row grow">
  <div class="card center" style="width:330px;--d:.1s" data-a="blur">
    <svg viewBox="0 0 260 260" class="clk">
      <circle cx="130" cy="130" r="104" fill="none" stroke="var(--line)" stroke-width="18"/>
      <circle cx="130" cy="130" r="104" fill="none" stroke="url(#clg)" stroke-width="18" stroke-linecap="round" transform="rotate(-90 130 130)" data-a="draw" style="--d:.3s;--dur:2.2s"/>
      <defs><linearGradient id="clg" x1="0" x2="1" y1="0" y2="1"><stop offset="0" stop-color="#f78320"/><stop offset="1" stop-color="#ffb066"/></linearGradient></defs>
      <text x="130" y="124" text-anchor="middle" font-size="40" font-weight="700" fill="var(--ink)">2:30</text>
      <text x="130" y="150" text-anchor="middle" font-size="13" fill="var(--muted)">saat · 2 kişi</text>
      <text x="130" y="170" text-anchor="middle" font-size="11.5" fill="var(--dim)">dizüstü bilgisayar gerekmez</text>
    </svg>
  </div>
  <div class="col grow steps6">
    ${[[IC.camera, 'Önce güvenlik', 'Hiçbir şeye dokunmadan termal kamerayla tara. Aşırı sıcak bir bağlantı varsa montaj yapılmaz, arıza bildirilir.', '10 dk', 'kritik'],
       [IC.therm, 'Isıl kelepçeler', 'Kabloların üzerine geçirilir, emniyet teliyle sabitlenir.', '30 dk', ''],
       [IC.eye, 'Termal kamera', 'Mıknatısla tabana oturur; telefondaki nişan yardımıyla hizalanır.', '20 dk', ''],
       [IC.wave, 'Ortam düğümü', 'Topraklama barasına takılır; yanlış takılırsa sistem kendisi uyarır.', '15 dk', ''],
       [IC.plug, 'Ağ geçidi', 'Ölçü kolonuna takılır, panodaki mevcut prizden beslenir.', '30 dk', 'uyari'],
       [IC.phone, 'Telefonla devreye alma', 'Etiketi okut, cihaza dokun, yerini çizimde işaretle; sistem kendini test eder.', '35 dk', 'ok']].map(([ic, t, d, m, c], i) =>
      `<div class="card tight st6 ${c}" data-a="left" style="--d:${.15 + i * .09}s"><span class="si">${ic}</span><div><h3>${t}</h3><p class="sub">${d}</p></div><span class="mono sm">${m}</span></div>`).join('')}
  </div>
</div>
<div class="row" style="gap:10px;flex-wrap:wrap" data-step="1"><span class="chip brand">İlk hafta: sistem panoyu tanır</span><span class="chip">Sensör sorunu ile pano sorunu ayrı iş emri</span><span class="chip">Mutlak sıcaklık sınırları ilk günden açık</span></div>
</div>`,
  notes: `Kurulum, şartnamenin en çok vurguladığı risk: kalabalık bir pano ve enerjili çalışma. Bu yüzden saha prosedürünü adım adım yazdık.

İki kişi, yaklaşık iki buçuk saat. Kesinti gerekmiyor; çünkü yalnız kablo bölmesine, ölçü kolonuna ve mevcut prize dokunuyoruz.

İlk adım bir güvenlik kapısı: ekip hiçbir şeye dokunmadan termal kamerayla bağlantıları tarıyor. Aşırı sıcak bir bağlantı varsa montaj yapılmıyor; o gün gidilecek iş ölçmek değil, onarmak.

Sonra kelepçeler, termal kamera, ortam düğümü ve ağ geçidi. Devreye alma dizüstü bilgisayarsız, telefonla: etiket kamerayla okunuyor, cihaza dokunuluyor, teknisyen cihazın yerini pano çizimi üzerinde parmağıyla işaretliyor. Elle yazılan pano numarası, filo yönetiminde en sık görülen hata; onu ortadan kaldırıyoruz.

[→] Sonra bir haftalık tanıma dönemi; bu sırada mutlak sıcaklık sınırları yine açık. Ve iki iş emri türü asla karışmıyor: pano iş emri elektrik işi, cihaz iş emri ise panoya dokunmadan sensörü düzeltmek.`,
  use: `<b>Kullan:</b> Liste sırayla gelir; → ile alt satır. <b>Dürüst sınır:</b> telefonla devreye alma akışı tasarlandı, sahada denenmedi. Ağ geçidinin ark rölesine kablo bağlantısı enerjili çalışma kuralına takılırsa planlı bir bakıma bırakılır; sistem o kablo olmadan da çalışır. <b>Jüri sorarsa — "İlk kurulumlar?":</b> ilk beş kurulumda 3,5–4 saat bekliyoruz.`,
});

/* ===================================================================== */
/* 16 · VERİLEN VERİ VE DİJİTAL İKİZ                                      */
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
  title: 'Verilen veri ve dijital ikiz', section: 'Doğrulama', time: '35 sn',
  html: () => `${HD('08 · Doğrulama', 'Verilen veri gerçek bir fider gibi davranmıyordu.')}
<div class="body"><div class="row grow">
  <div class="col" style="width:560px">
    <div class="card tight" data-a="up" style="--d:.1s"><p class="cap">Gerçek bir fider böyle görünür</p>${seriesSVG('real')}<p class="sub">Sabah yükselir, öğlen tepe yapar, akşam ikinci bir tepe. Ardışık ölçümler birbirine çok yakındır.</p></div>
    <div class="card tight" data-a="up" style="--d:.25s"><p class="cap">Bize verilen akım verisi</p>${seriesSVG('given')}<p class="sub">Her ölçüm bir öncekinden bağımsız; rastgele üretilmiş sayılarla uyumlu.</p></div>
  </div>
  <div class="col grow">
    <div class="card" data-a="up" style="--d:.35s"><p class="cap">Ne fark ettik?</p><p class="sub big-sub">Akım verisi rastgele sayılarla uyumluydu; sıcaklık-nem sayfası boştu, arıza kaydı yoktu. Bunu altı ayrı testle doğruladık.</p></div>
    <div class="card" data-step="1" style="border-color:rgba(53,192,122,.4)"><p class="cap">Bu yüzden ne yaptık?</p><p class="sub big-sub">Modeli bu veriye uydurmadık. Fiziğe dayalı bir <b class="ok">dijital ikiz</b> kurduk: gerçekçi yük, hava ve arıza senaryoları üreten sanal panolar. Sistemi bu senaryolarla sınadık.</p></div>
    <div class="g2" data-step="1">
      <div class="card tight kpi"><div class="v ok">17</div><div class="l">test senaryosu</div></div>
      <div class="card tight kpi"><div class="v izle">7</div><div class="l">"alarm vermemeli" kontrolü</div></div>
    </div>
    <p class="sub" data-step="1">Gerçek sahadaki başarımı ancak bir pilot uygulama gösterebilir; ilk iş olarak bunu öneriyoruz.</p>
  </div>
</div></div>`,
  notes: `Yarışmada bize bir akım verisi verildi. Önce onu inceledik ve şunu fark ettik: bu veri gerçek bir fider gibi davranmıyor.

Üstte gerçek bir fiderin nasıl görünmesi gerektiği: sabah yükselen, öğlen tepe yapan, akşam ikinci bir tepe yapan bir eğri. Komşu iki ölçüm neredeyse aynıdır.

Altta verilen veri: her ölçüm bir öncekinden tamamen bağımsız, rastgele üretilmiş sayılarla uyumlu. Altı ayrı test aynı sonucu verdi. Ayrıca sıcaklık-nem sayfası boştu ve arıza kaydı yoktu. Bunu bir "yakaladık" gösterisi olarak değil, sonucunu hesaba katmak için söylüyoruz.

[→] Bu yüzden modelimizi bu veriye uydurmadık. Fiziğe dayalı bir dijital ikiz kurduk: gerçekçi yük, hava ve arıza senaryoları üreten sanal panolar. On yedi senaryo; bunların yedisi "alarm vermemesi gereken" durumlar. Sistem hem alarm vermesi gerektiğinde verdi, hem vermemesi gerektiğinde sustu.

Dürüst olalım: gerçek sahadaki başarımı ancak bir pilot uygulama gösterebilir. Bunu saklamak yerine, pilotun ölçeceği ilk şey olarak öneriyoruz.`,
  use: `<b>Kullan:</b> Ton önemli: suçlama değil, sonuç. <b>Jüri sorarsa — "Hangi testler?":</b> ardışık ölçümler arası ilişki (gerçek fiderde 0,97'nin üstünde, verilende ≈ 0), dağılım şekli, günün saatine bağlılık; altısı da rastgele sayı üretecini (Excel RASTGELEARADA 15–90) işaret ediyor. <b>Kaynak:</b> README §6, docs/09, <span class="mono">python -m analysis.supplied_data</span>.`,
});

/* ===================================================================== */
/* 17 · ŞARTNAME KARŞILIĞI                                                */
/* ===================================================================== */
const REQ = [
  ['Kabin içi modül tasarımı', 'Kısmen', 'uyari', '9 cihazlık kit, yerleşim ve malzeme listesi. Devre kartı çizimi yok.'],
  ['Elektronik dokümantasyon', 'Kısmen', 'uyari', 'Blok şemalar, bağlantı tabloları, güç tasarımı.'],
  ['Yazılım mimarisi', 'Tamam', 'ok', 'Cihaz yazılımı, sunucu ve arayüz çalışıyor.'],
  ['İzleme ekranları', 'Tamam', 'ok', 'Filo haritası, pano ikizi, kanıt, bastırılan alarmlar.'],
  ['SCADA entegrasyonu', 'Tamam', 'ok', 'Çalışan Modbus bağlantısı, yalnız okunur.'],
  ['Kurum içi kurulum', 'Tamam', 'ok', 'Tek komutla çalışır; internet ve bulut gerekmez.'],
  ['SMS / anlık bildirim', 'Kısmen', 'uyari', 'En yakın ekibe konumlu bildirim, kademe ve onay çalışıyor; gönderim simüle.'],
  ['En az 100 modül', 'Tamam', 'ok', '112 panolu sanal filoyla denendi.'],
];
add({
  title: 'Şartname karşılığı', section: 'Özet', time: '25 sn',
  html: () => `${HD('09 · Özet', 'Şartnamenin istedikleri ve bugünkü durumu.')}
<div class="body"><div class="row grow">
  <div class="card grow reqs" data-a="up" style="--d:.1s">${REQ.map(([t, s, c, d], i) => `<div class="rq" data-a="left" style="--d:${.2 + i * .08}s"><span class="chip ${c}">${c === 'ok' ? IC.check : '◐'} ${s}</span><b>${t}</b><span class="sub">${d}</span></div>`).join('')}</div>
  <div class="col" style="width:300px">
    ${[['9', 'cihazlık pano modülü'], ['6', 'izleme ekranı'], ['17', 'test senaryosu'], ['173', 'otomatik test'], ['11', 'teknik belge']].map(([v, l], i) =>
      `<div class="card tight kpi mini" data-a="left" style="--d:${.4 + i * .1}s"><div class="v">${v}</div><div class="l">${l}</div></div>`).join('')}
  </div>
</div></div>`,
  notes: `Şartnamenin beklediği çıktıları bugünkü durumla eşledik ve renk yerine kelimeyle yazdık: Tamam ya da Kısmen.

Yazılım, izleme ekranları, SCADA entegrasyonu, kurum içi kurulum ve yüz modül ölçeği tamam. Modül tasarımı ve elektronik dokümantasyon kısmen: blok şemalar ve malzeme listesi var, devre kartı çizimleri yok. SMS kısmen: kademeli bildirim ve onay çalışıyor, gönderim simüle ediliyor.

Arkasındaki iş: dokuz cihazlık bir pano modülü, altı izleme ekranı, on yedi test senaryosu, yüz yetmiş üç otomatik test ve on bir teknik belge.`,
  use: `<b>Kullan:</b> Hızlı geçin; jüri tabloyu okur. "Kısmen" satırlarını siz söyleyin, sorulmasını beklemeyin. <b>Sorulursa kod büyüklüğü:</b> ≈ 33 bin satır Python, 4,5 bin satır C99 firmware, 7,9 bin satır arayüz (3 Ekim itibarıyla; teslim öncesi tekrar sayın).`,
});

/* ===================================================================== */
/* 18 · KAPANIŞ                                                           */
/* ===================================================================== */
add({
  title: 'Kapanış', section: 'Kapanış', noCorner: true, time: '25 sn',
  html: () => `
<div class="cover end">
  <div class="cv-l">
    <p class="kicker" data-a="fade">Kapanış</p>
    <h1 class="end-t" data-a="up" style="--d:.1s">Arızayı, yangından haftalar önce görmek.</h1>
    <div class="ends">
      <div data-a="up" style="--d:.3s"><b>Faz karşılaştırması</b><span>Hava ve yükten etkilenmez; montaj günü çalışmaya başlar.</span></div>
      <div data-a="up" style="--d:.42s"><b>Az ama doğru</b><span>Gereksiz alarmı gerekçesiyle ayıklar; telefon yalnız gerektiğinde çalar.</span></div>
      <div data-a="up" style="--d:.54s"><b>Dürüstlük</b><span>Göremediğini ve bilmediğini ekranda söyler.</span></div>
    </div>
    <div class="cv-logos" data-a="fade" style="--d:.8s"><img src="${A.adm}" alt="ADM Elektrik Dağıtım"><i></i><img src="${A.gdz}" alt="GDZ Elektrik Dağıtım"><i></i><img src="${A.gridup}" alt="Grid Up" style="height:46px"></div>
    <p class="thanks" data-a="up" style="--d:.9s">Teşekkürler. Sorularınızı bekliyoruz.</p>
  </div>
  <div class="cv-r" data-a="blur" style="--d:.2s">${coverSVG('ed')}</div>
</div>`,
  scene(el, ctx) { return SL[0].scene(el, ctx, 'ed'); },
  notes: `Kapatırken üç şey.

Bir: faz karşılaştırması. Bir bağlantıyı aynı çıkışın diğer fazlarıyla karşılaştırdığımız için hava ve yük bizi yanıltmıyor; geçmiş veri istemediği için de montaj gününden itibaren çalışıyor.

İki: az ama doğru alarm. Yüz panoyu yönetilebilir kılan şey, ürettiğimiz alarmlar kadar üretmediğimiz alarmlar. Telefon yalnız gerçekten gerektiğinde çalıyor.

Üç: dürüstlük. Göremediğimiz yeri ve bilmediğimizi ekranda söylüyoruz. Bir dağıtım şirketi, ne zaman güvenmemesi gerektiğini söyleyen bir sisteme güvenir.

Hedefimiz basit: arızayı, yangından haftalar önce görmek.

Teşekkürler. Sorularınızı bekliyoruz.`,
  use: `<b>Kullan:</b> Son cümleden sonra susun ve bekleyin. Soru-cevap için <b>Q</b> tuşu hazır cevap panelini açar (arama kutulu). Belirli bir slayta dönmek için slayt numarasını yazıp Enter'a basın ya da <b>O</b> ile haritayı açın.`,
});

/* ===================================================================== */
/* JÜRİ SORULARI — hazır cevaplar (Q)                                    */
/* ===================================================================== */
const QA = [
  { q: 'Kalibrasyonu nasıl yapıyorsunuz?', a: 'θ bir <b>fark</b>tır; iki sensörün ortak sapması çıkar. Mutlak doğruluk yalnız 110/130 °C limitleri için gerekir ve TMP117 fabrikada ±0,1 °C\'dir. IR dizisinde fazlar arası fark gürültüsü 0,8 K alınır.', ref: 'docs/04 §1' },
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
  { q: 'Alarm hangi ekibe gidiyor? Konumu nereden biliyor?', a: 'Her nöbetçi ekibin <b>görev yeri koordinatı</b> nöbet listesinde, her panonun koordinatı varlık kaydında. Kritik/Acil alarm panoya kuş uçuşu <b>en yakın tek ekibe</b> gider; aynı ekip panonun harita bağlantısını ayrı, tek parçalık bir SMS ile bir kez alır. Tekrar SMS ve sesli arama da o ekibe. <b>Canlı konum yok</b>: telefonda uygulama gerektirir. Koordinatı olmayan panoda bütün ekipler aranır, kimse atlanmaz. Harita bağlantısı yalnız SMS metni; sunucu dışarı istek atmaz.', ref: 'notify/escalation.py · docs/01 §8' },
  { q: 'Neden bulut yok? Ölçek için gerekmez mi?', a: 'Gerekçe kurumsal: şebeke topolojisi ve arıza geçmişi kritik altyapı verisi. Teknik olarak da gerekmiyor: 100 pano ≈ 18 GB disk, 1000 pano tek çekirdeğin dörtte biri. 500 GB NVMe 100 panoda 25 kat baş boşluğu bırakır.', ref: 'docs/01 §4–5' },
  { q: '1000 / 10 000 panoda ne olur?', a: '1000 pano: 4 vCPU / 16 GB, tek Mosquitto. 10 000: bölge başına (ADM / GDZ, sonra il) yığın + federe salt okunur görünüm, bölge başına broker, ağ geçitlerinde 0–300 sn jitter. SQLite ~10 000\'de biter; TimescaleDB sürücüsü yazılmadı. ICD MAX_PANELS = 200.', ref: 'docs/06' },
  { q: 'Verilen veriyi neden kullanmadınız?', a: 'Sentetik: lag-1 otokorelasyon +0,0003 (gerçek fiderde > 0,97), altı bağımsız test. Sıcaklık-nem sayfası boş, etiketli arıza yok, faz yapısı yok. Fizikten türetilmiş dijital ikiz kurduk ve verilen kümeyi de aynı kabul testlerinden geçirdik.', ref: 'README §6 · docs/09' },
  { q: 'OG hücreler ne olacak?', a: 'OG çizimi verilmedi; istedik. docs/10 jenerik 36 kV kablo bölmesi için <b>konsept</b>: HFCT kablo ekranı topraklamasında, TEV, ultrasonik, kablo başlıklarında θ. Hücre başına ~€502 (özel HFCT). Montaj planlı bakım penceresine eklenir; ayrı kesinti istemez.', ref: 'docs/10' },
  { q: 'Kurulum için kesinti gerekir mi?', a: 'Hayır: kit yalnız alt kablo bölmesi, ölçü kolonu DIN rayı ve mevcut 10 A prize dokunur. Tek istisna RS-485\'in TVOC-2 ve MPR-53CS\'e indirilmesi: DSO kuralı enerjili iletken indirmeye izin vermezse planlı kesintiye ertelenir; sistem RS-485\'siz de çalışır.', ref: 'docs/05 §3' },
  { q: 'SCADA\'dan komut verebilir miyiz?', a: 'Hayır. Modbus slave istisnasız salt okunur; FC 05/06/15/16 exception 0x01 döner. TVOC-2 otokontrol ve açma sıfırlama yalnız ağ geçidinde, operatör kimlik doğrulaması <b>ve</b> fiziksel anahtar arkasında.', ref: 'docs/PANOGOZ-ICD-v2.0' },
  { q: 'Sensör arızası sağlam bir bağlantıyı sıktırır mı?', a: 'Hayır. DEVICE_MOUNT_LOST, AIM_SHIFTED, DRIFT, STUCK, CELL_LOW <b>cihaz iş emri</b> üretir, pano iş emri asla. Kelepçe düşerse okunan sıcaklık havanınkidir; tork iş emri yapısal olarak engellenir.', ref: 'docs/05 §8.2' },
  { q: 'Nem ve yoğuşmayı nasıl izliyorsunuz?', a: 'Su havadan değil, çiy noktasının altındaki <b>yüzeyde</b> yoğuşur. Duvar sıcaklığını havanın τ ≈ 90 dk gecikmesi olarak modelliyoruz, pay = T_duvar − T_çiy. Boolean değil pay raporlanır. Tek başına İzle/Uyarı; yükselen PD ile birlikte Kritik.', ref: 'docs/04 §9.2' },
  { q: 'Ağ geçidi ile sunucu bağlantısı koparsa?', a: 'Üç yerel kural çalışmaya devam eder (≥ 90 °C, Δ ≥ 20 K, ark). 20 000 çerçeve halka tamponda tutulur, PUBACK geldikçe filigran ilerler; ark olayı tamponun başına alınır. Tampon dolarsa en eskiler düşer ve düşen sayısı bir sağlık metriği olarak yayınlanır.', ref: 'docs/01 §2.1' },
  { q: 'Maliyeti ne, ne zaman geri öder?', a: 'Modül donanımı €470,59 (1000 adet) / €660,91 (100 adet), kurulum €150. 100 pano tekdüze: 6,9 yıl (5 yılda −€30 166). Aynı 100 modül en kötü ondalıkta: <b>2,2 yıl</b>. 1000 pano tekdüze: 3,3 yıl. Faydanın %43,5\'i tespit oranından bağımsız (termografi ziyareti).', ref: 'docs/07' },
  { q: 'Üç fazdan ikisi birden bozulursa?', a: 'Medyan kendisi hariç diğer iki fazdan alınır, yani ikisinin ortalamasıdır. İki faz eşit bozulursa her birinin θ\'sı yaklaşık <b>yarıya iner ama görünür kalır</b>; sağlam üçüncü faz negatif θ gösterir. Üç faz birden ve aynı hızda bozulursa θ bunu <b>görmez</b>: bu yöntemin kör noktasıdır ve onu her koşulda açık olan mutlak limitler (90/110/130 °C) kapsar.', ref: 'formülden türetildi · belgede ayrıca yazılı değil, provada doğrulayın' },
];

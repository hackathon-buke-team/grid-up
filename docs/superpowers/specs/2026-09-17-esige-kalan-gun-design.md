# Eşiğe kalan gün · tasarım belgesi

Tarih: 17 Eylül 2026
Dal: `esige-kalan-gun` (paket dallarından birine sığmıyor; `contracts/` değiştiği için
PR §7.3 gereği dört kişiye birden haber verilerek açılacak)
Durum: onaylandı, uygulama planı henüz yazılmadı

---

## 0 · Bir cümle

`joint_daily` üzerindeki günlük θ medyanlarının Theil-Sen eğimini **bir sonraki seviye
basamağına kalan gün** olarak çevirir, belirsizliği eğimin parametrik olmayan güven
aralığından taşır ve beş durumda sayı vermeyi reddeder.

### Neden

Ürün bugün "haftalar önce haber veririm" diyor ve bunu kanıtlıyor: CUSUM sürüklenmeyi
teyit ediyor, `changepoint.detect_changepoint()` bozulmanın **başladığı** günü
tarihliyor, `theta_delta()` son yedi günün hareketini gösteriyor. Üç sayının hepsi
geçmişe bakıyor. Bakım planlayıcısının sorduğu soru ise ileriye bakar:

> "Bu pabuç ne zaman benim sorunum olacak?"

Bu soruya bugün cevap veremiyoruz ve cevabı elimizdeki verinin içinde duruyor.
`slope_per_week()` zaten K/hafta cinsinden bir eğim üretiyor; eksik olan eğimin
**belirsizliği** ve sayı vermeyi reddetme kurallarıdır. Yeni kestirici yazmıyoruz, var
olan kestiriciyi bir tarihe çeviriyoruz.

Yaptığı **fayda iddiası** budur ve sınırlıdır: bir iş emrinin bu haftaya mı gelecek
aya mı yazılacağına karar vermeye yeter. Bir kesinti tarihini bu sayıya göre planlamaya
yetmez ve belge bunu söyler.

---

## 1 · Girdi ve birim sözleşmesi

| Girdi | Kaynak | Birim |
|---|---|---|
| Günlük θ serisi | `joint_daily.theta_med`, gün gün | anma akımında kelvin |
| Gün damgası | `joint_daily.day` × `DAY_S` | epoch saniye |
| Günlük görülebilirlik tabanı | `joint_daily.theta_min` | kelvin |
| Günlük örnek sayısı | `joint_daily.n` | adet |
| Eşik merdiveni | `engine.THETA_ABS_LADDER` | kelvin |

**Projeksiyon `theta_med`'in son geçerli gününden başlar, anlık `theta_k`'dan
başlamaz.** "Son geçerli gün", pencere içinde `n > 0` ve `theta_med IS NOT NULL` olan en
yeni gündür; bugün hiç örnek yoksa dünden başlar ve `valid_days` bunu taşır.
Eğim günlük medyanlar üzerinde hesaplanmıştır; anlık bir okumayı günlük bir
eğimle birleştirmek birim uyuşmazlığıdır ve saat 15:00'te çekilen bir projeksiyonu saat
03:00'te çekilenden farklı yapar. Aynı gün içinde iki kez sorulan soru aynı cevabı
vermek zorundadır.

Nötr iletkenler (`assets` içinde `conductor == "N"`) kapsam dışıdır: onların serisi θ
değil K_N'dir, `engine._refresh_stats()` zaten ayrı bir dalda işliyor ve mutlak eşik
merdiveni onlara uygulanmaz. H3 kuralı nötrü kendi yöntemiyle yargılar.

---

## 2 · Matematik · Theil-Sen eğiminin güven aralığı

### 2.1 Neden bu yöntem

`theil_sen()` bugün bütün ikili eğimleri üretiyor, medyanını alıyor ve **listeyi atıyor.**
Aynı listenin rank kuantilleri, eğimin parametrik olmayan güven aralığıdır (Sen 1968;
Helsel & Hirsch, *Statistical Methods in Water Resources*, §7.5). Yani aralık için ek
bir model, ek bir dağılım varsayımı ve ek bir geçiş gerekmez — bir `sorted()` gerekir.

Bootstrap reddedildi: RNG bağımlılığı getirir, tekrarlanabilirlik için tohum sabitlemek
gerekir ve 112 pano × 74 bağlantı × 2000 yeniden örnekleme ölçülmemiş bir CPU maliyetidir.
Çoklu pencere duyarlılığı (14/21/28 gün) reddedildi: okunması kolaydır ama bir güven
aralığı **değildir** ve öyle etiketlenmesi gerekirdi.

### 2.2 Formüller

n günlük nokta için, ikili eğim sayısı ve Kendall S istatistiğinin varyansı:

```
N        = n(n-1)/2
Var(S)   = [ n(n-1)(2n+5) - Σ_g t_g(t_g-1)(2t_g+5) ] / 18
C        = z · sqrt(Var(S))
lo_rank  = floor( (N - C) / 2 )
hi_rank  = ceil(  (N + C) / 2 ) + 1
```

`t_g`, θ değerlerinde birbirine eşit olan her grubun büyüklüğüdür. Zaman tarafında
bağlanma **olamaz**: `joint_daily`'nin birincil anahtarı `(day, panel_key, joint_key)`,
yani bir bağlantı için bir günde tek satır vardır.

Eğimler artan sırada 1-indeksli `s[1..N]` olmak üzere sınırlar `s[lo_rank]` ve
`s[hi_rank]`; her iki rank `[1, N]` aralığına kırpılır. `floor`/`ceil+1` seçimi
**bilinçli olarak muhafazakârdır**: aralığı bir rank genişletir, yani gün aralığını
genişletir. Emniyetle ilgili bir sayıda yanılma yönü budur.

Bunun bedeli ölçüldü: nominal seviye %90 iken fiilî kapsama %88–93 arasında, yani
aralık nominalden bir miktar geniştir (§12.1). Arayüzde ve belgede seviye **%90 nominal**
olarak adlandırılır; "tam olarak %90" denmez.

z tablosu modülde sabittir — `{0.90: 1.6449, 0.95: 1.9600}`. `scipy` kurulu olmasına
rağmen kullanılmıyor: `detector/` altında `prpd_classify.py` dışında hiçbir modül
stdlib'in ötesine çıkmıyor ve `changepoint.py` yalnız `math` + `statistics.median`
kullanıyor. Yeni modül bu ayak izini korur.

### 2.3 Sayısal kontrol (n = 14, conf = 0.90)

```
N       = 14·13/2                = 91
Var(S)  = 14·13·33/18            = 333.67
C       = 1.6449 · 18.267        = 30.05
lo_rank = floor((91-30.05)/2)    = 30
hi_rank = ceil((91+30.05)/2) + 1 = 62
```

30 ve 62, 91 elemanlı listenin içindedir; kırpma devreye girmez. Bu dört sayı tasarım
aşamasında atılabilir bir betikle **ölçülmüş** ve yukarıdaki değerlerle birebir
doğrulanmıştır.

`floor`/`ceil+1` yerine ranklar arasında tam interpolasyon yapmak, aynı tohumda kapsamayı
%93.2'den %93.0'a taşıyor — 0.2 puanlık fark, dört satır fazla kod. Basit olan seçildi.

### 2.4 `theil_sen()`'in davranışı değişmez

Fonksiyon ortak bir yardımcıya bölünür (`_pairwise_slopes()`), `theil_sen()` onun
medyanını döndürmeye devam eder. Modülün kendi öz-testindeki `assert`'ler — tek 25 K
aykırı değer altında eğimin 0.05 K/hafta içinde kalması dahil — dönüş değerini bit
düzeyinde kilitler ve refaktörün kanıtı bunların geçmesidir.

---

## 3 · Projeksiyon aritmetiği

```
kalan_K  = hedef_eşik - θ_son_gün
gün_med  = kalan_K · 7 / eğim_med          # eğim K/hafta
gün_lo   = kalan_K · 7 / eğim_hi           # hızlı uç  → az gün
gün_hi   = kalan_K · 7 / eğim_lo           # yavaş uç  → çok gün
```

`eğim_lo ≤ 0` ise `gün_hi = None`, yani ∞. Bu, "yükseliyor olabilir de olmayabilir de"
cümlesinin matematikten çıkan hâlidir; elle yazılan bir uyarı değildir.

### 3.1 Yuvarlama yönü

Gün sayıları tam güne indirilir ve **yön muhafazakârdır** — aralık daralmaz, genişler:

| Alan | Yuvarlama | Neden |
|---|---|---|
| `days_lo` | aşağı (`floor`) | en erken tarih daha da erkene çekilir |
| `days` | en yakına (`round`) | medyan bir tahmindir, yönü yoktur |
| `days_hi` | yukarı (`ceil`) | en geç tarih daha da geriye atılır |

Örnek: 13.06 → 13, 21.0 → 21, 31.9 → 32.

Yarım gün hassasiyeti iddia eden bir sayı, 21 günlük bir pencereden türetilmiş bir
ekstrapolasyonda yanlış bir kesinlik iddiasıdır.

---

## 4 · Hedef eşiğin seçimi

`engine.py` dört mevcut sabitten türeyen tek bir merdiven ilan eder — hiçbir sayı ikinci
kez tanımlanmaz:

```python
THETA_ABS_LADDER = (("IZLE",   THETA_ABS_IZLE_K),      #  2 K
                    ("UYARI",  THETA_ABS_UYARI_K),     #  5 K
                    ("KRITIK", THETA_ABS_KRITIK_K),    # 12 K
                    ("ACIL",   THETA_ABS_ACIL_K))      # 25 K
```

Hedef, **θ'nın son günlük değerinin bulunduğu bandın bir üstüdür.** `JointView.severity`
kullanılmaz ve bu önemlidir: füzyon seviyeyi mutlak sıcaklık, aktif ark açması veya PD
kanıtıyla yükseltebilir. θ'sı 3 K olan ama ark rölesi açmış bir bağlantı KRITIK
görünür; onun için "ACIL'e kalan gün" hesaplamak, ısıl olmayan bir kanıtla ısıl bir
projeksiyon kurmak olurdu. Merdiven θ'nın merdivenidir, olayın seviyesi değildir.

`horizon` merdiveni **parametre olarak alır**, `engine`'den import etmez: `engine` →
`changepoint` bağımlılığı zaten var, ters yönde bir import döngü kurardı. Öz-test kendi
merdivenini geçirir.

---

## 5 · Susma sözleşmesi

Kapılar sırayla değerlendirilir, ilk tutan kazanır ve tek bir gerekçe kodu döner.

| Sıra | Kod | Koşul | Ekranda |
|---|---|---|---|
| 1 | `NOTR_KAPSAM_DISI` | `conductor == "N"` | `—` |
| 2 | `ZIRVEDE` | θ ≥ ACIL eşiği (25 K); üstünde basamak yok | `—` |
| 3 | `YETERSIZ_GECMIS` | 21 günlük pencerede `n > 0` olan gün sayısı < 14 | `— (9 gün)` |
| 4 | `GORUNURLUK_DUSUK` | pencere medyanı `theta_min` ≥ hedef eşik | `— (θ_min 14 K)` |
| 5 | `EGIM_YOK` | medyan eğim ≤ 0 | `—` |
| — | `""` | yukarıdakilerin hiçbiri | `KRITIK'e 21 g (13-32)` |

1, 2 ve 5 **arıza değildir**; sistemin doğru çalıştığı durumlardır. 3 ve 4, körlüğün
kendisidir ve README §8'in ikinci dürüstlük kuralı gereği pano arızalarından ayrı
raporlanır.

### 5.1 Görünürlük kapısının kriteri neden yüzde değil

`engine.py:1330` bugün `sensitivity_pct < 100.0` olduğunda `SENSITIVITY_LOW` bayrağı
kuruyor. Bu bayrak için doğru bir eşiktir, projeksiyon için değildir: tam yükün altındaki
her bağlantıyı susturur ve kolon neredeyse hep boş çıkar.

Fiziksel olarak doğru soru şudur: **θ_min hedef eşiğin üstündeyse o eşiğe doğru yapılan
projeksiyon anlamsızdır**, çünkü eşiğin kendisi gürültü tabanının altında kalır.
θ_min = 3σ/f² için `joint_daily`'de `theta_min` kolonu **vardır**, yeni kolon
gerekmiyor, yeni sabit gerekmiyor ve kriter panonun o günkü yüküne göre kendiliğinden
hareket ediyor.

**Ön koşul — kolon tanımlı ama dolu değil.** Uygulama planı yazılırken ölçüldü:
`schema.sql:106-125` `theta_min`'i tanımlıyor, fakat `engine.roll_daily()` onu
**atlıyor** — `det.theta_min_k` örneklerini okuyup yalnız `load_mean`'i türetiyor,
kolonu `NULL` bırakıyor. Bu kapı bugünkü kodda ölü doğardı.

Düzeltme, aynı `upsert_joint_daily()` çağrısına tek bir kwarg eklemektir
(`theta_min=float(median(tmins))`) ve uygulama planının kendi görevi vardır. Mevcut bir
eksiğin kapatılmasıdır, yeni bir özellik değildir. Bedeli: `joint_sample` 90 günde
budandığı için daha eski günlük satırlar geriye doldurulamaz; onlarda `theta_min`
`NULL` kalır ve kapı — bilmediği bir tabanla eşiğin görünür olduğunu iddia etmemek
için — susma tarafına düşer.

Ekranda gösterilen sayı **kriterin kendisidir** (`θ_min 14 K`), sebebi olan yük değildir.
Yükü ipucu metni açıklar: θ_min = 3σ/f², yani yük düştükçe taban yükselir. Kriter olarak
θ_min'i, gerekçe olarak yükü göstermek ikisini karıştırmayı önler.

### 5.2 14 gün nereden geliyor

İstatistiksel güçten değil, **pencere kapsamasından.** Pencere 21 gündür; en az 14
geçerli gün istemek, pencerenin en çok bir haftasının boş olmasına izin vermek demektir.
Bir hafta susmuş bir düğüm, enerjisiz kalmış bir pano ya da IDLE kadansına düşüp günde
tek örnek üretmiş bir bağlantı bu kapıya takılır.

Gürültüye karşı koruma bu kapıda değil, **güven aralığının kendisindedir**: seri
gürültülüyse alt sınır kendiliğinden sıfırın altına iner, üst gün sınırı ∞ olur ve sayı
kendi şüphesini taşır. İki ayrı mekanizmayı tek kapıya yüklemiyoruz.

### 5.3 90 gün tavanı

Medyan gün > 90 ise `capped = True` ve arayüz `>90 g` yazar. Gerekçe: 21 günlük bir
pencereden 412 günlük bir tarih türetmek, gözlem penceresinin yirmi katına
ekstrapolasyondur. Ayrıca 90 gün ileri bir mevsim sınırını geçer; θ yük için normalize
edilmiştir ama günlük medyanın gürültü tabanı yükle birlikte hareket eder ve o hareket
modelin içinde değildir.

Tavan bir susma değildir: hedef eşik ve gerekçe kodu yine döner, yalnız gün sayısı
aralık olarak değil eşik olarak yazılır.

---

## 6 · İki itiraz, iki cevap

### 6.1 Doğrusallık

Projeksiyon doğrusaldır. `thermal_runaway` arıza modu süper-doğrusaldır: ısınan bir
temas direncinin artması daha fazla ısınmaya yol açar. Bu modda doğrusal projeksiyon
**iyimserdir** — gerçek tarih hesaplanandan erkendir.

Sayı gizlenmez. `model` alanı `"dogrusal"` değerini taşır, ve `thermal_runaway` kanıtı
olan bir bağlantıda arayüz "bu gidişle **en geç** 21 gün" der, "en erken" demez. Belgede
de bu yönde yazılır. Süper-doğrusal bir model uydurmak, kalibre edecek saha verisi
olmadan ölçülemeyen bir iddia eklemek olurdu.

### 6.2 Basamak ↔ rampa

On gün önce 3 K'lık bir kademe atlayıp sonra düzleşen bir seri, 21 günlük pencerede sahte
bir rampa üretir ve bugünkü `slope_per_week()` bu hataya açıktır.

`detect_changepoint()` pencere içinde bir tarih veriyorsa projeksiyon **yalnız o günden
sonrasını** kullanır (o segmentte ≥ 3 nokta varsa; yoksa tüm pencereye düşer ve bunu
bildirir). `from_changepoint` ve `changepoint_ts` alanları bu seçimi taşır.

**Mevcut `slope_k_per_week` tanımına dokunulmaz.** Filo tablosundaki eğim kolonu,
`SLOPE_ESCALATE_K_PER_WEEK` kuralı ve `joint_state.slope` kolonu aynı anlamı korur.
Projeksiyonun fiilen kullandığı eğim `slope_k_per_week` olarak `EtaView` içinde ayrı
raporlanır; ikisi ayrıştığında kanıt ekranı nedenini yazar:

> "14 Temmuz'da bir basamak var; projeksiyon yalnız o günden sonrasını kullanıyor."

İki sayı, iki soru, iki yer. Tek sayıya indirmek, birinin diğerinin yerine geçmesi
demektir.

---

## 7 · Pano düzeyine yükseltme ve sıralama

`PanelLive.eta`, panonun bağlantıları arasından **hedef seviyesi en yüksek**, eşitlikte
**günü en yakın** olanın projeksiyonudur.

Sadece `min(gün)` almak yanlış olurdu: IZLE'ye 3 gün kalan bir bağlantı, KRITIK'e 18 gün
kalan bir bağlantının önüne geçer ve kontrol odası yanlış panoya bakar. Sıralama anahtarı
`(hedef_seviye_ağırlığı azalan, gün artan)`.

Filo tablosundaki "Eşiğe" kolonu aynı bileşik anahtarla sıralanır ve bu, kolonun ipucu
metninde yazılır. Gerekçe kodu dönen satırlar (`days = None`) sıralama yönü ne olursa
olsun **sona** gider — boş bir hücre, "en yakın" listesinin başında durmamalıdır.

`theta_delta_7d` en kötü bağlantıdan yükseltiliyor; `eta` farklı bir anahtarla
yükseltiliyor. Bu bilinçli bir ayrımdır ve `live.py`'de yorumla işaretlenir.

---

## 8 · Veri modeli ve API

### 8.1 Kalıcılık: yeni tablo yok, yeni kolon yok

Projeksiyon türetilmiş bir sayıdır ve `_refresh_stats()` içinde `joint_daily`'den
yeniden hesaplanır. `joint_state`'e yazılmaz. Gerekçe, `_refresh_stats()`'ın kendi
docstring'inde yazan kuraldır: sekiz ay sonra kimsenin `SELECT` ile yeniden üretemediği
bir istatistik kanıt değildir. Yeniden başlatmadan sonra ilk `detect` turunda (5 s)
yeniden dolar.

Maliyet: `_pairwise_slopes()` pencere başına bir kez üretilir ve hem medyan hem rank
sınırları aynı listeden okunur. 21 günlük pencerede 210 çift; ölçülmesi gereken bir
maliyet değil.

### 8.2 `contracts/live.py` · `EtaView`

`ArcView` / `PdView` desenini izleyen iç içe bir dataclass. `JointView.eta` ve
`PanelLive.eta` olarak taşınır.

```python
@dataclass
class EtaView:
    target: str | None = None          # "KRITIK" · hedef basamak
    days: float | None = None          # medyan, tam gün
    days_lo: float | None = None       # hızlı uç
    days_hi: float | None = None       # yavaş uç · None = ∞
    slope_k_per_week: float = 0.0      # projeksiyonun KULLANDIĞI eğim
    slope_lo_k_per_week: float = 0.0
    slope_hi_k_per_week: float = 0.0
    valid_days: int = 0                # pencerede kaç geçerli gün vardı
    from_changepoint: bool = False
    changepoint_ts: float | None = None
    model: str = "dogrusal"
    capped: bool = False               # medyan > 90 g
    reason: str = ""                   # boş = sayı geçerli
```

`days_hi = None` iki ayrı şeyi ifade eder ve karıştırılmamalıdır: `reason` boşsa ∞,
`reason` doluysa "sayı yok". Arayüz `reason`'a bakar, `days_hi`'ye değil.

### 8.3 Uçlar

| Uç | Değişiklik |
|---|---|
| `GET /api/panel/{key}` | her bağlantının nesnesine `eta`, pano düzeyine `eta` |
| `GET /api/fleet` | `panel_summary()` içine `eta` (kolon bunu okur) |
| `GET /api/panel/{key}/onset` | ileri yön eklenir — aşağıya bakın |
| `GET /api/panel/{key}/daily` | değişmez |

**Yeni uç açılmıyor.** `/onset` bugün iki zaman sorusunu cevaplıyor: bozulma ne zaman
başladı, kanıt ne zaman yeterli oldu. Üçüncü zaman sorusu — ne zaman eşiği aşar — aynı
uçta, aynı istekte, aynı `joint_daily` oynatmasından çıkar. Kanıt ekranı üç cevabı bir
istekle alır ve operatör geçmişle geleceği yan yana görür.

---

## 9 · Arayüz

**Filo · S1.** Yeni kolon "Eşiğe", `type: 'eta'`. İçerik `KRITIK'e 21 g (13-32)`, gerekçe
durumunda `—` ve parantez içinde kısa neden. Sıralama §7'deki bileşik anahtar.
**Varsayılan sıralama Δ7g olarak kalıyor** — belgelenmiş bir varsayılanı değiştirmiyoruz
(`view-fleet.js` başlığındaki gerekçe geçerliliğini koruyor). Kolon ipucu susma
sözleşmesini operatörün dilinde anlatır.

**Kanıt · S3.** θ grafiğine **hedef eşik yatay çizgisi** eklenir. Projeksiyonun kendisi
`resistanceCard` / `factsCard` desenini izleyen ayrı bir **metin kartı** olur: kullanılan
eğim ve %90 nominal CI, hedef basamak, gün aralığı, pencerede kaç geçerli gün vardı,
basamak notu (varsa), sonsuz sınır notu (varsa), doğrusallık notu.

**Kesikli yelpaze çizilmiyor ve gerekçesi bir kısıt, bir tercih değil.** Ekranın dört
grafiği tek ve ortak bir x eksenini paylaşıyor (`view-evidence.js` başlığındaki
sözleşme) ve o eksenin sağ kenarı "şimdi"dir. `TimeChart` noktaları
`X(t) = R.x + ((t − d[0]) / (d[1] − d[0])) · R.w` ile eşliyor, yani `t > d[1]` olan bir
nokta tuvalin dışına düşer — gelecekteki kesişim **hiç çizilmez**. Alanı geleceğe uzatmak
dört grafiğin hepsini birden sıkıştırır ve senkron eksen sözünü bozar. Projeksiyona ayrı
bir küçük grafik açmak da reddedildi: üç sayının (başlangıç θ, eğim + CI, hedef)
taşımadığı hiçbir bilgiyi taşımaz ve ekranda zaten dört grafik var.

**Alarmlar · S5.** UYARI ve üstü olaylarda tek cümle: *"Bu gidişle KRITIK eşiğine 21 gün
(13–32)."* Gerekçe kodu varsa cümle yazılmaz; yerine hiçbir şey yazılmaz. Boş bir alan,
uydurulmuş bir tarihten iyidir.

`type: 'eta'` biçimleyicisi `fmt.js`'e girer, üç ekran aynı biçimleyiciyi kullanır.

---

## 10 · Bildirim metni

Metni kuran yer `notify/sms.py` değil, `notify/escalation.py:compose()`'dur. Gövdeye
`" · KRITIK'e 21 g (13-32)"` eklenir — 24 karakter. Gerekçe kodu dönüyorsa satır hiç
eklenmez.

Bütçe **160 değildir** ve bu ölçüldü. Türkçe metin GSM-7'ye girmediği için UCS2 gider;
tek parça 70, birleştirilmiş parça 67 karakterdir (`sms.py:73-74`). `compose()`'un kendi
tavanı `2 * UCS2_SINGLE_CHARS` = 140 karakterdir ve tavan aşılırsa **aksiyon metnini
kısaltır**.

Ölçülen mevcut gövdeler ve eklemeden sonrası:

| Seviye · mod | Şimdi | Parça | +eta | Parça |
|---|---:|---:|---:|---:|
| KRITIK · loose_connection | 84 | 2 | 108 | 2 |
| ACIL · loose_connection | 82 | 2 | 106 | 2 |
| ACIL · thermal_runaway | 90 | 2 | 114 | 2 |
| UYARI · overload | 76 | 2 | 100 | 2 |

Gövdeler zaten iki parçadır; ekleme üçüncü parça açmıyor ve 140 tavanına çarpmıyor, yani
aksiyon metni kısalmıyor. `live` geçildiğinde metrik alanı (`θ=31.0K`) ~9 karakter daha
ekler; en kötü hâl 123 karakter, yine iki parça.

Marj ince olduğu için sözleşme şudur: **bütçe daralırsa ilk düşen şey eta satırıdır.**
Operatöre "bağlantıyı torkla" demek, "21 gün" demekten değerlidir. Bir test bunu
kilitler: eta eklenmiş gövde 2 parçayı geçemez; geçecekse eta düşer, aksiyon kalır.

Tek sayı yazılmaz. README §8'in birinci dürüstlük kuralı bildirim gecikmesini 4–13 s
aralığı olarak veriyor ve tek temiz sayı vermemeyi kural saymış; aynı kural burada da
geçerlidir.

Tek sayı yazılmaz. README §8'in birinci dürüstlük kuralı bildirim gecikmesini 4–13 s
aralığı olarak veriyor ve tek temiz sayı vermemeyi kural saymış; aynı kural burada da
geçerlidir.

---

## 11 · SCADA · bilinçli olarak dokunulmuyor

Pano bloğunun 48 register'ı **tam doludur**; `PANEL_REGS` 0–47 arası her offset'i
kullanıyor, boş yer yok (ölçüldü: `len(used) == 48`).

İki register eklemek `REGS_PER_PANEL`'i 50 yapar ve her panonun taban adresini kaydırır:
14 numaralı pano `1000 + 48·13 = 1624`'ten `1000 + 50·13 = 1650`'ye gider. Bu tek
değişiklik yayınlanmış ICD v2.0'ı, README §2'deki çalışılmış adres örneğini,
`docs/panogoz_points.csv`'yi ve bu haritayı almış bir RTU konfigürasyonunu birlikte
bozar. Bir izleme sisteminin entegrasyon sözleşmesini bir ekran kolonu için kırması
kabul edilemez.

**Bu alt projede SCADA haritasına dokunulmuyor.**

Temiz yol kayda geçiriliyor ve sonraki tura bırakılıyor: `TOP_ADDRESS`'in üstünde yeni
bir ETA bloğu (`ETA_BASE`, pano başına 2 register — `ETA_DAYS` u16 ve `ETA_REASON` enum
u16) açmak **hiçbir mevcut adresi kaydırmaz**, tamamen eklemelidir ve ICD'yi v2.1 olarak
geriye dönük uyumlu biçimde büyütür. Kararı bu belgenin kapsamı dışında.

---

## 12 · Test planı

Önce kırmızı. Her madde, düzeltmeden önce düşen bir test.

**`tests/test_horizon.py` · yeni**

| Test | Ne kilitler |
|---|---|
| Monotonluk | `days_lo ≤ days ≤ days_hi` her zaman; `slope_lo ≤ slope_med ≤ slope_hi` |
| CI kapsaması | Sabit tohumlu 400 sentetik rampa (0.2 K/hafta, σ = 0.8 K), gerçek eğimin %90 aralığında kalma oranı **%84–96** arasında — gerekçesi §12.1'de ölçülmüştür |
| Sonsuz üst sınır | Gürültülü düz seri → `days_hi is None`, `reason == ""` |
| Beş gerekçe kodu | Her biri için kendi kurgusu; dönen kodun tam eşitliği |
| Basamak ≠ rampa | 10 gün önce 3 K kademe + sonrası düz seri → changepoint sonrası segment kullanılır, gün sayısı kademeden türetilmez. **Bu testin düşmesi özelliğin yanlış olduğunu gösterir** |
| 90 gün tavanı | `capped is True`, `target` yine dolu |
| Zirve | θ > ACIL → `ZIRVEDE`, sayı yok |
| Birim | Eğim K/hafta, gün tam sayı; 3.6 K / 1.20 K-hafta → 21 g elle doğrulanır |
| Hedef seçimi | Füzyon seviyesi KRITIK ama θ = 3 K olan bağlantı → hedef UYARI, ACIL değil |

**`changepoint.py` öz-testi:** CI bölümü eklenir, modül kendi kanıtını basar (§2.3'ün
sayıları dahil). Mevcut `assert`'ler değişmeden geçer.

### 12.1 Kapsama bandının ölçülmüş gerekçesi

%84–96 bandı seçilmiş değil, ölçülmüştür. Tasarım aşamasında atılabilir bir betikle
(saklanmadı; test bunu kalıcı hâle getirecek) n = 21, σ = 0.8 K, 400 koşum, beş ayrı
tohum:

| Tohum | Kapsama |
|---|---:|
| 1 | %90.0 |
| 7 | %92.5 |
| 42 | %90.5 |
| 20260917 | %93.2 |
| 999983 | %88.0 |

Gözlenen aralık %88.0–93.2, nominal %90'ın etrafında ve 400 koşumun binom standart
sapması olan %1.5 ile tutarlı. Bandı bu yayılımın iki katına açmak (%84–96), testi tohum
değişimine karşı kırılgan olmaktan çıkarır ve yine de bozuk bir kestiriciyi yakalar:
kırpma hatası ya da rank kayması kapsamayı %70'lerin altına indirir.

σ değişimi kapsamayı **hiç** değiştirmiyor (0.8 → 0.4'te aynı sayı): hem aralık hem
gürültü σ ile doğrusal ölçekleniyor, dolayısıyla kapsama ölçek-bağımsızdır. Bu, testin σ
seçimine bağlı olmadığının kanıtıdır ve testin yorumunda yazılır.

**`tests/test_negative_pipeline.py`:** yedi negatif kontrolün hiçbiri geçerli bir
projeksiyon üretmemeli — hepsi sağlıklı, yani `EGIM_YOK` ya da `YETERSIZ_GECMIS`
dönmeli. Pozitif kontrol (`gevsek_baglanti`) aynı koşumda hedefli bir projeksiyon
üretmeli; onsuz "projeksiyon yok" ile "projeksiyon çalışmıyor" ayırt edilemez.

**`tests/test_integration.py`:** uçtan uca kapı, demo panosunda hedefli bir projeksiyon
ve sağlıklı bir panoda gerekçe kodu görmeli; `/api/panel/{key}` ve `/api/fleet`
çıktılarında `eta` alanının şeması doğrulanmalı.

---

## 13 · Belge değişiklikleri

| Belge | Ne eklenir |
|---|---|
| `docs/04-ANOMALI-TESPIT.md` | Yeni bölüm: yöntem, Sen CI'ı, susma sözleşmesi tablosu, doğrusallık itirafı, basamak/rampa ayrımı, **"yapmadığı şeyler"** listesi |
| `README.md` §1 | Tek satır: ileri yönlü projeksiyonun da geçmiş gerektirdiği (≥14 gün) |
| `README.md` §9 | "Belgelendi, kodlanmadı" tablosuna ETA register bloğu satırı |
| `docs/08-DEMO-SENARYOSU.md` | Jürinin "21 gün"ü gördüğü beat, repliğiyle |
| `docs/11-ACIK-SORULAR.md` | Yeni soru: DSO'nun iş emri planlama ufku kaç gün? (90 gün tavanı bu cevaba göre değişir) |

---

## 14 · Kapsam dışı

Bu belgenin **yapmadığı** şeyler, yapmadığını söylemek için listelenmiştir:

- Yeni veritabanı tablosu ya da kolonu yok.
- SCADA register haritasına dokunulmuyor (§11).
- Makine öğrenmesi yok, süper-doğrusal model yok, mevsimsel model yok.
- Dört basamağın hepsi için ayrı gün sayısı gösterilmiyor; yalnız bir sonraki basamak.
- `slope_k_per_week`, `theta_delta_7d`, `SLOPE_ESCALATE_K_PER_WEEK` ve filo tablosunun
  varsayılan sıralaması değişmiyor.
- Nötr iletkenler için projeksiyon yok.
- Bu sayıya dayanarak otomatik iş emri açılmıyor, ekip yönlendirilmiyor, kesinti
  planlanmıyor. Projeksiyon bir **gösterge**dir; aksiyon merdiveni `channels.py`'deki
  seviye tanımlarına bağlı kalır.

---

## 15 · Dokunulan dosyalar

```
panogoz/detector/changepoint.py   _pairwise_slopes(), theil_sen_ci(), öz-test bölümü
panogoz/detector/horizon.py       YENİ · projeksiyon, susma kapıları, öz-test
panogoz/detector/engine.py        THETA_ABS_LADDER; _JointRuntime.eta;
                                  _refresh_stats() çağrısı; JointView/PanelLive yazımı
panogoz/contracts/live.py         EtaView; JointView.eta; PanelLive.eta   ← contracts/
panogoz/api/app.py                panel_summary() ve joint çıktısı; /onset genişlemesi
panogoz/notify/escalation.py      compose() gövdesine eta satırı + parça sözleşmesi
frontend/js/fmt.js                eta biçimleyicisi
frontend/js/view-fleet.js         "Eşiğe" kolonu + bileşik sıralama
frontend/js/view-evidence.js      projeksiyon bandı + metin blok
frontend/js/view-alarms.js        tek cümle
tests/test_horizon.py             YENİ
tests/test_negative_pipeline.py   projeksiyon kontrolleri
tests/test_integration.py         uçtan uca şema kapısı
docs/04, README, docs/08, docs/11 §13
```

`contracts/live.py` değişiyor: PR §7.3 gereği dört kişiye birden haber verilerek açılır.

---

## 16 · Riskler ve kalan kararlar

| Risk | Karşılık |
|---|---|
| Doğrusal model süper-doğrusal modda iyimser | `model` alanı + arayüz "en geç" dili + belgede itiraf (§6.1) |
| 14 ve 90 sayıları saha verisiyle kalibre edilmemiş | İkisi de tek yerde sabit, ikisi de belgede gerekçeli; `docs/11`'e müşteri sorusu olarak eklenir |
| Operatör iki eğim görüp karışabilir | Kanıt ekranı ikisi ayrıştığında nedenini yazar; filo tablosunda yalnız biri var |
| Kolon kalabalığı | Filo tablosu 10 kolondan 11'e çıkıyor; varsayılan sıralama değişmediği için mevcut iş akışı bozulmuyor |
| G+6 dondurma kuralı | Takım G+0'ı kendisi belirliyor (görev dağılımı §5 Kilometre taşları, "gün numaraları göreceli"). Bu özellik yeni bir özelliktir; dondurma günü geçtiyse **uygulanmamalıdır**. Kararı takıma aittir |

Son satır bu belgenin en önemli satırıdır: takım görev dağılımı belgesi G+6'dan sonra
yeni özellik eklenmemesini kural saymış ve gerekçesini de yazmış — *"son gün eklenen
özellik, sunumda çöken özelliktir."* Bu spec, o kural içinde uygulanabilir olduğu
sürece geçerlidir.

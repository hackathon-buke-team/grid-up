# PANO GÖZ — Akış Diyagramları

> Şartnamenin 3. maddesi mikrodenetleyici kaynak kodunu, programın çalışma
> mantığını ve mümkünse bir akış diyagramını istiyor. Bu dosya o akış
> diyagramlarını içerir. Hepsi Mermaid; olduğu gibi sunuma yapıştırılabilir.
>
> Kaynak kod: `firmware/node/` — C99, kayan nokta yok, libm yok, ilk
> kurulumdan sonra dinamik bellek ayırma yok. Çalışma mantığının anlatımı:
> `firmware/README.md`.

---

## 1. Düğüm ana döngüsü (STM32WLE5CC)

Isıl kelepçe düğümünün (TC-01…TC-06) durum makinesi. `DE_ENERGISED` ve
`LOW_BATTERY` birer hata yolu değil, **birinci sınıf durum**: sistem kör
olduğunda bunu söyler, kör olduğu anı panonun arızasıyla karıştırmaz.

```mermaid
stateDiagram-v2
    direction TB
    [*] --> COLD_START

    COLD_START: COLD_START
    COLD_START: IWDG 8 s · reset nedeni okunur
    COLD_START: FRAM halkası + OTA durumu yüklenir

    SELF_TEST: SELF_TEST
    SELF_TEST: TMP117 · pil OCV · 50 mA yük altında pil
    SELF_TEST: kelepçe temas anahtarı · pasivasyon testi

    PROVISION: PROVISION
    PROVISION: kimlik FRAM'den 64 bayt
    PROVISION: pano · cihaz · bağlantı · I_ref · CT var mı

    SAMPLE: SAMPLE
    SAMPLE: TMP117 tek atım · CT gerçek RMS 1 şebeke çevrimi
    SAMPLE: sıfır geçişi periyodu · pil · MCU sıcaklığı

    AGGREGATE: AGGREGATE
    AGGREGATE: min · maks · ortalama · RMS akım
    AGGREGATE: theta = dt / f² · theta_min = 3σ / f²
    AGGREGATE: theta eğim yazmacı · tetik değerlendirmesi

    TX: TX
    TX: önce FRAM halkasına yaz · sonra gönder
    TX: ETSI %1 kullanım oranı denetimi
    TX: TEK alma penceresi = onay + işaret + kardeş medyanı

    SLEEP: SLEEP
    SLEEP: STOP2 + RTC · IWDG donmuş
    SLEEP: 900 s / 60 s / 10 s

    DE_ENERGISED: DE_ENERGISED
    DE_ENERGISED: sıfır geçişi YOK ve akım YOK
    DE_ENERGISED: tüm ısıl göstergeler geçersiz ilan edilir
    DE_ENERGISED: yavaş kalp atışı sürer · sessiz kalınmaz

    LOW_BATTERY: LOW_BATTERY
    LOW_BATTERY: hayatta kalma kadansı · sağlık çerçevesi
    LOW_BATTERY: MUTLAK sıcaklık limitleri AÇIK kalır

    FAULT: FAULT
    FAULT: kimlik ve neden yayını

    COLD_START --> SELF_TEST
    SELF_TEST --> PROVISION: sensör ve hücre uygun
    SELF_TEST --> FAULT: TMP117 hatası veya hücre kritik
    PROVISION --> SAMPLE

    SAMPLE --> DE_ENERGISED: şebeke yok VE akım yok
    SAMPLE --> LOW_BATTERY: hücre kritik
    SAMPLE --> AGGREGATE: ölçüm geçerli

    AGGREGATE --> TX
    TX --> SLEEP
    SLEEP --> SAMPLE

    DE_ENERGISED --> DE_ENERGISED: hâlâ şebeke yok
    DE_ENERGISED --> SAMPLE: şebeke geri geldi
    LOW_BATTERY --> LOW_BATTERY: hâlâ kritik
    LOW_BATTERY --> TX: MUTLAK limit aşıldı
    LOW_BATTERY --> SAMPLE: hücre toparladı
    FAULT --> FAULT
```

### 1a. Kadans kararı — 2 yukarı / 4 aşağı histerezis

Kadans yanlış ayarlanırsa on üç yıllık düğüm altı aylık düğüme dönüşür.
Bu yüzden **yumuşak** tetikler en fazla `WATCH`'a çıkar; `BURST` yalnızca
şu anda olan bir şey içindir.

```mermaid
flowchart TB
    A["AGGREGATE bitti<br/>tetik maskesi hazır"] --> B{"Hücre zayıf mı?"}
    B -- evet --> Z["Kadans = IDLE 900 s<br/>sayaçlar sıfırlanır"]
    B -- hayır --> C{"SERT tetik?<br/>T ≥ 90 °C · T ≥ 110 °C<br/>ham kardeş farkı ≥ 20 K"}
    C -- evet --> D["Kadans = BURST 10 s<br/>en az 120 s tutulur<br/>sayma yok, doğrudan"]
    C -- hayır --> E{"YUMUŞAK tetik?<br/>theta ≥ 5 K · theta eğimi<br/>· theta basamağı"}
    E -- evet --> F["yukarı sayaç++<br/>aşağı sayaç = 0"]
    F --> G{"yukarı sayaç ≥ 2?"}
    G -- evet --> H["Bir kademe yükselt<br/>ÜST SINIR = WATCH 60 s"]
    G -- hayır --> K["Kadans değişmez"]
    E -- hayır --> I["aşağı sayaç++<br/>yukarı sayaç = 0"]
    I --> J{"BURST tabanı<br/>hâlâ geçerli mi?"}
    J -- evet --> K
    J -- hayır --> L{"aşağı sayaç ≥ 4?"}
    L -- evet --> M["Bir kademe düşür"]
    L -- hayır --> K
```

### 1b. Bir uyanma çevriminde theta

```mermaid
flowchart LR
    T1["TMP117<br/>ham LSB = 1/128 °C<br/>hiç dönüştürülmez"] --> D1
    P1["Kardeş medyanı<br/>· doğrudan komşu dinleme<br/>· veya ağ geçidi onayında"] --> D1
    D1["dt = T_kendi − medyan(kardeşler)<br/>KENDİSİ HARİÇ"] --> TH
    C1["Kendi ayrılabilir CT'si<br/>1 şebeke çevrimi gerçek RMS"] --> F1
    F1["f = I / I_ref &nbsp;Q16"] --> TH
    TH["theta = dt / f²<br/>anma akımında kelvin"] --> G1
    F1 --> TM["theta_min = 3σ / f²<br/>şu an görülebilen en küçük değer"]
    TM --> G1
    G1{"f ≥ 0.35 mi?"}
    G1 -- hayır --> S1["SENSITIVITY_LOW<br/>theta yayınlanır ama<br/>tetik olarak kullanılmaz<br/>MUTLAK limitler açık"]
    G1 -- evet --> G2{"theta ≥ 5 K<br/>ve theta ≥ theta_min?"}
    G2 -- evet --> TR["PG_TRIG_THETA"]
    G2 -- hayır --> TRD["Eğim yazmacına yaz<br/>en fazla 30 dakikada bir<br/>≥ 8 saat kapsamda eğim"]
```

---

## 2. Ağ geçidi ana döngüsü (DIN ray, ölçü kolonu, mevcut 10 A priz)

Ağ geçidi panodaki şebeke beslemeli ve WAN radyolu tek cihazdır. Dört işi
vardır ve saat 03:00'te önem sırası budur.

```mermaid
flowchart TB
    S(["Açılış"]) --> INIT["RS-485 uçları açılır<br/>MPR-53CS söz dizimi ve kelime sırası<br/>otomatik saptanır · TVOC-2 sürümü okunur"]
    INIT --> BIRTH["BIRTH mesajları<br/>9 cihaz · her biri göndereceği<br/>kanal listesini ilan eder"]
    BIRTH --> LOOP

    LOOP["1 Hz tarama çevrimi"] --> ARC["TVOC-2 oku<br/>reg 1300 sistem durumu<br/>reg 200-212 · 222-225<br/>reg 1300 yoksa 0x0000 = ARIZA YOK"]
    ARC --> MPR["MPR-53CS oku<br/>32 bit ölçümler · FC03 125 kayıt sınırı<br/>nedeniyle çok bloklu"]
    MPR --> RADIO["Sub-GHz çerçeveleri al<br/>8 pilli düğüm · her birine ONAY<br/>onaya kardeş medyanı iliştirilir"]
    RADIO --> LOCAL{"YEREL KRİTİK KURALLAR<br/>· ark açması<br/>· pabuç ≥ 90 °C<br/>· kardeş farkı ≥ 20 K ve f ≥ 0.35"}

    LOCAL -- tetiklendi --> DRY["Yerel kuru kontak + siren<br/>WAN · broker · sunucu · SMS<br/>hiçbirini BEKLEMEZ"]
    LOCAL -- temiz --> NORM
    DRY --> NORM["Çerçeve normalleştirilir<br/>her değer kanal aralığına karşı doğrulanır"]

    NORM --> STORE["SQLite'a yaz<br/>sample + joint_sample"]
    STORE --> RING["Sınırlı halkaya koy<br/>20 000 zarf"]
    RING --> PUB{"MQTT QoS 1<br/>PUBACK geldi mi?"}
    PUB -- evet --> ADV["Halka su seviyesi ilerler<br/>kayıt emekliye ayrılır"]
    PUB -- hayır --> BUF["Halkada kalır<br/>taşarsa EN ESKİ düşer ve<br/>düşen sayısı YAYINLANIR"]
    ADV --> LOOP
    BUF --> LOOP

    LOOP -.-> WILL["Son vasiyet mesajı<br/>ağ geçidi ölürse pano<br/>zaman aşımıyla değil<br/>ANINDA bilinir"]
```

> **Neden Sparkplug B değil:** Sparkplug 3.0 DDATA için QoS 0 **zorunlu**
> kılar. Dayanıklılık iddiamız PUBACK ile ilerleyen bir su seviyesine
> dayanıyor ve QoS 0'da PUBACK yoktur. Şartnamenin yasakladığı bir
> mekanizmaya dayanan garanti, garanti değildir. Sparkplug'ın işe yarayan
> dört fikri — birth, last will, cihaz başına sıra numarası, death/rebirth —
> kırk satırda korunmuştur.

---

## 3. OTA — takas ve geri alma durum makinesi

Bu panoda **AG giriş kesicisi yoktur** (Madde 2.2.10.2.vi, "direk bara
bağlantı"). Panoyu enerjisiz bırakmak, tüm dağıtım merkezini OG tarafından
karartmak demektir. Bu yüzden tuğlalanmış bir düğüm "gidip yeniden
programlarız" değil, "bir mahalleye kesinti planlarız" demektir.

Bir düğümün tuğlalanması için **dört bağımsız şeyin** aynı anda bozulması
gerekir.

```mermaid
stateDiagram-v2
    direction TB
    [*] --> IDLE

    IDLE: IDLE
    IDLE: çalışan imaj · sürüm bilinir

    OFFERED: OFFERED
    OFFERED: ağ geçidi yeni sürüm ilan etti

    ENERGY_HOLD: ENERGY_HOLD
    ENERGY_HOLD: reddedildi ama SESSİZCE DEĞİL
    ENERGY_HOLD: neden kaydı güncel tutulur

    DOWNLOADING: DOWNLOADING
    DOWNLOADING: PASİF slot silinir
    DOWNLOADING: 192 baytlık parçalar
    DOWNLOADING: çalışan imaja DOKUNULMAZ

    VERIFIED: VERIFIED
    VERIFIED: tüm slot üzerinde CRC32 + imza

    PENDING_SWAP: PENDING_SWAP
    PENDING_SWAP: takas BOOTLOADER'a devredilir
    PENDING_SWAP: deneme sayacı flash'a yazılır

    TRIAL: TRIAL
    TRIAL: yeni imaj çalışıyor ama ONAYSIZ
    TRIAL: bootloader HER AÇILIŞTA sayacı azaltır

    CONFIRMED: CONFIRMED
    CONFIRMED: 3 açılış içinde 3 onaylı çerçeve

    REVERTED: REVERTED
    REVERTED: eski slot geri alınır · o slot hiç silinmemişti

    FAILED: FAILED
    FAILED: boyut · CRC · deneme sayısı

    IDLE --> OFFERED: sürüm > mevcut
    OFFERED --> FAILED: imaj slot boyutunu aşıyor
    OFFERED --> ENERGY_HOLD: ENERJİ KAPISI · hücre %25 altında · pasive
    OFFERED --> ENERGY_HOLD: OLAY KAPISI · düğüm bir bağlantıyı izliyor
    ENERGY_HOLD --> OFFERED: her iki kapı da açıldı
    OFFERED --> DOWNLOADING: kapılar açık
    DOWNLOADING --> ENERGY_HOLD: indirme sırasında hücre düştü
    DOWNLOADING --> FAILED: 8 deneme tükendi
    DOWNLOADING --> FAILED: CRC32 tutmadı
    DOWNLOADING --> VERIFIED: tüm imaj + CRC tamam
    VERIFIED --> PENDING_SWAP
    PENDING_SWAP --> TRIAL: yeniden açılış · diğer slot
    TRIAL --> CONFIRMED: işaret alındı VE 3 onaylı çerçeve gönderildi
    TRIAL --> REVERTED: deneme sayacı sıfırlandı
    TRIAL --> REVERTED: BEKÇİ KÖPEĞİ sıfırladı · askıda kalma denemeyi yakar
    CONFIRMED --> IDLE
    REVERTED --> IDLE
    FAILED --> IDLE
```

### 3a. Neden tuğlalanamaz — flash haritası

```mermaid
flowchart TB
    subgraph FLASH["STM32WLE5CC · 256 kB flash"]
        BL["0x08000000 · 16 kB<br/><b>BOOTLOADER</b><br/>WRP + RDP seviye 1<br/>ASLA güncellenmez"]
        RC["0x08004000 · 48 kB<br/><b>KURTARMA İMAJI</b><br/>WRP · ASLA güncellenmez<br/>sadece işaret yayar ve OTA kabul eder"]
        A["0x08010000 · 88 kB<br/>SLOT A"]
        B["0x08026000 · 88 kB<br/>SLOT B"]
        CFG["0x0803C000 · 16 kB<br/>OTA üstverisi · dönüşümlü yazım"]
    end
    BL --> Q1{"Açılışta:<br/>deneme sayacı > 0 mı?"}
    Q1 -- "evet" --> DEC["Sayacı azalt · yeni slotu başlat"]
    Q1 -- "hayır ve onaysız" --> SWAP["Eski slota geri dön"]
    DEC --> Q2{"Yeni imaj onay verdi mi?"}
    Q2 -- evet --> OK["Onaylandı · sayaç kaldırılır"]
    Q2 -- hayır --> SWAP
    SWAP --> Q3{"Her iki slot da bozuk mu?"}
    Q3 -- evet --> RC
    Q3 -- hayır --> OK
```

Açılış döngüsü, düğümü yok etmek yerine **geri alır**. Bekçi köpeği
sıfırlaması bir denemeyi yakar; üç sıfırlama eski imajı geri getirir.

---

## 4. Uçtan uca veri yolu — sensörden SMS'e

```mermaid
flowchart TB
    subgraph PANO["Pano içi · TEDAŞ-MLZ/2003-06.B · 1600 kVA"]
        TMP["TMP117<br/>alt bölme · kablo pabucu<br/>1 LSB = 1/128 °C"]
        CT["Ayrılabilir CT<br/>kelepçenin içinde<br/><i>hiçbir çıkışta sayaç CT'si yok</i>"]
        IR["MLX90640 32×24<br/>48 pabuç sırasına bakar"]
        HF["HFCT + AD8318<br/>PE saplamasında"]
        MPR["Entes MPR-53CS<br/>RS-485"]
        TV["ABB TVOC-2<br/>RS-485 · SIL-2"]
    end

    TMP --> EDGE
    CT --> EDGE
    EDGE["<b>DÜĞÜM UÇ ANALİTİĞİ</b><br/>theta = dt / f² · eğim · RMS<br/>tamsayı · kayan nokta yok"]
    EDGE --> FRAM["FRAM halkası<br/>MB85RS64V · 200 kayıt<br/>50 saat @ 900 s"]
    FRAM --> LORA["868 MHz LoRa SF7<br/>35 bayt · 78 ms hava süresi<br/>ETSI %1 denetlenir"]

    IR --> LORA
    HF --> LORA
    LORA --> GW
    MPR --> GW
    TV --> GW

    GW["<b>AĞ GEÇİDİ</b><br/>yerel kritik kurallar<br/>+ sakla-ilet halkası"]
    GW ==> DRY["<b>YEREL KURU KONTAK</b><br/>WAN'ı beklemez"]
    GW --> MQ["MQTT QoS 1<br/>PUBACK su seviyesi"]

    MQ --> DET["<b>SUNUCU · DEDEKTÖR</b><br/>RLS ısıl gecikme çözümü<br/>CUSUM k=0.5 h=8<br/>değişim noktası · Theil-Sen<br/>çiy noktası · nötr kuralı H3"]
    DET --> RULES["<b>KURALLAR</b><br/>bastırma → füzyon → alarm<br/>7 arıza modu · sağlık endeksi"]
    RULES --> SUP["Bastırılmış alarmlar<br/><i>kendi ekranı ve kendi<br/>gerekçeleri olan bir ÖZELLİK</i>"]
    RULES --> INC{"Şiddet<br/>KRİTİK veya ACİL?"}
    INC -- hayır --> Q["Kuyruk · haftalık özet<br/>· iş emri"]
    INC -- evet --> SMS["<b>SMS + sesli arama</b><br/>UCS-2 · nöbet listesi<br/>onay jetonu · tırmandırma"]
    RULES --> SCADA["SCADA Modbus TCP kölesi<br/>pano başına 48 kayıt<br/>salt okunur"]

    style DRY fill:#c0392b,color:#fff
    style SMS fill:#c0392b,color:#fff
    style EDGE fill:#1f6f8b,color:#fff
    style DET fill:#1f6f8b,color:#fff
```

### 4a. Bildirim gecikmesi — tek bir sayı DEĞİL, bir ARALIK

```mermaid
flowchart LR
    E["Olay"] --> T1["TVOC-2 Modbus görüntüsünün<br/>yayılması<br/><b>0.2 – 2 s</b><br/><i>ABB dokümante etmiyor</i>"]
    T1 --> T2["Ağ geçidi taraması<br/><b>0 – 1 s</b>"]
    T2 --> T3["Broker + sunucu<br/>+ kural hattı<br/><b>0.5 – 3 s</b>"]
    T3 --> T4["SMS yolu<br/>operatör kuyruğu<br/><b>3 – 7 s</b>"]
    T4 --> R["<b>TOPLAM 4 – 13 s</b>"]
    E --> TRIP["<b>TVOC-2 açması ≈ 1 ms</b><br/>SIL-2 donanım<br/>PANO GÖZ'ü BEKLEMEZ<br/>PANO GÖZ kurulmasa da olur"]
    style TRIP fill:#c0392b,color:#fff
    style R fill:#e67e22,color:#fff
```

**PANO GÖZ koruma değildir.** Yukarıdaki zincirin tamamı bir *bildirimi*
kısaltır, bir *açmayı* değil. Açma, yazılım devrede olmadan, ayrı bir SIL-2
cihazda, yaklaşık 1 milisaniyede olur.

---

## 5. Kör olduğumuz durumlar — hepsi ayrı raporlanır

Bir izleme sisteminin en tehlikeli hâli, göremediği bir şeyi "sorun yok"
diye raporlamasıdır. Bu durumlar pano arızalarıyla **asla** karıştırılmaz.

```mermaid
flowchart TB
    R["Bir uyanma çevrimi"] --> Q1{"Şebeke ve akım var mı?"}
    Q1 -- hayır --> DE["<b>DE_ENERGISED</b><br/>Akım yok → hiçbir ısıl<br/>gösterge anlamlı değil.<br/>Soğuk bağlantı, sağlam<br/>bağlantı DEMEK DEĞİLDİR."]
    Q1 -- evet --> Q2{"Kelepçe yerinde mi?"}
    Q2 -- hayır --> ML["<b>MOUNT_LOST</b><br/>theta yayınlanmaz.<br/>Düşmüş kelepçe −19 K theta<br/>ve −59 µΩ 'fazla direnç'<br/>üretir. Bu bir CİHAZ durumu."]
    Q2 -- evet --> Q3{"Kardeş faz verisi taze mi?"}
    Q3 -- hayır --> PL["<b>PEER_LOST</b><br/>Kardeş yoksa theta yok.<br/>Bu bir radyo sorunudur."]
    Q3 -- evet --> Q4{"f ≥ 0.35 mi?"}
    Q4 -- hayır --> SL["<b>SENSITIVITY_LOW</b><br/>theta_min = 3σ / f²<br/>f=0.20 → 15 K altını göremeyiz.<br/>Bunu SÖYLERİZ.<br/>Mutlak limitler açık kalır."]
    Q4 -- evet --> OK["Tam duyarlılık<br/>theta güvenilir"]
    R --> Q5{"Hücre zayıf mı?"}
    Q5 -- evet --> CL["<b>CELL_LOW</b><br/>Hayatta kalma kadansı.<br/>Mutlak limitler AÇIK kalır."]
    R --> Q6{"Ağ geçidi ulaşılabilir mi?"}
    Q6 -- hayır --> BF["<b>BUFFERING</b><br/>FRAM halkası doluyor.<br/>Taşarsa en eski düşer ve<br/>düşen sayısı YAYINLANIR."]

    style DE fill:#7f8c8d,color:#fff
    style ML fill:#7f8c8d,color:#fff
    style PL fill:#7f8c8d,color:#fff
    style SL fill:#7f8c8d,color:#fff
    style CL fill:#7f8c8d,color:#fff
    style BF fill:#7f8c8d,color:#fff
    style OK fill:#27ae60,color:#fff
```

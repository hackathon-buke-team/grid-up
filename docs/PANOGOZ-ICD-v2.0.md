# PANO GÖZ · SCADA Arayüz Kontrol Dokümanı (ICD) v2.0.0

**Protokol:** Modbus TCP · **Rol:** slave (server) · **Port:** 502 (yapılandırılabilir)

**Desteklenen fonksiyon kodları:** 03 (Read Holding Registers), 04 (Read Input Registers).
Her ikisi de aynı adres uzayını okur.

**Reddedilen fonksiyon kodları:** 05, 06, 15, 16 → exception `0x01 ILLEGAL_FUNCTION`.
Bu harita **salt okunurdur ve istisnası yoktur.** Modbus'ta kimlik doğrulama yoktur;
ark koruma rölesine otokontrol komutu verebilen bir sisteme kimliksiz yazma yolu açmak
kabul edilebilir değildir. PANO GÖZ'deki iki aktüatör yolu (TVOC-2 reg 213 otokontrol ve
reg 1000 açma sıfırlama) ağ geçidinde, operatör kimlik doğrulaması ve fiziksel anahtar
arkasındadır; bu bus üzerinden erişilemez.

**Adresleme:** tüm adresler 0 tabanlı PDU'dur. `modpoll` ile `-0` bayrağını kullanın.
Modicon 4x sütunu yalnızca kolaylık içindir.

**32 bit değerler:** big-endian, yüksek word önce (ABCD).

**Doygunluk:** aralık dışı değerler sarmaz, tam ölçekte doyar. Sarmış bir register
makul küçük bir sayı gibi görünür ve SCADA'yı sessizce yanıltır; doymuş bir register
ise açıkça aralık dışıdır.

**Bayatlık:** `DATA_AGE_S` > 90 s olduğunda `STATUS_WORD.STALE` kurulur.
Bu değer tipik 30 s'lik SCADA tarama çevriminin üç katıdır.

---

## 1. Adres planı

| Blok | Unit ID | PDU aralığı | Boyut |
|---|---:|---|---:|
| Global | 1 | 0 … 31 | 32 register |
| Pano n (1…200) | 1 | 1000 + 48·(n−1) | 48 register |

Sabit adım, delik yok, sürüm dalı yok. SCADA mühendisi tek blok tanımlar ve 200
kez kopyalar. Tanımsız pano bloğu sıfır okur ve `DATA_VALID` biti temizdir; tarama hatası
ile boş pano birbirinden ayırt edilebilir olmalıdır.

Örnek: 14 numaralı pano → PDU 1624 … 1671 (4x: 41625 …).

Doğrulama komutu:

```
modpoll -m tcp -0 -r 0    -c 20  <sunucu>     # global blok
modpoll -m tcp -0 -r 1624 -c 48  <sunucu>     # 14 numaralı pano
```

---

## 2. Global blok

| PDU (dec) | PDU (hex) | 4x | Ofset | Ad | Tip | Ölçek | Birim | Aralık | Anlam | Not |
|---:|---|---:|---:|---|---|---:|---|---|---|---|
| 0 | 0x0000 | 40001 | +0 | `ICD_VERSION` | u32 | 1 | - | 0 … 4.29497e+09 | ICD sürümü | majör*10000 + minör*100 + yama |
| 2 | 0x0002 | 40003 | +2 | `PANEL_COUNT` | u16 | 1 | adet | 0 … 65535 | Tanımlı pano sayısı |  |
| 3 | 0x0003 | 40004 | +3 | `PANELS_ONLINE` | u16 | 1 | adet | 0 … 65535 | Çevrimiçi pano sayısı |  |
| 4 | 0x0004 | 40005 | +4 | `FLEET_WORST_SEVERITY` | u16 | 1 | - | 0 … 65535 | Filodaki en yüksek seviye | 0 BILGI · 1 IZLE · 2 UYARI · 3 KRITIK · 4 ACIL |
| 5 | 0x0005 | 40006 | +5 | `FLEET_ALARMS_ACTIVE` | u16 | 1 | adet | 0 … 65535 | Aktif alarm |  |
| 6 | 0x0006 | 40007 | +6 | `FLEET_ALARMS_CRITICAL` | u16 | 1 | adet | 0 … 65535 | Kritik ve üzeri alarm |  |
| 7 | 0x0007 | 40008 | +7 | `WATCHDOG_HEARTBEAT` | u16 | 1 | - | 0 … 65535 | Canlılık sayacı | Her saniye artar, 65535'te sarar. Durursa PANO GÖZ ölmüştür. |
| 8 | 0x0008 | 40009 | +8 | `SERVER_TIME` | u32 | 1 | s | 0 … 4.29497e+09 | Sunucu zamanı | Unix epoch, UTC |
| 10 | 0x000A | 40011 | +10 | `ENGINE_STATE` | bits | 1 | - | 0 … 65535 | Motor durumu | ENGINE_BITS |
| 11 | 0x000B | 40012 | +11 | `DETECTOR_LAG_S` | u16 | 1 | s | 0 … 65535 | Dedektör gecikmesi | Son tamamlanan çevrimden beri geçen süre |
| 12 | 0x000C | 40013 | +12 | `REGS_PER_PANEL` | u16 | 1 | - | 0 … 65535 | Pano blok boyu | Sabit |
| 13 | 0x000D | 40014 | +13 | `PANEL_BLOCK_BASE` | u32 | 1 | - | 0 … 4.29497e+09 | İlk pano blok adresi |  |
| 15 | 0x000F | 40016 | +15 | `FLEET_HEALTH_MIN` | u16 | 1 | - | 0 … 65535 | En düşük sağlık endeksi |  |
| 16 | 0x0010 | 40017 | +16 | `FLEET_HEALTH_MEAN` | u16 | 1 | - | 0 … 65535 | Ortalama sağlık endeksi |  |
| 17 | 0x0011 | 40018 | +17 | `DISPATCH_QUEUE` | u16 | 1 | adet | 0 … 65535 | Ekip yönlendirme kuyruğu |  |
| 18 | 0x0012 | 40019 | +18 | `SUPPRESSED_24H` | u16 | 1 | adet | 0 … 65535 | Son 24 saatte bastırılan alarm | Gerekçeleriyle birlikte kayıtlı |
| 19 | 0x0013 | 40020 | +19 | `PANELS_SENSITIVITY_LOW` | u16 | 1 | adet | 0 … 65535 | Görünürlüğü düşük pano | Bu panolarda θ geçici olarak güvenilir değil |

---

## 3. Pano bloğu

| PDU (dec) | PDU (hex) | 4x | Ofset | Ad | Tip | Ölçek | Birim | Aralık | Anlam | Not |
|---:|---|---:|---:|---|---|---:|---|---|---|---|
| 1000 | 0x03E8 | 41001 | +0 | `PANEL_ID` | u32 | 1 | - | 0 … 4.29497e+09 | Pano kimliği | Sayısal varlık numarası |
| 1002 | 0x03EA | 41003 | +2 | `HEALTH_INDEX` | u16 | 1 | - | 0 … 65535 | Sağlık endeksi | 100 sağlıklı, 0 en kötü |
| 1003 | 0x03EB | 41004 | +3 | `SEVERITY` | u16 | 1 | - | 0 … 65535 | Seviye | 0 BILGI · 1 IZLE · 2 UYARI · 3 KRITIK · 4 ACIL |
| 1004 | 0x03EC | 41005 | +4 | `STATUS_WORD` | bits | 1 | - | 0 … 65535 | Durum bitleri | STATUS_BITS |
| 1005 | 0x03ED | 41006 | +5 | `ACTIVE_ALARMS` | u16 | 1 | adet | 0 … 65535 | Aktif alarm sayısı |  |
| 1006 | 0x03EE | 41007 | +6 | `THETA_MAX` | i16 | 0.1 | K | -3276.8 … 3276.7 | En kötü θ | Anma akımında sıcaklık fazlası |
| 1007 | 0x03EF | 41008 | +7 | `THETA_MAX_JOINT` | u16 | 1 | - | 0 … 65535 | En kötü bağlantı indeksi | JOINTS dizisindeki sıra |
| 1008 | 0x03F0 | 41009 | +8 | `THETA_SLOPE` | i16 | 0.001 | K/hafta | -32.768 … 32.767 | θ eğimi | Pozitif ise bozulma sürüyor |
| 1009 | 0x03F1 | 41010 | +9 | `SENSITIVITY_PCT` | u16 | 1 | % | 0 … 65535 | Görünürlük | Yüke bağlı tespit yeteneği |
| 1010 | 0x03F2 | 41011 | +10 | `RISK_LOOSE` | u16 | 0.1 | % | 0 … 6553.5 | Gevşek bağlantı riski |  |
| 1011 | 0x03F3 | 41012 | +11 | `RISK_OVERLOAD` | u16 | 0.1 | % | 0 … 6553.5 | Aşırı yük riski |  |
| 1012 | 0x03F4 | 41013 | +12 | `RISK_ARC_INTEGRITY` | u16 | 0.1 | % | 0 … 6553.5 | Ark koruma bütünlüğü riski |  |
| 1013 | 0x03F5 | 41014 | +13 | `RISK_THERMAL` | u16 | 0.1 | % | 0 … 6553.5 | Isıl kaçış riski |  |
| 1014 | 0x03F6 | 41015 | +14 | `RISK_HARMONIC` | u16 | 0.1 | % | 0 … 6553.5 | Harmonik nötr riski |  |
| 1015 | 0x03F7 | 41016 | +15 | `RISK_MOISTURE` | u16 | 0.1 | % | 0 … 6553.5 | Nem / yoğuşma riski |  |
| 1016 | 0x03F8 | 41017 | +16 | `RISK_INSULATION` | u16 | 0.1 | % | 0 … 6553.5 | Yalıtım riski |  |
| 1017 | 0x03F9 | 41018 | +17 | `T_JOINT_MAX` | i16 | 0.1 | °C | -3276.8 … 3276.7 | En yüksek bağlantı sıcaklığı |  |
| 1018 | 0x03FA | 41019 | +18 | `T_AIR` | i16 | 0.1 | °C | -3276.8 … 3276.7 | Kabin içi hava |  |
| 1019 | 0x03FB | 41020 | +19 | `RH` | u16 | 0.1 | % | 0 … 6553.5 | Bağıl nem |  |
| 1020 | 0x03FC | 41021 | +20 | `DEWPOINT_MARGIN` | i16 | 0.1 | K | -3276.8 … 3276.7 | Yoğuşma payı | Negatif ise yüzeyde yoğuşma var |
| 1021 | 0x03FD | 41022 | +21 | `I_L1` | u16 | 0.1 | A | 0 … 6553.5 | L1 akımı |  |
| 1022 | 0x03FE | 41023 | +22 | `I_L2` | u16 | 0.1 | A | 0 … 6553.5 | L2 akımı |  |
| 1023 | 0x03FF | 41024 | +23 | `I_L3` | u16 | 0.1 | A | 0 … 6553.5 | L3 akımı |  |
| 1024 | 0x0400 | 41025 | +24 | `I_N` | u16 | 0.1 | A | 0 … 6553.5 | Nötr akımı |  |
| 1025 | 0x0401 | 41026 | +25 | `V_L1` | u16 | 0.1 | V | 0 … 6553.5 | L1 gerilimi |  |
| 1026 | 0x0402 | 41027 | +26 | `V_L2` | u16 | 0.1 | V | 0 … 6553.5 | L2 gerilimi |  |
| 1027 | 0x0403 | 41028 | +27 | `V_L3` | u16 | 0.1 | V | 0 … 6553.5 | L3 gerilimi |  |
| 1028 | 0x0404 | 41029 | +28 | `FREQ` | u16 | 0.01 | Hz | 0 … 655.35 | Frekans |  |
| 1029 | 0x0405 | 41030 | +29 | `THD_V_MAX` | u16 | 0.1 | % | 0 … 6553.5 | En yüksek gerilim THD |  |
| 1030 | 0x0406 | 41031 | +30 | `THD_I_MAX` | u16 | 0.1 | % | 0 … 6553.5 | En yüksek akım THD | I > CT anmasının %10'u değilse 0 |
| 1031 | 0x0407 | 41032 | +31 | `LOAD_FACTOR` | u16 | 0.1 | % | 0 … 6553.5 | Yük faktörü | Anma akımına göre |
| 1032 | 0x0408 | 41033 | +32 | `PD_RATE` | u16 | 1 | 1/s | 0 … 65535 | RF darbe hızı |  |
| 1033 | 0x0409 | 41034 | +33 | `PD_QMAX` | u16 | 0.1 | dB | 0 … 6553.5 | RF tepe genlik | pC eşdeğeri, IEC 60270 izlenebilir DEĞİL |
| 1034 | 0x040A | 41035 | +34 | `PD_CLASS` | u16 | 1 | - | 0 … 65535 | PRPD sınıfı | 0 GURULTU · 1 BOSLUK · 2 YUZEY · 3 KORONA · 4 YUZEN |
| 1035 | 0x040B | 41036 | +35 | `TEV_LEVEL` | u16 | 0.1 | dB | 0 … 6553.5 | TEV seviyesi |  |
| 1036 | 0x040C | 41037 | +36 | `ARC_STATE` | bits | 1 | - | 0 … 65535 | Ark koruma durumu | ARC_BITS |
| 1037 | 0x040D | 41038 | +37 | `ARC_DETECTORS_OK` | u16 | 1 | adet | 0 … 65535 | Sağlam dedektör |  |
| 1038 | 0x040E | 41039 | +38 | `ARC_DETECTORS_TOTAL` | u16 | 1 | adet | 0 … 65535 | Kurulu dedektör |  |
| 1039 | 0x040F | 41040 | +39 | `ARC_AMBIENT_WARN` | u16 | 1 | adet | 0 … 65535 | Işık uyarısı veren dedektör |  |
| 1040 | 0x0410 | 41041 | +40 | `ARC_DETECTOR_MAP_LO` | bits | 1 | - | 0 … 65535 | Dedektör haritası düşük | TVOC-2 reg 210 aynası · X1:1-10, X2:1-5 |
| 1041 | 0x0411 | 41042 | +41 | `ARC_DETECTOR_MAP_HI` | bits | 1 | - | 0 … 65535 | Dedektör haritası yüksek | TVOC-2 reg 211 aynası · X2:6-10, X3:1-10 |
| 1042 | 0x0412 | 41043 | +42 | `ARC_LAST_SELFTEST_D` | u16 | 1 | gün | 0 … 65535 | Son otokontrolden beri |  |
| 1043 | 0x0413 | 41044 | +43 | `DEVICES_ONLINE` | u16 | 1 | adet | 0 … 65535 | Çevrimiçi cihaz | 9 üzerinden |
| 1044 | 0x0414 | 41045 | +44 | `DEVICE_FAULT_MAP` | bits | 1 | - | 0 … 65535 | Cihaz arıza haritası | DEVICE_FAULT_BITS |
| 1045 | 0x0415 | 41046 | +45 | `DATA_AGE_S` | u16 | 1 | s | 0 … 65535 | Veri yaşı | Son başarılı güncellemeden beri geçen saniye |
| 1046 | 0x0416 | 41047 | +46 | `UPDATED_AT` | u32 | 1 | s | 0 … 4.29497e+09 | Son güncelleme | Unix epoch, UTC |

---

## 4. Bit alanları

### STATUS_WORD (pano +4)

| Bit | Ad | Anlam | Not |
|---:|---|---|---|
| 0 | `DATA_VALID` | Veri geçerli | 0 ise bu blok doldurulmadı, alarm olarak yorumlamayın |
| 1 | `STALE` | Veri bayat | DATA_AGE_S eşiği aşıldı |
| 2 | `SENSITIVITY_LOW` | Görünürlük düşük | Yük çok düşük, θ güvenilir değil |
| 3 | `DE_ENERGISED` | Pano enerjisiz | Akım yok, hiçbir ısıl gösterge anlamlı değil |
| 4 | `LEARN_MODE` | Öğrenme modu | Devreye alma sonrası 7 gün; mutlak limitler yine de aktif |
| 5 | `SUPPRESSED` | Bastırılmış alarm var | Gerekçesi alarm konsolunda kayıtlı |
| 6 | `MAINTENANCE` | Bakım modu | Operatör tarafından elle bastırıldı |
| 7 | `ANALYSER_COMMS_LOST` | Analizör haberleşmesi yok | Entes MPR-53CS RS-485 |
| 8 | `ARC_RELAY_COMMS_LOST` | Ark rölesi haberleşmesi yok | ABB TVOC-2 RS-485 · cihazın kendisi bunu bildiremez |
| 9 | `GATEWAY_COMMS_LOST` | Ağ geçidi çevrimdışı |  |
| 10 | `MOUNT_LOST` | Sensör düştü/kaydı | Mıknatıs kaide teması kayboldu |
| 11 | `AIM_SHIFTED` | Termal dizi nişanı kaydı | Referans noktaları eşleşmiyor |
| 12 | `CELL_LOW` | Pil zayıf |  |
| 13 | `CLOCK_UNSYNCED` | Saat senkron değil |  |
| 14 | `CONFIG_MISMATCH` | Yapılandırma uyuşmazlığı |  |
| 15 | `SELFTEST_DUE` | Ark otokontrolü gecikti |  |

### ARC_STATE (pano +36)

| Bit | Ad | Anlam | Not |
|---:|---|---|---|
| 0 | `ACTIVE_TRIP` | Aktif açma | TVOC-2 reg 1300 bit0 |
| 1 | `ACTIVE_ERROR` | Aktif hata | TVOC-2 reg 1300 bit1 |
| 2 | `START_SEQUENCE` | Başlatma dizisi | TVOC-2 reg 1300 bit2 |
| 3 | `DIAGNOSTICS_RUNNING` | Otokontrol çalışıyor | TVOC-2 reg 1300 bit3 |
| 4 | `DETECTOR_FAULT` | Dedektör arızası | reg 222/223 · yalnız FW >= 03.00.00 |
| 5 | `AMBIENT_WARNING` | Ortam ışığı uyarısı | reg 224/225 · dedektör kör olabilir |
| 6 | `COMMS_LOST` | Haberleşme yok | PANO GÖZ tarafından üretilir |
| 7 | `SELFTEST_DISABLED` | Otokontrol devre dışı | ABB yazılı teyidi alınana kadar varsayılan |
| 8 | `NOT_FITTED` | Ark rölesi takılı değil | Bu panoda TVOC-2 yok |

### DEVICE_FAULT_MAP (pano +44)

| Bit | Ad | Anlam | Not |
|---:|---|---|---|
| 0 | `DEV_TC01` | TC01 arızalı |  |
| 1 | `DEV_TC02` | TC02 arızalı |  |
| 2 | `DEV_TC03` | TC03 arızalı |  |
| 3 | `DEV_TC04` | TC04 arızalı |  |
| 4 | `DEV_TC05` | TC05 arızalı |  |
| 5 | `DEV_TC06` | TC06 arızalı |  |
| 6 | `DEV_TNIR` | TNIR arızalı |  |
| 7 | `DEV_PD01` | PD01 arızalı |  |
| 8 | `DEV_GW01` | GW01 arızalı |  |

### ENGINE_STATE (global +10)

| Bit | Ad | Anlam | Not |
|---:|---|---|---|
| 0 | `INGEST_OK` | Toplama servisi çalışıyor |  |
| 1 | `DETECTOR_OK` | Dedektör çalışıyor |  |
| 2 | `STORE_OK` | Veri tabanı erişilebilir |  |
| 3 | `NOTIFY_OK` | Bildirim servisi çalışıyor |  |
| 4 | `SMS_PATH_OK` | SMS yolu doğrulandı |  |
| 5 | `STORM_ACTIVE` | Alarm fırtınası bastırma etkin |  |
| 6 | `DEGRADED` | Sistem düşük kapasitede |  |

---

## 5. Diğer protokoller

IEC 60870-5-104 tercih edilen güney yönlü arayüzdür; alarmlarımız olay biçimlidir ve
104'ün spontane COT=3 gönderimi bunu Modbus taramasından daha iyi taşır. Nokta adresi
`IOA = pano_no * 1000 + nokta_no`, ölçümler `M_ME_NC_1` kısa kayan nokta, zaman damgası
`CP56Time2a`. OPC UA ise varlık yönetimi tarafına `PanelType` bilgi modeli + Part 9
Alarms & Conditions ile hizmet eder. Her üç arayüz de aynı 1 Hz canlı görüntüyü okur.

Bu hackathon kapsamında **yalnız Modbus TCP slave çalışır durumda teslim edilmiştir.**
104 ve OPC UA nokta listeleri tablo olarak yazılmıştır, sunucuları kurulmamıştır.

# PANO GÖZ ICD v2.0.0 — Modbus TCP Register Haritası

> **Bu dosya `python -m tools.gen_icd` ile ÜRETİLİR; elle düzenlemeyin.** Tek gerçek kaynak
> `panogoz/scada/icd.py`. `tests/test_icd.py` bu dosyanın koddan üretilenle birebir aynı
> olduğunu doğrular (ICD ↔ kod tutarlılık testi, K2 2.5).

## Genel

- Protokol: **Modbus TCP**, yalnız **FC04 (Read Input Registers)** — salt okunur; Holding Register bloğu boş.
- Pano başına **32 register**; pano `p` (0 tabanlı) için taban adres = `p × 32`; en çok **200 pano** (6400 register).
- Değer = ham / ölçek. `s16`: 16 bit işaretli (two's complement). `bits`: bit alanı.
- Sürüm kaydı: bloğun son register'ı (ofset 31) `200` (= 2.0.0).
- Modbus FC04 tek istekte **en çok 125 register** okutur (≈ 3 pano); master birden çok okuma yapar.
- Olay tipi (latching) alarmlar (ark TRIP) sinyal dönse de onaylanana kadar `SEVERITY_CODE`/`SEV_ARC`/`FLAGS`'ta görünür.
- Eski v1 haritası (8 register/bağlantı) `docs/modbus-haritalama.md`'de, yalnızca `tools/run_modbus_server.py` için korunmuştur.

## Noktalar (pano başına)

| Ofset | Ad | Tip | Ölçek | Birim | Açıklama | Kaynak |
| ---: | --- | --- | ---: | --- | --- | --- |
| 0 | `SEVERITY_CODE` | u16 | 1 | — | Pano şiddeti: 0 NORMAL, 1 UYARI, 2 ALARM, 3 KRİTİK (süreç izlerinin en yükseği) | rules/pipeline: fused |
| 1 | `ALARMS_OPEN` | u16 | 1 | adet | Onay bekleyen (OPEN) alarm sayısı | rules/alarms |
| 2 | `ALARMS_ACTIVE` | u16 | 1 | adet | Aktif (OPEN + ACKED) alarm sayısı | rules/alarms |
| 3 | `FLAGS` | bits | 1 | — | Bit alanı, aşağıdaki FLAG_BITS tablosuna bakın | detector/flags + rules |
| 4 | `THETA_MAX_X10` | s16 | 10 | K | En yüksek |θ| (üç faz, kardeş medyanına göre, süzülmüş I²'ye normalize) | detector/theta |
| 5 | `CURRENT_L1_X10` | u16 | 10 | A | L1 akımı | CT / MPR-53CS |
| 6 | `CURRENT_L2_X10` | u16 | 10 | A | L2 akımı | CT / MPR-53CS |
| 7 | `CURRENT_L3_X10` | u16 | 10 | A | L3 akımı | CT / MPR-53CS |
| 8 | `NEUTRAL_CURRENT_X10` | u16 | 10 | A | Nötr akımı | CT / MPR-53CS |
| 9 | `JOINT_TEMP_L1_X10` | s16 | 10 | °C | L1 bağlantı sıcaklığı | MAX31855 (TC düğümü) |
| 10 | `JOINT_TEMP_L2_X10` | s16 | 10 | °C | L2 bağlantı sıcaklığı | MAX31855 (TC düğümü) |
| 11 | `JOINT_TEMP_L3_X10` | s16 | 10 | °C | L3 bağlantı sıcaklığı | MAX31855 (TC düğümü) |
| 12 | `NEUTRAL_TEMP_X10` | s16 | 10 | °C | Nötr bağlantı sıcaklığı | MAX31855 (TC düğümü) |
| 13 | `AMBIENT_TEMP_X10` | s16 | 10 | °C | Kabin içi hava sıcaklığı | T/RH sensörü (donanımda EKSİK, docs/09 §5) |
| 14 | `WALL_TEMP_X10` | s16 | 10 | °C | Kabin duvarı (soğuk nokta) sıcaklığı | NTC (donanımda EKSİK, docs/09 §5) |
| 15 | `HUMIDITY_X10` | u16 | 10 | %RH | Bağıl nem | T/RH sensörü (donanımda EKSİK, docs/09 §5) |
| 16 | `DEW_MARGIN_X10` | s16 | 10 | K | Çiy noktası marjı (duvar − çiy noktası); ≤0 yoğuşma | detector/condensation |
| 17 | `PD_INDEX_X10` | u16 | 10 | idx | Kısmi deşarj indeksi (1,5 sa medyan) | HFCT30/50 (IR/PD düğümü) |
| 18 | `OVERLOAD_RATIO_X100` | u16 | 100 | ×Ir | 1 saatlik RMS akım / anma akımı | detector/overload |
| 19 | `NEUTRAL_LOADING_X100` | u16 | 100 | ×In | 1 saatlik RMS nötr akımı / nötr anma | detector/neutral |
| 20 | `SEV_LOOSE_BOLT` | u16 | 1 | — | Gevşek cıvata izi şiddeti (0..3) | rules/pipeline |
| 21 | `SEV_OVERLOAD` | u16 | 1 | — | Aşırı yük izi şiddeti (0..3) | rules/pipeline |
| 22 | `SEV_NEUTRAL` | u16 | 1 | — | Nötr izleri (yüklenme/bağlantı) şiddeti (0..3) | rules/pipeline |
| 23 | `SEV_CONDENSATION` | u16 | 1 | — | Yoğuşma/nem izleri şiddeti (0..3) | rules/pipeline |
| 24 | `SEV_PD` | u16 | 1 | — | PD izi şiddeti, füzyon sonrası (0..3) | rules/pipeline |
| 25 | `SEV_ARC` | u16 | 1 | — | Ark koruma izleri (trip/bütünlük) şiddeti (0..3) | rules/pipeline |
| 26 | `DATA_AGE_S` | u16 | 1 | s | Son geçerli örnekten bu yana geçen süre (65535'te doyar) | detector/flags (STALE) |
| 27 | `RESERVED_27` | u16 | 1 | — | Ayrılmış (0) | - |
| 28 | `RESERVED_28` | u16 | 1 | — | Ayrılmış (0) | - |
| 29 | `RESERVED_29` | u16 | 1 | — | Ayrılmış (0) | - |
| 30 | `RESERVED_30` | u16 | 1 | — | Ayrılmış (0) | - |
| 31 | `ICD_VERSION` | u16 | 1 | — | ICD sürümü: 2.0.0 -> 200 | sabit |

## FLAGS bit alanı (ofset 3)

| Bit | Ad | Anlam |
| ---: | --- | --- |
| 0 | `STALE` | Cihaz beklenen periyotta örnek göndermiyor (3 x periyot) |
| 1 | `DE_ENERGISED` | Akım anma akımının %2'sinin altında: enerjisiz / kesici açık |
| 2 | `ARC_TRIP_LATCHED` | Ark koruma TRIP alarmı onay bekliyor (olay tipi, sinyal dönse de açık) |
| 3 | `ARC_INTEGRITY_FAULT` | Ark koruma tanılama hatası: koruma devre dışı |
| 4 | `MUTED` | Bu panoda en az bir iz sessize alınmış |
| 5 | `PD_ADVISORY` | PD yükselmiş ama ikinci kanal ailesi olmadığı için UYARI'da tutuluyor |
| 6 | `ALARM_PAGED` | En az bir ALARM+ alarm nöbetçiye sevk edildi ve onay bekliyor |

## Şiddet kodları

| Kod | Anlam |
| ---: | --- |
| 0 | NORMAL |
| 1 | UYARI |
| 2 | ALARM |
| 3 | KRİTİK |

## Örnek: pano 2'nin sıcaklığını okumak

```
taban = 2 x 32 = 64
JOINT_TEMP_L2_X10  -> adres 74 (FC04)
modpoll -m tcp -a 1 -r <adres+1> -c 1 -t 3 127.0.0.1 -p 5020   # modpoll 1 tabanlı adres kullanır
```

## IEC 60870-5-104 (ikinci SCADA protokolü)

Aynı 32'lik blok IEC 104 üzerinden de yayınlanır (`panogoz/scada/iec104.py`, TCP **2404**, ortak adres **1**).

| Bilgi | Tip | IOA | Not |
| --- | --- | --- | --- |
| 32 ölçüm/kod (bloğun tüm ofsetleri) | `M_ME_NB_1` (11), ölçekli | `1 + pano × 32 + ofset` (1…6400) | Değer = Modbus register'ı ile aynı tam sayı (s16 işaretli; u16 32767'de doyar → OV bitli). STALE iken NT biti. |
| FLAGS bit'leri (7 adet) | `M_SP_NA_1` (1) genel taramada, `M_SP_TB_1` (30, CP56Time2a) anlık olayda | `10001 + pano × 8 + bit` | Bit adları yukarıdaki FLAGS tablosunda |
| Genel tarama | `C_IC_NA_1` (100), QOI 20 | — | ACT_CON → veri (COT 20) → ACT_TERM |
| Kendiliğinden bildirim | COT 3 | — | Şiddet/alarm sayacı/SEV_* değişimi (`M_ME_NB_1`), bayrak değişimi (`M_SP_TB_1`) |
| Saat senkronu | `C_CS_NA_1` (103) | — | Sunucunun olay zaman damgası ofseti ayarlanır |
| Okuma / test | `C_RD_NA_1` (102) / `C_TS_NA_1` (104) | — | Okuma COT 5 ile yanıtlanır |
| Kontrol komutları (45…69) | — | — | **Reddedilir** (yalnız izleme; ACT_CON negatif, COT 44) |

Varsayılan APCI parametreleri: k=12, w=8, t1=15 s, t2=10 s, t3=20 s.

## Alarm ↔ register eşlemesi

SCADA'nın alarm listesi `SEVERITY_CODE` ve `SEV_*` register'larından türetilir; `FLAGS` bit'leri
alarm kaynağını (ark, PD tavsiyesi, haberleşme) açıklar. Konsoldaki SCADA sekmesi aynı
register'ları ham + çözülmüş haliyle yan yana gösterir (görsel kanıt).

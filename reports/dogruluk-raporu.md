# Doğruluk Raporu — PANO GÖZ (K4 §4.4)

Varsayılan theta eşiği: 0.02

## 17 Senaryo x Tespit Matrisi

| ID | Senaryo | Beklenen | Tespit | Uyum | Şiddet | Kanal Ailesi | Haber Verme (gün) |
|---|---|---|---|---|---|---|---|
| A1 | Gevşek bağlantı - hızlı gelişen | ALARM | ALARM | OK | ALARM | thermal | 0 |
| A2 | Gevşek bağlantı - yavaş sürüklenme (haftalar önce haber) | ALARM | ALARM | OK | ALARM | thermal | 5 |
| A3 | Aşırı yük - sürekli %118 | ALARM | ALARM | OK | ALARM | overload | 2 |
| A4 | Isıl kaçış - mutlak limitlere tırmanış | ALARM | ALARM | OK | EMERGENCY | thermal,thermal_absolute | 1 |
| A5 | Nötr harmonik yüklenme | ALARM | ALARM | OK | ALARM | neutral_harmonic | 2 |
| A6 | Nem/yoğuşma - marj ihlali | ALARM | ALARM | OK | ALARM | condensation | 2 |
| A7 | Yalıtım bozulması - PD artışı | ALARM | ALARM | OK | ALARM | insulation_pd | 8 |
| A8 | Ark bütünlüğü - dedektör öz test hatası | ALARM | ALARM | OK | ALARM | arc_integrity | 0 |
| A9 | Ark bütünlüğü - gerçek trip olayı | ALARM | ALARM | OK | EMERGENCY | arc_trip | 0 |
| A10 | Kombine arıza - gevşek bağlantı + aşırı yük | ALARM | ALARM | OK | ALARM | thermal | 0 |
| N1 | Normal dengeli yük (mevsimsel dalgalanma) | - | - | OK | NORMAL | - | - |
| N2 | Ani yük geçişi (transient) - debounce eler | - | - | OK | NORMAL | - | - |
| N3 | Sensör/iletişim kopması - yalnız STALE | - | - | OK | NORMAL | - | - |
| N4 | Planlı bakım - de-enerjize fider | - | - | OK | NORMAL | - | - |
| N5 | Hafif nem - marj içinde | - | - | OK | NORMAL | - | - |
| N6 | Şebeke olayı adayı (THD) - ısıl bulgu yok | - | - | OK | NORMAL | - | - |
| N7 | Sensör drift - kalibrasyon kayması | - | - | OK | NORMAL | - | - |

## Özet

- Duyarlılık (10 alarm senaryosu): 10/10
- Yanlış alarm bütçesi (7 negatif kontrol): 0/7
- Haber verme süresi dağılımı (gün): min=0, medyan=2, max=8

## Duyarlılık Eğrisi (theta eşiği taraması)

Üretim hattı = debounce + CUSUM + akım korelasyonu. Ham eşik = bastırmasız, tek örnekte eşik aşımı (klasik sabit eşik yaklaşımının simülasyonu).

| Eşik | Üretim - Tespit | Üretim - Yanlış Alarm | Ham Eşik - Tespit | Ham Eşik - Yanlış Alarm |
|---|---|---|---|---|
| 0.000 | 1.00 | 0.00 | 1.00 | 1.00 |
| 0.001 | 1.00 | 0.00 | 1.00 | 1.00 |
| 0.001 | 1.00 | 0.00 | 1.00 | 1.00 |
| 0.002 | 1.00 | 0.00 | 1.00 | 0.00 |
| 0.002 | 1.00 | 0.00 | 1.00 | 0.00 |
| 0.005 | 1.00 | 0.00 | 1.00 | 0.00 |
| 0.010 | 1.00 | 0.00 | 1.00 | 0.00 |
| 0.020 | 1.00 | 0.00 | 1.00 | 0.00 |
| 0.030 | 1.00 | 0.00 | 1.00 | 0.00 |
| 0.050 | 1.00 | 0.00 | 1.00 | 0.00 |
| 0.080 | 1.00 | 0.00 | 1.00 | 0.00 |
| 0.120 | 1.00 | 0.00 | 0.00 | 0.00 |
| 0.200 | 1.00 | 0.00 | 0.00 | 0.00 |

Grafik: duyarlilik-egrisi.png

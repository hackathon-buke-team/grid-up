# Alarm ve yük düzeltmesi sonucu

11 Eylül 2026. Görev kapsamındaki değişiklikler tamamlandı; git/commit yok.

## Değişiklikler

- `panogoz/contracts/live.py`: `JointView.severity` varsayılanı açık karar-yok sentineli `None`; `BILGI` artık gerçek dedektör kararı. `PanelLive.feeder_load_factor` nullable ayrı alanı eklendi. `load_factor` ana bara anmasına göre tanımlandı.
- `panogoz/detector/engine.py`: panel yükü üç faz ortalaması / 2312 A; ayrı tahmini fider yükü ortalama / 3250 A. Panel sensitivity hesabı fider ölçeğinde tutuldu. JointView üretiminde başlangıç kararı açık `BILGI`; per-joint CT ve fider akım tahmini `_load_factor` hesabı değiştirilmedi. Ingestion/cadence alanlarına dokunulmadı. Engine sahipliği ana ajana geri verildi.
- `panogoz/rules/fusion.py`: geçerli JointView kararı anlık theta ile yükseltilmiyor; theta fallback yalnız karar yokken. Mutlak sıcaklık safety floor aynen korunuyor. Overload evidence maksimum faz / 2312 A oranını da kullanıyor; ekrandaki ve SCADA'daki oran faz ortalaması olmaya devam ediyor.
- `tests/test_alarm_load_regression.py`: IR-only anlık theta sıçraması, açık BILGI/KRITIK kararı, 130 °C ACIL, karar-yok fallback, arc ACIL, tam bara yükü, dengesiz faz aşırı yükü, Modbus LOAD_FACTOR ve fider/sensitivity ölçekleri.

## TDD ve ham sonuçlar

İlk `python -m pytest tests/test_alarm_load_regression.py -q` çalışması, üretim değişikliği öncesi:

```text
FFF..FF                                                                  [100%]
IR engine BILGI -> fusion KRITIK: AssertionError
explicit BILGI -> KRITIK: AssertionError
explicit KRITIK -> ACIL: AssertionError
full busbar load: Obtained 0.7113846153846154, Expected 1.0
unbalanced mean load: Obtained 0.6153846153846154, Expected 0.8650519031141869
5 failed, 2 passed in 0.64s
```

Uygulama sonrası ilk yeşil sonuç:

```text
.......                                                                  [100%]
7 passed in 0.41s
```

Arc override ve düşük fider yükü/sensitivity koruma kapsamı eklenmiş son regresyon sonucu:

```text
.........                                                                [100%]
9 passed in 0.41s
```

`PYTHONIOENCODING=utf-8; python -m tests.test_rules` (exit 0):

```text
37/37 kontrol geçti
```

`PYTHONIOENCODING=utf-8; python -m tests.test_detector` (exit 0):

```text
[PASS] defect theta above the 5 K alarm level  10.24 K
[PASS] defect reaches KRITIK  KRITIK
[PASS] no healthy phase joint raises above BILGI  ['BILGI']
[PASS] state survives a restart bit for bit
PDU 1031  LOAD_FACTOR      raw [1155]       -> 115.5 %
[PASS] THETA_MAX word matches the image
[PASS] 48-word block
SONUÇ
    all detector claims verified with computed numbers
```

## Uyumluluk ve kapsam sınırı

Mevcut test fixture'larını değiştirmek gerekmedi. Elle üretilen JointView varsayılan `None` ile önceki theta fallback davranışını açık biçimde sürdürüyor; geçerli BILGI kararını fallback olarak kullanmıyor. Gerçek engine görüntülerinde izlenmeyen joint'ler dahil severity her zaman bir string. `fusion.apply` manuel görüntüyü de kararlarla dolduruyor. SCADA demo fixture'ı fusion öncesi `None` taşıyabilir; mevcut register kodlayıcısı joint severity okumuyor. Manuel bir görüntünün ölçümlerini değiştirerek tekrar sınıflandıran tüketici, yeni dedektör kararı sağlamalı veya severity'yi tekrar `None` yapmalıdır.

Tüm Python load_factor kullanımları tarandı. Ana ajana `rules/alarms.py:468` ve `rules/suppression.py:408` fider kapılarının yeni `feeder_load_factor` alanını kullanması devredildi; bu dosyalara burada müdahale edilmedi. API/UI ve SCADA mevcut panel `load_factor` alanını kullandığı için ana bara oranını alıyor. Runtime yük geçmişi panel ölçeğinde; yük-adımı eşiği de bu ölçeğe göre gözden geçirilmeli (ana ajan bilgilendirildi). Simülatörün termal modellerindeki fider yük tanımı değiştirilmedi.

Son geniş kabul testleri ve değişikliklerin birlikte doğrulanması ana ajanın sorumluluğunda. Panel yükünün artık %100 üstüne çıkabilmesi doğrudur: örnek eski 0.82 fider yükü, toplam fider anması 3250 A olduğundan ana baranın yaklaşık %115 yüküne karşılık gelir.

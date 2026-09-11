# Alarm ve yük hesabı görevi

Kullanıcı inceleme bulgularını düzeltmemizi istedi. Bu görev mevcut Python prototipindeki dedektör/fusion çelişkisi ile bara/fider yük karışmasını düzeltir. Git deposu yok; commit yok. Doğrudan çalış, tekrar onay isteme. TDD kullan: yeni testleri mevcut kodda başarısız gör, sonra düzelt.

Sahip olduğun dosyalar: panogoz/detector/engine.py (yalnız yük/şiddet; ingestion, cadence dokunma), panogoz/rules/fusion.py, panogoz/contracts/live.py, tests/test_alarm_load_regression.py; gerekirse mevcut testlerde sadece ilgili fixture sözleşmesini güncelle (ana ajanla koordinasyon). Diğer dosyalara dokunma.

Gereksinimler:
- Dedektörün geçerli JointView.severity sonucu fusion tarafından anlık theta kullanılarak yeniden yükseltilmesin. Mutlak sıcaklık ve arc safety override korunsun. Elle oluşturulmuş JointView için default severity geçerli mi/yok mu ayrımı gerekiyorsa açık optional sentinel tasarla ve mevcut tüketicileri kontrol et; tercih dedektör sonucu taşıyan geçerli değere saygı, fallback yalnız karar yokken.
- Regresyon: IR-only C01-L1-PABUC, temp 45, theta 20, theta_min 3, theta_daily .5, drift teyidi yok: engine BILGI -> fusion BILGI. Geçerli BILGI/KRITIK kararları korunsun; 130 C sıcaklık ACIL'e yükseltsin.
- live.load_factor ana bara akımından hesaplanmalı (faz ortalaması / 2312); full rating ->1.0. Dengesiz fazlarda overload kanıtı en yüksek fazın /2312 oranını da görmeli (ayrı field veya mevcut observations). Mevcut per-feeder tahmini I/3250 ayrı ölçekte kalmalı: tüm kullanım yerlerini incele, pano normalize faktörünü fider theta/sensitivity kapısına körlemesine uygulama. SCADA LOAD_FACTOR ve UI ana bara oranını göstermeli.
- Mevcut testler ile default demo uyumlu olsun; fixture'ların eski theta fallback davranışını açıkça belirtmesi gerekiyorsa kapsamı raporla.

Testler: pytest yeni dosya; python -m tests.test_rules, python -m tests.test_detector (uzun sürebilir) ve ilgili acceptance modüllerini ana ajan finalde çalıştıracak. Ham sonuçları ve değişiklikleri docs/superpowers/plans/task-alarm-load-result.md içinde kaydet. Önce engine düzenlemelerini tamamla ve ana ajana haber ver; ardından testi sürdür ki ana ajan ingestion/cadence kısmını düzenleyebilsin.

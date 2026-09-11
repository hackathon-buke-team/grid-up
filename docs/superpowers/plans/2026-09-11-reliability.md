# PANO GÖZ güvenilirlik düzeltmeleri

Amaç: Kullanıcının onayladığı inceleme bulgularını mevcut demo yapısını koruyarak düzeltmek.

Tasarım: Dedektör bağlantı seviyesinin tek sahibi; bara ve fider yükleri ayrı. MQTT yayını PUBACK olmadan tamamlanmış sayılmaz; ağ geçidi onaysız mesajları SQLite kuyruğunda saklar. Tekrarlı/eski ölçümler canlı durumu geriye alamaz. Beklenen cihaz yayın aralığı zarf içinde taşınır. TimescaleDB ve saha dağıtımı, uygulanmadıkları ölçüde açıkça plan olarak belgelenir.

Alternatifler: Yalnız belge düzeltmesi gerçek hataları bırakır; altyapıyı tamamen yeniden yazmak gereksiz kapsam ekler. Mevcut bileşenlerin sözleşmelerini onarmak seçildi.

Bu klasör Git deposu değil; commit/worktree adımları uygulanamaz. Kaynakların değişiklik öncesi kopyası geçici klasörde saklanacak. Uygulama sırası:

- [ ] 1. Alarm kararı ve yük oranları: IR theta 20 K/günlük 0,5 K BILGI kalmalı; bara 2312 A yüzde 100, fider tahmini ayrı olmalı. Önce regresyon testleri, sonra engine/fusion/live değişiklikleri ve ilgili testler.
- [ ] 2. Sıra ve kadans: eski/tekrar mesaj güncel ölçümü ezmemeli; 900 s sensör normal aralıkta çevrimdışı olmamalı, kaçırılan süre sonunda çevrimdışı olmalı. Envelope/engine/gateway sözleşmesini testlerle düzelt.
- [ ] 3. MQTT: Paho ReasonCode başarılı/başarısız bağlantıları; bağlantı yok, PUBACK yok, olumlu ACK ve tekrar bağlantı; kalıcı kuyruk yeniden başlatma ve retain davranışı testleri. bus/gateway/store düzeltmeleri.
- [ ] 4. Negatif ve eşzamanlı arıza senaryolarını gerçek pipeline üzerinden test et; zorunlu kontrol atlanmasını başarısız kabul et. THD artışını aday olarak sınıflandır; tek başına yerel arızayı bastırmasın.
- [ ] 5. SQLite dışı DSN'yi açık hata ile reddet; demo Compose'u yerel erişime sınırla, gerçek üretim gibi sunma. README/docs/firmware açıklamalarını güncelle.
- [ ] 6. Yedi mevcut Python modülü, yeni regresyonlar, host C öztesti ve yerel API smoke testi. Ayrı kod incelemesi; bulguları düzelt ve sonuç/limitleri raporla.

Global kısıtlar: Gerçek SMS gönderilmeyecek; saha donanımına bağlanılmayacak; yeni TimescaleDB veya kimlik sistemi kurulmuş gibi iddia edilmeyecek. Mutlak sıcaklık ve ark bildirimleri korunacak. Kalıcı kuyruk broker onayını garanti eder; broker onayı son tüketicinin veritabanına yazmasıyla karıştırılmayacak.

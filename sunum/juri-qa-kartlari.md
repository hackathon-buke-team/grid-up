# K4 · 4.5 Jüri Soru-Cevap Kartları

> Her kart: olası soru → kısa, dürüst cevap → (varsa) nereye bakılacağı. Anlatı
> script'iyle çelişen hiçbir şey söyleme — özellikle "yapıldı" ile "planlanan"
> ayrımını koru (bkz. [`anlati-script.md`](anlati-script.md) §6).

## Ürün / metodoloji

**S: θ metriği neden sabit sıcaklık eşiğinden daha iyi?**
> Sabit eşik mevsim/yük etkisini ayıramaz — yazın gerçek arızayı yakalayamaz
> (zaten sıcak), kışın yanlış alarm üretir (soğukken düşük eşik bile aşılır).
> θ, kardeş fazların ortak ısınmasını (yük+mevsim) medyanla iptal edip geriye
> yalnızca fazlar-arası anormal farkı bırakıyor, bunu da yük karesine göre
> normalize ediyor.

**S: Yalnızca bir arıza modu mu simüle ettiniz?**
> Evet, şu an uçtan uca tam kanıtlanan tek senaryo gevşek cıvatalı bağlantı.
> Diğer 4 modun (aşırı yük, yoğuşma, nötr harmonik, ark) fiziksel modeli
> CLAUDE.md'de tarif edildi ama sentetik senaryo üretimi henüz kod olarak
> yazılmadı — bunu gizlemiyoruz, sıradaki iş paketi bu.

**S: 17 senaryo/7 arıza modu iddiası nereden geliyor?**
> O rakamlar projenin daha önceki (silinip sıfırdan yeniden yazılan) bir
> sürümüne ait plan belgesinden — CLAUDE.md'de bilerek "kod seviyesinde
> doğrulanmadı" diye işaretlendi. Şu anki kod tabanında henüz o kapsamda
> değiliz, tek doğrulanmış senaryo yukarıdaki.

**S: Düşük yükte (gece, hafif yük) sistem çalışır mı?**
> %40 anma akımının altında θ hesaplanmıyor (gürültü patlıyor) — bu bilinçli
> bir tasarım kararı, "veri yok" ile "arıza yok" birbirine karıştırılmıyor.
> Bu bantta izleme METİN olarak "yetersiz veri" diye işaretleniyor, sahte
> "normal" denmiyor.

## Mühendislik / gerçeklik

**S: Bu gerçekten çalışıyor mu, yoksa hepsi simülasyon mu?**
> Akış gerçek: gerçek CT sensör verisi (organizatörün verdiği ham Excel),
> gerçek Telegram mesajı (iki kez gönderildi), gerçek Modbus TCP round-trip
> (pymodbus client), gerçek MQTT broker'a karşı 5 senaryo (bağlanma/
> reconnect/restart/replay/dedup, ayrı bir OS process'i). Sentetik olan
> yalnızca üç fazlı ısıl model + arıza enjeksiyonu — organizatörün kendisi
> de "Sıcaklık_Nem"/"ARC"/"PD" için gerçek veri vermedi, kendi fizik
> modelimizden üretilmesi bekleniyordu (bkz. CLAUDE.md §4).

**S: Neden Eclipse Mosquitto değil de amqtt kullandınız?**
> Denedik — bu geliştirme makinesinde resmi Windows installer'ı admin/UAC
> istiyor ve iki ayrı gerçek denemeyle (biri 600 saniye donup watchdog'la
> öldürüldü, diğeri Windows'un UAC'yi otomatik reddettiğini gösteren anlık
> bir hata verdi) bunun bu ortamda mümkün olmadığı kanıtlandı. amqtt gerçek
> bir MQTT 3.1.1 implementasyonu, mock değil — ayrı bir process, gerçek
> TCP/gerçek protokol. `mqtt_bus.py` yalnız MQTT 3.1.1'e bağlı olduğu için
> admin erişimi olan bir ortamda kod değişmeden gerçek Mosquitto'ya
> geçilebilir. Detay: `docs/01-MIMARI.md` §2.

**S: Modbus/SCADA entegrasyonu gerçek bir RTU'ya mı bağlanıyor?**
> Hayır, yarışma şartnamesi bunu istemiyor — yalnızca haritalamanın (ICD)
> gösterilmesi yeterli (bkz. CLAUDE.md §1). Bizim tarafımız gerçek: gerçek
> bir Modbus TCP slave çalıştırıyoruz, gerçek bir `pymodbus` client'la
> round-trip test edilmiş, register haritası dokümante (`docs/modbus-
> haritalama.md`).

**S: Ölçek nasıl? 100+ pano hedefine ne kadar yakınsınız?**
> Şu an ölçek testi yapılmadı (CLAUDE.md P2, K2 2.4 — 250→500→1000 pano
> kademeli yük testi henüz kurulmadı). Mimari (SQLite outbox, sabit register
> bloğu/bağlantı, bağımsız uç düğümler) ölçeklenebilir tasarlandı ama bunu
> henüz sayıyla kanıtlamadık — dürüst açık madde.

## Donanım

**S: Fiziksel bir prototip var mı?**
> Yok, ve yarışma şartnamesi de istemiyor (CLAUDE.md §1: "fiziksel prototip
> istenmiyor... kart lehimlenmeyecek"). Elimizde gerçek, ERC/DRC temiz KiCad
> tasarım dosyaları (şematik + PCB yerleşimi + 3D render) var — üretime
> hazır tasarım seviyesinde.

**S: Neden STM32WLE5CC seçildi?**
> Entegre sub-GHz radyo + düşük güç, pil ömrü gerektiren uç düğümler için
> (TC/IR-PD) tek çipte MCU+radyo. Gateway kartı ayrıca kablolu Ethernet
> (W5500) kullanıyor çünkü sabit/mains-beslemeli, güvenilirlik önceliği var.

**S: HFCT/PD sensörü Modbus'tan mı okunuyor?**
> Hayır — HFCT30/50 tamamen pasif/analog bir endüktif sensör, RF ön-uç +
> yüksek hızlı örnekleme gerektiriyor. IR/PD düğümü şemasında bunun için
> ayrı bir analog zincir (`RF_Frontend`, bant geçiren filtre+LNA+log-amp
> zarf dedektörü) var, bilinçli bir basitleştirme olarak dokümante edildi
> (`docs/03-ELEKTRONIK-DOKUMANTASYON.md` §5).

## Zor/tuzak sorular

**S: Bu kodun ne kadarını siz mi yazdınız, ne kadarını AI mı?**
> Proje Claude Code ile birlikte, solo geliştirildi — kod üretimi AI
> destekli ama her adım (özellikle KiCad/PCB gibi doğrulanması zor
> çıktılar) ham dosya üzerinden bizzat kontrol edildi. İki kez, bir
> subagent'ın "kontrol ettim" dediği ama gerçekte hatalı olduğu çıktılar
> (bkz. proje notları) böyle yakalandı — süreç şeffaf.

**S: Yarın gerçek bir panoya kurulsa ne olur?**
> Olmaz henüz — bu bir tasarım/yazılım kanıtı, saha kurulumu (gerçek
> sensör kalibrasyonu, uzun-vadeli veri toplama, gerçek arıza dağılımı
> ile eşik ayarı) ayrı bir aşama. Şu anki θ eşikleri (15/30/60) ilk plan
> değeri, sahada gerçek veriyle ayarlanması gerekir.

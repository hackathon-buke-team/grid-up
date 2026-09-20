# PANO GÖZ / uç düğüm firmware / B1

20.09.2026. C99 çekirdek ve gerçek STM32WLE5CC TC portu. Mimari repo ile uyumludur; cihaz/kanal sözleşmeleri değiştirilmez. Eski yalnız-host port, 13,1 yıllık enerji ve uygulanmış OTA varsayımlarının yerine bu sürüm geçer.

## İki çalıştırma yolu

| Yol | HAL / araç | Ne kanıtlar |
|---|---|---|
| Host | `node/host_sim.c`, GCC/MinGW | Deterministik sanal sensör, durum makinesi, theta/PRPD/kadans/enerji öz testi |
| STM32WLE5CC | `node/port/stm32wle5`, Arm GNU 14.3 | Gerçek ST HAL/CMSIS ile ARM ELF/BIN/MAP; fiziksel çalıştırma yapılmadı |

Aynı `main.c`, `theta_edge.c`, `prpd_bin.c`, `radio.c`, `power.c` çekirdeği kullanılır. Çekirdek tamsayı/sabit noktalıdır; heap/libm bağımlılığı yoktur. Hedef HAL'de basit memcpy/memset uygulamaları vardır. Vendor kodundaki kullanılmayan işlevler link sırasında atılır.

## Derleme

```sh
cd firmware/node
make host
./panogoz_node --selftest
./panogoz_node --scenario energy
./panogoz_node --scenario prpd
make target
```

ARM zinciri PATH'te değilse `ARM_GCC_BIN`, Python için `PYTHON` ayarlanır. Taşınabilir alternatif, repo kökünden:

```sh
python firmware/node/build_target.py --toolchain /path/to/arm/bin --node 4
python -m pytest -q firmware/tests
```

`--node 1..6` TC kimliğini seçer. Derleyici bulunamazsa komut **hata verir**, hedef derlemesini başarılıymış gibi atlamaz. Ürünler `node/build/stm32wle5/` içindedir; son teslimin kopyası `hardware/B1/evidence/target/` altındadır. Gerçek sonuç için `memory_report.json` ve `.map` birlikte okunur. 4 KiB yığın RAM rezervine dahildir. Dosyalar SWD ile 0x08000000 başlangıç adresine yöneliktir; kart yokken programlama yapılmaz.

## Çalışma mantığı

`COLD_START → SELF_TEST → PROVISION → SAMPLE → AGGREGATE → TX → SLEEP` ana döngüsüne `FAULT`, `DE_ENERGISED`, `LOW_BATTERY` dalları eşlik eder. [Akış diyagramı](AKIS-DIYAGRAMI.md).

TC-01..03 C06-L1/L2/L3, TC-04..06 C07-L1/L2/L3 pabuçlarını eşler. Önceki TC-04→C06-L1 hatası giderildi. Geçersiz TMP veya negatif/hatalı CT örneği SENSOR_FAULT oluşturur; sıfır akım gibi değerlendirilerek DE_ENERGISED'e sokulmaz. Geçerli ölçüm geri geldiğinde hata bayrağı enerjisiz dala geçerken de temizlenir. Geçerli sıfır akım ve faz yokluğu DE_ENERGISED için gereklidir; fiziksel açık CT'nin geçerli bias vermesi ek teşhis gerektirir.

Ham sıcaklık 1/128°C, akım mA'dir. Kardeş fazlarla yük-normalize theta hesaplanır; geçerli kardeş/yük bulunmadığında değer yokluğu korunur. Uç theta kadansı seçer, sunucu yetkili anomali kararını verir. Kadans 900/60/10 saniye; yumuşak olaylar için iki yukarı/dört aşağı histerezisi, sert olayda hızlı kadans vardır. Alarm karar algoritması veya kanal kayıtları K1 kapsamında değiştirilmedi.

Gönderim önce FRAM'e kaydedilir, ACK sonrasında kuyruktan düşer. Hedef FRAM sürücüsü yazdıktan sonra geri okur. RTC ile STOP2 uykusu 2 saniyelik veya daha kısa aralıklara bölünerek IWDG beslenir; son kısmi aralık aktif beklemez. Gerçek ADC, I²C, SPI ve sub-GHz işlemleri zaman aşımı kontrolü içerir.

## Enerji / PRPD / OTA sınırları

B1 TC bekleme bütçesi 50 µA: OPA333, bias, FRAM standby ve RTC/IWDG payı. 1,2 Ah ER14250, %85 kullanılabilir kapasite, yıllık %1 özdeşarj ve %97/%2,5/%0,5 kadans karmasıyla **721 gün yaklaşık 2 yıl** hesaplanır. Bu bir ölçüm veya garanti değildir. IR/PD bu pil hesabını kullanamaz; özellikle 5 V PD RF zinciri için yaklaşık 0,35 A pil tepe bütçesi vardır. Ayrıntı [docs/02](../docs/02-DONANIM-TASARIMI.md).

PRPD histogram/binleme ve paketleme hostta çalışır. B1 PD AD8318 çıkışı negatif eğimlidir; pozitif genlik dönüşümü, pC izlenebilir kalibrasyon ve gerçek faz girişi PD hedef sürücüsünde henüz uygulanmadı. TC akım fazı, şebeke gerilim fazı değildir. Nominal 400 V gerilim tek başına kısmi deşarjı dışlamak için yeterli değildir. Host örüntüsü fiziksel ölçüm diye sunulmaz.

Host OTA durum makinesi senaryosu vardır. **TC hedefinde OTA kapalıdır:** imzalı bootloader yok; flash yazma/silme HAL girişimleri başarısız döner. Üretim OTA'sı, imza/anti-rollback/anahtar koruması ve güç-kesilme testleri ayrı geliştirmedir.

## K2 ile uyum

`tools/radio_bridge.py` 35 bayt C radyo çerçevesini mevcut `Envelope` biçimine dönüştürür. `node/tests/wire_fixtures.c` vektör kaynağı; CRC/uzunluk/sürüm/kimlik/kadans ve geçersiz ölçüm testleri `tests/test_radio_bridge.py` altında. `forward()` zarfı `Gateway.ingest_node_envelope()` ile kalıcı outbox/QoS1 yoluna verir; seq/boot/kadans değişmez. Kuyruk yazımı, yeniden başlama, PUBACK ve hata halinde radyo tesliminin reddi `tests/test_b1_integration.py` ile doğrulanır. Fiziksel GW alıcısı ve RF ACK sürücüsü henüz yoktur; [hedef port README](node/port/stm32wle5/README.md).

## Kanıtlar

`hardware/B1/evidence/`: son tam pytest günlüğü, host öz testi (0 hata), C kimlik/CT/enerji regresyonu, enerji/PRPD senaryoları, ARM MAP/BIN/ELF. Ayrıca başarısız negatif-kontrol koşuları saklanır. KiCad/STEP tasarım ve elektronik bağlantılar [hardware/README.md](../hardware/README.md) üzerinden açılır. PANO GÖZ bir koruma rölesi değildir.

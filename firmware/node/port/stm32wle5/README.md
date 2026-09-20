# STM32WLE5CC / TC B1 hedef portu

`make target`, `build_target.py` üzerinden gerçek ARM ELF/BIN/MAP üretir. ST HAL ve CMSIS kaynakları lisansları ve sürüm kayıtlarıyla `vendor/` altında sabitlenmiştir; sahte HAL veya host derlemesi değildir.

```powershell
python firmware/node/build_target.py --toolchain '<Arm GNU 14.3.Rel1>/bin' --node 4
# veya ARM_GCC_BIN ve Python PATH tanımlıysa firmware/node içinde:
make target
```

`--node 1..6`, sırasıyla TC-01..06 / C06-L1..L3 ve C07-L1..L3 pabuç kimliğini seçer. Varsayılan TC-04'tür. SWD başlangıç adresi `0x08000000`; 16 KiB kalıcı ayar alanı için ayrılmıştır. 88 KiB uygulama bütçesi linker assert ile korunur. 4 KiB yığın rezervi RAM raporuna dahildir. Tüm varyantlarda aynı kod ve çevre birimi bağlantıları kullanılır.

## Hedefte gerçekleştirilenler

- TMP117 I²C tek ölçümü, data-ready ve zaman aşımı; hata değeri geçerli ölçüm gibi yayımlanmaz.
- CT: VREFINT ile ADC besleme hesabı, 20 ms/64 örnek RMS, DC bias çıkarma, doygunluk/hata kontrolü; 3000:1 ve 5,1 ohm. Açık CT'nin ADC'yi geçerli orta noktada bırakması yazılımla kesin ayırt edilemez; saha testinde ayrıca kontrol edilir.
- 68 ohm / 10 ms fiziksel pil yükü, anahtarlanan bölücü; SPI FRAM yazımı ve geri okuma doğrulaması.
- RTC/LSE, STOP2, IWDG. Uykunun son kısmi aralığı da RTC ile beklenir; 2 saniyeye kadar gereksiz aktif bekleme giderildi.
- Dahili sub-GHz LoRa: 868,1 MHz, SF7/BW125/CR4/5, özel senkron 0x1424, +14 dBm LP; gerçek TX/RX komutları ve CRC/timeout kontrolü. Bu ayarlar RF/spektrum uygunluk sertifikası değildir.

`board.h` ile `hardware/B1/TC/pinmap.csv` eşlenir. PB4, iki transistörlü anahtara aktif-yüksek DIV_EN verir. RF CTRL ve CTRL_N tamamlayıcıdır. PA8 CT akımının fazıdır; PD için gerilim-faz referansı gibi yorumlanmaz.

## Kapsam sınırı

Derleme, gerçek donanım üzerinde çalıştırma değildir. TC'de hava sensörü ve PD kanalı bulunmadığı için HAL bunlara gerçek dışı veri üretmez. IR/PD sürücüleri ve H563 GW uygulaması bu hedefe dahil değildir. OTA kapalıdır; flash yazma girişimleri hata döndürür, imzasız yazılım yüklenmez. Bootloader/anahtar yönetimi ve gateway OTA akışı gelecekte ayrıca tamamlanmalıdır.

## K2'ye radyo devri

`firmware/tools/radio_bridge.py`, gerçek C `pg_wire_encode` vektörlerini mevcut Python `Envelope` biçimine çevirir. CRC, uzunluk, sürüm, cihaz ve kadans denetlenir; geçersiz ölçüm sağlıklı veri gibi eklenmez. Zaman senkron değilse alıcı zamanı açık metadata ile kullanılır. Host senaryoları fiziksel sensör kanıtı sayılmaz.

```python
from firmware.tools.radio_bridge import decode
envelope = decode(packet_bytes, site='AYDIN', panel='SOKE-14', received_at=unix_seconds)
topic, payload = envelope.topic, envelope.to_json()
```

`forward(packet_bytes, gateway, received_at=unix_seconds)` artık `Gateway.ingest_node_envelope` üzerinden mevcut kalıcı outbox/QoS1 yoluna bağlıdır. `gateway`, disk üzerindeki `Store` ile kurulmalıdır; kalıcı kuyruk yoksa, doluysa veya yazılamazsa hata verilir. Radyo alıcısı yalnız `forward` başarıyla döndüğünde teslim alma ACK'i gönderebilir. Node seq/boot, 900/60/10 s kadansı ve kanal adları korunur; tekrarlar sunucu tarafından aynı kimlikle ayıklanır. Yeniden başlama ve PUBACK bekleme testlidir. Gerçek SPI/UART alıcı sürücüsü ve fiziksel radyo ACK üretimi henüz yoktur.

Testler: `python -m pytest -q firmware/tests`; C `node/tests/k1_regression.c`; `panogoz_node --selftest`; `--scenario energy`. Enerji sonucu B1 tahminidir: 50 µA bekleme bütçesi, görev karmasında yaklaşık 2 yıl; gerçek akım ölçümü yoktur.

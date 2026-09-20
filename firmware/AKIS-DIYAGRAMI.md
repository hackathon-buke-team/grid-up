# B1 uç düğüm akışları

Bu diyagramlar TC B1 hedefini ve mevcut tamsayı çekirdeğini özetler. IR/PD/GW uygulama portları tamamlanmış değildir; host senaryoları donanım çalıştırma kanıtı sayılmaz.

## Ölçüm / yayın

```mermaid
flowchart TD
 A[Başlat / kimlik / ST HAL] --> B[Öz test ve FRAM kaydı]
 B -->|hata| F[FAULT sağlık bildirimi]
 B -->|geçerli| C[Provision / RTC ve kalıcı durum]
 C --> S[TMP117 + CT RMS + pil örneği]
 S --> V{Sıcaklık ve CT geçerli mi?}
 V -->|hayır| E[SENSOR_FAULT / sağlıklı ölçüm yok]
 V -->|evet| Z[Eski SENSOR_FAULT bayrağını temizle]
 Z --> D{Faz yok ve akım düşük mü?}
 D -->|evet| DE[DE_ENERGISED / yavaş sağlık]
 D -->|hayır| T[Kardeş/yük uygunsa theta ve eğim]
 E --> P[Pil durumu ve kadans seçimi]
 T --> P
 P --> L[Özet / sıra numarası / CRC]
 L --> Q[Önce FRAM kuyruğuna yaz ve geri oku]
 Q --> R[LoRa TX + ACK alım penceresi]
 R --> K{ACK geldi mi?}
 K -->|evet| X[Kuyruktan onaylanan öğeyi düş]
 K -->|hayır| O[Kuyrukta tut / sonraki çevrime bırak]
 X --> U[RTC STOP2 / IWDG için en fazla 2 saniyelik aralıklar]
 O --> U
 DE --> U
 F --> U
 U --> S
```

## K1 / K2 veri sınırı

```mermaid
flowchart LR
 A[TMP117 ve CT] --> B[TC C99 / 35 bayt çerçeve]
 B --> C[868 MHz LoRa]
 C -. Gerçek alıcı sürücüsü gerekli .-> D[GW donanımı]
 D -. K2 entegrasyonu .-> E[K1 radio_bridge.decode]
 E --> F[Mevcut Envelope / seq / boot / kadans]
 F -. K2 kalıcı outbox .-> G[MQTT / sunucu / SCADA]
 H[C wire_fixtures / host] --> E
```

Düz oklar veri biçimi/yerel işlevi, kesik oklar tamamlanmamış gerçek donanım entegrasyonunu gösterir. Ortak `panogoz/contracts/` değiştirilmez.

## Hedef yazılım teslimi

```mermaid
flowchart LR
 A[C99 çekirdek] --> L[arm-none-eabi-gcc / Cortex-M4]
 B[ST HAL + CMSIS + startup + linker] --> L
 L --> E[ELF / BIN / MAP]
 E --> R[Flash / RAM / uyarı / sembol raporu]
 E -. Kart geldiğinde .-> S[SWD / fiziksel ölçüm ve RF testleri]
```

Hedef 0x08000000'den başlar. OTA durum makinesi yalnız hostta benzetilir; TC B1'de imzalı bootloader bulunmadığından hedef flash güncellemesi kapalıdır.

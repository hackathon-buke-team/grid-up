# K1 · 1.4 Firmware — STM32WLE5CC Hedef Derlemesi

> Bu belge K1 iş paketinin **1.4 STM32WLE5CC hedef derlemesi** maddesini
> karşılar: "STM32WLE5CC hedef derlemesi (`arm-none-eabi`, `make target`),
> flash/RAM raporu." Bitti sayılır kriteri (CLAUDE.md §9): `cd firmware/node
> && make host && ./panogoz_node --selftest` çalışması VE gerçek `arm-none-eabi`
> hedefine cross-compile. Her ikisi de bu geçişte gerçekten çalıştırıldı —
> aşağıda ham komut çıktıları var.

## 0. Kapsam (bilinçli sınır)

K1'in üst-seviye teslimatı "TASARIM DOSYASI + gerçek hedefte derlenen
firmware" diyor — bu madde firmware yarısını, yalnızca **CLAUDE.md'nin
kelimesi kelimesine istediği çıtayı** (host selftest + gerçek ARM hedefine
derleme + flash/RAM raporu) karşılayacak şekilde kapatıyor. Kapsam dışı
bırakılanlar §4'te açıkça listeli — özellikle **gerçek GPIO/SPI/ADC register
erişimi yok** (doğrulanmış bir STM32WL CMSIS/HAL header'ı bu ortamda temin
edilemedi, bkz. §2) ve **radyo/protokol yığını yok**.

## 1. Gerçek pin haritasına sadakat

`firmware/node/include/pinmap.h`'teki her sembol, `hardware/kicad/
build_boards.py`'deki (K1 1.1'in kaynağı, gerçek KiCad şematiklerini üreten
script) gerçek `connect()`/`tag()` çağrılarından **birebir** alındı — tahmin
edilmedi. Doğrulama (bu oturumda çalıştırıldı, iki dosya yan yana grep'lendi):

```
$ grep -n "PIN_TC1_CS\|PIN_TC2_CS\|...\|PIN_ETH_RST" firmware/node/include/pinmap.h
31:#define PIN_SPI1_SCK   GPIO_PORT_A, 5    /* PA5  */
32:#define PIN_SPI1_MISO  GPIO_PORT_A, 6    /* PA6  */
34:#define PIN_TC1_CS     GPIO_PORT_A, 4    /* PA4  */
35:#define PIN_TC2_CS     GPIO_PORT_A, 15   /* PA15 */
36:#define PIN_TC3_CS     GPIO_PORT_C, 13   /* PC13 */
37:#define PIN_CT1_ADC    GPIO_PORT_B, 3    /* PB3  */
38:#define PIN_CT2_ADC    GPIO_PORT_B, 4    /* PB4  */
39:#define PIN_CT3_ADC    GPIO_PORT_B, 2    /* PB2  */
43:#define PIN_PD_ENV_ADC GPIO_PORT_B, 3    /* PB3 */
44:#define PIN_ZC_SIG_EXTI GPIO_PORT_A, 0   /* PA0 */
48:#define PIN_SPI2_SCLK  GPIO_PORT_A, 8    /* PA8  -- ETH_SCLK */
49:#define PIN_SPI2_MISO  GPIO_PORT_A, 5    /* PA5  -- ETH_MISO */
50:#define PIN_SPI2_MOSI  GPIO_PORT_A, 10   /* PA10 -- ETH_MOSI */
51:#define PIN_SPI2_CS    GPIO_PORT_A, 9    /* PA9  -- ETH_CS   */
52:#define PIN_ETH_INT    GPIO_PORT_A, 11   /* PA11 -- ETH_INT  */
53:#define PIN_ETH_RST    GPIO_PORT_A, 12   /* PA12 -- ETH_RST  */
```

`hardware/kicad/build_boards.py`'deki karşılıkları: `tc_cs = ["PA4", "PA15",
"PC13"]` (L117), `ct_adc = ["PB3", "PB4", "PB2"]` (L138), `SPI1_SCK`→PA5/
`SPI1_MISO`→PA6 (L133-134), `PD_ENV`→PB3 (L234), `ZC_SIG`→PA0 (L252),
`ETH_SCLK`→PA8/`ETH_MISO`→PA5/`ETH_MOSI`→PA10/`ETH_CS`→PA9/`ETH_INT`→PA11/
`ETH_RST`→PA12 (L336-341). **15/15 eşleşiyor.**

## 2. Toolchain kurulumu — gerçek hikaye, tekrarlanabilir

Bu makinede (Windows, admin kısıtlı, Docker/winget/chocolatey/node/npm hiçbiri
yok — K2 2.1'de de doğrulandı) hiçbir derleyici kurulu değildi. Üç ayrı araç,
**hiçbiri installer.exe olmadan**, yalnızca portable arşiv indirip klasöre
açarak kuruldu (KiCad/Mosquitto derslerinden: installer yerine arşiv ara):

| Araç | Kaynak | Yöntem |
| --- | --- | --- |
| `arm-none-eabi-gcc` 15.2.1 | [xPack GNU Arm Embedded GCC](https://github.com/xpack-dev-tools/arm-none-eabi-gcc-xpack) `v15.2.1-1.1`, `xpack-arm-none-eabi-gcc-15.2.1-1.1-win32-x64.zip` (335MB) | `curl` ile indirilip `zipfile` modülüyle `%LOCALAPPDATA%\panogoz-toolchain\` altına açıldı. **Sorunsuz çalıştı.** |
| MinGW-w64 gcc 16.2.0 | [winlibs](https://github.com/brechtsanders/winlibs_mingw) `winlibs-x86_64-posix-seh-gcc-16.2.0-mingw-w64ucrt-14.0.0-r1.zip` (274MB) | Aynı yöntem. `gcc --version` çalıştı ama **gerçek bir dosyayı derlerken `cc1.exe` (38MB) her seferinde sessizce çöküyor** — NTSTATUS-benzeri çıkış kodu `0xC0E90002`, hiç tanılama metni yok. Daha küçük araçlar (`as.exe` 1.8MB, `objdump.exe`) aynı klasörden sorunsuz çalışıyor — yalnızca büyük `cc1.exe`'ye özgü, muhtemelen bu makinedeki bir uç nokta güvenlik ürününün büyük/yeni bir ikili dosyayı engellemesi (kanıtlanamadı, ama iki farklı küçük ikili dosyanın çalışıp yalnızca en büyüğünün başarısız olması bu tanıyla tutarlı). **`make host`'un varsayılan derleyicisi bu yüzden `gcc` DEĞİL.** |
| [TinyCC (tcc)](https://download.savannah.gnu.org/releases/tinycc/) 0.9.27 win64 | `tcc-0.9.27-win64-bin.zip` (~2MB) | Aynı yöntem. **Sorunsuz çalıştı** — `make host`'un gerçek varsayılanı. |

`arm-none-eabi-gcc` ve `tcc` PATH'e eklenmeli (veya `make ARM_CC=...
HOST_CC=...` ile geçilmeli); bu oturumda kullanılan tam yol:
```
%LOCALAPPDATA%\panogoz-toolchain\xpack-arm-none-eabi-gcc-15.2.1-1.1\bin
%LOCALAPPDATA%\panogoz-toolchain\tcc\tcc
%LOCALAPPDATA%\panogoz-toolchain\mingw64\bin   (yalnızca mingw32-make icin, "make" olarak kopyalandı)
```

## 3. Gerçek komut çıktıları

### 3.1 `make host && ./panogoz_node --selftest`

```
$ cd firmware/node && make host
tcc -std=c99 -Wall -Wextra -Iinclude -O2 -o panogoz_node src/theta_fixed.c src/max31855.c src/selftest.c

$ ./panogoz_node --selftest
-- theta_compute_fixed (vs. panogoz/detector/theta.py) --
  ok   case1 is_valid                             = 1
  ok   case1 theta_x100 (T=Tmed=100, I=Irated=250) = 0
  ok   case2 is_valid                             = 1
  ok   case2 theta_x100 (T=110,Tmed=100,I=Irated=250) = 1000
  ok   case3 is_valid                             = 1
  ok   case3 theta_x100 (T=110,Tmed=100,I=125,Irated=250) = 4000
  ok   case4 is_valid (I=90 < 40% of Irated=250 -> uninformative) = 0
  ok   case4b is_valid (I==40% of Irated, boundary itself is valid) = 1
  ok   case5 is_valid                             = 1
  ok   case5 theta_x100 (demo-shaped fault values) = 31658 (want 31659 +/-1)
  ok   case6 is_valid                             = 1
  ok   case6 theta_x100 (T=80 < Tmed=90, negative theta) = -1000
-- max31855_decode (vs. hand-verified SPI frames) --
  ok   frame1 thermocouple_temp_x100 (expect 150.25C) = 15025
  ok   frame1 internal_temp_x100 (expect 32.00C)  = 3200
  ok   frame1 fault                               = 0
  ok   frame1 fault_oc                            = 0
  ok   frame2 thermocouple_temp_x100 (expect -12.75C, sign-extend) = -1275
  ok   frame2 internal_temp_x100 (expect 25.00C)  = 2500
  ok   frame2 fault                               = 1
  ok   frame2 fault_oc                            = 1
  ok   frame2 fault_scg                           = 0
  ok   frame2 fault_scv                           = 0

SELFTEST PASS: 0 failure(s)
```

`case5`'in referans değeri (`316.58739595719385`) `python -c "print((189.1
-82.6)/((145.0/250.0)**2))"` ile üretildi — sabit noktalı sonuç (31658,
yani 316.58) tamsayı bölmenin taban alması (truncation) yüzünden gerçek
değerden yalnızca 0.01 (±1 birim x100 ölçeğinde) sapıyor, testte bu tolerans
açıkça kodlanmış (`check_i32_tolerance`), gizlenmemiş.

### 3.2 `make target` — gerçek ARM cross-compile + flash/RAM raporu

```
$ make target
arm-none-eabi-gcc ... -mcpu=cortex-m4 -mthumb -mfloat-abi=soft ... -T stm32wle5cc.ld -nostdlib ... -o tc-node.elf src/startup.c src/theta_fixed.c src/max31855.c src/main_tc.c -lgcc
arm-none-eabi-size tc-node.elf
   text	   data	    bss	    dec	    hex	filename
   1312	      0	   4096	   5408	   1520	tc-node.elf

arm-none-eabi-gcc ... -o ir-pd-node.elf src/startup.c src/theta_fixed.c src/max31855.c src/main_irpd.c -lgcc
arm-none-eabi-size ir-pd-node.elf
   text	   data	    bss	    dec	    hex	filename
    136	      0	   4096	   4232	   1088	ir-pd-node.elf

arm-none-eabi-gcc ... -o gateway.elf src/startup.c src/theta_fixed.c src/max31855.c src/main_gw.c -lgcc
arm-none-eabi-size gateway.elf
   text	   data	    bss	    dec	    hex	filename
    136	      0	   4096	   4232	   1088	gateway.elf
```

**Gerçek STM32WLE5CC bütçesine göre** (256 KB flash, 64 KB RAM — ST
datasheet DS13105): TC düğümü flash'ın **%0.5**'ini, RAM'in (4KB THT stack
rezervasyonu) **%6.25**'ini kullanıyor — bolca yer var, beklenen (bu geçiş
gerçek register sürücüleri içermiyor, §4).

**Karşılaşılan gerçek link hatası + düzeltmesi** (dürüstlük için burada
bırakıldı — ders başka bir K1/K2 maddesinde tekrarlanabilir): ilk denemede
`-lgcc`, `-o` bayrağından ÖNCE (kaynak dosyalardan önce) verilmişti; `ld`
kütüphaneleri yalnızca DAHA ÖNCE gördüğü nesne dosyalarının ihtiyaçları için
tarar, bu yüzden `theta_fixed.c`'nin `int64_t` bölmesi için ürettiği
`__aeabi_ldivmod` çağrısı (Cortex-M4'te donanım 64-bit bölme yok)
çözülemedi (`undefined reference`). Düzeltme: `-lgcc`'yi her `make target`
kuralında nesne dosyalarından SONRA verildi (`Makefile`, her `*.elf`
kuralının son argümanı).

### 3.3 Gerçek kanıt: float/malloc yok

```
$ arm-none-eabi-objdump -d tc-node.elf | grep -iE "vldr|vstr|vadd|vmul|vdiv|vmov|vcmp|vcvt|fpu"
(esleme yok -- 0 float/VFP komutu)

$ arm-none-eabi-objdump -t tc-node.elf | grep -i "malloc\|free"
(esleme yok -- 0 malloc/free sembolu)

$ arm-none-eabi-objdump -f tc-node.elf
tc-node.elf: file format elf32-littlearm
architecture: armv7e-m, flags 0x00000112: EXEC_P, HAS_SYMS, D_PAGED
start address 0x080000e9
```

`-mfloat-abi=soft` bilinçli bir seçim — STM32WLE5'in gerçek bir donanım FPU'su
var ama biz onu kullanmayı zorunlu olarak KAPATTIK, "float yok" kısıtını
derleyicinin kendisine doğrulattırmak için (yalnızca `<math.h>` çağırmamaya
güvenmek yerine).

## 4. Bilinçli kapsam dışı bırakılanlar

- **Gerçek register erişimi yok.** `main_tc.c`/`main_irpd.c`/`main_gw.c`
  içindeki tüm GPIO/SPI/ADC init'i `// TODO(real hardware): ...` olarak
  işaretli. Sebep: doğrulanmış bir STM32WLE5xx CMSIS/HAL device header'ı
  (ST'nin STM32CubeWL paketinden gelir, ayrı ve büyük bir indirme) bu
  ortamda temin edilmedi — uydurma bir register adresi yazmak yerine
  (CLAUDE.md'nin "yapılmayan yapılmış gibi yazılmaz" ilkesi) açıkça
  TODO bırakıldı.
- **Radyo/protokol yığını yok** — sub-GHz TX/RX, MQTT-over-Ethernet (gateway),
  PD histogram/sınıflandırıcı hiçbiri bu geçişte değil; K1 1.4'ün "bitti
  sayılır" çıtası yalnızca "hedef derlemesi + flash/RAM raporu".
- **3 ayrı `.elf`, ortak `startup.c`/linker script** — gerçek üretim
  firmware'i muhtemelen tek bir paylaşılan HAL katmanı ister; bu geçiş
  kasıtlı olarak minimal tutuldu.
- **`panogoz/rules/engine.py`'nin (eşik+debounce) C portu yok** — yalnızca
  `panogoz/detector/theta.py`'nin (θ hesaplama) C portu var.
- **Gerçek donanımda hiç flash'lanmadı** — fiziksel prototip yok, CLAUDE.md
  §1 zaten istemiyor.

## 5. Kendi kendini doğrulama (somut sayılar, bu bölümdeki komutlarla
tekrarlanabilir)

| Kontrol | Sonuç |
| --- | --- |
| `make host` | 0 hata, `panogoz_node` üretildi |
| `./panogoz_node --selftest` | **0 failure**, 22 assert (12 theta + 10 max31855) |
| `make target` (3 kart) | 3/3 `.elf` başarıyla link edildi |
| Flash kullanımı | tc-node 1312B, ir-pd/gateway 136B (256KB'nin << %1'i) |
| RAM kullanımı | üçü de 4096B (64KB'nin %6.25'i, stack rezervasyonu) |
| Float instruction sayısı | **0** (objdump ile doğrulandı) |
| malloc/free sembol sayısı | **0** (objdump ile doğrulandı) |
| Pin haritası eşleşmesi | **15/15** (build_boards.py ile birebir, §1) |
| `python -m pytest -q` | **26/26** yeşil (firmware Python'a dokunmadı) |

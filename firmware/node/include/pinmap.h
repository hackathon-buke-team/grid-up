/* pinmap.h -- real GPIO pin assignments, mirrored from the KiCad schematic
 * generator (hardware/kicad/build_boards.py), NOT re-derived/guessed here.
 * Every symbolic name below corresponds 1:1 to a `connect(s, mcu, "<pin>",
 * "<net>")` or `tag(b, u1, MCU, "<pin>", "<net>")` call in that file (and its
 * PCB counterpart, hardware/kicad/build_pcbs.py) -- see the exact grep in
 * docs/07-FIRMWARE.md Sec.1 for the line-by-line cross-check.
 *
 * These are PORT/PIN identifiers, not register addresses -- this firmware
 * pass does not drive real GPIO/SPI/ADC peripherals (no verified STM32WL
 * CMSIS/HAL device header was available in this environment; see
 * docs/07-FIRMWARE.md Sec.4 "Kapsam disi birakilanlar"). Each symbol is the
 * STM32 pin name silkscreened on the real schematic; PORT_x/PIN_x split out
 * for whichever peripheral-init code fills in the TODOs in main_*.c.
 */
#ifndef PANOGOZ_PINMAP_H
#define PANOGOZ_PINMAP_H

#define GPIO_PORT_A 0
#define GPIO_PORT_B 1
#define GPIO_PORT_C 2

/* ---- Common to all 3 boards (hardware/kicad/{tc-node,ir-pd-node,gateway}) ---- */
#define PIN_SWDIO   GPIO_PORT_A, 13   /* PA13 */
#define PIN_SWCLK   GPIO_PORT_A, 14   /* PA14 */
/* RFO_HP (radio TX into the 2.2pF match network) is an internal MCU radio
 * pin, not a GPIO -- no PIN_* symbol here; out of scope, see docs/07 Sec.4. */

/* ---- TC node (hardware/kicad/tc-node, x6/pano) -----------------------------
 * 3x MAX31855KASA on shared SPI1 (SCK/MISO), each with its own CS; 3x
 * clip-on CT interface on individual ADC-capable pins. */
#define PIN_SPI1_SCK   GPIO_PORT_A, 5    /* PA5  */
#define PIN_SPI1_MISO  GPIO_PORT_A, 6    /* PA6  */
#define PIN_SPI1_MOSI  GPIO_PORT_A, 7    /* PA7  (unused: MAX31855 is read-only) */
#define PIN_TC1_CS     GPIO_PORT_A, 4    /* PA4  */
#define PIN_TC2_CS     GPIO_PORT_A, 15   /* PA15 */
#define PIN_TC3_CS     GPIO_PORT_C, 13   /* PC13 */
#define PIN_CT1_ADC    GPIO_PORT_B, 3    /* PB3  */
#define PIN_CT2_ADC    GPIO_PORT_B, 4    /* PB4  */
#define PIN_CT3_ADC    GPIO_PORT_B, 2    /* PB2  */

/* ---- IR/PD node (hardware/kicad/ir-pd-node, x1/pano) -----------------------
 * HFCT front-end envelope output (ADC) + zero-cross phase reference (EXTI). */
#define PIN_PD_ENV_ADC GPIO_PORT_B, 3    /* PB3 */
#define PIN_ZC_SIG_EXTI GPIO_PORT_A, 0   /* PA0 */

/* ---- Gateway (hardware/kicad/gateway, x1/pano) -----------------------------
 * W5500 SPI Ethernet controller on SPI2. */
#define PIN_SPI2_SCLK  GPIO_PORT_A, 8    /* PA8  -- ETH_SCLK */
#define PIN_SPI2_MISO  GPIO_PORT_A, 5    /* PA5  -- ETH_MISO */
#define PIN_SPI2_MOSI  GPIO_PORT_A, 10   /* PA10 -- ETH_MOSI */
#define PIN_SPI2_CS    GPIO_PORT_A, 9    /* PA9  -- ETH_CS   */
#define PIN_ETH_INT    GPIO_PORT_A, 11   /* PA11 -- ETH_INT  */
#define PIN_ETH_RST    GPIO_PORT_A, 12   /* PA12 -- ETH_RST  */

#endif /* PANOGOZ_PINMAP_H */

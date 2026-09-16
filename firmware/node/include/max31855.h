/* max31855.h -- MAX31855KASA SPI frame decoder (TC node, hardware/kicad/tc-node).
 *
 * Real 32-bit SPI read frame, per the MAX31855 datasheet (Maxim/Analog
 * Devices), MSB first:
 *   D[31:18] signed 14-bit thermocouple temperature, LSB = 0.25 degC
 *   D17      reserved, always 0
 *   D16      FAULT   (1 = one of OC/SCG/SCV below is set)
 *   D[15:4]  signed 12-bit internal (cold-junction) reference temp, LSB = 0.0625 degC
 *   D3       reserved, always 0
 *   D2       SCV fault (thermocouple shorted to VCC)
 *   D1       SCG fault (thermocouple shorted to GND)
 *   D0       OC  fault (open circuit / no thermocouple connected)
 *
 * C99, no float/double, no malloc -- the 0.25 degC/LSB thermocouple field
 * rescales to "_x100" (hundredths of a degree) as an EXACT integer multiply
 * (0.25 * 100 = 25, no remainder); the internal reference field's 0.0625
 * degC/LSB does not divide evenly into x100, so it goes through one
 * multiply-then-divide rescale (informational only -- theta_fixed.c never
 * consumes it, MAX31855 already does its own cold-junction compensation
 * on-chip).
 */
#ifndef PANOGOZ_MAX31855_H
#define PANOGOZ_MAX31855_H

#include <stdint.h>

typedef struct {
    int32_t thermocouple_temp_x100; /* degC * 100; meaningless if fault != 0 */
    int32_t internal_temp_x100;     /* cold-junction reference, degC * 100 */
    uint8_t fault;      /* D16 -- 1 if any of fault_oc/fault_scg/fault_scv is set */
    uint8_t fault_oc;   /* D0  -- open circuit */
    uint8_t fault_scg;  /* D1  -- short to GND */
    uint8_t fault_scv;  /* D2  -- short to VCC */
} max31855_reading_t;

/* word: the raw 32-bit value shifted in MSB-first over SPI1 (see
 * hardware/kicad/tc-node: SCK=PA5, MISO=PA6, CS=TCn_CS). Pure decode, no
 * SPI bus access here -- the caller supplies the already-clocked-in word. */
max31855_reading_t max31855_decode(uint32_t word);

#endif /* PANOGOZ_MAX31855_H */

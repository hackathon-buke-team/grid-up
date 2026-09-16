/* main_tc.c -- TC node (hardware/kicad/tc-node) target firmware skeleton.
 *
 * SCOPE (see docs/07-FIRMWARE.md Sec.4 for the full, honest list): this pass
 * proves the K1 1.4 "bitti sayilir" bar -- theta_fixed.c/max31855.c cross-
 * compile and link for the real STM32WLE5CC target (Cortex-M4, no float
 * instructions, real flash/RAM report) using the real pin map from
 * hardware/kicad/build_boards.py. It does NOT drive real GPIO/SPI/ADC
 * peripherals -- no verified STM32WL CMSIS/HAL device header was available
 * in this environment (STM32CubeWL is a large, separate ST download; not
 * fetched here -- see docs/07 Sec.2). Every register-level TODO below is
 * left as a TODO, not a guessed address.
 */
#include <stdint.h>
#include "pinmap.h"
#include "theta_fixed.h"
#include "max31855.h"

#define RATED_CURRENT_A_X100 25000 /* 250.00 A, panogoz/sim/demo_fleet.py RATED_CURRENT_A */

/* TODO(real hardware): SPI1 read of TCn_CS, returning the raw 32-bit
 * MAX31855 frame. Needs a verified STM32WLE5xx SPI1 register header
 * (RCC_AHB2ENR/APB2ENR bit positions, SPI1 CR1/CR2/SR/DR) that this
 * environment did not have access to -- see docs/07 Sec.4. */
static uint32_t read_max31855_spi1(int cs_port, int cs_pin)
{
    (void)cs_port;
    (void)cs_pin;
    return 0; /* placeholder: 0 decodes to 0.00 degC, fault=0 -- not real data */
}

/* TODO(real hardware): ADC read of a CT interface channel, returning a
 * current already converted to hundredths of an ampere. Needs the real
 * ADC calibration constant (CT clamp ratio, burden resistor, bias divider
 * -- see docs/03-ELEKTRONIK-DOKUMANTASYON.md Sec.5 "Generic:CT_Interface")
 * which is a PCB-stage value, not fixed yet. */
static int32_t read_ct_current_x100(int adc_port, int adc_pin)
{
    (void)adc_port;
    (void)adc_pin;
    return 0;
}

int main(void)
{
    /* TODO(real hardware): clock tree init (HSE 32MHz -> SYSCLK), GPIO/SPI1/
     * ADC peripheral enable via RCC, GPIO AF mux for PIN_SPI1_SCK/MISO and
     * PIN_TC{1,2,3}_CS / PIN_CT{1,2,3}_ADC (see pinmap.h) -- all blocked on
     * the same missing verified register header noted above. */

    for (;;) {
        uint32_t tc1_word = read_max31855_spi1(PIN_TC1_CS);
        uint32_t tc2_word = read_max31855_spi1(PIN_TC2_CS);
        uint32_t tc3_word = read_max31855_spi1(PIN_TC3_CS);

        max31855_reading_t tc1 = max31855_decode(tc1_word);
        max31855_reading_t tc2 = max31855_decode(tc2_word);
        max31855_reading_t tc3 = max31855_decode(tc3_word);

        int32_t i1 = read_ct_current_x100(PIN_CT1_ADC);
        int32_t i2 = read_ct_current_x100(PIN_CT2_ADC);
        int32_t i3 = read_ct_current_x100(PIN_CT3_ADC);

        /* sibling median of the OTHER two phases' surface temp, per phase --
         * panogoz/detector/theta.py computes median(all 3), matching that
         * exactly needs a 3-way median; TC1 shown here as the worked case,
         * TC2/TC3 follow the same pattern (elided -- see docs/07 Sec.4). */
        int32_t sib_median_for_tc1 =
            (tc2.thermocouple_temp_x100 < tc3.thermocouple_temp_x100)
                ? tc2.thermocouple_temp_x100
                : tc3.thermocouple_temp_x100; /* TODO: real 3-way median incl. tc1 */

        theta_result_t theta1 = theta_compute_fixed(
            tc1.thermocouple_temp_x100, sib_median_for_tc1, i1, RATED_CURRENT_A_X100);

        (void)theta1;
        (void)i2;
        (void)i3;

        /* TODO(real hardware): hand theta1 (and theta2/theta3) to
         * panogoz/rules/engine.py's C99 counterpart (not yet ported) and
         * onward to the radio TX path -- out of scope for K1 1.4. */
    }
}

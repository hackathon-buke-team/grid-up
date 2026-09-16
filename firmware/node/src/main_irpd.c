/* main_irpd.c -- IR/PD node (hardware/kicad/ir-pd-node) target firmware
 * skeleton. Scope note: see main_tc.c's header comment -- same honest
 * limits apply (docs/07-FIRMWARE.md Sec.4).
 */
#include <stdint.h>
#include "pinmap.h"

/* TODO(real hardware): ADC read of the HFCT front-end's envelope output
 * (Generic:RF_Frontend -- bandpass+LNA+log-amp envelope detector, see
 * docs/03-ELEKTRONIK-DOKUMANTASYON.md Sec.5). No verified STM32WL ADC
 * register header available in this environment -- see docs/07 Sec.4. */
static int32_t read_pd_envelope_adc(int adc_port, int adc_pin)
{
    (void)adc_port;
    (void)adc_pin;
    return 0;
}

/* TODO(real hardware): EXTI-driven zero-cross timestamp capture on
 * PIN_ZC_SIG_EXTI (opto-isolated phase reference, see
 * hardware/kicad/ir-pd-node build_ir_pd_node()). */
static uint32_t last_zero_cross_timestamp_ticks;

int main(void)
{
    /* TODO(real hardware): clock tree init, EXTI0 (PA0) rising/falling edge
     * config for PIN_ZC_SIG_EXTI, ADC init for PIN_PD_ENV_ADC. */

    for (;;) {
        int32_t pd_envelope = read_pd_envelope_adc(PIN_PD_ENV_ADC);
        (void)pd_envelope;
        (void)last_zero_cross_timestamp_ticks;

        /* TODO(real hardware): phase-resolved PD histogram/classifier (see
         * CLAUDE.md Sec.2 "PD: faz cozunurluklu histogram/siniflandirici")
         * and radio TX path -- out of scope for K1 1.4. */
    }
}

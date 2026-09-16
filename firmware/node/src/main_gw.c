/* main_gw.c -- Gateway (hardware/kicad/gateway) target firmware skeleton.
 * Scope note: see main_tc.c's header comment -- same honest limits apply
 * (docs/07-FIRMWARE.md Sec.4).
 */
#include <stdint.h>
#include "pinmap.h"

/* TODO(real hardware): SPI2 register-level W5500 access (chip select on
 * PIN_SPI2_CS, interrupt on PIN_ETH_INT, reset on PIN_ETH_RST -- see
 * hardware/kicad/gateway build_gateway()). No verified STM32WL SPI2
 * register header available in this environment -- see docs/07 Sec.4. */
static void w5500_reset(int rst_port, int rst_pin)
{
    (void)rst_port;
    (void)rst_pin;
}

int main(void)
{
    /* TODO(real hardware): clock tree init, GPIO AF mux for
     * PIN_SPI2_{SCLK,MISO,MOSI,CS}, W5500 socket/MAC init, MQTT-over-TCP
     * publish loop relaying sub-GHz frames received from TC/IR-PD nodes
     * into panogoz/bus (panogoz/bus/mqtt_bus.py is the server-side
     * counterpart, proven against a real broker tonight -- K2 2.1). */
    w5500_reset(PIN_ETH_RST);

    for (;;) {
        /* TODO(real hardware): sub-GHz receive -> W5500 TCP publish.
         * Out of scope for K1 1.4 (pin map + cross-compile proof only). */
    }
}

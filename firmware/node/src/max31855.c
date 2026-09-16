#include "max31855.h"

max31855_reading_t max31855_decode(uint32_t word)
{
    max31855_reading_t r;

    /* D[31:18]: 14-bit signed thermocouple temperature. */
    int32_t raw_tc = (int32_t)((word >> 18) & 0x3FFFu);
    if (raw_tc & 0x2000) { /* sign bit (bit13 of the 14-bit field) set */
        raw_tc -= 0x4000;  /* two's-complement sign-extend 14 -> 32 bit */
    }
    r.thermocouple_temp_x100 = raw_tc * 25; /* 0.25 degC/LSB * 100 == 25, exact */

    /* D[15:4]: 12-bit signed cold-junction reference temperature. */
    int32_t raw_internal = (int32_t)((word >> 4) & 0x0FFFu);
    if (raw_internal & 0x0800) { /* sign bit (bit11 of the 12-bit field) set */
        raw_internal -= 0x1000; /* two's-complement sign-extend 12 -> 32 bit */
    }
    /* 0.0625 degC/LSB == 1/16 degC; rescale to x100 via multiply-then-divide
     * (100/16 is not integer, so this is a deliberate truncating rescale --
     * informational field only, not consumed by theta_fixed.c). */
    r.internal_temp_x100 = (raw_internal * 100) / 16;

    r.fault = (uint8_t)((word >> 16) & 0x1u);
    r.fault_scv = (uint8_t)((word >> 2) & 0x1u);
    r.fault_scg = (uint8_t)((word >> 1) & 0x1u);
    r.fault_oc = (uint8_t)(word & 0x1u);

    return r;
}

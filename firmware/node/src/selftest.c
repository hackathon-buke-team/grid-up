/* selftest.c -- host-native entry point: `panogoz_node --selftest`
 * (CLAUDE.md Sec.9 "Hizli Komutlar": `cd firmware/node && make host &&
 * ./panogoz_node --selftest`). Not part of the target (ARM) build -- this
 * is the native test driver that exercises theta_fixed.c/max31855.c
 * against known values, most of them cross-checked against the real
 * Python reference (panogoz/detector/theta.py) run alongside this file's
 * comments -- see docs/07-FIRMWARE.md Sec.3 for the exact `python -c`
 * commands used to generate each expected value below.
 */
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

#include "theta_fixed.h"
#include "max31855.h"

static int g_failures = 0;

static void check_i32(const char *label, int32_t got, int32_t want)
{
    if (got != want) {
        printf("  FAIL %-42s got=%d want=%d\n", label, got, want);
        g_failures++;
    } else {
        printf("  ok   %-42s = %d\n", label, got);
    }
}

static void check_u8(const char *label, uint8_t got, uint8_t want)
{
    if (got != want) {
        printf("  FAIL %-42s got=%u want=%u\n", label, (unsigned)got, (unsigned)want);
        g_failures++;
    } else {
        printf("  ok   %-42s = %u\n", label, (unsigned)got);
    }
}

/* Tolerance-based check for the one case (theta_case5) whose Python
 * reference is a non-terminating decimal (316.58739595719385...) -- the
 * fixed-point result is compared within +/-1 hundredth-of-a-degree
 * (|error| <= 1 on the _x100 scale), not bit-exact. */
static void check_i32_tolerance(const char *label, int32_t got, int32_t want, int32_t tol)
{
    int32_t diff = got - want;
    if (diff < 0) diff = -diff;
    if (diff > tol) {
        printf("  FAIL %-42s got=%d want=%d (tol=%d)\n", label, got, want, tol);
        g_failures++;
    } else {
        printf("  ok   %-42s = %d (want %d +/-%d)\n", label, got, want, tol);
    }
}

static void test_theta(void)
{
    printf("-- theta_compute_fixed (vs. panogoz/detector/theta.py) --\n");

    /* Case 1: diff=0 -> theta=0 exactly, any load fraction >= min gate.
     * python -c "print((100.0-100.0)/((250.0/250.0)**2))" -> 0.0 */
    {
        theta_result_t r = theta_compute_fixed(10000, 10000, 25000, 25000);
        check_u8("case1 is_valid", r.is_valid, 1);
        check_i32("case1 theta_x100 (T=Tmed=100, I=Irated=250)", r.theta_x100, 0);
    }

    /* Case 2: full load (load_fraction=1.0) -> theta == raw diff.
     * python -c "print((110.0-100.0)/((250.0/250.0)**2))" -> 10.0 */
    {
        theta_result_t r = theta_compute_fixed(11000, 10000, 25000, 25000);
        check_u8("case2 is_valid", r.is_valid, 1);
        check_i32("case2 theta_x100 (T=110,Tmed=100,I=Irated=250)", r.theta_x100, 1000);
    }

    /* Case 3: half load (load_fraction=0.5) -> theta == diff / 0.25 == 4*diff.
     * python -c "print((110.0-100.0)/((125.0/250.0)**2))" -> 40.0 */
    {
        theta_result_t r = theta_compute_fixed(11000, 10000, 12500, 25000);
        check_u8("case3 is_valid", r.is_valid, 1);
        check_i32("case3 theta_x100 (T=110,Tmed=100,I=125,Irated=250)", r.theta_x100, 4000);
    }

    /* Case 4: current below the 40% min-load gate (90A < 0.40*250=100A)
     * -> Python returns None. python -c "print(90.0 < 0.40*250.0)" -> True */
    {
        theta_result_t r = theta_compute_fixed(11000, 10000, 9000, 25000);
        check_u8("case4 is_valid (I=90 < 40% of Irated=250 -> uninformative)", r.is_valid, 0);
    }

    /* Case 4b: exactly at the gate boundary (100A == 0.40*250A) -> Python's
     * `<` means the boundary itself IS informative (not excluded).
     * python -c "print(100.0 < 0.40*250.0)" -> False (so theta IS computed) */
    {
        theta_result_t r = theta_compute_fixed(11000, 10000, 10000, 25000);
        check_u8("case4b is_valid (I==40% of Irated, boundary itself is valid)", r.is_valid, 1);
    }

    /* Case 5: demo-shaped values (T=189.1, Tmed=82.6, I=145.0, Irated=250.0),
     * a non-terminating decimal in Python -- reference computed via:
     * python -c "print((189.1-82.6)/((145.0/250.0)**2))" -> 316.58739595719385 */
    {
        theta_result_t r = theta_compute_fixed(18910, 8260, 14500, 25000);
        check_u8("case5 is_valid", r.is_valid, 1);
        check_i32_tolerance("case5 theta_x100 (demo-shaped fault values)", r.theta_x100, 31659, 1);
    }

    /* Case 6: negative diff (phase cooler than siblings) stays negative,
     * exercises the int64_t signed path.
     * python -c "print((80.0-90.0)/((250.0/250.0)**2))" -> -10.0 */
    {
        theta_result_t r = theta_compute_fixed(8000, 9000, 25000, 25000);
        check_u8("case6 is_valid", r.is_valid, 1);
        check_i32("case6 theta_x100 (T=80 < Tmed=90, negative theta)", r.theta_x100, -1000);
    }
}

static void test_max31855(void)
{
    printf("-- max31855_decode (vs. hand-verified SPI frames) --\n");

    /* word32 = 0x09642000: thermocouple raw=601 (150.25 degC), internal
     * raw=512 (32.00 degC), no fault. Frame built + verified via:
     *   python -c "raw_tc=601; raw_i=512; \
     *     w=(raw_tc<<18)|(raw_i<<4); print(hex(w))"  -> 0x9642000 */
    {
        max31855_reading_t r = max31855_decode(0x09642000u);
        check_i32("frame1 thermocouple_temp_x100 (expect 150.25C)", r.thermocouple_temp_x100, 15025);
        check_i32("frame1 internal_temp_x100 (expect 32.00C)", r.internal_temp_x100, 3200);
        check_u8("frame1 fault", r.fault, 0);
        check_u8("frame1 fault_oc", r.fault_oc, 0);
    }

    /* word32 = 0xFF351901: thermocouple raw=-51 (-12.75 degC, sign-extend
     * exercised), internal raw=400 (25.00 degC), FAULT=1, OC=1. Built +
     * verified via:
     *   python -c "raw_tc=(-51)&0x3FFF; raw_i=400; \
     *     w=(raw_tc<<18)|(1<<16)|(raw_i<<4)|1; print(hex(w))" -> 0xff351901 */
    {
        max31855_reading_t r = max31855_decode(0xFF351901u);
        check_i32("frame2 thermocouple_temp_x100 (expect -12.75C, sign-extend)", r.thermocouple_temp_x100, -1275);
        check_i32("frame2 internal_temp_x100 (expect 25.00C)", r.internal_temp_x100, 2500);
        check_u8("frame2 fault", r.fault, 1);
        check_u8("frame2 fault_oc", r.fault_oc, 1);
        check_u8("frame2 fault_scg", r.fault_scg, 0);
        check_u8("frame2 fault_scv", r.fault_scv, 0);
    }
}

static void run_selftest(void)
{
    test_theta();
    test_max31855();
    printf("\n%s: %d failure(s)\n", g_failures == 0 ? "SELFTEST PASS" : "SELFTEST FAIL", g_failures);
}

int main(int argc, char **argv)
{
    if (argc >= 2 && strcmp(argv[1], "--selftest") == 0) {
        run_selftest();
        return g_failures == 0 ? 0 : 1;
    }
    printf("usage: %s --selftest\n", argc > 0 ? argv[0] : "panogoz_node");
    return 2;
}

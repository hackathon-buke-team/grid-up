/* theta_fixed.h -- fixed-point reimplementation of panogoz/detector/theta.py
 *
 * Reference (Python, panogoz/detector/theta.py):
 *   MIN_LOAD_FRACTION = 0.40
 *   if current_a < MIN_LOAD_FRACTION * rated_current_a: theta = None
 *   else: theta = (surface_temp_c - sibling_median_c) / (current_a/rated_current_a)**2
 *
 * C99, no float/double, no malloc (CLAUDE.md K1 constraint: uc dugum firmware
 * is float/malloc-free). All physical quantities are carried as integers
 * scaled by 100 ("_x100" suffix -- hundredths of a degree C, or hundredths of
 * an ampere) so a real sensor reading like 82.64 degC round-trips as 8264
 * with no precision loss up front; every division happens exactly once, at
 * the end, against a pre-multiplied numerator -- see theta_fixed.c.
 */
#ifndef PANOGOZ_THETA_FIXED_H
#define PANOGOZ_THETA_FIXED_H

#include <stdint.h>

/* MIN_LOAD_FRACTION = 40/100, matches Python's 0.40 exactly (no rounding). */
#define THETA_MIN_LOAD_NUM 40
#define THETA_MIN_LOAD_DEN 100

typedef struct {
    int32_t theta_x100; /* valid only when is_valid != 0 */
    uint8_t is_valid;   /* 0 == Python's `None` (current below min-load gate) */
} theta_result_t;

/* temp_phase_x100, temp_sibling_median_x100: degC * 100 (signed -- surface
 * temperature deltas can be negative relative to the sibling median).
 * current_a_x100, rated_current_a_x100: amperes * 100 (always >= 0). */
theta_result_t theta_compute_fixed(int32_t temp_phase_x100,
                                    int32_t temp_sibling_median_x100,
                                    int32_t current_a_x100,
                                    int32_t rated_current_a_x100);

#endif /* PANOGOZ_THETA_FIXED_H */

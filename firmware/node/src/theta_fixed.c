#include "theta_fixed.h"

theta_result_t theta_compute_fixed(int32_t temp_phase_x100,
                                    int32_t temp_sibling_median_x100,
                                    int32_t current_a_x100,
                                    int32_t rated_current_a_x100)
{
    theta_result_t r;
    r.theta_x100 = 0;
    r.is_valid = 0;

    /* min_load_a_x100 = 0.40 * rated_current_a_x100, integer-exact since
     * rated_current_a_x100 * 40 cannot overflow int64_t for any realistic
     * rated current (<= a few hundred amps). */
    int64_t min_load_x100 =
        ((int64_t)rated_current_a_x100 * THETA_MIN_LOAD_NUM) / THETA_MIN_LOAD_DEN;

    if ((int64_t)current_a_x100 < min_load_x100) {
        /* Python: theta = None (uninformative at low load). */
        return r;
    }

    /* theta = diff / (I/I_rated)^2 = diff * I_rated^2 / I^2
     * Multiply by I_rated^2 BEFORE dividing by I^2 (single integer divide,
     * done last) instead of computing the load-fraction ratio first -- that
     * would need a fractional square, which integer math can't represent
     * without its own separate fixed-point scale. All three intermediates
     * (diff_x100, rated_sq, cur_sq) are carried in int64_t: diff_x100 is
     * at most a few times 10^4 (a few hundred degC * 100), rated_sq/cur_sq
     * are at most ~(60000)^2 = 3.6*10^9 for a 600A-class rated current --
     * their product is ~10^14, three orders of magnitude below INT64_MAX. */
    int64_t diff_x100 = (int64_t)temp_phase_x100 - (int64_t)temp_sibling_median_x100;
    int64_t rated_sq = (int64_t)rated_current_a_x100 * (int64_t)rated_current_a_x100;
    int64_t cur_sq = (int64_t)current_a_x100 * (int64_t)current_a_x100;

    if (cur_sq == 0) {
        /* Unreachable in practice: current_a_x100 >= min_load_x100 > 0
         * whenever rated_current_a_x100 > 0, but guard the divide anyway. */
        return r;
    }

    int64_t numerator = diff_x100 * rated_sq;
    int64_t theta = numerator / cur_sq;

    r.theta_x100 = (int32_t)theta;
    r.is_valid = 1;
    return r;
}

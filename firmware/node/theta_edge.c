/* ==========================================================================
 * PANO GOZ - on-node edge analytics
 *
 * Everything here is integer.  There is no float, no libm, no division by a
 * runtime value that could be zero without a guard, and no allocation.  The
 * heaviest operation in the file is one 64-bit divide per aggregate (not per
 * sample), which on a Cortex-M4 costs about 60 cycles through __aeabi_ldivmod
 * - roughly 1.3 us at 48 MHz, i.e. 0.006 uAs.  It is not worth optimising.
 *
 * WHAT theta IS, AND WHY THE NODE COMPUTES IT AT ALL
 * ---------------------------------------------------
 *   theta_i = [ T_i - median(siblings of i) ] / (I / I_ref)^2
 *
 * Load-independent because I^2 divides out.  Ambient- and season-independent
 * because it is a difference of co-located sensors.  Emissivity-independent
 * for the IR variant because identical surfaces cancel.  It needs NO history:
 * three identical phases on one busbar are a valid baseline on installation
 * day.  theta IS the load-corrected "delta-T over a similar component" that
 * IR thermography practice already prescribes; we just made it a number
 * instead of a photograph.
 *
 * The node computes it for ONE reason only: to decide how to spend radio
 * energy.  The authoritative theta - with the RLS thermal-lag deconvolution,
 * the CUSUM, the change point and the load-bias correction - is computed on
 * the server from the raw LSB this node ships.  The node's copy is a
 * trigger, deliberately cruder, and it never alarms on its own.
 *
 * SELF IS EXCLUDED FROM THE SIBLING MEDIAN.  With three phases the temptation
 * is to take the median of all three, which is one instruction cheaper.  It
 * is also wrong: once the faulted phase crosses one of its siblings the
 * median jumps to a different member and about 40 % of the signal silently
 * disappears.  With exactly two siblings the median is their mean, and that
 * is what this file computes.
 * ========================================================================== */

#include "node.h"

/* ---------------------------------------------------------------------- */
/* Integer utilities                                                       */
/* ---------------------------------------------------------------------- */

/* Bit-by-bit integer square root.  No libm, no Newton iteration that could
 * fail to converge, no table.  Exact floor(sqrt(v)) for the whole 64-bit
 * range in at most 32 iterations. */
uint32_t pg_isqrt64(uint64_t v)
{
    uint64_t rem = 0, root = 0;
    int i;
    for (i = 0; i < 32; i++) {
        root <<= 1;
        rem = (rem << 2) | (v >> 62);
        v <<= 2;
        if (root < rem) {
            rem -= root | 1u;
            root += 2;
        }
    }
    return (uint32_t)(root >> 1);
}

/* Round-half-away-from-zero integer division.  Truncation would bias every
 * mean in this file towards zero, and a systematic 0.5 LSB bias on a sibling
 * difference is 0.004 K of free error we do not have to accept. */
int32_t pg_div_round(int64_t num, int64_t den)
{
    if (den == 0) return 0;
    if ((num < 0) != (den < 0)) {
        return (int32_t)((num - den / 2) / den);
    }
    return (int32_t)((num + den / 2) / den);
}

static int64_t pg_abs64(int64_t v) { return v < 0 ? -v : v; }

/* ---------------------------------------------------------------------- */
/* Ring window                                                             */
/* ---------------------------------------------------------------------- */

void pg_edge_init(pg_edge_t *e)
{
    int i;
    for (i = 0; i < PG_WIN_N; i++) { e->t[i] = 0; e->i[i] = 0; e->ts[i] = 0; }
    e->head = 0;
    e->count = 0;
    for (i = 0; i < PG_TH_N; i++) { e->th[i] = 0; e->th_min[i] = 0; e->th_ts[i] = 0; }
    e->th_head = 0;
    e->th_count = 0;
    e->th_last_ts = 0;
    e->relay_t = 0;
    e->relay_ts = 0;
    e->peer_n = 0;
    for (i = 0; i < 2; i++) { e->peer_t[i] = 0; e->peer_ts[i] = 0; e->peer_id[i] = 0; }
    e->theta_lsb = PG_THETA_INVALID;
    e->theta_min_lsb = 0;
    e->f_q16 = 0;
    e->flags = 0;
}

void pg_edge_push(pg_edge_t *e, const pg_sample_t *s)
{
    if (!s->ok) return;
    e->t[e->head]  = s->t_lsb;
    e->i[e->head]  = s->i_ma;
    e->ts[e->head] = s->ts;
    e->head = (uint8_t)((e->head + 1u) % PG_WIN_N);
    if (e->count < PG_WIN_N) e->count++;
}

int16_t pg_edge_last_t(const pg_edge_t *e, int *ok)
{
    if (e->count == 0) { if (ok) *ok = 0; return 0; }
    if (ok) *ok = 1;
    return e->t[(e->head + PG_WIN_N - 1u) % PG_WIN_N];
}

/* THE TREND REGISTER.
 *
 * Two independent reasons this is not simply "the slope of the sample
 * window":
 *
 *  1. It must be the slope OF THETA.  Raw lug temperature climbs about 8 K
 *     between the 04:00 trough and the 19:00 peak of an ordinary Turkish LV
 *     secondary feeder.  Fitting a line through that gives roughly 12 K/day
 *     every morning on a joint in perfect condition.  theta divides the load
 *     out, and dividing the load out is the entire point of the project.
 *
 *  2. Its spacing must NOT follow the telemetry cadence.  In an event burst
 *     the node samples every 10 s; 32 such samples span five minutes, and a
 *     line fitted through five minutes of 0.2 K noise produces a slope of
 *     hundreds of kelvin per day.  The register therefore accepts at most
 *     one theta per PG_TH_MIN_DT_S and the slope is only believed once the
 *     stored samples span PG_TH_MIN_SPAN_S.
 *
 * And it refuses samples taken below the sensitivity floor, because a trend
 * fitted through values the instrument could not resolve is still a trend,
 * and it will be a convincing one. */
void pg_edge_push_theta(pg_edge_t *e, int32_t theta_lsb, int32_t theta_min_lsb,
                        uint32_t ts, uint32_t f_q16)
{
    if (theta_lsb == PG_THETA_INVALID) return;
    if (f_q16 < PG_SENSITIVITY_FLOOR_Q16) return;
    if (e->th_last_ts != 0 && ts >= e->th_last_ts &&
        (ts - e->th_last_ts) < PG_TH_MIN_DT_S) return;

    e->th[e->th_head]     = theta_lsb;
    /* Carry the resolution the node had AT THAT MOMENT alongside the value.
     * Without it the trend test cannot tell a 3 K rise measured at f = 0.8
     * (where one sigma is 0.3 K) from a 3 K rise measured at f = 0.36
     * (where one sigma is 1.5 K), and it would treat them as equally real. */
    e->th_min[e->th_head] = theta_min_lsb;
    e->th_ts[e->th_head] = ts;
    e->th_head = (uint8_t)((e->th_head + 1u) % PG_TH_N);
    if (e->th_count < PG_TH_N) e->th_count++;
    e->th_last_ts = ts;
}

/* A peer frame arrived on the shared sub-GHz channel.  The three clips of one
 * feeder are on the same channel and hear each other directly - the sibling
 * median is therefore available at the edge without a round trip through the
 * gateway, which is what lets the node make a cadence decision in the same
 * wake cycle it took the reading. */
void pg_edge_peer(pg_edge_t *e, uint16_t peer_id, int16_t t_lsb, uint32_t ts)
{
    int i;
    for (i = 0; i < e->peer_n; i++) {
        if (e->peer_id[i] == peer_id) {
            e->peer_t[i] = t_lsb;
            e->peer_ts[i] = ts;
            return;
        }
    }
    if (e->peer_n < 2) {
        i = e->peer_n++;
    } else {
        /* replace the stalest */
        i = (e->peer_ts[0] <= e->peer_ts[1]) ? 0 : 1;
    }
    e->peer_id[i] = peer_id;
    e->peer_t[i]  = t_lsb;
    e->peer_ts[i] = ts;
}

/* ---------------------------------------------------------------------- */
/* Aggregate: min / max / mean / p2p / RMS current / slope                  */
/* ---------------------------------------------------------------------- */

/* Ordinary least squares over the theta trend register, plus the peak-to-peak
 * and the median.  Same integer arithmetic as the raw-temperature slope; the
 * conversion constant 86400*1000/128 = 675000 is exact. */
static int32_t med_of(int32_t *a, int n)
{
    int i, j;
    for (i = 1; i < n; i++) {
        int32_t v = a[i];
        for (j = i - 1; j >= 0 && a[j] > v; j--) a[j + 1] = a[j];
        a[j + 1] = v;
    }
    if (n <= 0) return 0;
    return (n & 1) ? a[n / 2] : pg_div_round((int64_t)a[n / 2 - 1] + a[n / 2], 2);
}

static void pg_theta_trend(const pg_edge_t *e, pg_agg_t *out)
{
    int64_t sx = 0, sy = 0, sxx = 0, sxy = 0, sxy_c, sxx_c;
    int32_t buf[PG_TH_N], half[PG_TH_N];
    uint32_t t0;
    int n = e->th_count, k, idx, h;

    if (n == 0) return;
    idx = (int)((e->th_head + PG_TH_N - n) % PG_TH_N);
    t0  = e->th_ts[idx];

    for (k = 0; k < n; k++) {
        int     m = (idx + k) % PG_TH_N;
        int64_t y = e->th[m];
        int64_t x = (int64_t)(e->th_ts[m] - t0);
        sx += x; sy += y; sxx += x * x; sxy += x * y;
        buf[k] = (int32_t)y;
    }

    out->theta_n      = (uint32_t)n;
    out->theta_span_s = e->th_ts[(idx + n - 1) % PG_TH_N] - t0;

    /* Typical resolution over the window.  A median, not a mean: one sample
     * taken at the bottom of the night trough should not set the standard
     * for the whole day. */
    for (k = 0; k < n; k++) buf[k] = e->th_min[(idx + k) % PG_TH_N];
    out->theta_min_med_lsb = med_of(buf, n);

    for (k = 0; k < n; k++) buf[k] = e->th[(idx + k) % PG_TH_N];
    out->theta_med_lsb = med_of(buf, n);

    /* STEP = median of the newer half minus median of the older half.
     * A median-of-halves difference has a standard deviation of about
     * 0.44 sigma however long the window is; a peak-to-peak has one that
     * GROWS with the sample count, so watching a healthy joint for longer
     * would make a peak-to-peak test fire more often.  That is backwards,
     * and it is the usual reason a trend detector has to be switched off in
     * month three. */
    h = n / 2;
    if (h >= 3) {
        int32_t a, b;
        for (k = 0; k < h; k++) half[k] = e->th[(idx + k) % PG_TH_N];
        a = med_of(half, h);
        for (k = 0; k < n - h; k++) half[k] = e->th[(idx + h + k) % PG_TH_N];
        b = med_of(half, n - h);
        out->theta_step_lsb = b - a;
        /* Floor: k_sigma * 0.44 * (theta_min_med / K_SIGMA), i.e. the noise
         * of the difference of two medians, never below the fixed 6 K. */
        out->theta_step_floor_lsb =
            pg_div_round((int64_t)PG_TREND_K_SIGMA * 44 * out->theta_min_med_lsb,
                         100 * PG_K_SIGMA);
        if (out->theta_step_floor_lsb < PG_STEP_THETA_LSB)
            out->theta_step_floor_lsb = PG_STEP_THETA_LSB;
    }

    out->theta_slope_floor_mk_d = PG_SLOPE_RISING_MK_D;
    if (n < PG_TH_MIN_N || out->theta_span_s < PG_TH_MIN_SPAN_S) return;

    /* Noise floor of the SLOPE estimator itself.
     *   sigma_theta        = theta_min_med / K_SIGMA          [LSB]
     *   sigma_x            = span / sqrt(12)                  [s]
     *   sigma_slope        = sigma_theta / (sigma_x * sqrt(n)) [LSB/s]
     *   per day, in mK     = sigma_slope * 86400 * 1000 / 128
     * Folded together with sqrt(12) = 3.464 and 86400000/128 = 675000:
     *   floor_mk_d = k_sigma * theta_min_med * 3464 * 675000
     *                / (K_SIGMA * 1000 * span * isqrt(n))
     * All integer, one 64-bit divide, once per aggregate. */
    {
        uint32_t rn = pg_isqrt64((uint64_t)n * 1000000ull);   /* sqrt(n)*1000 */
        int64_t  num = (int64_t)PG_TREND_K_SIGMA * out->theta_min_med_lsb
                       * 3464LL * 675000LL;
        int64_t  den = (int64_t)PG_K_SIGMA * 1000LL * (int64_t)out->theta_span_s
                       * (int64_t)rn / 1000LL;
        int32_t  floor_mk = (den > 0) ? pg_div_round(num, den) : 0;
        if (floor_mk > out->theta_slope_floor_mk_d)
            out->theta_slope_floor_mk_d = floor_mk;
    }

    sxy_c = (int64_t)n * sxy - sx * sy;
    sxx_c = (int64_t)n * sxx - sx * sx;
    if (sxx_c <= 0) return;
    while (pg_abs64(sxy_c) > (int64_t)13000000000000LL) {
        sxy_c >>= 4;
        sxx_c >>= 4;
        if (sxx_c == 0) return;
    }
    out->theta_slope_mk_per_day = pg_div_round(sxy_c * 675000LL, sxx_c);
}

void pg_edge_aggregate(const pg_edge_t *e, pg_agg_t *out)
{
    int64_t  sum_t = 0, sum_i = 0, sum_i2 = 0;
    int64_t  sx = 0, sy = 0, sxx = 0, sxy = 0;
    int64_t  sxy_c, sxx_c;
    int32_t  tmin = 0x7FFFFFFF, tmax = -0x7FFFFFFF;
    uint32_t t0 = 0;
    int      n = e->count;
    int      k, idx;

    out->n = (uint32_t)n;
    out->t_min_lsb = out->t_max_lsb = out->t_mean_lsb = 0;
    out->t_p2p_lsb = 0;
    out->i_rms_ma = out->i_mean_ma = 0;
    out->slope_mk_per_day = 0;
    out->theta_slope_mk_per_day = 0;
    out->theta_slope_floor_mk_d = PG_SLOPE_RISING_MK_D;
    out->theta_step_lsb = 0;
    out->theta_step_floor_lsb = PG_STEP_THETA_LSB;
    out->theta_med_lsb = 0;
    out->theta_min_med_lsb = 0;
    out->theta_n = 0;
    out->theta_span_s = 0;
    pg_theta_trend(e, out);
    if (n == 0) return;

    /* oldest sample first, so x is monotonically increasing */
    idx = (int)((e->head + PG_WIN_N - n) % PG_WIN_N);
    t0 = e->ts[idx];

    for (k = 0; k < n; k++) {
        int j = (idx + k) % PG_WIN_N;
        int64_t y = e->t[j];
        int64_t x = (int64_t)(e->ts[j] - t0);      /* seconds since window start */
        int64_t im = e->i[j];

        if (y < tmin) tmin = (int32_t)y;
        if (y > tmax) tmax = (int32_t)y;
        sum_t += y;
        if (im >= 0) { sum_i += im; sum_i2 += im * im; }

        sx  += x;
        sy  += y;
        sxx += x * x;
        sxy += x * y;
    }

    out->t_min_lsb  = tmin;
    out->t_max_lsb  = tmax;
    out->t_p2p_lsb  = tmax - tmin;
    out->t_mean_lsb = pg_div_round(sum_t, n);
    out->i_mean_ma  = pg_div_round(sum_i, n);

    /* True RMS over the window.  RMS, not mean, because a joint's dissipation
     * follows I^2 and the mean of I understates it whenever the load is
     * peaky - which on a Turkish LV secondary feeder it always is. */
    out->i_rms_ma = (int32_t)pg_isqrt64((uint64_t)(sum_i2 / (int64_t)n));

    /* Ordinary least squares slope, integer.  Q: LSB per second, converted
     * to milli-kelvin per day by  x * 86400 s/day * 1000 mK/K / 128 LSB/K
     * = x * 675000.  Exact: 86400*1000/128 = 675000, no rounding. */
    if (n >= 4) {
        sxy_c = (int64_t)n * sxy - sx * sy;
        sxx_c = (int64_t)n * sxx - sx * sx;
        if (sxx_c > 0) {
            /* Guard the multiply: keep |sxy_c| * 675000 inside int64. */
            while (pg_abs64(sxy_c) > (int64_t)13000000000000LL) {
                sxy_c >>= 4;
                sxx_c >>= 4;
                if (sxx_c == 0) break;
            }
            if (sxx_c > 0)
                out->slope_mk_per_day = pg_div_round(sxy_c * 675000LL, sxx_c);
        }
    }
}

/* ---------------------------------------------------------------------- */
/* Load factor and theta                                                   */
/* ---------------------------------------------------------------------- */

uint32_t pg_load_factor_q16(int32_t i_ma, uint32_t i_ref_a)
{
    uint64_t q;
    if (i_ma <= 0 || i_ref_a == 0) return 0;
    /* f = I / I_ref, Q16.  i_ma is milliamps, i_ref_a is amps, so
     * f_q16 = i_ma * 65536 / (i_ref_a * 1000). */
    q = ((uint64_t)(uint32_t)i_ma << 16) / ((uint64_t)i_ref_a * 1000u);
    if (q > 0xFFFFFFFFu) q = 0xFFFFFFFFu;
    return (uint32_t)q;
}

void pg_edge_relayed_median(pg_edge_t *e, int16_t t_lsb, uint32_t ts)
{
    e->relay_t  = t_lsb;
    e->relay_ts = ts;
}

int32_t pg_sibling_excess_lsb(const pg_edge_t *e, int16_t t_lsb,
                              uint32_t now, int *valid)
{
    int32_t  sum = 0;
    int      n = 0, i;

    for (i = 0; i < e->peer_n; i++) {
        if (e->peer_ts[i] == 0) continue;
        if (now >= e->peer_ts[i] && (now - e->peer_ts[i]) > PG_PEER_MAX_AGE_S) continue;
        sum += e->peer_t[i];
        n++;
    }
    if (n == 0 && e->relay_ts != 0 &&
        !(now >= e->relay_ts && (now - e->relay_ts) > PG_PEER_MAX_AGE_S)) {
        /* Gateway-relayed median.  It is ALREADY a median, so it stands
         * alone; averaging it with a direct peer would weight one phase
         * twice. */
        if (valid) *valid = 1;
        return (int32_t)t_lsb - (int32_t)e->relay_t;
    }
    if (n == 0) { if (valid) *valid = 0; return 0; }
    if (valid) *valid = 1;
    /* median of two peers == their mean; median of one == itself.  SELF IS
     * NEVER IN THIS SUM - see the header comment. */
    return (int32_t)t_lsb - pg_div_round(sum, n);
}

int32_t pg_theta_lsb(int32_t dt_lsb, uint32_t f_q16)
{
    uint64_t f2_q16;
    int64_t  num;

    if (f_q16 == 0) return PG_THETA_INVALID;
    /* f^2 in Q16: (f_q16 * f_q16) >> 16.  f_q16 <= ~131072 so the product is
     * at most 1.7e10 and needs the 64-bit intermediate. */
    f2_q16 = ((uint64_t)f_q16 * (uint64_t)f_q16) >> 16;
    if (f2_q16 == 0) return PG_THETA_INVALID;

    num = (int64_t)dt_lsb << 16;
    return pg_div_round(num, (int64_t)f2_q16);
}

int32_t pg_theta_min_lsb(uint32_t f_q16, int32_t sigma_lsb)
{
    uint64_t f2_q16;
    int64_t  v;

    if (f_q16 == 0) return 0x7FFFFFFF;
    f2_q16 = ((uint64_t)f_q16 * (uint64_t)f_q16) >> 16;
    if (f2_q16 == 0) return 0x7FFFFFFF;
    v = ((int64_t)PG_K_SIGMA * sigma_lsb) << 16;
    v = v / (int64_t)f2_q16;
    if (v > 0x7FFFFFFF) v = 0x7FFFFFFF;
    return (int32_t)v;
}

/* ---------------------------------------------------------------------- */
/* Excess contact resistance - ALWAYS an interval                          */
/* ---------------------------------------------------------------------- */

/* R_th for a 240 mm2 bolted CABLE LUG, tenths of K/W.  2.0 .. 4.0 K/W.
 *
 * NOT the busbar figure.  A localised source on a 2x(100x10) mm2 tinned
 * copper bar acts as a TWO-SIDED FIN,  R_th = 1/(2*sqrt(h*P*k*A))  with
 * k = 400 W/mK, A = 2e-3 m2, P ~ 0.44 m, h = 5..12 W/m2K, which lands at
 * 0.24 .. 0.38 K/W.  A lug is a far worse heat spreader and is an order of
 * magnitude higher.  Using the busbar number for a lug (or, worse, the
 * 3.44 K/W that a careless one-dimensional derivation produces for a bar)
 * predicts a physically impossible rise and is how a monitoring system ends
 * up reporting a joint as failed when it is fine.
 *
 * Because R_th is only known to a factor of two, dR is REPORTED AS AN
 * INTERVAL WITH THE R_th RANGE ATTACHED.  Never as an exact number. */
#define PG_RTH_LUG_LO_X10   20
#define PG_RTH_LUG_HI_X10   40

void pg_excess_r_nohm(int32_t theta_lsb, uint32_t i_ref_a,
                      int32_t *lo_nohm, int32_t *hi_nohm)
{
    int64_t num, den;

    if (lo_nohm) *lo_nohm = 0;
    if (hi_nohm) *hi_nohm = 0;
    if (i_ref_a == 0 || theta_lsb == PG_THETA_INVALID) return;

    /* dR = theta / (R_th * I_ref^2).
     * theta[K] = theta_lsb / 128, so in NANO-ohms
     *   dR_n = theta_lsb * 1e10 / (128 * R_th_x10 * I_ref^2).
     * A larger R_th implies a SMALLER excess resistance for the same theta,
     * so the high end of the interval uses the low end of R_th. */
    num = (int64_t)theta_lsb * 10000000000LL;

    den = (int64_t)128 * PG_RTH_LUG_HI_X10 * (int64_t)i_ref_a * (int64_t)i_ref_a;
    if (lo_nohm) *lo_nohm = pg_div_round(num, den);

    den = (int64_t)128 * PG_RTH_LUG_LO_X10 * (int64_t)i_ref_a * (int64_t)i_ref_a;
    if (hi_nohm) *hi_nohm = pg_div_round(num, den);
}

/* ---------------------------------------------------------------------- */
/* Event trigger                                                           */
/* ---------------------------------------------------------------------- */

/* Newest sample timestamp in the window, or 0 when the window is empty. */
static uint32_t pg_edge_now(const pg_edge_t *e)
{
    if (e->count == 0) return 0;
    return e->ts[(e->head + PG_WIN_N - 1u) % PG_WIN_N];
}

uint32_t pg_edge_trigger(const pg_edge_t *e, const pg_agg_t *a, int32_t theta_lsb)
{
    uint32_t trig = PG_TRIG_NONE;
    uint32_t now  = pg_edge_now(e);
    int      valid = 0;
    int32_t  dt;

    /* --- absolute limits.  These need no baseline, no peer and no server,
     * and they stay armed in LEARN_MODE and in SENSITIVITY_LOW. --- */
    if (a->t_max_lsb >= PG_ABS_CRITICAL_LSB) trig |= PG_TRIG_ABS_CRIT;
    else if (a->t_max_lsb >= PG_ABS_HOT_LSB) trig |= PG_TRIG_ABS_HOT;

    /* --- raw sibling delta, uncorrected for load.  Deliberately blunt: the
     * node has no history and cannot rule out a sensor fault, so it uses a
     * threshold well above anything a healthy joint produces.
     * Built from the NEWEST sample, never from the window mean: the sibling
     * median we hold arrived a moment ago, and differencing a now-value
     * against an eight-hour average would manufacture a fault every
     * morning as the feeder loads up. --- */
    {
        int have = 0;
        int16_t t_now = pg_edge_last_t(e, &have);
        if (have) {
            dt = pg_sibling_excess_lsb(e, t_now, now, &valid);
            if (valid && dt >= PG_RAW_DELTA_HOT_LSB) trig |= PG_TRIG_RAW_DELTA;
        }
    }

    /* --- theta.  Only meaningful when it is above what this node can
     * actually resolve at the present load.  theta_min(f) = 3 sigma / f^2,
     * so at f = 0.35 the floor is 24 K and firing below it would be noise
     * dressed up as a finding. --- */
    if (theta_lsb != PG_THETA_INVALID && e->f_q16 >= PG_SENSITIVITY_FLOOR_Q16) {
        if (theta_lsb >= PG_THETA_NOTIFY_LSB && theta_lsb >= e->theta_min_lsb)
            trig |= PG_TRIG_THETA;
    }

    /* --- rising trend IN THETA.  1.5 K/day sustained is about 10 K/week,
     * the shape a bolt that is backing off makes.  pg_theta_trend() has
     * already refused to produce a number until the register spans eight
     * hours and holds twelve samples taken above the sensitivity floor. --- */
    if (a->theta_n >= PG_TH_MIN_N &&
        a->theta_slope_mk_per_day >= a->theta_slope_floor_mk_d)
        trig |= PG_TRIG_SLOPE;

    /* --- step IN THETA.  A peak-to-peak across the trend window far larger
     * than the window's own slope is a discontinuity, not a load swing. --- */
    if (a->theta_n >= PG_TH_MIN_N &&
        a->theta_step_lsb >= a->theta_step_floor_lsb &&
        a->theta_slope_mk_per_day < a->theta_slope_floor_mk_d)
        trig |= PG_TRIG_STEP;

    return trig;
}

const char *pg_trigger_text_tr(uint32_t trig)
{
    if (trig & PG_TRIG_ABS_CRIT)  return "mutlak sicaklik 110 C uzerinde";
    if (trig & PG_TRIG_ABS_HOT)   return "mutlak sicaklik 90 C uzerinde";
    if (trig & PG_TRIG_RAW_DELTA) return "kardes fazlara gore 20 K ham fark";
    if (trig & PG_TRIG_THETA)     return "theta esigi asildi";
    if (trig & PG_TRIG_SLOPE)     return "theta yukselen egilimde";
    if (trig & PG_TRIG_STEP)      return "ani sicaklik basamagi";
    return "yok";
}

/* ---------------------------------------------------------------------- */
/* Formatting helper - the only place a "degree" appears on the node       */
/* ---------------------------------------------------------------------- */

void pg_fmt_scaled(char *buf, int cap, int32_t value, int32_t scale, int dp)
{
    int32_t  mul = 1;
    int32_t  whole, frac;
    int64_t  scaled;
    int      neg = 0, i, pos = 0;
    char     tmp[16];

    if (cap <= 0) return;
    for (i = 0; i < dp; i++) mul *= 10;
    if (scale == 0) scale = 1;

    scaled = ((int64_t)value * mul);
    /* round half away from zero */
    if (scaled < 0) { scaled = -((-scaled + scale / 2) / scale); }
    else            { scaled =  ( (scaled + scale / 2) / scale); }

    if (scaled < 0) { neg = 1; scaled = -scaled; }
    whole = (int32_t)(scaled / mul);
    frac  = (int32_t)(scaled % mul);

    if (neg && pos < cap - 1) buf[pos++] = '-';

    /* whole part */
    i = 0;
    if (whole == 0) tmp[i++] = '0';
    while (whole > 0 && i < (int)sizeof(tmp)) { tmp[i++] = (char)('0' + whole % 10); whole /= 10; }
    while (i > 0 && pos < cap - 1) buf[pos++] = tmp[--i];

    if (dp > 0 && pos < cap - 1) {
        buf[pos++] = '.';
        for (i = dp - 1; i >= 0; i--) {
            int32_t d = frac, j;
            for (j = 0; j < i; j++) d /= 10;
            if (pos < cap - 1) buf[pos++] = (char)('0' + (d % 10));
        }
    }
    buf[pos] = '\0';
}

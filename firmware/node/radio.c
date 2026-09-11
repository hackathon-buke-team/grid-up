/* ==========================================================================
 * PANO GOZ - sub-GHz link, frame format, duty cycle and time synchronisation
 *
 * RADIO
 * -----
 * STM32WLE5CC: the sub-GHz transceiver is on the same die as the Cortex-M4.
 * One crystal, one supply, one antenna, no inter-chip SPI to get wrong, and
 * no second BOM line.  868 MHz, LoRa SF7 BW125 CR4/5 by default.
 *
 * Why not 2.4 GHz / BLE: the link runs from the bottom cable compartment to
 * the roof communication compartment (Madde 2.2.8.1.iv) through a
 * 1600x1500x450 mm sheet-steel box with a 2 mm galvanised DSYA mounting
 * plate across the middle.  At 868 MHz (lambda = 345 mm) the 400 mm open
 * bottom onto the cable trench (Madde 2.2.8.6 Not:2) is an aperture that
 * actually couples; at 2.4 GHz (lambda = 125 mm) the box is a badly
 * overmoded cavity and the link budget is dominated by fades you cannot
 * predict or fix from the ground.  We also get a 20 dB link-budget gift from
 * LoRa's processing gain that we spend on not needing line of sight.
 *
 * At SF7 BW125 a 35-byte frame is 71.9 ms of airtime.  At the 900 s idle
 * cadence that is 0.008 % duty; even in a 10 s event burst it is 0.72 %,
 * inside the 1 % ETSI EN 300 220 limit for the g1 sub-band with margin, and
 * the limit is ENFORCED here rather than assumed - see pg_duty_allow().
 *
 * TIME SYNCHRONISATION - two clocks, two jobs
 * -------------------------------------------
 * 1. FINE PHASE: the mains zero crossing, taken from a capacitive E-field
 *    pickup (a copper pour on the node PCB, no galvanic connection to
 *    anything, no clamp on a phase conductor).  A comparator latches the
 *    free-running timer on every crossing.  This reference is
 *      - DRIFT-FREE in the long term, because the grid's time deviation is
 *        actively controlled in the Continental European synchronous area,
 *      - COMMON-MODE across the whole panel, because every node is looking
 *        at the same three phases in the same box.
 *    Comparator + interrupt latency gives about 1.5 deg (83 us) of jitter,
 *    1 sigma, per node.  Two nodes therefore agree on WHEN inside the mains
 *    cycle to about +/- 120 us (2 sigma of the difference).  That is what
 *    makes a PRPD from PD-01 and a thermal step from TC-04 comparable on the
 *    same phase axis.
 *
 * 2. COARSE WALL CLOCK: a 32.768 kHz crystal driving the RTC, plus a
 *    300 s beacon from the gateway.  The crystal is a tuning fork with a
 *    parabolic tempco, df/f = -k (T - T0)^2, k = 0.034 ppm/degC^2,
 *    T0 = 25 degC.  Uncompensated that is -42 ppm at the 60 degC a node
 *    inside a loaded panel actually sees; compensated against the stored
 *    curve using the MCU's own temperature sensor the residual is about
 *    +/- 5 ppm.
 *
 * WHAT WE CLAIM, AND WHAT WE DO NOT
 * ----------------------------------
 *   * node wall clock vs gateway wall clock, beacons being received:
 *         +/- 5 ms   (5 ppm over a 300 s beacon gap, plus ~1 ms of LoRa
 *                     symbol-boundary timestamp granularity)
 *   * node wall clock, beacon lost for 24 h:      +/- 0.5 s
 *   * gateway wall clock vs UTC:                  +/- 1 s   (NTP over the
 *         WAN with no PPS; we do not claim better than that and the gateway
 *         publishes CLOCK_UNSYNCED when it cannot reach a server)
 *   * two nodes in the same panel, relative event timing: +/- 120 us
 *
 * We do NOT claim absolute microsecond timestamps.  The number that matters
 * for arc/PD correlation is the RELATIVE one, and that one is good because
 * it rides on the grid, not on our crystal.
 * ========================================================================== */

#include "node.h"

/* ---------------------------------------------------------------------- */
/* CRC-16/CCITT-FALSE.  Bitwise: 35 bytes x 8 = 280 iterations, ~1400
 * cycles, 30 us at 48 MHz.  A 512-byte table would be faster and would cost
 * more flash than the whole duty-cycle limiter; the STM32WL also has a
 * hardware CRC unit that the target port uses instead.
 * ---------------------------------------------------------------------- */
uint16_t pg_crc16(const uint8_t *p, int n)
{
    uint16_t crc = 0xFFFFu;
    int i, b;
    for (i = 0; i < n; i++) {
        crc ^= (uint16_t)p[i] << 8;
        for (b = 0; b < 8; b++)
            crc = (crc & 0x8000u) ? (uint16_t)((crc << 1) ^ 0x1021u) : (uint16_t)(crc << 1);
    }
    return crc;
}

/* ---------------------------------------------------------------------- */
/* Frame codec.  Little endian, fixed 35 bytes, no padding, no struct
 * punning - the wire layout is written out byte by byte so a compiler's
 * alignment choices can never change it.
 *
 *   0      magic 'P'
 *   1      version<<4 | msgtype
 *   2..3   node_id
 *   4..7   seq
 *   8      boot
 *   9..12  ts (epoch seconds)
 *   13..14 flags (low 16 bits of PG_F_*)
 *   15     cadence<<6 | trigger<<0   (6 trigger bits, 3 cadence values)
 *   16..17 t_mean_lsb
 *   18..19 t_min_lsb
 *   20..21 t_max_lsb
 *   22..23 theta_lsb clipped to int16 (0x8000 = invalid / no sibling)
 *   24..25 slope, mK/day, clipped to int16
 *   26..28 i_rms_ma, unsigned 24-bit (0xFFFFFF = no CT on this node)
 *   29..30 vbat_mv
 *   31     rssi of the last peer/gateway frame, dBm
 *   32     mcu temperature, degC
 *   33..34 crc16 over bytes 0..32
 * ---------------------------------------------------------------------- */

#define PG_FRAME_LEN  35

static void put16(uint8_t *b, int off, uint16_t v)
{
    b[off]     = (uint8_t)(v & 0xFFu);
    b[off + 1] = (uint8_t)(v >> 8);
}
static void put32(uint8_t *b, int off, uint32_t v)
{
    b[off]     = (uint8_t)(v & 0xFFu);
    b[off + 1] = (uint8_t)((v >> 8) & 0xFFu);
    b[off + 2] = (uint8_t)((v >> 16) & 0xFFu);
    b[off + 3] = (uint8_t)((v >> 24) & 0xFFu);
}
static uint16_t get16(const uint8_t *b, int off)
{
    return (uint16_t)(b[off] | ((uint16_t)b[off + 1] << 8));
}
static uint32_t get32(const uint8_t *b, int off)
{
    return (uint32_t)b[off] | ((uint32_t)b[off + 1] << 8)
         | ((uint32_t)b[off + 2] << 16) | ((uint32_t)b[off + 3] << 24);
}

static int16_t clip16(int32_t v)
{
    if (v > 32767) return 32767;
    if (v < -32767) return -32767;
    return (int16_t)v;
}

int pg_frame_encode(const pg_frame_t *f, uint8_t *out, int cap)
{
    uint32_t irms;
    int16_t  th;

    if (cap < PG_FRAME_LEN) return -1;

    out[0] = PG_FRAME_MAGIC;
    out[1] = (uint8_t)((PG_PROTO_VERSION << 4) | (f->msgtype & 0x0Fu));
    put16(out, 2, f->node_id);
    put32(out, 4, f->seq);
    out[8] = f->boot;
    put32(out, 9, f->ts);
    put16(out, 13, (uint16_t)(f->flags & 0xFFFFu));
    out[15] = (uint8_t)(((f->cadence & 0x03u) << 6) | (f->trig & 0x3Fu));
    put16(out, 16, (uint16_t)clip16(f->t_mean_lsb));
    put16(out, 18, (uint16_t)clip16(f->t_min_lsb));
    put16(out, 20, (uint16_t)clip16(f->t_max_lsb));

    th = (f->theta_lsb == PG_THETA_INVALID) ? (int16_t)0x8000 : clip16(f->theta_lsb);
    put16(out, 22, (uint16_t)th);
    put16(out, 24, (uint16_t)clip16(f->slope_mk_d));

    irms = (f->i_rms_ma < 0) ? 0xFFFFFFu : (uint32_t)f->i_rms_ma;
    if (irms > 0xFFFFFFu) irms = 0xFFFFFFu;
    out[26] = (uint8_t)(irms & 0xFFu);
    out[27] = (uint8_t)((irms >> 8) & 0xFFu);
    out[28] = (uint8_t)((irms >> 16) & 0xFFu);

    put16(out, 29, f->vbat_mv);
    out[31] = (uint8_t)f->rssi_dbm;
    out[32] = (uint8_t)f->mcu_c;
    put16(out, 33, pg_crc16(out, 33));
    return PG_FRAME_LEN;
}

int pg_frame_decode(const uint8_t *in, int len, pg_frame_t *f)
{
    uint32_t irms;
    int16_t  th;

    if (len < PG_FRAME_LEN)          return -1;
    if (in[0] != PG_FRAME_MAGIC)     return -2;
    if ((in[1] >> 4) != PG_PROTO_VERSION) return -3;
    if (get16(in, 33) != pg_crc16(in, 33)) return -4;

    f->msgtype   = (uint8_t)(in[1] & 0x0Fu);
    f->node_id   = get16(in, 2);
    f->seq       = get32(in, 4);
    f->boot      = in[8];
    f->ts        = get32(in, 9);
    f->flags     = get16(in, 13);
    f->cadence   = (uint8_t)((in[15] >> 6) & 0x03u);
    f->trig      = (uint8_t)(in[15] & 0x3Fu);
    f->t_mean_lsb = (int16_t)get16(in, 16);
    f->t_min_lsb  = (int16_t)get16(in, 18);
    f->t_max_lsb  = (int16_t)get16(in, 20);

    th = (int16_t)get16(in, 22);
    f->theta_lsb = (th == (int16_t)0x8000) ? PG_THETA_INVALID : (int32_t)th;
    f->slope_mk_d = (int16_t)get16(in, 24);

    irms = (uint32_t)in[26] | ((uint32_t)in[27] << 8) | ((uint32_t)in[28] << 16);
    f->i_rms_ma = (irms == 0xFFFFFFu) ? -1 : (int32_t)irms;

    f->vbat_mv = get16(in, 29);
    f->rssi_dbm = (int8_t)in[31];
    f->mcu_c    = (int8_t)in[32];
    return PG_FRAME_LEN;
}

/* ---------------------------------------------------------------------- */
/* Airtime and duty cycle                                                  */
/* ---------------------------------------------------------------------- */

/* LoRa modem settings.  Fixed at compile time so airtime is a pure integer
 * function with no runtime configuration to drift out of step with the
 * regulator's arithmetic. */
#define PG_LORA_SF        7
#define PG_LORA_BW_HZ     125000u
#define PG_LORA_CR        1        /* 4/5                                   */
#define PG_LORA_PREAMBLE  8
#define PG_LORA_DE        0        /* low-data-rate optimise off at SF7      */

uint32_t pg_airtime_ms(int payload_len)
{
    /* Tsym = 2^SF / BW.  At SF7 BW125 that is exactly 1024 us. */
    uint32_t tsym_us = (uint32_t)(((uint64_t)(1u << PG_LORA_SF) * 1000000u) / PG_LORA_BW_HZ);
    /* Tpreamble = (npreamble + 4.25) * Tsym, done in quarters to stay integer. */
    uint32_t tpre_us = ((uint32_t)PG_LORA_PREAMBLE * 4u + 17u) * tsym_us / 4u;
    int32_t  num = 8 * payload_len - 4 * PG_LORA_SF + 28 + 16;   /* CRC on, explicit header */
    int32_t  den = 4 * (PG_LORA_SF - 2 * PG_LORA_DE);
    uint32_t symb = 8;
    uint32_t total_us;

    if (num > 0 && den > 0) {
        int32_t ceil_div = (num + den - 1) / den;
        symb += (uint32_t)ceil_div * (uint32_t)(PG_LORA_CR + 4);
    }
    total_us = tpre_us + symb * tsym_us;
    return (total_us + 999u) / 1000u;      /* round up: never under-report */
}

/* Sliding-window duty limiter.  12 buckets of 300 s cover one hour, which is
 * the ETSI observation window.  Bucket granularity means we are at worst
 * 300 s pessimistic, never optimistic - the right direction for a limit. */
#define PG_DUTY_BUCKETS   12
#define PG_DUTY_BUCKET_S  (PG_DUTY_WINDOW_S / PG_DUTY_BUCKETS)

static uint32_t s_duty_ms[PG_DUTY_BUCKETS];
static uint32_t s_duty_epoch[PG_DUTY_BUCKETS];

static void duty_age(uint32_t now)
{
    int i;
    for (i = 0; i < PG_DUTY_BUCKETS; i++)
        if (s_duty_epoch[i] != 0 && (now - s_duty_epoch[i]) >= PG_DUTY_WINDOW_S) {
            s_duty_ms[i] = 0;
            s_duty_epoch[i] = 0;
        }
}

uint32_t pg_duty_used_ms(uint32_t now)
{
    uint32_t sum = 0;
    int i;
    duty_age(now);
    for (i = 0; i < PG_DUTY_BUCKETS; i++) sum += s_duty_ms[i];
    return sum;
}

int pg_duty_allow(uint32_t now, uint32_t airtime_ms)
{
    uint32_t budget = PG_DUTY_WINDOW_S * PG_DUTY_PERMILLE;  /* ms in the window */
    return (pg_duty_used_ms(now) + airtime_ms) <= budget;
}

void pg_duty_charge(uint32_t now, uint32_t airtime_ms)
{
    uint32_t slot = (now / PG_DUTY_BUCKET_S) % PG_DUTY_BUCKETS;
    duty_age(now);
    if (s_duty_epoch[slot] == 0 || (now - s_duty_epoch[slot]) >= PG_DUTY_BUCKET_S) {
        s_duty_ms[slot] = 0;
        s_duty_epoch[slot] = now - (now % PG_DUTY_BUCKET_S);
    }
    s_duty_ms[slot] += airtime_ms;
}

/* ---------------------------------------------------------------------- */
/* Time                                                                    */
/* ---------------------------------------------------------------------- */

#define PG_BEACON_PERIOD_S   300u
/* Residual crystal error after temperature compensation, ppm.  This is not
 * the crystal's spec (+/- 20 ppm at 25 degC plus the parabola); it is what is
 * left after subtracting the stored curve, and it is dominated by the +/- 20 %
 * spread on k and the +/- 5 degC spread on T0, not by the ADC. */
#define PG_XTAL_RESIDUAL_PPM 5u
/* LoRa symbol-boundary granularity on the beacon timestamp, ms. */
#define PG_BEACON_GRAN_MS    1u

void pg_time_init(pg_time_t *t)
{
    t->epoch = 0;
    t->local_ms = 0;
    t->ppm_q10 = 0;
    t->beacons = 0;
    t->cycles = 0;
    t->period_us = 20000;      /* 50 Hz nominal until we measure one */
    t->last_zc_us = 0;
    t->synced = 0;
    t->mains_ok = 0;
}

void pg_time_beacon(pg_time_t *t, uint32_t gw_epoch, uint32_t local_ms)
{
    /* Measure our own drift against the gateway before adopting its time:
     * (what we thought it was) - (what it is) over the elapsed interval. */
    if (t->synced && local_ms > t->local_ms) {
        uint32_t dt_ms = local_ms - t->local_ms;
        int32_t  ours  = (int32_t)(t->epoch + dt_ms / 1000u);
        int32_t  err_s = ours - (int32_t)gw_epoch;
        if (dt_ms >= 60000u) {
            /* ppm, Q10.  err_s seconds over dt_ms/1000 seconds. */
            int64_t ppm_q10 = ((int64_t)err_s * 1000000LL * 1024LL) / (int64_t)(dt_ms / 1000u);
            if (ppm_q10 >  200LL * 1024LL) ppm_q10 =  200LL * 1024LL;
            if (ppm_q10 < -200LL * 1024LL) ppm_q10 = -200LL * 1024LL;
            t->ppm_q10 = (int32_t)ppm_q10;
        }
    }
    t->epoch = gw_epoch;
    t->local_ms = local_ms;
    t->synced = 1;
    t->beacons++;
}

void pg_time_zero_cross(pg_time_t *t, uint32_t period_us)
{
    /* Sanity gate: 45-65 Hz.  A capacitive pickup in a panel also sees
     * switching transients, and a 3 us "period" is a transient, not a grid. */
    if (period_us < 15384u || period_us > 22222u) return;
    t->period_us = period_us;
    t->cycles++;
    t->mains_ok = 1;
}

uint32_t pg_time_now(const pg_time_t *t, uint32_t local_ms)
{
    if (!t->synced) return 0;
    if (local_ms < t->local_ms) return t->epoch;      /* uptime wrapped */
    return t->epoch + (local_ms - t->local_ms) / 1000u;
}

uint32_t pg_time_error_ms(const pg_time_t *t, uint32_t since_s)
{
    /* Free-run error = residual ppm * elapsed, plus the beacon timestamp
     * granularity.  Reported as a worst case, not an RMS - a monitoring
     * system that quotes its own timing as an RMS is quoting the number that
     * makes it look good rather than the one an incident review needs. */
    uint64_t drift_ms = ((uint64_t)PG_XTAL_RESIDUAL_PPM * (uint64_t)since_s * 1000ull)
                        / 1000000ull;
    if (!t->synced) return 0xFFFFFFFFu;
    if (drift_ms > 0xFFFFF000ull) return 0xFFFFFFFFu;
    return (uint32_t)drift_ms + PG_BEACON_GRAN_MS;
}

uint32_t pg_time_phase_q16(const pg_time_t *t, uint32_t us_since_zc)
{
    uint64_t q;
    if (t->period_us == 0) return 0;
    if (us_since_zc >= t->period_us) us_since_zc %= t->period_us;
    q = ((uint64_t)us_since_zc << 16) / t->period_us;
    return (uint32_t)(q & 0xFFFFu);
}

int32_t pg_xtal_ppm_q10(int16_t t_c10)
{
    /* Tuning-fork parabola: df/f = -k (T - T0)^2, k = 0.034 ppm/degC^2,
     * T0 = 25 degC.  Input is tenths of a degree, output is Q10 ppm.
     *   ppm      = -34 * dt_c10^2 / 100000
     *   ppm_q10  = -34 * 1024 * dt_c10^2 / 100000
     * dt_c10 reaches 350 in a hot panel, so dt^2 = 122500 and the numerator
     * is 4.3e9 - it needs the 64-bit intermediate, and it gets one. */
    int64_t dt = (int64_t)t_c10 - 250;
    int64_t v  = -(34LL * 1024LL * dt * dt) / 100000LL;
    if (v < -200LL * 1024LL) v = -200LL * 1024LL;
    return (int32_t)v;
}

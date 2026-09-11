/* ==========================================================================
 * PANO GOZ - PRPD binning on the node.  NO LOGARITHM IS EVER COMPUTED.
 *
 * THE WHOLE POINT
 * ---------------
 * A phase-resolved partial discharge pattern is normally built by taking
 * 20*log10(q) of every pulse.  On a Li-SOCl2-powered node at 10 kpulse/s that
 * is 10 000 logarithms per second, which is not affordable and not necessary,
 * because THE LOGARITHM ALREADY HAPPENED IN THE ANALOGUE DETECTOR.  The
 * AD8318 is a demodulating logarithmic amplifier: its output voltage is
 * linear in the input power in dB, at 24 mV/dB over a 60 dB range.  So the
 * ADC reading IS the dB value, up to a scale and an offset, and binning it is
 * a SUBTRACT and a SHIFT.
 *
 *   Amplitude, shipped board (PG_PRPD_FE_DIVIDER)
 *     A 0.859 resistive divider between the AD8318 output and the 12-bit
 *     3.3 V ADC (805.664 uV/LSB) makes the effective slope exactly
 *     25.6 ADC LSB per dB.  One 2.5 dB amplitude bin is then exactly
 *     2.5 * 25.6 = 64 ADC LSB = 1 << 6.
 *         bin = (adc - adc0) >> 6
 *     One subtract, one shift.  This is the variant panogoz/sim/prpd.py
 *     models and the one the wire format assumes.
 *
 *   Amplitude, bare board (PG_PRPD_FE_RAW)
 *     Without the divider the slope is 24000 uV/dB / 805.664 uV/LSB
 *     = 29.79 ADC LSB per dB, so one 2.5 dB bin is 74.47 LSB, which is not a
 *     power of two.  Dividing by 74.47 is a Q16 multiply by
 *     65536 / 74.4697 = 880.0:
 *         bin = ((adc - adc0) * 880) >> 16
 *     One subtract, one multiply, one shift.  Still no divide, still no log.
 *
 *   Phase
 *     ONE DIVIDE PER MAINS CYCLE, not per pulse.  The zero-cross comparator
 *     latches the free-running timer; pg_prpd_new_cycle() takes the measured
 *     period and computes the reciprocal
 *         recip = ceil( (64 << 24) / period_ticks )
 *     once.  Every pulse in that cycle is then
 *         bin = (dt_ticks * recip) >> 24
 *     which is one multiply and one shift.  The ceiling (rather than a plain
 *     truncation) is deliberate: with a truncated reciprocal the exact
 *     half-cycle point lands one bin low, and the half-cycle is precisely
 *     where the two mechanisms we are trying to separate live.
 *
 * WHERE THE PULSES SIT IS THE DISCRIMINATOR, NOT HOW BIG THEY ARE
 * ----------------------------------------------------------------
 *   * Voltage-driven discharge (void, surface, corona) ignites while the
 *     applied field is high and STILL RISING, so it clusters on the RISING
 *     SLOPES OF THE VOLTAGE, ahead of the voltage peaks.
 *   * A series micro-arc across a degrading bolted joint is CURRENT driven.
 *     It extinguishes when the current through it collapses and reignites
 *     when the recovery voltage is re-established, so its pulses cluster
 *     around the CURRENT ZERO CROSSINGS, at phi and 180+phi where
 *     phi = acos(cos_phi).  They do NOT follow the current peaks.
 *
 * HONESTY
 * -------
 * At 400 V classical partial discharge does not occur - the Paschen minimum
 * for air is 327 V.  What this channel measures at LV is loose-joint
 * micro-arcing.  It is reported as a pC-EQUIVALENT in dB, it is NOT IEC
 * 60270 traceable, and at LV it is NEVER a dispatch channel on its own: it
 * only corroborates a thermal finding.  The node's job here is to ship a
 * histogram, not to reach a conclusion.
 * ========================================================================== */

#include "node.h"

void pg_prpd_init(pg_prpd_t *p, pg_prpd_fe_t fe, uint16_t amp_offset_lsb)
{
    int i;
    for (i = 0; i < PG_PRPD_CELLS; i++) p->cell[i] = 0;
    p->cycles = 0;
    p->pulses = 0;
    p->dropped = 0;
    p->period_ticks = 0;
    p->recip_q16 = 0;
    p->amp_offset_lsb = amp_offset_lsb;
    p->fe = (uint8_t)fe;
    /* 5 pC-equivalent field threshold = 20*log10(5) = 13.98 dB(pC),
     * and 13.98 / 2.5 dB per bin = bin 5. */
    p->thr_bin = 5;
}

void pg_prpd_clear(pg_prpd_t *p)
{
    int i;
    for (i = 0; i < PG_PRPD_CELLS; i++) p->cell[i] = 0;
    p->cycles = 0;
    p->pulses = 0;
    p->dropped = 0;
}

/* Called from the zero-cross ISR.  THIS is the only divide in the PRPD path,
 * and it runs 50 times a second, not 10 000. */
void pg_prpd_new_cycle(pg_prpd_t *p, uint32_t period_ticks)
{
    if (period_ticks == 0) { p->recip_q16 = 0; return; }
    p->period_ticks = period_ticks;
    /* recip = ceil( NPHASE << 24 / period ).  Named _q16 in the struct for
     * historical reasons; the shift is 24 and is spelled out below. */
    p->recip_q16 = (uint32_t)((((uint64_t)PG_PRPD_NPHASE << 24) + period_ticks - 1u)
                              / period_ticks);
    p->cycles++;
}

uint8_t pg_prpd_phase_bin(const pg_prpd_t *p, uint32_t dt_ticks)
{
    uint32_t b;
    if (p->recip_q16 == 0) return 0;
    if (dt_ticks >= p->period_ticks) dt_ticks = p->period_ticks - 1u;
    /* (dt * recip) is bounded by (NPHASE << 24) * (1 + 1/period), i.e. about
     * 1.07e9, so it never overflows uint32 and needs no 64-bit intermediate. */
    b = (dt_ticks * p->recip_q16) >> 24;
    if (b >= PG_PRPD_NPHASE) b = PG_PRPD_NPHASE - 1u;
    return (uint8_t)b;
}

uint8_t pg_prpd_amp_bin(const pg_prpd_t *p, uint16_t adc_lsb)
{
    uint32_t raw, b;

    /* The offset subtraction also absorbs the AD8318's INVERTED slope: the
     * front end puts a unity-gain inverting buffer between the detector and
     * the divider, so a bigger discharge is a bigger ADC code and the
     * calibration constant is the code at 0 dB(pC) = 1 pC-equivalent. */
    raw = (adc_lsb > p->amp_offset_lsb) ? (uint32_t)(adc_lsb - p->amp_offset_lsb) : 0u;

    if (p->fe == PG_PRPD_FE_DIVIDER) {
        b = raw >> PG_AMP_BIN_SHIFT;               /* 64 ADC LSB per 2.5 dB */
    } else {
        b = (raw * PG_AMP_BIN_RECIP_Q16) >> 16;    /* 74.47 LSB per 2.5 dB  */
    }
    if (b >= PG_PRPD_NAMP) b = PG_PRPD_NAMP - 1u;
    return (uint8_t)b;
}

void pg_prpd_pulse(pg_prpd_t *p, uint32_t dt_ticks, uint16_t adc_lsb)
{
    uint8_t  ab = pg_prpd_amp_bin(p, adc_lsb);
    uint8_t  pb;
    uint16_t *c;

    if (ab < p->thr_bin) { p->dropped++; return; }   /* below the field threshold */
    pb = pg_prpd_phase_bin(p, dt_ticks);

    /* Phase-major, exactly like the numpy array the server unpacks:
     * hist[phase][amp] flattened row-major. */
    c = &p->cell[(uint32_t)pb * PG_PRPD_NAMP + ab];
    if (*c != 0xFFFFu) (*c)++;                       /* saturating, never wraps */
    p->pulses++;
}

uint32_t pg_prpd_occupied(const pg_prpd_t *p)
{
    uint32_t n = 0;
    int i;
    for (i = 0; i < PG_PRPD_CELLS; i++) if (p->cell[i]) n++;
    return n;
}

/* ---------------------------------------------------------------------- */
/* Wire format: sparse RLE + LEB128 varint.
 * Byte-identical to panogoz.sim.prpd.pack() / unpack():
 *   "PG" ver varint(n_phase) varint(n_amp)
 *   then records of  varint(zeros_skipped) varint(run_len) run_len*varint(v)
 *   over the row-major flattening; trailing zeros are implicit.
 *
 * A PRPD is mostly empty, so this is lossless and small.  It is NOT always
 * small enough for one radio frame: a healthy panel packs to 340-380 bytes,
 * a surface-tracking record occupies over half the grid and needs ~1.7 kB.
 * The node therefore fragments a PRPD record over several PG_MSG_PRPD frames
 * and the gateway reassembles.  We report the measured size rather than a
 * marketing number.
 * ---------------------------------------------------------------------- */

static int pg_put_varint(uint8_t *out, int cap, int pos, uint32_t v)
{
    for (;;) {
        uint8_t b = (uint8_t)(v & 0x7Fu);
        v >>= 7;
        if (pos >= cap) return -1;
        out[pos++] = (uint8_t)(b | (v ? 0x80u : 0x00u));
        if (!v) return pos;
    }
}

int pg_prpd_pack(const pg_prpd_t *p, uint8_t *out, int cap)
{
    int      pos = 0;
    uint32_t i = 0, n = PG_PRPD_CELLS;

    if (cap < 5) return -1;
    out[pos++] = 'P';
    out[pos++] = 'G';
    out[pos++] = 1;                       /* _PACK_VERSION */
    pos = pg_put_varint(out, cap, pos, PG_PRPD_NPHASE);
    if (pos < 0) return -1;
    pos = pg_put_varint(out, cap, pos, PG_PRPD_NAMP);
    if (pos < 0) return -1;

    while (i < n) {
        uint32_t z = 0, start;
        while (i < n && p->cell[i] == 0) { z++; i++; }
        start = i;
        while (i < n && p->cell[i] != 0) i++;
        if (i == start) break;            /* trailing zeros, implicit */
        pos = pg_put_varint(out, cap, pos, z);
        if (pos < 0) return -1;
        pos = pg_put_varint(out, cap, pos, i - start);
        if (pos < 0) return -1;
        while (start < i) {
            pos = pg_put_varint(out, cap, pos, p->cell[start++]);
            if (pos < 0) return -1;
        }
    }
    return pos;
}

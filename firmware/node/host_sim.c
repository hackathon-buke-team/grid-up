/* ==========================================================================
 * PANO GOZ - host implementation of the hardware abstraction layer
 *
 * This file exists so that the EXACT SAME firmware source that targets an
 * STM32WLE5CC can be compiled with gcc, run on a laptop, and shown to a
 * judge.  Nothing in main.c, theta_edge.c, prpd_bin.c, radio.c or power.c
 * knows whether it is running on silicon or here: they call hal_* and this
 * file answers.  On the target the same prototypes are answered by
 * port/stm32wle5/hal_stm32.c against the CubeWL LL drivers.
 *
 * The virtual panel behind these HAL calls is a deliberately SMALL integer
 * model - one feeder, three phases, one joint that can be made to degrade.
 * It is not the real simulator; panogoz/sim/ is, and it is 4000 lines of
 * Python with a fleet, weather and an acceptance-tested load generator.
 * This one exists to exercise the FIRMWARE, and it is integer-only and
 * seeded so a run is reproducible to the bit.
 *
 * THERE IS NO WALL CLOCK IN HERE.  hal_sleep_ms() advances a virtual clock;
 * every timebase is an explicit argument.  Two runs with the same seed
 * produce identical output, which is what makes this a test rather than a
 * demo.
 * ========================================================================== */

#define __USE_MINGW_ANSI_STDIO 1
#include <stdio.h>
#include <stdarg.h>
#include <string.h>
#include <stdlib.h>

#include "node.h"

/* ---------------------------------------------------------------------- */
/* Deterministic PRNG - xorshift32.  No rand(), no time(), no float.       */
/* ---------------------------------------------------------------------- */

static uint32_t s_rng = 0x9E3779B9u;

static uint32_t rnd32(void)
{
    uint32_t x = s_rng;
    x ^= x << 13;
    x ^= x >> 17;
    x ^= x << 5;
    s_rng = x;
    return x;
}
/* Uniform in [-span, +span]. */
static int32_t rnd_sym(int32_t span)
{
    if (span <= 0) return 0;
    return (int32_t)(rnd32() % (uint32_t)(2 * span + 1)) - span;
}

/* ---------------------------------------------------------------------- */
/* Scenario                                                                */
/* ---------------------------------------------------------------------- */

typedef enum {
    SC_HEALTHY = 0, SC_DRIFT, SC_STEP, SC_DEENERGISED, SC_LOWBAT,
    SC_MOUNTLOST, SC_BURST, SC_OUTAGE, SC_OTA, SC_PRPD, SC_ENERGY, SC_ALL,
    SC_COUNT
} scenario_t;

static const char *const sc_names[SC_COUNT] = {
    "healthy", "drift", "step", "deenergised", "lowbat",
    "mountlost", "burst", "outage", "ota", "prpd", "energy", "all"
};
static const char *const sc_tr[SC_COUNT] = {
    "Saglikli pano - hicbir sey olmuyor (negatif kontrol)",
    "Civata yavas gevsiyor - temas direnci gunler icinde tirmaniyor",
    "Ani basamak - bir pabuc birden bozuluyor",
    "Pano enerjisiz - OG tarafindan kesildi, tum isil gostergeler gecersiz",
    "Pil bitiyor - hayatta kalma kadansi, mutlak limitler acik kaliyor",
    "Kelepce dustu - sicaklik akimdan koptu",
    "Olay patlamasi - mutlak sicaklik limiti asildi",
    "Ag gecidi ulasilamiyor - FRAM halkasi doluyor, sonra bosaliyor",
    "OTA durum makinesi - enerji kapisi, deneme ve geri alma",
    "PRPD biriktirme ve paketleme",
    "Sadece enerji butcesi tablosu",
    "Hepsi (kisa)"
};

/* ---------------------------------------------------------------------- */
/* Virtual panel                                                           */
/* ---------------------------------------------------------------------- */

/* Feeder 6 of a TEDAS 1600 kVA panel: 400 A DSYA, 2 Boy.  Three cable lugs
 * in the bottom compartment, each with a thermal clip and its own split-core
 * CT - because NO outgoing way in this panel has a utility CT (the 2500/5
 * measures the incomer only). */
#define VP_I_REF_A      400
#define VP_PEAK_MA      300000       /* 300 A at the daily peak             */

/* Daily load shape, permille of peak, per hour.  A Turkish LV secondary
 * feeder: an evening peak, a 03:00 trough, and never anything like flat. */
static const uint16_t vp_shape[24] = {
    420, 380, 355, 350, 360, 400, 470, 560, 640, 690, 720, 740,
    760, 750, 730, 720, 760, 850, 960,1000, 980, 880, 700, 520
};

/* Per-phase unbalance.  20-40 % is ROUTINE on these feeders and assuming
 * balance is how a monitoring system invents faults; here it is mild so the
 * healthy theta is visibly, honestly, near zero. */
static const uint16_t vp_phase[3] = { 1000, 950, 1060 };   /* L1 L2 L3, permille */

typedef struct {
    scenario_t sc;
    uint32_t   t_ms;            /* virtual monotonic clock, ms              */
    uint32_t   epoch0;          /* wall clock at t_ms == 0                  */
    uint32_t   hours;           /* run length                               */

    int32_t    r_uohm[3];       /* joint resistance per phase, micro-ohm    */
    int32_t    t_joint[3];      /* lagged joint temperature, LSB            */
    int32_t    i_ma[3];
    int32_t    ambient_lsb;

    uint8_t    mains_ok;
    uint8_t    mount_ok;
    uint8_t    gw_up;
    uint16_t   vbat_mv;
    uint32_t   last_beacon;
    uint32_t   pending_ack;     /* set when the node just transmitted       */
    int16_t    relay_median;

    uint8_t    fram[PG_FRAM_SIZE];
    uint32_t   fram_writes;
    uint32_t   reset_cause;

    /* OTA stub accounting */
    uint32_t   slot_bytes[2];
    uint32_t   slot_crc[2];
    uint8_t    trial_slot;
    uint8_t    trial_cycles;

    uint32_t   tx_frames;
    uint32_t   rx_frames;
    uint32_t   wdt_kicks;
    uint8_t    verbose;
} vpanel_t;

static vpanel_t VP;

/* --- helpers ---------------------------------------------------------- */

static uint32_t vp_now_s(void)  { return VP.epoch0 + VP.t_ms / 1000u; }
static uint32_t vp_hour(void)   { return (vp_now_s() / 3600u) % 24u; }
static uint32_t vp_elapsed_s(void) { return VP.t_ms / 1000u; }

/* Ambient inside the bottom cable compartment, LSB.  Tablo 1 gives 40 C max
 * and a 35 C 24 h mean for the dahili type; the compartment sits a few
 * kelvin above the room because the panel bottom opens onto a cable trench
 * that is cooler at night and the fuse bases are above. */
static int32_t vp_ambient_lsb(void)
{
    uint32_t h = vp_hour();
    int32_t  base = 24 * PG_LSB_PER_K;
    int32_t  swing = ((int32_t)h >= 6 && (int32_t)h <= 18)
                   ? (int32_t)((h - 6) * (18 - h)) : 0;          /* 0..36 */
    return base + swing * 12 + rnd_sym(8);
}

static int32_t vp_current_ma(int phase)
{
    uint32_t h = vp_hour();
    int64_t  v = (int64_t)VP_PEAK_MA * vp_shape[h] / 1000;
    v = v * vp_phase[phase] / 1000;
    /* +/- 4 % of minute-to-minute wander */
    v += (int64_t)rnd_sym((int32_t)(v / 25));
    if (!VP.mains_ok) return 0;
    return (int32_t)v;
}

/* Steady-state joint temperature, LSB.
 *   P[mW]    = i_ma^2 * r_uohm / 1e9          (400 A at 50 uohm -> 8000 mW)
 *   dT[LSB]  = P[mW] * R_th_x10 * 128 / 10000 (R_th = 3.0 K/W for a lug)
 * plus a common air rise that scales with the panel load and cancels in the
 * sibling difference - which is the entire point of theta. */
#define VP_RTH_X10   30

static int32_t vp_joint_ss_lsb(int phase)
{
    int64_t p_mw, rise, air;
    int64_t i = VP.i_ma[phase];
    int64_t f_permille;

    p_mw = (i * i) / 1000000LL * VP.r_uohm[phase] / 1000LL;   /* == i^2*r/1e9 */
    rise = p_mw * VP_RTH_X10 * PG_LSB_PER_K / 10000LL;

    f_permille = (i * 1000LL) / (VP_I_REF_A * 1000LL);
    air = (int64_t)20 * PG_LSB_PER_K * f_permille * f_permille / 1000000LL;

    return (int32_t)(VP.ambient_lsb + air + rise);
}

/* First-order lag, tau = 900 s for a bolted lug on 240 mm2 cable. */
static void vp_advance(uint32_t dt_s)
{
    int p;
    VP.ambient_lsb = vp_ambient_lsb();
    for (p = 0; p < 3; p++) {
        int32_t ss;
        VP.i_ma[p] = vp_current_ma(p);
        ss = vp_joint_ss_lsb(p);
        if (dt_s == 0) { VP.t_joint[p] = ss; continue; }
        VP.t_joint[p] += (int32_t)(((int64_t)(ss - VP.t_joint[p]) * dt_s) / (int64_t)(dt_s + 900u));
    }
    /* The gateway hears all three clips, so the relayed sibling median for
     * our node (L1) is the median of L2 and L3 - SELF EXCLUDED. */
    VP.relay_median = (int16_t)((VP.t_joint[1] + VP.t_joint[2]) / 2);
}

/* --- scenario injection, applied once per virtual second block --------- */
static void vp_scenario_tick(uint32_t dt_s)
{
    uint32_t el = vp_elapsed_s();
    uint32_t total = VP.hours * 3600u;

    switch (VP.sc) {
    case SC_DRIFT: {
        /* A bolt backing off.  3 -> 30 uohm over the run: at 300 A that is
         * 2.7 W and about 8 K of local rise, i.e. a theta that crosses the
         * 5 K notification threshold part way through and keeps climbing.
         * Only L1 degrades; L2 and L3 are the baseline, on installation day,
         * with no history required. */
        int32_t r = 3 + (int32_t)((27LL * el) / (total ? total : 1));
        VP.r_uohm[0] = r;
        break;
    }
    case SC_STEP:
        VP.r_uohm[0] = (el > total / 2) ? 45 : 3;
        break;
    case SC_DEENERGISED:
        VP.mains_ok = (el > total / 3 && el < (2 * total) / 3) ? 0u : 1u;
        break;
    case SC_LOWBAT: {
        /* Walk the cell down through CELL_LOW (3200 mV) into the critical
         * floor (2900 mV) over the run.  A real ER14250 does not do this in
         * a day - it does it over a fortnight at the very end of an
         * eleven-year life - but the STATE TRANSITIONS being shown are the
         * same ones. */
        uint32_t span = total ? total : 1u;
        uint32_t drop = (760u * el) / span;
        VP.vbat_mv = (uint16_t)(3610u - (drop > 760u ? 760u : drop));
        break;
    }
    case SC_MOUNTLOST:
        if (el > total / 3) {
            VP.mount_ok = 0;
            /* The clip has come off the cable: it now reads compartment air,
             * so its temperature DECOUPLES FROM CURRENT.  That is a
             * different signature from a cold joint and the reason
             * MOUNT_LOST exists as a state rather than being reported as a
             * healthy reading. */
            VP.t_joint[0] += (VP.ambient_lsb - VP.t_joint[0]) / 4;
        }
        break;
    case SC_BURST:
        VP.r_uohm[0] = (el > total / 2) ? 230 : 3;   /* ~19 W at 287 A -> >90 C */
        break;
    case SC_OUTAGE:
        VP.gw_up = (el > total / 4 && el < (3 * total) / 4) ? 0u : 1u;
        break;
    default:
        break;
    }
}

/* ==========================================================================
 * HAL implementation
 * ========================================================================== */

void hal_init(void) { }

uint32_t hal_uptime_ms(void) { return VP.t_ms; }
uint32_t hal_uptime_us(void) { return VP.t_ms * 1000u; }

void hal_sleep_ms(uint32_t ms, int deep)
{
    uint32_t s = ms / 1000u;
    (void)deep;
    VP.t_ms += ms;
    vp_scenario_tick(s);
    vp_advance(s);
}

int16_t hal_tmp117_oneshot(void)
{
    /* TMP117: +/- 0.1 C over -20..+50 C, 16-bit, 1 LSB = 1/128 C exactly.
     * We return the RAW register value, never a converted temperature -
     * see the header comment for why. */
    int32_t v;
    if (VP.sc == SC_MOUNTLOST && !VP.mount_ok && (rnd32() & 0x3Fu) == 0)
        return PG_T_FAULT;
    v = VP.t_joint[0] + rnd_sym(18);   /* ~0.14 K 1-sigma per sensor, so a
                                        * PAIR gives the 0.2 K the detector
                                        * assumes */
    if (v > 19200) v = 19200;          /* +150 C, the part's limit */
    if (v < -5120) v = -5120;          /* -40 C                    */
    return (int16_t)v;
}

int16_t hal_air_temp_lsb(void) { return (int16_t)(VP.ambient_lsb + rnd_sym(12)); }

int32_t hal_ct_rms_ma(void)
{
    /* Split-core CT integrated into the clip, sampled over a full 20 ms
     * mains cycle and reduced to a true RMS in the ADC DMA callback.  This
     * CT is the reason the clip can normalise theta at all: the panel's
     * 2500/5 measures the INCOMER only and no outgoing way has a utility CT. */
    if (!VP.mains_ok) return 0;
    return VP.i_ma[0] + rnd_sym(VP.i_ma[0] / 200 + 1);
}

int8_t   hal_mcu_temp_c(void)   { return (int8_t)(VP.ambient_lsb / PG_LSB_PER_K + 3); }
uint16_t hal_vbat_mv(void)      { return VP.vbat_mv; }

uint16_t hal_vbat_loaded_mv(void)
{
    /* 50 mA passivation test pulse.  A healthy ER14250 droops about 200 mV
     * into the HLC; a passivated one collapses. */
    uint16_t droop = 200;
    if (VP.sc == SC_LOWBAT && VP.vbat_mv < 3300u) droop = 700;
    if (VP.vbat_mv <= droop) return 0;
    return (uint16_t)(VP.vbat_mv - droop);
}

int hal_mount_ok(void) { return VP.mount_ok; }

uint32_t hal_mains_period_us(void)
{
    if (!VP.mains_ok) return 0;
    /* 50 Hz +/- 60 ppm of grid wander, plus 1.5 deg of comparator jitter. */
    return 20000u + (uint32_t)(int32_t)rnd_sym(20);
}

int hal_pd_pop(uint32_t *dt_ticks, uint16_t *adc_lsb)
{
    /* PD-01 only.  Micro-arcing across a degrading joint is CURRENT driven:
     * it extinguishes when the current collapses and reignites when the
     * recovery voltage returns, so its pulses cluster around the CURRENT
     * ZERO CROSSINGS at phi and 180+phi, NOT at the current peaks.  At
     * cos phi = 0.95 lagging, phi = 18.19 deg. */
    static uint32_t emitted;
    uint32_t phase_deg;
    if (VP.sc != SC_PRPD && VP.sc != SC_ALL) return 0;
    if (emitted++ > 20000u) { emitted = 0; return 0; }
    if ((rnd32() & 3u) == 0) return 0;

    phase_deg = ((rnd32() & 1u) ? 18u : 198u) + (uint32_t)(int32_t)rnd_sym(11);
    phase_deg %= 360u;
    *dt_ticks = (phase_deg * 20000u) / 360u;                 /* 1 us ticks   */
    /* 20*log10(q) already done by the AD8318: 25.6 ADC LSB per dB, so a
     * 30 pC-equivalent pulse (29.5 dB) is code 755. */
    *adc_lsb = (uint16_t)(600u + (rnd32() % 400u));
    return 1;
}

/* --- FRAM: MB85RS64V, 8 kB, byte-writable, 1e13 endurance --------------- */

int hal_fram_read(uint16_t addr, void *dst, uint16_t n)
{
    if ((uint32_t)addr + n > PG_FRAM_SIZE) return -1;
    memcpy(dst, &VP.fram[addr], n);
    return 0;
}

int hal_fram_write(uint16_t addr, const void *src, uint16_t n)
{
    if ((uint32_t)addr + n > PG_FRAM_SIZE) return -1;
    memcpy(&VP.fram[addr], src, n);
    VP.fram_writes++;
    return 0;
}

/* --- radio -------------------------------------------------------------- */

int hal_radio_tx(const uint8_t *buf, int len)
{
    uint32_t air = pg_airtime_ms(len);
    VP.tx_frames++;
    if (!VP.gw_up) return -1;              /* nobody listening              */
    VP.pending_ack = 1;
    return (int)air;
}

int hal_radio_rx(uint8_t *buf, int cap, uint32_t win_ms)
{
    pg_frame_t f;
    uint32_t now = vp_now_s();
    (void)win_ms;

    if (!VP.gw_up) return 0;

    memset(&f, 0, sizeof f);
    f.i_rms_ma = -1;
    f.theta_lsb = PG_THETA_INVALID;
    f.mcu_c = 25;
    f.vbat_mv = 3600;
    f.ts = now;

    if (VP.pending_ack) {
        VP.pending_ack = 0;
        f.msgtype = PG_MSG_ACK;
        f.node_id = 0xFFFFu;                       /* the gateway            */
        f.t_mean_lsb = VP.relay_median;            /* sibling median relayed */
        VP.rx_frames++;
        return pg_frame_encode(&f, buf, cap);
    }
    if (now - VP.last_beacon >= 300u) {
        VP.last_beacon = now;
        f.msgtype = PG_MSG_BEACON;
        f.node_id = 0xFFFFu;
        f.t_mean_lsb = (int16_t)0x8000;
        VP.rx_frames++;
        return pg_frame_encode(&f, buf, cap);
    }
    return 0;
}

int8_t hal_radio_rssi(void)
{
    /* Bottom cable compartment to roof communication bay through a 2 mm
     * galvanised plate: -95 to -105 dBm at 868 MHz with LoRa SF7, i.e.
     * 10-20 dB of margin over the -123 dBm sensitivity. */
    return (int8_t)(-98 + rnd_sym(6));
}

/* --- watchdog / reset --------------------------------------------------- */

void hal_wdt_start(uint32_t ms) { (void)ms; }
void hal_wdt_kick(void)         { VP.wdt_kicks++; }
void hal_wdt_stop(void)         { }
uint32_t hal_reset_cause(void)  { return VP.reset_cause; }
void hal_reboot(void)           { }

/* --- flash: STUB.  See the OTA comment in main.c: the state machine is
 * real, the driver underneath it is not, because there is no ARM toolchain
 * and no silicon here and pretending otherwise would be a lie. ----------- */

int hal_flash_erase_slot(uint8_t slot)
{
    if (slot > 1) return -1;
    VP.slot_bytes[slot] = 0;
    VP.slot_crc[slot] = 0;
    return 0;
}

int hal_flash_write(uint8_t slot, uint32_t off, const uint8_t *p, uint32_t n)
{
    uint32_t i;
    if (slot > 1) return -1;
    for (i = 0; i < n; i++) VP.slot_crc[slot] = VP.slot_crc[slot] * 31u + p[i];
    VP.slot_bytes[slot] = off + n;
    return 0;
}

uint32_t hal_flash_crc32(uint8_t slot, uint32_t len)
{
    (void)len;
    if (slot > 1) return 0;
    return VP.slot_crc[slot] ? VP.slot_crc[slot] : 0xC0FFEE01u;
}

void hal_flash_mark_trial(uint8_t slot, uint8_t cycles)
{
    VP.trial_slot = slot;
    VP.trial_cycles = cycles;
}

/* --- logging ------------------------------------------------------------ */

void hal_log(const char *s) { printf("%s\n", s); }

void hal_logf(const char *fmt, ...)
{
    char buf[512];
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(buf, sizeof buf, fmt, ap);
    va_end(ap);
    printf("%s\n", buf);
}

/* ==========================================================================
 * Scenario drivers
 * ========================================================================== */

static void vp_reset(scenario_t sc, uint32_t seed, uint32_t hours, int verbose)
{
    int p;
    memset(&VP, 0, sizeof VP);
    s_rng = seed ? seed : 1u;
    VP.sc = sc;
    VP.hours = hours;
    VP.epoch0 = 1789000000u;         /* an explicit epoch, never time(NULL) */
    VP.mains_ok = 1;
    VP.mount_ok = 1;
    VP.gw_up = 1;
    VP.vbat_mv = 3610;
    VP.reset_cause = PG_RST_POR;
    VP.verbose = (uint8_t)verbose;
    for (p = 0; p < 3; p++) VP.r_uohm[p] = 3;    /* healthy tinned joint */
    VP.ambient_lsb = vp_ambient_lsb();
    vp_advance(0);
}

static void banner(const char *title)
{
    printf("\n");
    printf("================================================================\n");
    printf(" %s\n", title);
    printf("================================================================\n");
}

/* Run a node through a scenario and narrate it. */
static void run_scenario(scenario_t sc, uint32_t seed, uint32_t hours, int verbose)
{
    static pg_node_t node;      /* static: NO dynamic allocation, anywhere */
    uint32_t wakes = 0, last_report = 0;
    uint32_t prev_cad = 0xFFu;

    vp_reset(sc, seed, hours, verbose);
    banner(sc_tr[sc]);
    printf(" senaryo=%s  seed=%lu  sure=%lu saat  fw=%s\n",
           sc_names[sc], (unsigned long)seed, (unsigned long)hours, PG_FW_STRING);
    printf(" dugum: SOKE-14 / TC-04 / C06-L1-PABUC, 400 A DSYA cikisi\n");
    printf("----------------------------------------------------------------\n");

    pg_node_init(&node, 0x0104, VP_I_REF_A);

    /* Provision the node the way a commissioning engineer would: 64 bytes
     * into FRAM.  One binary serves the whole fleet. */
    {
        uint8_t prov[64];
        memset(prov, 0, sizeof prov);
        prov[0] = 'P';
        prov[1] = (uint8_t)(VP_I_REF_A & 0xFF);
        prov[2] = (uint8_t)(VP_I_REF_A >> 8);
        prov[3] = 1;                                  /* has its own CT */
        strcpy((char *)&prov[4], "C06-L1-PABUC");
        hal_fram_write(PG_FRAM_PROV, prov, sizeof prov);
    }

    while (vp_elapsed_s() < hours * 3600u && wakes < 20000u) {
        pg_state_t before = node.state;
        pg_node_step(&node);
        if (before == PG_ST_SLEEP || before == PG_ST_DE_ENERGISED ||
            before == PG_ST_LOW_BATTERY) {
            wakes++;
            if (node.cadence != prev_cad) {
                char tb[24];
                pg_fmt_scaled(tb, sizeof tb,
                              node.edge.theta_lsb == PG_THETA_INVALID ? 0
                                                                      : node.edge.theta_lsb,
                              PG_LSB_PER_K, 2);
                printf("  t+%5lu dk  KADANS -> %lu s   (theta %s K, tetik: %s)\n",
                       (unsigned long)(vp_elapsed_s() / 60u),
                       (unsigned long)pg_period_s(node.cadence),
                       node.edge.theta_lsb == PG_THETA_INVALID ? "n/a" : tb,
                       pg_trigger_text_tr(node.trig));
                prev_cad = node.cadence;
            }
            if (verbose || vp_elapsed_s() - last_report >= 6u * 3600u) {
                char b1[24], b2[24];
                last_report = vp_elapsed_s();
                pg_fmt_scaled(b1, sizeof b1, node.agg.t_mean_lsb, PG_LSB_PER_K, 2);
                pg_fmt_scaled(b2, sizeof b2,
                              node.edge.theta_lsb == PG_THETA_INVALID ? 0
                                                                      : node.edge.theta_lsb,
                              PG_LSB_PER_K, 2);
                printf("  t+%5lu dk  T=%s C  I=%ld A  theta=%s K  halka=%u\n",
                       (unsigned long)(vp_elapsed_s() / 60u), b1,
                       (long)(node.agg.i_rms_ma / 1000),
                       node.edge.theta_lsb == PG_THETA_INVALID ? "n/a" : b2,
                       (unsigned)pg_ring_depth(&node.ring));
            }
        }
    }

    printf("----------------------------------------------------------------\n");
    printf(" SONUC (%lu uyanma cevrimi, %lu saat sanal zaman)\n",
           (unsigned long)wakes, (unsigned long)(vp_elapsed_s() / 3600u));
    pg_node_report(&node);
    {
        /* Ground truth from the virtual panel.  The node never sees this; it
         * is printed only so the excess-resistance INTERVAL can be checked
         * against the resistance that was actually injected.  An interval
         * that brackets the truth is the honest claim; a point estimate that
         * happens to land near it is not. */
        char bt[24];
        int64_t p_mw = ((int64_t)VP.i_ma[0] * VP.i_ma[0]) / 1000000LL
                       * VP.r_uohm[0] / 1000LL;
        pg_fmt_scaled(bt, sizeof bt, (int32_t)p_mw, 1000, 2);
        printf("  [GERCEK DEGER - dugum bunu asla gormez] enjekte edilen fazla\n"
               "   temas direnci %ld uohm, o andaki kayip %s W. Yukaridaki\n"
               "   ARALIK bu degeri kapsiyorsa kestirim dogrudur.\n",
               (long)(VP.r_uohm[0] - 3), bt);
    }
    {
        char b[24];
        uint32_t err = pg_time_error_ms(&node.clock, 300);
        pg_fmt_scaled(b, sizeof b, (int32_t)pg_duty_used_ms(vp_now_s()), 1000, 2);
        printf("  zaman: %lu isaret alindi, %lu sifir gecisi sayildi, "
               "duvar saati hatasi +/-%lu ms\n",
               (unsigned long)node.clock.beacons, (unsigned long)node.clock.cycles,
               (unsigned long)err);
        printf("  ETSI kullanim orani: %s s / %lu s penceresinde "
               "(sinir %%%u.%u)\n", b, (unsigned long)PG_DUTY_WINDOW_S,
               (unsigned)(PG_DUTY_PERMILLE / 10), (unsigned)(PG_DUTY_PERMILLE % 10));
        /* Endurance, computed rather than asserted.  13 years at the idle
         * cadence is 13*365*96 = 455 520 wake cycles and three FRAM writes
         * each (one record, two alternating header commits), so 1.37 M
         * writes against a 1e13 rating: seven orders of magnitude of
         * headroom.  The same duty on internal flash would erase one 2 kB
         * page 22 times a day and reach its 10 000-cycle rating in about
         * FIFTEEN MONTHS. */
        printf("  FRAM: %lu yazma bu kosumda. 13 yil IDLE kadansta ~1.37 M\n"
               "        yazma; MB85RS64V dayanimi 1e13 -> 7 mertebe pay.\n"
               "        Ayni yuk dahili flash'ta 2 kB sayfayi gunde 22 kez\n"
               "        siler ve 10 000 cevrimlik omrunu ~15 AYDA bitirir.\n",
               (unsigned long)VP.fram_writes);
    }
}

/* --- OTA walk ----------------------------------------------------------- */

static void run_ota(uint32_t seed)
{
    pg_ota_t o;
    pg_power_t pw;
    pg_ota_state_t st;
    int i;

    vp_reset(SC_OTA, seed, 1, 0);
    banner(sc_tr[SC_OTA]);
    printf(" Bir dugumu canli panoda TUGLALAYAMAYAN guncelleme semasi.\n");
    printf(" Bootloader ve kurtarma imaji YAZMA KORUMALI ve hicbir zaman\n"
           " guncellenmez. A/B slot; calisan imaj asla silinmez. Yeni imaj\n"
           " onayi HAK ETMEK zorunda: %d acilis icinde %d onayli cerceve.\n",
           PG_OTA_TRIAL_CYCLES, PG_OTA_TRIAL_ACKS);
    printf("----------------------------------------------------------------\n");

    /* --- 1. energy gate refuses --------------------------------------- */
    pg_power_init(&pw);
    pg_ota_init(&o);
    pg_power_update_cell(&pw, 3150, 2400);        /* low + passivated */
    printf(" 1) Zayif hucre ile teklif:\n");
    st = pg_ota_step(&o, &pw, PG_TRIG_NONE, 1, 0x00010001u, 40000u, 0, 0);
    printf("      %-14s\n", pg_ota_state_name(st));
    st = pg_ota_step(&o, &pw, PG_TRIG_NONE, 1, 0x00010001u, 40000u, 0, 0);
    printf("      %-14s  <- %s\n", pg_ota_state_name(st), pg_ota_reason_tr(o.reason));

    /* --- 2. event gate refuses ---------------------------------------- */
    pg_power_init(&pw);
    pg_power_update_cell(&pw, 3600, 3400);
    printf(" 2) Saglikli hucre ama dugum aktif olay izliyor:\n");
    st = pg_ota_step(&o, &pw, PG_TRIG_THETA, 1, 0x00010001u, 40000u, 0, 0);
    printf("      %-14s  <- %s\n", pg_ota_state_name(st), pg_ota_reason_tr(o.reason));

    /* --- 3. clean path to CONFIRMED ------------------------------------ */
    printf(" 3) Temiz yol (olay yok, hucre iyi):\n");
    for (i = 0; i < 3 && o.state != PG_OTA_DOWNLOADING; i++) {
        st = pg_ota_step(&o, &pw, PG_TRIG_NONE, 1, 0x00010001u, 40000u, 0, 0);
        printf("      %-14s\n", pg_ota_state_name(st));
    }
    for (i = 0; i < 400 && o.state == PG_OTA_DOWNLOADING; i++) {
        st = pg_ota_step(&o, &pw, PG_TRIG_NONE, 0, 0, 0, 1, 0);
    }
    printf("      %-14s  (%lu/%lu bayt, CRC32 0x%08lX)\n",
           pg_ota_state_name((pg_ota_state_t)o.state),
           (unsigned long)o.received, (unsigned long)o.size,
           (unsigned long)o.crc32);
    st = pg_ota_step(&o, &pw, PG_TRIG_NONE, 0, 0, 0, 0, 0);
    printf("      %-14s  (bootloader'a devredildi, deneme sayaci=%u)\n",
           pg_ota_state_name(st), (unsigned)o.trial_left);
    st = pg_ota_step(&o, &pw, PG_TRIG_NONE, 0, 0, 0, 0, 0);
    printf("      %-14s  (slot %c'ye gecildi)\n",
           pg_ota_state_name(st), o.active_slot ? 'B' : 'A');
    for (i = 0; i < PG_OTA_TRIAL_ACKS; i++)
        st = pg_ota_step(&o, &pw, PG_TRIG_NONE, 0, 0, 0, 0, 1);
    printf("      %-14s  <- %s\n", pg_ota_state_name(st), pg_ota_reason_tr(o.reason));

    /* --- 4. the new image never confirms -> automatic revert ------------ */
    printf(" 4) Yeni imaj onay alamiyor (ag gecidine ulasamiyor):\n");
    pg_ota_step(&o, &pw, PG_TRIG_NONE, 0, 0, 0, 0, 0);      /* CONFIRMED->IDLE */
    o.version = 0x00010001u;
    for (i = 0; i < 4 && o.state != PG_OTA_DOWNLOADING; i++)
        pg_ota_step(&o, &pw, PG_TRIG_NONE, 1, 0x00010002u, 40000u, 0, 0);
    for (i = 0; i < 400 && o.state == PG_OTA_DOWNLOADING; i++)
        pg_ota_step(&o, &pw, PG_TRIG_NONE, 0, 0, 0, 1, 0);
    pg_ota_step(&o, &pw, PG_TRIG_NONE, 0, 0, 0, 0, 0);      /* VERIFIED    */
    pg_ota_step(&o, &pw, PG_TRIG_NONE, 0, 0, 0, 0, 0);      /* PENDING_SWAP*/
    printf("      %-14s  (slot %c)\n", pg_ota_state_name((pg_ota_state_t)o.state),
           o.active_slot ? 'B' : 'A');
    for (i = 0; i < PG_OTA_TRIAL_CYCLES + 1; i++) {
        st = pg_ota_step(&o, &pw, PG_TRIG_NONE, 0, 0, 0, 0, 0);   /* no acks */
        printf("      %-14s  deneme kalan=%u\n", pg_ota_state_name(st),
               (unsigned)o.trial_left);
        if (st == PG_OTA_REVERTED) break;
    }
    printf("      <- %s\n", pg_ota_reason_tr(o.reason));
    printf("      Calisan imaj slot %c'de bozulmadan duruyordu: dugum ayakta.\n",
           o.active_slot ? 'B' : 'A');
    printf("----------------------------------------------------------------\n");
    printf(" DURUST NOT: yukaridaki durum makinesi GERCEK ve calisti.\n"
           " Altindaki flash surucusu (hal_flash_*) bu agacta bir TASLAK -\n"
           " bayt sayar ve CRC hesaplar, STM32 flash bankasi programlamaz.\n"
           " Hedef port firmware/README.md icinde tarif edilmistir.\n");
}

/* --- PRPD walk ---------------------------------------------------------- */

/* One PRPD record does not fit in a telemetry frame.  LoRa allows a 255-byte
 * payload; we fragment at 192 so a lost fragment costs 350 ms of airtime to
 * repeat rather than half a second, and so the record still fits a 255-byte
 * radio buffer with a fragment header. */
#define PRPD_FRAG 192

static void run_prpd(uint32_t seed, int dump_hex)
{
    static pg_prpd_t prpd;
    static uint8_t   blob[3072];
    uint32_t dt, cyc;
    uint16_t adc;
    int      n, i, row, col;

    vp_reset(SC_PRPD, seed, 1, 0);
    banner(sc_tr[SC_PRPD]);
    printf(" AD8318 cikisi ZATEN dB cinsinden dogrusal (24 mV/dB), bu yuzden\n"
           " dugum HICBIR YERDE logaritma hesaplamaz. Genlik binleme bir\n"
           " CIKARMA ve bir KAYDIRMA; faz binleme MAINS CEVRIMI BASINA bir\n"
           " bolme (darbe basina degil), onceden hesaplanmis ters carpanla.\n");
    printf("----------------------------------------------------------------\n");

    pg_prpd_init(&prpd, PG_PRPD_FE_DIVIDER, 0);
    for (cyc = 0; cyc < 3000u; cyc++) {          /* 60 s at 50 Hz */
        pg_prpd_new_cycle(&prpd, 20000u);        /* 1 us timer ticks */
        for (i = 0; i < 4; i++)
            if (hal_pd_pop(&dt, &adc)) pg_prpd_pulse(&prpd, dt, adc);
    }

    printf(" biriktirme : %lu cevrim (60 s @ 50 Hz), %lu darbe binlendi, "
           "%lu esik alti\n",
           (unsigned long)prpd.cycles, (unsigned long)prpd.pulses,
           (unsigned long)prpd.dropped);
    printf(" izgara     : %d faz bin x 5.625 derece, %d genlik bin x 2.5 dB\n",
           PG_PRPD_NPHASE, PG_PRPD_NAMP);
    printf(" bellek     : %u bayt (uint16 hucre, doyumlu, asla sarmaz)\n",
           (unsigned)sizeof prpd.cell);
    printf(" dolu hucre : %lu / %d\n",
           (unsigned long)pg_prpd_occupied(&prpd), PG_PRPD_CELLS);

    n = pg_prpd_pack(&prpd, blob, sizeof blob);
    printf(" paketlenmis: %d bayt (seyrek RLE + LEB128 varint, kayipsiz)\n", n);
    printf("              -> %d adet %u baytlik PG_MSG_PRPD parcasi,\n"
           "                 toplam %lu ms hava suresi (saatte bir kayit)\n",
           (n + PRPD_FRAG - 1) / PRPD_FRAG, (unsigned)PRPD_FRAG,
           (unsigned long)(((n + PRPD_FRAG - 1) / PRPD_FRAG)
                           * pg_airtime_ms(PRPD_FRAG + 8)));
    printf("              ilk baytlar: %02X %02X %02X %02X %02X  ('P' 'G' v1 64 32)\n",
           blob[0], blob[1], blob[2], blob[3], blob[4]);
    if (dump_hex) {
        int q;
        printf("PRPD_HEX ");
        for (q = 0; q < n; q++) printf("%02x", blob[q]);
        printf("\n");
    }

    /* Tiny ASCII PRPD so the phase clustering is visible on a terminal. */
    printf("\n faz cozunurlu desen (satir = genlik bin, sutun = 8 faz bin):\n");
    printf("      0     45    90   135   180   225   270   315 derece\n");
    for (row = PG_PRPD_NAMP - 1; row >= 0; row -= 2) {
        uint32_t tot = 0;
        char line[16];
        for (col = 0; col < 8; col++) {
            uint32_t s = 0;
            int k, a;
            for (k = col * 8; k < (col + 1) * 8; k++)
                for (a = row; a >= row - 1 && a >= 0; a--)
                    s += prpd.cell[(uint32_t)k * PG_PRPD_NAMP + a];
            tot += s;
            line[col] = s == 0 ? '.' : (s < 10 ? '-' : (s < 60 ? '+' : (s < 200 ? '*' : '#')));
        }
        line[8] = '\0';
        if (tot || row < 12)
            printf("  %4d dB |%s|\n", (int)(row * 25 / 10), line);
    }
    printf("\n Darbeler 18 ve 198 derece civarinda kumeleniyor: cos phi = 0.95\n"
           " gecikmeli bir yukun AKIM SIFIR GECISLERI. Seri mikro-ark akimla\n"
           " suruluyor - akim TEPELERINI izlemez.\n");
    printf(" DURUSTLUK: 400 V'ta klasik kismi desarj OLMAZ (Paschen minimumu\n"
           " 327 V). Bu kanal gevsek baglanti mikro-arkini olcer, pC-ESDEGERI\n"
           " olarak dB cinsinden raporlanir, IEC 60270 izlenebilir DEGILDIR ve\n"
           " AG'da tek basina asla is emri acmaz - yalnizca isil bulguyu\n"
           " destekler.\n");
}

/* --- self-test of the pure functions ------------------------------------ */

static int expect(const char *what, int32_t got, int32_t want, int32_t tol)
{
    int32_t d = got - want;
    if (d < 0) d = -d;
    printf("   %-46s got=%-10ld want=%-10ld %s\n", what, (long)got, (long)want,
           (d <= tol) ? "OK" : "FAIL");
    return (d <= tol) ? 0 : 1;
}

static int run_selftest(void)
{
    int fail = 0;
    char b[24];

    banner("BIRIM OZ TESTI - sabit noktali cekirdek");

    printf("  theta = dt / f^2   (dt LSB, f Q16)\n");
    /* 8 K excess at f = 1.0 -> theta = 8 K */
    fail += expect("theta(1024 LSB, f=1.000)", pg_theta_lsb(1024, 65536), 1024, 1);
    /* the same 8 K at f = 0.5 -> theta = 32 K, four times bigger */
    fail += expect("theta(1024 LSB, f=0.500)", pg_theta_lsb(1024, 32768), 4096, 2);
    fail += expect("theta(1024 LSB, f=0.250)", pg_theta_lsb(1024, 16384), 16384, 8);

    printf("  theta_min(f) = 3 sigma / f^2, sigma_TC = %d LSB (0.20 K)\n",
           PG_SIGMA_TC_LSB);
    pg_fmt_scaled(b, sizeof b, pg_theta_min_lsb(65536 * 85 / 100, PG_SIGMA_TC_LSB),
                  PG_LSB_PER_K, 2);
    printf("   f=0.85 -> %s K   (beklenen 0.83-0.85)\n", b);
    pg_fmt_scaled(b, sizeof b, pg_theta_min_lsb(65536 * 60 / 100, PG_SIGMA_TC_LSB),
                  PG_LSB_PER_K, 2);
    printf("   f=0.60 -> %s K   (beklenen 1.67-1.70)\n", b);
    pg_fmt_scaled(b, sizeof b, pg_theta_min_lsb(65536 * 40 / 100, PG_SIGMA_TC_LSB),
                  PG_LSB_PER_K, 2);
    printf("   f=0.40 -> %s K   (beklenen 3.75-3.81)\n", b);
    pg_fmt_scaled(b, sizeof b, pg_theta_min_lsb(65536 * 20 / 100, PG_SIGMA_TC_LSB),
                  PG_LSB_PER_K, 2);
    printf("   f=0.20 -> %s K   (beklenen 15.0-15.3)  <- SENSITIVITY_LOW\n", b);

    printf("\n  Fazla temas direnci ARALIK olarak (R_th 2.0-4.0 K/W):\n");
    {
        int32_t lo, hi;
        char bl[24], bh[24];
        /* 400 A lug, 50 uohm -> 8.0 W -> 16..32 K.  Feed 32 K back in and the
         * interval must contain the 50 uohm we started from. */
        pg_excess_r_nohm(32 * PG_LSB_PER_K, 400, &lo, &hi);
        pg_fmt_scaled(bl, sizeof bl, lo, 1000, 1);
        pg_fmt_scaled(bh, sizeof bh, hi, 1000, 1);
        printf("   theta=32.00 K @ 400 A  ->  %s .. %s uohm\n", bl, bh);
        fail += expect("   alt sinir (R_th=4.0)", lo, 50000, 200);
        fail += expect("   ust sinir (R_th=2.0)", hi, 100000, 300);
        pg_excess_r_nohm(16 * PG_LSB_PER_K, 400, &lo, &hi);
        pg_fmt_scaled(bl, sizeof bl, lo, 1000, 1);
        pg_fmt_scaled(bh, sizeof bh, hi, 1000, 1);
        printf("   theta=16.00 K @ 400 A  ->  %s .. %s uohm   "
               "(brief: 50 uohm -> 8.0 W -> 16-32 K)\n", bl, bh);
    }

    printf("\n  Tamsayi karekok ve RMS:\n");
    fail += expect("isqrt64(1e12)", (int32_t)pg_isqrt64(1000000000000ull), 1000000, 0);
    fail += expect("isqrt64(2)",    (int32_t)pg_isqrt64(2), 1, 0);

    printf("\n  Cerceve kodlama/cozme (35 bayt, CRC-16/CCITT):\n");
    {
        pg_frame_t f, g;
        uint8_t buf[PG_FRAME_MAX];
        int n;
        memset(&f, 0, sizeof f);
        f.node_id = 0x0104; f.seq = 123456; f.boot = 7; f.ts = 1789000123u;
        f.flags = PG_F_DATA_VALID | PG_F_LEARN_MODE; f.msgtype = PG_MSG_EVENT;
        f.cadence = PG_CAD_WATCH; f.trig = PG_TRIG_THETA;
        f.t_mean_lsb = 7168; f.t_min_lsb = 6900; f.t_max_lsb = 7400;
        f.theta_lsb = 812; f.slope_mk_d = 640; f.i_rms_ma = 287345;
        f.vbat_mv = 3598; f.rssi_dbm = -99; f.mcu_c = 31;
        n = pg_frame_encode(&f, buf, sizeof buf);
        printf("   kodlanmis uzunluk %d bayt, hava suresi %lu ms "
               "(LoRa SF7 BW125 CR4/5)\n", n, (unsigned long)pg_airtime_ms(n));
        fail += expect("   cozme donus degeri", pg_frame_decode(buf, n, &g), n, 0);
        fail += expect("   seq round-trip", (int32_t)g.seq, 123456, 0);
        fail += expect("   theta round-trip", g.theta_lsb, 812, 0);
        fail += expect("   i_rms round-trip", g.i_rms_ma, 287345, 0);
        buf[10] ^= 0x01u;
        fail += expect("   bozulmus cerceve reddedildi",
                       pg_frame_decode(buf, n, &g), -4, 0);
    }

    printf("\n  PRPD binleme (logaritma yok):\n");
    {
        pg_prpd_t p;
        pg_prpd_init(&p, PG_PRPD_FE_DIVIDER, 0);
        pg_prpd_new_cycle(&p, 20000u);
        fail += expect("   genlik: 640 ADC LSB (25 dB) -> bin", pg_prpd_amp_bin(&p, 640), 10, 0);
        fail += expect("   faz: 0 tick -> bin", pg_prpd_phase_bin(&p, 0), 0, 0);
        fail += expect("   faz: yarim cevrim -> bin", pg_prpd_phase_bin(&p, 10000), 32, 0);
        fail += expect("   faz: cevrim sonu -> bin", pg_prpd_phase_bin(&p, 19999), 63, 0);
        pg_prpd_init(&p, PG_PRPD_FE_RAW, 0);
        pg_prpd_new_cycle(&p, 20000u);
        /* raw board: 29.79 LSB/dB, 74.47 LSB/bin.  25 dB = 745 LSB -> bin 10 */
        fail += expect("   ham kart: 745 ADC LSB (25 dB) -> bin",
                       pg_prpd_amp_bin(&p, 745), 10, 0);
    }

    printf("\n  Kadans histerezisi (2 yukari / 4 asagi):\n");
    {
        static pg_node_t n;
        int i;
        pg_node_init(&n, 1, 400);
        pg_cadence_update(&n, PG_TRIG_THETA, 0);
        fail += expect("   1 nitelikli cevrim sonrasi periyot",
                       (int32_t)pg_period_s(n.cadence), 900, 0);
        pg_cadence_update(&n, PG_TRIG_THETA, 0);
        fail += expect("   2 nitelikli cevrim sonrasi periyot",
                       (int32_t)pg_period_s(n.cadence), 60, 0);
        for (i = 0; i < 3; i++) pg_cadence_update(&n, PG_TRIG_NONE, 0);
        fail += expect("   3 sessiz cevrim sonrasi periyot (hala 60)",
                       (int32_t)pg_period_s(n.cadence), 60, 0);
        pg_cadence_update(&n, PG_TRIG_NONE, 0);
        fail += expect("   4 sessiz cevrim sonrasi periyot",
                       (int32_t)pg_period_s(n.cadence), 900, 0);
        pg_node_init(&n, 1, 400);
        pg_cadence_update(&n, PG_TRIG_ABS_CRIT, 1000);
        fail += expect("   sert olay: dogrudan patlama",
                       (int32_t)pg_period_s(n.cadence), 10, 0);
    }

    printf("\n  Kristal sicaklik telafisi (parabolik, k=0.034 ppm/C^2):\n");
    {
        char t1[24], t2[24];
        pg_fmt_scaled(t1, sizeof t1, pg_xtal_ppm_q10(250), 1024, 2);
        pg_fmt_scaled(t2, sizeof t2, pg_xtal_ppm_q10(600), 1024, 2);
        printf("   25 C -> %s ppm, 60 C -> %s ppm (telafi edilmezse)\n", t1, t2);
    }

    printf("\n  ozet: %d hata\n", fail);
    return fail;
}

/* ==========================================================================
 * main
 * ========================================================================== */

static void usage(void)
{
    int i;
    printf("PANO GOZ dugum ureti yazilimi - ana bilgisayar kosumu\n");
    printf("  %s\n\n", PG_FW_STRING);
    printf("kullanim: panogoz_node [--scenario <ad>] [--hours N] [--seed N]\n"
           "                       [--verbose] [--selftest] [--list]\n\n");
    printf("senaryolar:\n");
    for (i = 0; i < SC_COUNT; i++)
        printf("  %-12s %s\n", sc_names[i], sc_tr[i]);
}

int main(int argc, char **argv)
{
    scenario_t sc = SC_DRIFT;
    uint32_t seed = 20260910u, hours = 72u;
    int verbose = 0, selftest = 0, prpd_hex = 0, i, fail = 0;

    setvbuf(stdout, NULL, _IOLBF, 0);

    for (i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "--scenario") && i + 1 < argc) {
            int j, found = 0;
            i++;
            for (j = 0; j < SC_COUNT; j++)
                if (!strcmp(argv[i], sc_names[j])) { sc = (scenario_t)j; found = 1; }
            if (!found) { printf("bilinmeyen senaryo: %s\n", argv[i]); usage(); return 2; }
        } else if (!strcmp(argv[i], "--hours") && i + 1 < argc) {
            hours = (uint32_t)strtoul(argv[++i], NULL, 10);
            if (hours == 0) hours = 1;
        } else if (!strcmp(argv[i], "--seed") && i + 1 < argc) {
            seed = (uint32_t)strtoul(argv[++i], NULL, 10);
        } else if (!strcmp(argv[i], "--verbose")) {
            verbose = 1;
        } else if (!strcmp(argv[i], "--selftest")) {
            selftest = 1;
        } else if (!strcmp(argv[i], "--prpd-hex")) {
            /* Dump the packed histogram as hex so the round trip through
             * panogoz.sim.prpd.unpack() can be checked from the outside.
             * A wire format that is only ever read by its own writer is not
             * a wire format, it is a habit. */
            prpd_hex = 1;
        } else if (!strcmp(argv[i], "--list")) {
            usage(); return 0;
        } else if (!strcmp(argv[i], "--help") || !strcmp(argv[i], "-h")) {
            usage(); return 0;
        } else {
            printf("bilinmeyen secenek: %s\n", argv[i]); usage(); return 2;
        }
    }

    printf("PANO GOZ - pano/hucre ici anomali erken uyari sistemi\n");
    printf("Ureti yazilimi: %s   hedef STM32WLE5CC (Cortex-M4 + 868 MHz radyo)\n",
           PG_FW_STRING);
    printf("Kayan nokta yok, libm yok, ilk kurulumdan sonra dinamik ayirma yok.\n");

    if (selftest) return run_selftest();

    switch (sc) {
    case SC_ENERGY:
        vp_reset(SC_ENERGY, seed, 1, 0);
        banner(sc_tr[SC_ENERGY]);
        { pg_power_t pw; pg_power_init(&pw);
          pg_power_update_cell(&pw, 3610, 3410);
          pg_power_report(&pw); }
        break;
    case SC_OTA:
        run_ota(seed);
        break;
    case SC_PRPD:
        run_prpd(seed, prpd_hex);
        break;
    case SC_ALL:
        fail += run_selftest();
        run_scenario(SC_HEALTHY, seed, 24, 0);
        run_scenario(SC_DRIFT, seed, 72, 0);
        run_scenario(SC_STEP, seed, 24, 0);
        run_scenario(SC_DEENERGISED, seed, 24, 0);
        run_scenario(SC_LOWBAT, seed, 24, 0);
        run_scenario(SC_MOUNTLOST, seed, 24, 0);
        run_scenario(SC_BURST, seed, 12, 0);
        run_scenario(SC_OUTAGE, seed, 24, 0);
        run_prpd(seed, 0);
        run_ota(seed);
        { pg_power_t pw; pg_power_init(&pw);
          pg_power_update_cell(&pw, 3610, 3410);
          banner("ENERJI BUTCESI"); pg_power_report(&pw); }
        break;
    default:
        run_scenario(sc, seed, hours, verbose);
        { pg_power_t pw; pg_power_init(&pw);
          pg_power_update_cell(&pw, VP.vbat_mv, hal_vbat_loaded_mv());
          pg_power_report(&pw); }
        break;
    }

    printf("\nDURUSTLUK: PANO GOZ KORUMA DEGILDIR. ABB TVOC-2 ayni panoda arki\n"
           "~1 ms'de, SIL-2 donanimda, yazilim devrede olmadan keser. Bu dugum\n"
           "gozler, konumlandirir, zaman damgalar ve yukseltir. Bildirim\n"
           "gecikmesi 4-13 saniyelik bir ARALIKTIR, tek bir temiz sayi degil.\n");
    return fail ? 1 : 0;
}

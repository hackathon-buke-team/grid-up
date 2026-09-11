/* ==========================================================================
 * PANO GOZ - edge node firmware, public header
 * Target : STM32WLE5CC  (Cortex-M4F, 256 kB flash, 64 kB SRAM,
 *                        integrated sub-GHz transceiver, 868 MHz)
 * Build  : C99, freestanding-friendly.  No float, no libm, no malloc.
 *
 * Why 868 MHz and not 2.4 GHz
 * ---------------------------
 * The link that has to work runs from the bottom cable compartment
 * (Madde 2.2.8.6 Not:2 - the panel bottom is fully open onto the cable
 * trench) up to the communication compartment in the roof
 * (Madde 2.2.8.1.iv mandates that compartment plus a sealed external
 * antenna outlet).  Between the two sits the 2 mm galvanised DSYA mounting
 * plate and a 1600x1500x450 mm sheet-steel box, i.e. a cavity that is
 * heavily overmoded at 2.4 GHz and only weakly so at 868 MHz.  The open
 * bottom is the one reliable aperture, and a 345 mm wavelength couples
 * through a 400 mm slot; a 125 mm wavelength does not, it just rattles
 * around inside the cavity and nulls.  One radio, one die, no BLE anywhere.
 *
 * FIXED POINT CONVENTIONS  (there is not one float in this firmware)
 * ------------------------------------------------------------------
 *   name        C type    unit / Q format                     range used
 *   t_lsb       int16_t   TMP117 native LSB = 1/128 degC       -40..+150 C
 *   dt_lsb      int32_t   same LSB, a difference               +/- 20000
 *   theta_lsb   int32_t   same LSB, "kelvin at I_ref"          +/- 40000
 *   i_ma        int32_t   milliamperes of PRIMARY current      0..600000
 *   f_q16       uint32_t  load factor I/I_ref, Q16 (1.0=65536) 0..~131072
 *   slope_mk_d  int32_t   milli-kelvin per day                 +/- 2e6
 *   mv          uint16_t  millivolts                           0..4500
 *   ua          uint32_t  microamperes                         0..400000
 *   nas         uint64_t  nanoampere-seconds (= nanocoulombs)  accumulator
 *   ph_q16      uint32_t  phase within the mains cycle, Q16    0..65535
 *
 * WHY TEMPERATURE NEVER LEAVES TMP117 LSB
 * ---------------------------------------
 * The TMP117 LSB is exactly 1/128 degC - a power of two, exact in binary,
 * with no rounding error at any stage.  theta is a DIFFERENCE of two
 * co-located sensors divided by a load ratio; every conversion to "degrees"
 * on the node would inject a rounding error into a quantity whose whole
 * point is that it resolves 0.2 K.  So the node stores, aggregates,
 * differences, slopes and transmits raw LSB, and the only place a human
 * unit appears is the print helper and the server.  Converting on an MCU
 * with no FPU-cheap divide would also cost cycles for nothing.
 *
 * HONESTY
 * -------
 * This node OBSERVES.  It is not protection.  The ABB TVOC-2 clears an arc
 * in about 1 ms in SIL-2 hardware with no software in the loop and does so
 * whether or not this node was ever installed.  Everything here shortens a
 * NOTIFICATION.  No energy harvesting is claimed anywhere: the node runs
 * from a primary Li-SOCl2 cell with a 9-16 year design life, and power.c
 * computes that number rather than asserting it.
 * ========================================================================== */

#ifndef PANOGOZ_NODE_H
#define PANOGOZ_NODE_H

#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

#define PG_FW_VERSION_MAJOR   1
#define PG_FW_VERSION_MINOR   0
#define PG_FW_VERSION_PATCH   0
#define PG_FW_STRING          "panogoz-node 1.0.0"
#define PG_PROTO_VERSION      1

/* ==========================================================================
 * 1. Asset constants  (mirrors panogoz/contracts/assets.py - keep in step)
 * ========================================================================== */

/* Tablo 3a main busbar rating, amperes.  Only the four roof stubs see it. */
#define PG_MAIN_BUSBAR_A        2312
/* DSYA outgoing way ratings.  EK-I/8 Tablo 8: 5 x 250 A + 5 x 400 A + 2 yedek. */
#define PG_FEEDER_250_A         250
#define PG_FEEDER_400_A         400
/* Sum of the ten non-spare way ratings; used as the fallback denominator when
 * a node has no CT of its own.  5*250 + 5*400 = 3250. */
#define PG_SUM_FEEDER_RATED_A   3250

/* Service conditions, Tablo 1 dahili column. */
#define PG_AMBIENT_MAX_C        40
#define PG_AMBIENT_MIN_C       (-5)

/* ==========================================================================
 * 2. Thermal / theta constants, all in TMP117 LSB
 * ========================================================================== */

#define PG_LSB_PER_K            128           /* exact, by construction      */
#define PG_K_TO_LSB(k)          ((int32_t)((k) * PG_LSB_PER_K))

/* Sibling-differential noise, 1 sigma.  A thermocouple/TMP117 PAIR gives
 * 0.2 K; an IR pixel pair gives 0.8 K.  This node is the TC variant. */
#define PG_SIGMA_TC_LSB         26            /* 0.203 K, rounded up         */
#define PG_SIGMA_IR_LSB         102           /* 0.797 K                     */

/* theta_min(f) = 3*sigma / f^2.  Below f = 0.35 the node is in reduced
 * sensitivity and SAYS SO - that is a feature, not a defect. */
#define PG_SENSITIVITY_FLOOR_Q16  22938       /* 0.35 * 65536                */
#define PG_K_SIGMA                3

/* Server-side alarm qualifier, repeated here only so the node can decide when
 * to spend radio energy.  The node NEVER alarms on its own. */
#define PG_THETA_NOTIFY_LSB     (5 * PG_LSB_PER_K)    /*  5.0 K   = 640      */
#define PG_THETA_WATCH_LSB      (2 * PG_LSB_PER_K)    /*  2.0 K   = 256      */

/* Absolute limits that do NOT need a baseline, a peer or a server.
 * PVC-insulated LV cable is rated 70 C at the conductor; a lug body at 90 C
 * means the insulation behind the crimp is already past its rating. */
#define PG_ABS_HOT_LSB          (90 * PG_LSB_PER_K)   /* 11520               */
#define PG_ABS_CRITICAL_LSB     (110 * PG_LSB_PER_K)  /* 14080               */

/* A raw sibling delta this large is a "go now" regardless of load, matching
 * the gateway's LOCAL_DELTA_K.  IR practice calls 15 K over a similar
 * component under similar load a major discrepancy; we use 20 K raw. */
#define PG_RAW_DELTA_HOT_LSB    (20 * PG_LSB_PER_K)   /* 2560                */

/* Slope that qualifies as "rising" for the cadence escalator, milli-kelvin
 * per day OF THETA.  1.5 K/day is roughly 3 sigma of the slope estimator over
 * the 16-hour theta trend window at typical sibling-pair noise, so a healthy
 * joint escalates the cadence about once a year rather than twice a day.
 *
 * IT IS THE SLOPE OF THETA, NEVER OF RAW TEMPERATURE.  A lug on a real
 * feeder warms 8 K between 04:00 and 19:00 every single day; trending that
 * gives a 12 K/day "rising trend" on a perfectly healthy joint, and a node
 * that escalates its cadence every morning has a three-year battery life and
 * a server full of noise.  theta divides the load out - that is the entire
 * thesis of this project - so theta is what gets trended. */
#define PG_SLOPE_RISING_MK_D    1500

/* A step in THETA this large between the two halves of the trend window is a
 * discontinuity rather than a load excursion.  It is compared against the
 * MEDIAN of each half, not against the peak-to-peak: the range of n draws
 * grows with n, so a peak-to-peak test gets more sensitive the longer you
 * watch a perfectly healthy joint, which is precisely backwards. */
#define PG_STEP_THETA_LSB       (6 * PG_LSB_PER_K)

/* Both trend thresholds are additionally floored at the NOISE the instrument
 * actually has at the load it actually saw.  theta = dt/f^2 amplifies the
 * 0.2 K sibling-pair noise by 1/f^2, so at f = 0.35 one sigma of theta is
 * 1.6 K and a fixed threshold that is fine at full load is pure noise at
 * light load.  k_sigma below multiplies the estimator's own standard
 * deviation; see pg_theta_trend(). */
#define PG_TREND_K_SIGMA        4

/* The theta trend register.  Deliberately DECOUPLED from the telemetry
 * cadence: theta is pushed here at most once every PG_TH_MIN_DT_S no matter
 * whether the node is sampling every 900 s or every 10 s, so the window
 * always spans hours and an event burst cannot manufacture a slope out of
 * five minutes of noise.  32 x 1800 s = 16 hours. */
#define PG_TH_N                 32
#define PG_TH_MIN_DT_S          1800u
#define PG_TH_MIN_SPAN_S        28800u    /* 8 h before a slope is believed */
#define PG_TH_MIN_N             12

/* Peer readings older than this are not a valid sibling median any more. */
#define PG_PEER_MAX_AGE_S       2400u

/* ==========================================================================
 * 3. Cadence (adaptive sampling)
 * ========================================================================== */

typedef enum {
    PG_CAD_IDLE  = 0,     /* 900 s - nothing interesting                    */
    PG_CAD_WATCH = 1,     /*  60 s - theta elevated or rising               */
    PG_CAD_BURST = 2      /*  10 s - event burst                            */
} pg_cadence_t;

#define PG_PERIOD_IDLE_S        900u
#define PG_PERIOD_WATCH_S       60u
#define PG_PERIOD_BURST_S       10u

/* 2-up / 4-down hysteresis.  Two consecutive qualifying cycles escalate one
 * step; four consecutive quiet cycles de-escalate one step.  Asymmetric on
 * purpose: escalating early costs a few mAh, de-escalating early costs the
 * data that would have shown the operator what happened. */
#define PG_HYST_UP              2
#define PG_HYST_DOWN            4

/* A burst is also floored in time so a single glitch cannot make the node
 * chatter: once in BURST it stays there for at least this long. */
#define PG_BURST_MIN_S          120u

/* ==========================================================================
 * 4. Node state machine
 * ========================================================================== */

typedef enum {
    PG_ST_COLD_START = 0,
    PG_ST_SELF_TEST,
    PG_ST_PROVISION,
    PG_ST_SAMPLE,
    PG_ST_AGGREGATE,
    PG_ST_TX,
    PG_ST_SLEEP,
    PG_ST_DE_ENERGISED,   /* branch: no mains, no current, nothing thermal   */
    PG_ST_LOW_BATTERY,    /* branch: survival cadence, health frames only    */
    PG_ST_FAULT,          /* self-test failed; beacon identity + reason only */
    PG_ST_COUNT
} pg_state_t;

const char *pg_state_name(pg_state_t s);

/* ==========================================================================
 * 5. Status flags - these mirror contracts/icd.py STATUS_BITS by NAME so a
 *    flag never means two things in two layers.  "We are blind" is a
 *    first-class report, kept separate from "the panel has a fault".
 * ========================================================================== */

#define PG_F_DATA_VALID       (1u << 0)
#define PG_F_STALE            (1u << 1)
#define PG_F_SENSITIVITY_LOW  (1u << 2)
#define PG_F_DE_ENERGISED     (1u << 3)
#define PG_F_LEARN_MODE       (1u << 4)
#define PG_F_MOUNT_LOST       (1u << 5)
#define PG_F_CELL_LOW         (1u << 6)
#define PG_F_CLOCK_UNSYNCED   (1u << 7)
#define PG_F_PEER_LOST        (1u << 8)   /* no sibling -> no theta at all   */
#define PG_F_SENSOR_FAULT     (1u << 9)
#define PG_F_BUFFERING        (1u << 10)  /* gateway unreachable, FRAM ring  */
#define PG_F_OTA_TRIAL        (1u << 11)  /* running an unconfirmed image    */
#define PG_F_BROWNOUT         (1u << 12)  /* last reset was a BOR            */

/* ==========================================================================
 * 6. Sample and aggregate records
 * ========================================================================== */

typedef struct {
    uint32_t ts;          /* seconds, gateway-synced wall clock              */
    int16_t  t_lsb;       /* own joint temperature, TMP117 raw               */
    int16_t  t_air_lsb;   /* compartment air, same LSB (SHT41 rescaled)      */
    int32_t  i_ma;        /* own conductor current, split-core CT            */
    uint16_t vbat_mv;
    int8_t   mcu_c;
    uint8_t  ok;          /* 0 = this sample is not usable                   */
} pg_sample_t;

/* Window of samples the edge analytics runs over.  32 entries at 900 s is
 * 8 hours; at 60 s it is 32 minutes.  Static, sized at compile time, never
 * malloc'd - see the no-dynamic-allocation rule. */
#define PG_WIN_N   32

typedef struct {
    int32_t  t_min_lsb;
    int32_t  t_max_lsb;
    int32_t  t_mean_lsb;     /* rounded, not truncated                       */
    int32_t  t_p2p_lsb;
    int32_t  i_rms_ma;       /* integer RMS over the window                  */
    int32_t  i_mean_ma;
    int32_t  slope_mk_per_day;      /* of RAW temperature - telemetry only  */
    uint32_t n;

    /* The trend that actually drives a decision.  See PG_SLOPE_RISING_MK_D. */
    int32_t  theta_slope_mk_per_day;
    int32_t  theta_slope_floor_mk_d;   /* noise floor the slope must beat   */
    int32_t  theta_step_lsb;           /* median(new half) - median(old)    */
    int32_t  theta_step_floor_lsb;
    int32_t  theta_med_lsb;
    int32_t  theta_min_med_lsb;        /* typical resolution over the window*/
    uint32_t theta_n;
    uint32_t theta_span_s;
} pg_agg_t;

/* Per-node running edge-analytics context. */
typedef struct {
    int16_t  t[PG_WIN_N];
    int32_t  i[PG_WIN_N];
    uint32_t ts[PG_WIN_N];
    uint8_t  head;
    uint8_t  count;

    /* peer (sibling) cache: exactly two peers for a 3-phase clip triplet.
     * median(siblings) with two members is their mean, and SELF IS EXCLUDED -
     * a self-inclusive median over three phases silently eats about 40 % of
     * the signal once the faulted phase crosses one of its siblings. */
    int16_t  peer_t[2];
    uint32_t peer_ts[2];
    uint16_t peer_id[2];
    uint8_t  peer_n;

    /* Fallback: the gateway hears all three clips of a feeder and can put
     * the sibling median straight into the acknowledgement.  Direct peer
     * snooping is preferred - it is lower latency and does not depend on the
     * gateway - but a node whose peers happen to transmit while it is asleep
     * would otherwise have no sibling at all, and no sibling means no theta. */
    int16_t  relay_t;
    uint32_t relay_ts;

    /* theta trend register - see PG_TH_N */
    int32_t  th[PG_TH_N];
    int32_t  th_min[PG_TH_N];      /* theta_min at the moment of that sample */
    uint32_t th_ts[PG_TH_N];
    uint8_t  th_head;
    uint8_t  th_count;
    uint32_t th_last_ts;

    /* last computed */
    int32_t  theta_lsb;
    int32_t  theta_min_lsb;
    uint32_t f_q16;
    uint32_t flags;
} pg_edge_t;

/* ==========================================================================
 * 7. theta_edge.c
 * ========================================================================== */

void     pg_edge_init(pg_edge_t *e);
void     pg_edge_push(pg_edge_t *e, const pg_sample_t *s);
void     pg_edge_peer(pg_edge_t *e, uint16_t peer_id, int16_t t_lsb, uint32_t ts);
/* Sibling median relayed by the gateway in an acknowledgement.  Already a
 * median, so it is used alone and never averaged with a direct peer. */
void     pg_edge_relayed_median(pg_edge_t *e, int16_t t_lsb, uint32_t ts);
void     pg_edge_aggregate(const pg_edge_t *e, pg_agg_t *out);
/* Push one theta into the trend register.  Rate limited internally to one
 * sample per PG_TH_MIN_DT_S and REFUSED when the load factor is below the
 * sensitivity floor - we do not trend a quantity we cannot presently
 * resolve, because a trend fitted through noise is still a trend. */
void     pg_edge_push_theta(pg_edge_t *e, int32_t theta_lsb, int32_t theta_min_lsb,
                            uint32_t ts, uint32_t f_q16);
/* Newest usable temperature sample.  theta must be built from THIS, not from
 * the window mean: the sibling median arrives now, and differencing a
 * now-value against an eight-hour average manufactures a fault every morning. */
int16_t  pg_edge_last_t(const pg_edge_t *e, int *ok);

/* Load factor I/I_ref in Q16.  i_ref_a is the DSYA rating of this way. */
uint32_t pg_load_factor_q16(int32_t i_ma, uint32_t i_ref_a);

/* Sibling excess: own temperature minus the median of the peers (self
 * excluded).  Returns 0 and sets *valid = 0 when there is no fresh peer. */
int32_t  pg_sibling_excess_lsb(const pg_edge_t *e, int16_t t_lsb,
                               uint32_t now, int *valid);

/* theta = dt / f^2, in the same LSB.  f_q16 == 0 -> PG_THETA_INVALID. */
#define  PG_THETA_INVALID  ((int32_t)0x7FFFFFFF)
int32_t  pg_theta_lsb(int32_t dt_lsb, uint32_t f_q16);

/* theta_min(f) = k*sigma / f^2, the smallest theta this node can resolve
 * right now.  Saturates rather than overflowing at very light load. */
int32_t  pg_theta_min_lsb(uint32_t f_q16, int32_t sigma_lsb);

/* Excess contact resistance as an INTERVAL, never a point value:
 * dR = theta / (R_th * I_ref^2) with R_th only known to a factor of two.
 * R_th for a 240 mm2 cable lug is 2..4 K/W; the busbar two-sided-fin figure
 * 1/(2*sqrt(h*P*k*A)) is 0.24..0.38 K/W and is NOT what a lug sees. */
void     pg_excess_r_nohm(int32_t theta_lsb, uint32_t i_ref_a,
                          int32_t *lo_nohm, int32_t *hi_nohm);

/* Event trigger.  Returns a bitmask of PG_TRIG_* saying WHY. */
#define PG_TRIG_NONE        0u
#define PG_TRIG_ABS_HOT     (1u << 0)
#define PG_TRIG_ABS_CRIT    (1u << 1)
#define PG_TRIG_RAW_DELTA   (1u << 2)
#define PG_TRIG_THETA       (1u << 3)
#define PG_TRIG_SLOPE       (1u << 4)
#define PG_TRIG_STEP        (1u << 5)
uint32_t pg_edge_trigger(const pg_edge_t *e, const pg_agg_t *a, int32_t theta_lsb);
const char *pg_trigger_text_tr(uint32_t trig);

/* Integer helpers, exposed because main.c and power.c need them too. */
uint32_t pg_isqrt64(uint64_t v);
int32_t  pg_div_round(int64_t num, int64_t den);

/* ==========================================================================
 * 8. prpd_bin.c  -  phase-resolved binning with NO logarithm
 * ========================================================================== */

#define PG_PRPD_NPHASE  64
#define PG_PRPD_NAMP    32
#define PG_PRPD_CELLS   (PG_PRPD_NPHASE * PG_PRPD_NAMP)

/* Front-end scaling.  The AD8318 output is ALREADY linear in dB at
 * 24 mV/dB, so binning amplitude is a subtract and a shift; the logarithm
 * happened in the analogue detector and the MCU never computes one. */
#define PG_AD8318_UV_PER_DB     24000u   /* 24 mV/dB                        */
/* Raw board: 12-bit ADC on a 3.3 V reference = 805.664 uV/LSB, so the raw
 * slope is 24000/805.664 = 29.79 ADC LSB per dB and one 2.5 dB bin is
 * 74.47 LSB.  Dividing by 74.47 is a Q16 multiply by 65536/74.47 = 880. */
#define PG_ADC_LSB_PER_DB_X100  2979u
#define PG_AMP_BIN_RECIP_Q16    880u
/* Divider board (the one we ship): a 0.859 resistive divider between the
 * AD8318 and the ADC makes the slope exactly 25.6 LSB/dB, so one 2.5 dB bin
 * is exactly 64 LSB and the divide degenerates to a shift.  This is the
 * variant panogoz/sim/prpd.py models and the one the wire format assumes. */
#define PG_AMP_BIN_SHIFT        6
#define PG_PHASE_BIN_SHIFT      6        /* 1 << 6 == PG_PRPD_NPHASE        */

typedef enum {
    PG_PRPD_FE_DIVIDER = 0,   /* shift path, 64 ADC LSB per bin (shipped)   */
    PG_PRPD_FE_RAW     = 1    /* Q16 reciprocal path, 74.47 LSB per bin     */
} pg_prpd_fe_t;

typedef struct {
    uint16_t cell[PG_PRPD_CELLS];   /* [phase][amp], phase-major, saturating */
    uint32_t cycles;                /* mains cycles accumulated              */
    uint32_t pulses;                /* pulses binned                         */
    uint32_t dropped;               /* below threshold or dead-time lost     */
    uint32_t period_ticks;          /* current mains period, timer ticks     */
    uint32_t recip_q16;             /* Q16 reciprocal of period_ticks        */
    uint16_t amp_offset_lsb;        /* calibration zero, subtracted first    */
    uint8_t  fe;                    /* pg_prpd_fe_t                          */
    uint8_t  thr_bin;               /* pulses below this amp bin are noise   */
} pg_prpd_t;

void     pg_prpd_init(pg_prpd_t *p, pg_prpd_fe_t fe, uint16_t amp_offset_lsb);
/* ONE divide per mains cycle, not per pulse: the zero-cross ISR calls this
 * with the measured period and it precomputes the Q16 reciprocal. */
void     pg_prpd_new_cycle(pg_prpd_t *p, uint32_t period_ticks);
/* Per pulse: two multiplies and two shifts, no divide, no logarithm. */
void     pg_prpd_pulse(pg_prpd_t *p, uint32_t dt_ticks, uint16_t adc_lsb);
uint8_t  pg_prpd_amp_bin(const pg_prpd_t *p, uint16_t adc_lsb);
uint8_t  pg_prpd_phase_bin(const pg_prpd_t *p, uint32_t dt_ticks);
/* Sparse RLE + LEB128 varint, byte-identical to panogoz.sim.prpd.pack(). */
int      pg_prpd_pack(const pg_prpd_t *p, uint8_t *out, int cap);
void     pg_prpd_clear(pg_prpd_t *p);
uint32_t pg_prpd_occupied(const pg_prpd_t *p);

/* ==========================================================================
 * 9. radio.c  -  frame format, duty cycle, time sync
 * ========================================================================== */

#define PG_FRAME_MAGIC     0x50u        /* 'P'                              */
#define PG_FRAME_MAX       48

typedef enum {
    PG_MSG_DATA   = 0,
    PG_MSG_EVENT  = 1,
    PG_MSG_BIRTH  = 2,
    PG_MSG_HEALTH = 3,
    PG_MSG_PRPD   = 4,
    PG_MSG_BEACON = 5,     /* gateway -> nodes                              */
    PG_MSG_ACK    = 6,     /* gateway -> node                               */
    PG_MSG_OTA    = 7
} pg_msgtype_t;

typedef struct {
    uint16_t node_id;
    uint32_t seq;
    uint8_t  boot;
    uint32_t ts;
    uint32_t flags;
    uint8_t  msgtype;
    uint8_t  cadence;
    uint8_t  trig;
    int16_t  t_mean_lsb;
    int16_t  t_min_lsb;
    int16_t  t_max_lsb;
    int32_t  theta_lsb;
    int32_t  slope_mk_d;
    int32_t  i_rms_ma;
    uint16_t vbat_mv;
    int8_t   rssi_dbm;
    int8_t   mcu_c;
} pg_frame_t;

int      pg_frame_encode(const pg_frame_t *f, uint8_t *out, int cap);
int      pg_frame_decode(const uint8_t *in, int len, pg_frame_t *f);
uint16_t pg_crc16(const uint8_t *p, int n);

/* --- Duty cycle.  ETSI EN 300 220 g3 (869.4-869.65 MHz) allows 10 %, the
 * g1 band 1 %.  We budget against 1 % so the node is legal in either. --- */
#define PG_DUTY_WINDOW_S    3600u
#define PG_DUTY_PERMILLE    10u          /* 1.0 %                           */
int      pg_duty_allow(uint32_t now, uint32_t airtime_ms);
void     pg_duty_charge(uint32_t now, uint32_t airtime_ms);
uint32_t pg_duty_used_ms(uint32_t now);
uint32_t pg_airtime_ms(int payload_len);

/* --- Time sync --------------------------------------------------------- */
typedef struct {
    uint32_t epoch;            /* wall clock seconds at last beacon         */
    uint32_t local_ms;         /* hal_uptime_ms() at that instant           */
    int32_t  ppm_q10;          /* measured RTC error, Q10 ppm               */
    uint32_t beacons;
    uint32_t cycles;           /* mains cycles counted since sync           */
    uint32_t period_us;        /* last measured mains period                */
    uint32_t last_zc_us;
    uint8_t  synced;
    uint8_t  mains_ok;
} pg_time_t;

void     pg_time_init(pg_time_t *t);
void     pg_time_beacon(pg_time_t *t, uint32_t gw_epoch, uint32_t local_ms);
void     pg_time_zero_cross(pg_time_t *t, uint32_t period_us);
uint32_t pg_time_now(const pg_time_t *t, uint32_t local_ms);
/* Worst-case wall-clock error in milliseconds, given seconds since the last
 * beacon and the crystal's temperature-compensated residual. */
uint32_t pg_time_error_ms(const pg_time_t *t, uint32_t since_s);
/* Phase within the mains cycle, Q16, from the last zero crossing. */
uint32_t pg_time_phase_q16(const pg_time_t *t, uint32_t us_since_zc);
/* 32.768 kHz crystal parabolic tempco, returned as Q10 ppm (negative). */
int32_t  pg_xtal_ppm_q10(int16_t t_c10);

/* ==========================================================================
 * 10. power.c  -  energy budget, cell model, battery gating
 * ========================================================================== */

typedef enum {
    PG_PWR_SLEEP = 0,     /* STOP2 + RTC + FRAM sleep + divider leakage     */
    PG_PWR_WAKE,          /* clock start, context restore                   */
    PG_PWR_SENSE,         /* TMP117 one-shot, MCU in low-power sleep        */
    PG_PWR_CT,            /* ADC burst over >= 1 mains cycle                */
    PG_PWR_COMPUTE,       /* edge analytics                                 */
    PG_PWR_FRAM,          /* SPI write of one ring record                   */
    PG_PWR_TX,            /* sub-GHz PA, +14 dBm, RFO_LP                    */
    PG_PWR_RX,            /* receive window: ack + peer snoop + beacon      */
    PG_PWR_PRPD,          /* 60 s PRPD accumulation, comparator + ADC       */
    PG_PWR_STATE_COUNT
} pg_pwr_state_t;

typedef struct {
    const char *name;
    uint32_t    ua;        /* microamperes drawn in this state              */
    uint32_t    typ_us;    /* typical duration per wake cycle               */
} pg_pwr_row_t;

extern const pg_pwr_row_t pg_pwr_table[PG_PWR_STATE_COUNT];

typedef struct {
    uint64_t nas[PG_PWR_STATE_COUNT];   /* nanoampere-seconds per state     */
    uint64_t total_nas;
    uint32_t cycles;
    uint32_t vbat_mv;
    uint32_t vloaded_mv;
    uint8_t  low;                       /* CELL_LOW latched                 */
    uint8_t  critical;                  /* below the OTA / TX floor         */
    uint8_t  passivated;                /* OCV fine, loaded voltage collapses*/
} pg_power_t;

/* ER14250 (1/2 AA Li-SOCl2): 1.2 Ah nominal, 3.6 V.  Derated to 85 % for
 * the low-temperature, pulse-load and end-of-discharge cutoff you actually
 * get in a panel that swings -5..+60 C, and charged 1.0 %/year of nominal
 * for self-discharge.  Both numbers are budget figures, not measurements. */
#define PG_CELL_NOMINAL_MAH     1200u
#define PG_CELL_USABLE_PCT      85u
#define PG_CELL_SELFDIS_PPM_YR  10000u     /* 1.0 %/year                    */
#define PG_CELL_NOMINAL_MV      3600u
#define PG_CELL_LOW_MV          3200u
#define PG_CELL_CRIT_MV         2900u
#define PG_CELL_LOADED_MIN_MV   3000u      /* under the 50 mA passivation pulse */

void     pg_power_init(pg_power_t *p);
void     pg_power_charge(pg_power_t *p, pg_pwr_state_t st, uint32_t us);
void     pg_power_charge_ua(pg_power_t *p, pg_pwr_state_t st, uint32_t ua, uint32_t us);
uint32_t pg_power_cycle_nas(void);                      /* nC per wake cycle */
uint32_t pg_power_cycle_uj(void);                       /* microjoules/cycle */
uint32_t pg_power_active_us(void);                      /* awake time/cycle  */
/* Average draw at a given cadence, in NANOAMPERES.  Nanoamps and not
 * microamps because the idle figure is 5.4 uA and the difference between
 * 5 and 6 is a difference of three years of service life. */
uint32_t pg_power_avg_na(uint32_t period_s);
/* Mission-weighted average: the honest number, because a node does not sit
 * at 900 s for ever.  Weights are permille of mission time and must sum to
 * 1000.  Includes cell self-discharge. */
uint32_t pg_power_mission_na(uint32_t w_idle, uint32_t w_watch, uint32_t w_burst);
uint32_t pg_power_selfdis_na(void);
uint32_t pg_power_life_days(uint32_t avg_na);           /* self-discharge in */
void     pg_power_update_cell(pg_power_t *p, uint16_t ocv_mv, uint16_t loaded_mv);
/* Coulomb-counted remaining capacity.  Li-SOCl2 has a famously FLAT
 * discharge curve - the terminal voltage says almost nothing until the knee -
 * so the primary estimate is the integral of what we actually spent, and the
 * open-circuit voltage is only a cross-check and an end-of-life detector. */
uint8_t  pg_power_pct(const pg_power_t *p);
uint8_t  pg_power_ocv_pct(uint16_t ocv_mv);
int      pg_power_allow_ota(const pg_power_t *p);
void     pg_power_report(const pg_power_t *p);          /* prints the table  */

/* ==========================================================================
 * 11. FRAM store-and-forward ring  (MB85RS64V, 8 kB, byte-writable)
 *
 * NEVER internal flash.  Three reasons, and they are all fatal:
 *   1. Endurance.  STM32WL flash is specified for 10 000 erase cycles per
 *      page.  A telemetry record every 60 s is 1440 writes/day; a 2 kB page
 *      holding 64 records is erased 22 times a day and reaches its rated
 *      endurance in about 15 MONTHS.  The FRAM is rated 1e13 cycles - at one
 *      write per second that is 300 000 years.
 *   2. Atomicity.  A flash page erase takes ~20 ms and cannot be resumed.
 *      A brown-out in the middle of it destroys 64 records, i.e. exactly the
 *      records covering the event that browned the node out.  An FRAM byte
 *      write completes inside the SPI transaction; a brown-out costs at most
 *      one byte, and the double-buffered CRC header catches that.
 *   3. Execution stall.  Writing internal flash stalls the flash bus, so the
 *      zero-cross ISR (which is our fine phase reference) is late exactly
 *      when we are logging.  FRAM is on SPI2 and touches nothing.
 * ========================================================================== */

#define PG_FRAM_SIZE          8192u
#define PG_FRAM_HDR_A         0x0000u
#define PG_FRAM_HDR_B         0x0020u    /* mirror; alternate-write commit   */
#define PG_FRAM_PROV          0x0040u    /* provisioning, 64 B               */
#define PG_FRAM_OTA           0x0080u    /* OTA state block, 64 B            */
#define PG_FRAM_RING          0x00C0u
#define PG_FRAM_REC_SZ        40u    /* 35-byte frame + length + reserve     */
#define PG_FRAM_RING_N        ((PG_FRAM_SIZE - PG_FRAM_RING) / PG_FRAM_REC_SZ) /* 200 */

typedef struct {
    uint32_t magic;       /* 'PGRB'                                          */
    uint16_t version;
    uint16_t head;        /* next write slot                                 */
    uint16_t tail;        /* oldest unacknowledged slot                      */
    uint16_t count;
    uint32_t seq;
    uint32_t boot;
    uint32_t dropped;     /* overwritten because the ring was full           */
    uint32_t writes;
    uint16_t crc;
    uint16_t pad;
} pg_ring_hdr_t;

void     pg_ring_init(pg_ring_hdr_t *h);          /* loads or formats        */
int      pg_ring_push(pg_ring_hdr_t *h, const uint8_t *rec, uint16_t n);
int      pg_ring_peek(pg_ring_hdr_t *h, uint8_t *rec, uint16_t n);
void     pg_ring_pop(pg_ring_hdr_t *h);           /* only after an ACK       */
void     pg_ring_commit(pg_ring_hdr_t *h);
uint16_t pg_ring_depth(const pg_ring_hdr_t *h);

/* ==========================================================================
 * 12. OTA - a scheme that cannot brick a node in a live panel
 *
 * Flash map, STM32WLE5CC (256 kB):
 *   0x08000000  16 kB  BOOTLOADER   WRP + RDP level 1, NEVER updated
 *   0x08004000  48 kB  RECOVERY     WRP, NEVER updated; beacons + accepts OTA
 *   0x08010000  88 kB  SLOT A
 *   0x08026000  88 kB  SLOT B
 *   0x0803C000  16 kB  CONFIG/OTA metadata (2 x 8 kB, alternate write)
 *
 * There is NO LV incoming breaker in this panel (Madde 2.2.10.2.vi, "direk
 * bara baglanti"): de-energising it means blacking out the whole secondary
 * substation from the MV side.  A bricked node is therefore not "drive out
 * and re-flash it", it is "schedule an outage for a whole neighbourhood".
 * That is why the bootloader and the recovery image are write-protected and
 * are never part of an update, and why the new image has to EARN the swap.
 * ========================================================================== */

typedef enum {
    PG_OTA_IDLE = 0,
    PG_OTA_OFFERED,        /* gateway advertised a version                  */
    PG_OTA_ENERGY_HOLD,    /* refused for now: cell cannot afford it        */
    PG_OTA_DOWNLOADING,
    PG_OTA_VERIFIED,       /* CRC32 + signature over the whole slot         */
    PG_OTA_PENDING_SWAP,
    PG_OTA_TRIAL,          /* running the new image, unconfirmed            */
    PG_OTA_CONFIRMED,
    PG_OTA_REVERTED,
    PG_OTA_FAILED,
    PG_OTA_COUNT
} pg_ota_state_t;

#define PG_OTA_TRIAL_CYCLES   3      /* wake cycles the new image must survive */
#define PG_OTA_TRIAL_ACKS     3      /* acknowledged frames it must deliver    */
#define PG_OTA_MIN_PCT        25     /* cell floor before a download starts    */
#define PG_OTA_IMAGE_MAX      (88u * 1024u)
#define PG_OTA_CHUNK          192u

typedef struct {
    uint32_t magic;
    uint8_t  state;
    uint8_t  active_slot;      /* 0 = A, 1 = B                              */
    uint8_t  trial_left;       /* decremented by the BOOTLOADER, not by us  */
    uint8_t  acks;
    uint32_t version;
    uint32_t size;
    uint32_t crc32;
    uint32_t received;
    uint32_t attempts;
    uint8_t  reason;           /* why we are where we are                   */
    uint8_t  pad[3];
} pg_ota_t;

void        pg_ota_init(pg_ota_t *o);
pg_ota_state_t pg_ota_step(pg_ota_t *o, const pg_power_t *pw, uint32_t trig,
                           int have_offer, uint32_t offer_version,
                           uint32_t offer_size, int chunk_ok, int ack_ok);
const char *pg_ota_state_name(pg_ota_state_t s);
const char *pg_ota_reason_tr(uint8_t reason);

/* ==========================================================================
 * 13. Hardware abstraction layer
 *
 * Everything below the line is implemented twice: once against the CubeWL
 * LL drivers on the target (port/stm32wle5/hal_stm32.c - documented in
 * firmware/README.md, NOT shipped in this hackathon tree because there is no
 * ARM toolchain in the judging environment), and once in host_sim.c against
 * a deterministic virtual panel so the SAME source can be run and shown.
 * ========================================================================== */

/* Reset cause bits, hal_reset_cause(). */
#define PG_RST_POR     (1u << 0)
#define PG_RST_PIN     (1u << 1)
#define PG_RST_IWDG    (1u << 2)   /* watchdog fired -> OTA trial must fail */
#define PG_RST_BOR     (1u << 3)   /* brown-out                             */
#define PG_RST_SW      (1u << 4)
#define PG_RST_LPWR    (1u << 5)

void     hal_init(void);
uint32_t hal_uptime_ms(void);
uint32_t hal_uptime_us(void);
/* Sleep.  deep != 0 means STOP2 with the RTC running.  On the host this
 * advances the virtual clock and returns immediately - every timebase in
 * this firmware is an explicit argument, never an implicit wall clock. */
void     hal_sleep_ms(uint32_t ms, int deep);

int16_t  hal_tmp117_oneshot(void);        /* raw LSB; PG_T_FAULT on error   */
#define  PG_T_FAULT  ((int16_t)0x8000)
int16_t  hal_air_temp_lsb(void);
int32_t  hal_ct_rms_ma(void);             /* -1 = no CT fitted on this node */
int8_t   hal_mcu_temp_c(void);
uint16_t hal_vbat_mv(void);
uint16_t hal_vbat_loaded_mv(void);        /* under a 50 mA pulse            */
int      hal_mount_ok(void);              /* magnet/clip contact switch     */

uint32_t hal_mains_period_us(void);       /* 0 = no zero crossings seen     */
int      hal_pd_pop(uint32_t *dt_ticks, uint16_t *adc_lsb);

int      hal_fram_read(uint16_t addr, void *dst, uint16_t n);
int      hal_fram_write(uint16_t addr, const void *src, uint16_t n);

int      hal_radio_tx(const uint8_t *buf, int len);   /* airtime ms, <0 err */
int      hal_radio_rx(uint8_t *buf, int cap, uint32_t win_ms);
int8_t   hal_radio_rssi(void);

void     hal_wdt_start(uint32_t ms);
void     hal_wdt_kick(void);
void     hal_wdt_stop(void);
uint32_t hal_reset_cause(void);
void     hal_reboot(void);

int      hal_flash_erase_slot(uint8_t slot);
int      hal_flash_write(uint8_t slot, uint32_t off, const uint8_t *p, uint32_t n);
uint32_t hal_flash_crc32(uint8_t slot, uint32_t len);
void     hal_flash_mark_trial(uint8_t slot, uint8_t cycles);

void     hal_log(const char *s);                       /* one line, no fmt  */
void     hal_logf(const char *fmt, ...);               /* host only; on the
                                                        * target this is a
                                                        * no-op unless
                                                        * PG_TRACE is set   */

/* ==========================================================================
 * 14. Node context and main loop
 * ========================================================================== */

typedef struct {
    uint16_t      node_id;
    uint16_t      i_ref_a;          /* DSYA rating of the way we sit on     */
    char          panel[16];
    char          device[8];
    char          joint[20];
    uint8_t       has_ct;
    uint8_t       is_pd_node;

    pg_state_t    state;
    pg_cadence_t  cadence;
    uint8_t       up_count;
    uint8_t       down_count;
    uint32_t      burst_until;

    uint32_t      seq;
    uint32_t      boot;
    uint32_t      flags;
    uint32_t      cycles;
    uint32_t      commissioned_ts;

    pg_edge_t     edge;
    pg_agg_t      agg;
    pg_time_t     clock;
    pg_power_t    power;
    pg_ring_hdr_t ring;
    pg_ota_t      ota;
    pg_prpd_t    *prpd;             /* NULL on a thermal clip               */

    uint32_t      trig;
    uint32_t      tx_ok;
    uint32_t      tx_fail;
    uint32_t      acks;
    int8_t        rssi;
} pg_node_t;

void        pg_node_init(pg_node_t *n, uint16_t node_id, uint16_t i_ref_a);
pg_state_t  pg_node_step(pg_node_t *n);      /* run exactly one state       */
/* Drive the machine until it has completed `max_wakes` SLEEP transitions.
 * Returns the number of wake cycles actually executed. */
uint32_t    pg_node_run(pg_node_t *n, uint32_t max_wakes);
uint32_t    pg_period_s(pg_cadence_t c);
void        pg_cadence_update(pg_node_t *n, uint32_t trig, uint32_t now);
void        pg_node_report(const pg_node_t *n);

/* Print helpers.  There is no float in the firmware, so these format a
 * scaled integer by hand.  `scale` is the divisor (128 for TMP117 LSB,
 * 1000 for milli-units); `dp` is how many decimals to show. */
void        pg_fmt_scaled(char *buf, int cap, int32_t value, int32_t scale, int dp);

#ifdef __cplusplus
}
#endif
#endif /* PANOGOZ_NODE_H */

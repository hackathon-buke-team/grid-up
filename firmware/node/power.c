/* PANO GOZ B1 engineering energy estimate, NOT a measured battery lifetime.
 * Whole-node TC budget at the primary cell. The fitted OPA333 (17 uA typ),
 * divider (1.5 uA), comparator, FRAM in standby (no deep-sleep command),
 * MCU/RTC/LSI/IWDG and 2-second watchdog wakeups invalidate the legacy 3 uA.
 * 50 uA is an explicit design allowance including unmeasured wake/leakage.
 * TX/RX include the polling MCU. WAKE charge includes a 68-ohm/10-ms
 * battery load pulse; its duration is an accounting equivalent, not timing.
 * Normal TC cycles only: fault retries, boot, radio loss and HLC leakage
 * need measured characterization. IR/PD use different duty/power profiles.
 * PD_PRPD: 5 V * 0.2 A / (3.6 V * 0.8 efficiency) ~= 0.35 A at battery.
 * Sources and limitations: docs/02-DONANIM-TASARIMI.md.
 * No harvesting, charging, physical measurement or 9-16 year claim.
 */
#include "node.h"

const pg_pwr_row_t pg_pwr_table[PG_PWR_STATE_COUNT] = {
    /* name        uA      typ_us   */
    { "SLEEP",       50,        0 },   /* analog + FRAM standby + RTC/WDG margin */
    { "WAKE",      5000,   120000 },   /* equivalent charge includes 10 ms battery load */
    { "SENSE",     5000,    20000 },
    { "CT",        5000,    22000 },
    { "COMPUTE",   5000,     3000 },
    { "FRAM",      6000,     1200 },
    { "TX",       30000,    77000 },
    { "RX",       11000,    60000 },
    { "PRPD",    350000,        0 }    /* PD 5 V front-end battery-side estimate */
};

#define PG_CELL_V_MV   3600u

/* --------------------------------------------------------------------- */
/* Accounting                                                             */
/* --------------------------------------------------------------------- */

void pg_power_init(pg_power_t *p)
{
    int i;
    for (i = 0; i < PG_PWR_STATE_COUNT; i++) p->nas[i] = 0;
    p->total_nas = 0;
    p->cycles = 0;
    p->vbat_mv = PG_CELL_NOMINAL_MV;
    p->vloaded_mv = PG_CELL_NOMINAL_MV;
    p->low = 0;
    p->critical = 0;
    p->passivated = 0;
}

/* charge[nAs] = uA * us / 1000.  Integer, exact for every table entry. */
void pg_power_charge_ua(pg_power_t *p, pg_pwr_state_t st, uint32_t ua, uint32_t us)
{
    uint64_t nas = ((uint64_t)ua * (uint64_t)us) / 1000ull;
    if ((unsigned)st >= PG_PWR_STATE_COUNT) return;
    p->nas[st]  += nas;
    p->total_nas += nas;
}

void pg_power_charge(pg_power_t *p, pg_pwr_state_t st, uint32_t us)
{
    pg_power_charge_ua(p, st, pg_pwr_table[st].ua, us);
}

uint32_t pg_power_active_us(void)
{
    uint32_t us = 0;
    int i;
    for (i = PG_PWR_WAKE; i <= PG_PWR_RX; i++) us += pg_pwr_table[i].typ_us;
    return us;
}

uint32_t pg_power_cycle_nas(void)
{
    uint64_t nas = 0;
    int i;
    for (i = PG_PWR_WAKE; i <= PG_PWR_RX; i++)
        nas += ((uint64_t)pg_pwr_table[i].ua * (uint64_t)pg_pwr_table[i].typ_us) / 1000ull;
    return (uint32_t)nas;
}

uint32_t pg_power_cycle_uj(void)
{
    /* E[uJ] = Q[nAs] * V[mV] / 1e6.  2267742 nAs * 3600 mV / 1e6 = 8163.9 uJ. */
    uint64_t uj = ((uint64_t)pg_power_cycle_nas() * PG_CELL_V_MV) / 1000000ull;
    return (uint32_t)uj;
}

uint32_t pg_power_avg_na(uint32_t period_s)
{
    uint64_t active_nas = pg_power_cycle_nas();
    uint32_t active_us  = pg_power_active_us();
    uint64_t period_us  = (uint64_t)period_s * 1000000ull;
    uint64_t sleep_us, sleep_nas, total;

    if (period_s == 0) return 0;
    sleep_us  = (period_us > active_us) ? (period_us - active_us) : 0;
    /* sleep charge[nAs] = uA * us / 1000 */
    sleep_nas = ((uint64_t)pg_pwr_table[PG_PWR_SLEEP].ua * sleep_us) / 1000ull;
    total     = active_nas + sleep_nas;
    /* average nA = total nAs / period s */
    return (uint32_t)(total / (uint64_t)period_s);
}

uint32_t pg_power_selfdis_na(void)
{
    /* 1.0 %/year of 1200 mAh = 12 mAh/year.  Spread over 8766 h that is
     * 1.369 uA = 1369 nA of drain that happens whether the node is on or
     * not.  At the idle cadence it is a QUARTER of the total budget, which
     * is why quoting "5.4 uA therefore 25 years" would be wrong by 45 %. */
    uint64_t uah_per_year = ((uint64_t)PG_CELL_NOMINAL_MAH * 1000ull
                             * PG_CELL_SELFDIS_PPM_YR) / 1000000ull;   /* uAh */
    return (uint32_t)((uah_per_year * 1000ull) / 8766ull);             /* nA  */
}

uint32_t pg_power_mission_na(uint32_t w_idle, uint32_t w_watch, uint32_t w_burst)
{
    uint64_t sum = (uint64_t)w_idle  * pg_power_avg_na(PG_PERIOD_IDLE_S)
                 + (uint64_t)w_watch * pg_power_avg_na(PG_PERIOD_WATCH_S)
                 + (uint64_t)w_burst * pg_power_avg_na(PG_PERIOD_BURST_S);
    uint32_t w = w_idle + w_watch + w_burst;
    if (w == 0) return 0;
    return (uint32_t)(sum / w) + pg_power_selfdis_na();
}

uint32_t pg_power_life_days(uint32_t avg_na)
{
    /* Usable capacity in nAh, then hours, then days.  avg_na is expected to
     * ALREADY include self-discharge when it comes from
     * pg_power_mission_na(); pg_power_avg_na() does not, so the caller adds
     * it - and pg_power_report() shows both columns so the difference is
     * visible rather than buried. */
    uint64_t usable_uah = ((uint64_t)PG_CELL_NOMINAL_MAH * 1000ull * PG_CELL_USABLE_PCT) / 100ull;
    uint64_t hours;
    if (avg_na == 0) return 0;
    hours = (usable_uah * 1000ull) / (uint64_t)avg_na;   /* nAh / nA = h */
    return (uint32_t)(hours / 24ull);
}

/* --------------------------------------------------------------------- */
/* Cell state                                                             */
/* --------------------------------------------------------------------- */

void pg_power_update_cell(pg_power_t *p, uint16_t ocv_mv, uint16_t loaded_mv)
{
    p->vbat_mv    = ocv_mv;
    p->vloaded_mv = loaded_mv;

    /* PASSIVATION.  A Li-SOCl2 cell that has sat at a few microamps for
     * years grows a LiCl film on the anode.  Its open-circuit voltage still
     * reads a healthy 3.6 V and its coulomb count still says 80 % - and then
     * it collapses to 2.4 V the first time the PA asks for 24 mA, the frame
     * is lost, and the node looks dead.  The ONLY way to see this is to load
     * it: hal_vbat_loaded_mv() applies a 50 mA pulse and measures under it.
     * The HLC (hybrid layer capacitor) in the BOM exists exactly to buffer
     * that pulse; a depassivation load is applied and the test repeated
     * before the cell is declared bad. */
    p->passivated = (ocv_mv >= 3500u && loaded_mv < PG_CELL_LOADED_MIN_MV) ? 1u : 0u;

    if (loaded_mv < PG_CELL_CRIT_MV || ocv_mv < PG_CELL_CRIT_MV) p->critical = 1;
    if (ocv_mv < PG_CELL_LOW_MV || p->passivated) p->low = 1;
    /* Latching: a cell that has been low once does not become healthy again
     * because it warmed up.  Recovery is a battery change, not a sunny day. */
}

uint8_t pg_power_pct(const pg_power_t *p)
{
    uint64_t usable_nah = (uint64_t)PG_CELL_NOMINAL_MAH * 1000ull
                          * PG_CELL_USABLE_PCT / 100ull * 1000ull;  /* nAh */
    uint64_t used_nah   = p->total_nas / 3600ull;                   /* nAs -> nAh */
    if (p->critical) return 0;
    if (used_nah >= usable_nah) return 0;
    return (uint8_t)(((usable_nah - used_nah) * 100ull) / usable_nah);
}

uint8_t pg_power_ocv_pct(uint16_t ocv_mv)
{
    /* Crude, and honestly labelled as such.  Li-SOCl2 sits at 3.6 V from
     * 100 % to about 10 % and then falls off a cliff, so this curve can only
     * distinguish "fine", "the knee has started" and "gone".  It exists to
     * cross-check the coulomb count, never to replace it. */
    if (ocv_mv >= 3550u) return 100;
    if (ocv_mv >= 3450u) return 60;
    if (ocv_mv >= 3300u) return 25;
    if (ocv_mv >= 3100u) return 10;
    if (ocv_mv >= 2900u) return 3;
    return 0;
}

int pg_power_allow_ota(const pg_power_t *p)
{
    /* ENERGY GATING.  Downloading 88 kB in 192-byte chunks is 470 frames.
     * Each costs an RX window plus a flash page write; the whole update is
     * about 1.5 mAh, which is 0.15 % of the cell but is also 280 times a
     * normal wake cycle.  Starting that on a cell that cannot finish it
     * leaves a node with a half-written slot in a panel that cannot be
     * de-energised without blacking out a neighbourhood.  So: */
    if (p->critical)   return 0;      /* below the TX floor entirely         */
    if (p->low)        return 0;      /* CELL_LOW latched                    */
    if (p->passivated) return 0;      /* it will droop out mid-download      */
    if (pg_power_pct(p) < PG_OTA_MIN_PCT) return 0;
    if (p->vloaded_mv < PG_CELL_LOADED_MIN_MV) return 0;
    return 1;
}

/* --------------------------------------------------------------------- */
/* Report                                                                 */
/* --------------------------------------------------------------------- */

void pg_power_report(const pg_power_t *p)
{
    uint32_t sd = pg_power_selfdis_na();
    uint32_t idle_na  = pg_power_avg_na(PG_PERIOD_IDLE_S);
    uint32_t watch_na = pg_power_avg_na(PG_PERIOD_WATCH_S);
    uint32_t burst_na = pg_power_avg_na(PG_PERIOD_BURST_S);
    uint32_t mis_na   = pg_power_mission_na(970, 25, 5);
    char     b1[24], b2[24], b3[24];
    int      i;

    hal_log("");
    hal_log("  ENERJI BUTCESI  (ER14250 Li-SOCl2, 1.2 Ah nominal, 3.6 V)");
    hal_log("  ----------------------------------------------------------------");
    hal_log("  durum      akim uA     sure ms      yuk nAs       enerji mJ");
    for (i = PG_PWR_WAKE; i <= PG_PWR_RX; i++) {
        uint32_t nas = (uint32_t)(((uint64_t)pg_pwr_table[i].ua
                                   * pg_pwr_table[i].typ_us) / 1000ull);
        uint32_t uj  = (uint32_t)(((uint64_t)nas * PG_CELL_V_MV) / 1000000ull);
        pg_fmt_scaled(b1, sizeof b1, (int32_t)pg_pwr_table[i].ua, 1, 0);
        pg_fmt_scaled(b2, sizeof b2, (int32_t)pg_pwr_table[i].typ_us, 1000, 2);
        pg_fmt_scaled(b3, sizeof b3, (int32_t)uj, 1000, 3);
        hal_logf("  %-9s %9s %11s %12lu %14s",
                 pg_pwr_table[i].name, b1, b2, (unsigned long)nas, b3);
    }
    pg_fmt_scaled(b1, sizeof b1, (int32_t)pg_pwr_table[PG_PWR_SLEEP].ua, 1, 1);
    hal_logf("  %-9s %9s   (B1 analog + FRAM standby + STOP2/RTC/IWDG payi)",
             "SLEEP", b1);

    pg_fmt_scaled(b1, sizeof b1, (int32_t)pg_power_active_us(), 1000, 1);
    pg_fmt_scaled(b2, sizeof b2, (int32_t)pg_power_cycle_nas(), 1000, 1);
    pg_fmt_scaled(b3, sizeof b3, (int32_t)pg_power_cycle_uj(), 1, 0);
    hal_logf("  toplam/cevrim: %s ms uyanik, %s uAs, %s uJ", b1, b2, b3);

    hal_log("");
    hal_log("  kadans      periyot   ort. akim   +oz desarj    omur");
    {
        static const uint32_t per[3] = { PG_PERIOD_IDLE_S, PG_PERIOD_WATCH_S,
                                         PG_PERIOD_BURST_S };
        static const char *nm[3] = { "IDLE ", "WATCH", "BURST" };
        uint32_t na[3];
        na[0] = idle_na; na[1] = watch_na; na[2] = burst_na;
        for (i = 0; i < 3; i++) {
            uint32_t days = pg_power_life_days(na[i] + sd);
            pg_fmt_scaled(b1, sizeof b1, (int32_t)na[i], 1000, 2);
            pg_fmt_scaled(b2, sizeof b2, (int32_t)(na[i] + sd), 1000, 2);
            pg_fmt_scaled(b3, sizeof b3, (int32_t)days, 365, 1);
            hal_logf("  %s      %5lu s  %8s uA %8s uA  %6lu gun (%s yil)",
                     nm[i], (unsigned long)per[i], b1, b2,
                     (unsigned long)days, b3);
        }
    }

    pg_fmt_scaled(b1, sizeof b1, (int32_t)mis_na, 1000, 2);
    pg_fmt_scaled(b2, sizeof b2, (int32_t)pg_power_life_days(mis_na), 365, 1);
    hal_logf("  GOREV KARMASI (%%97.0 idle / %%2.5 watch / %%0.5 burst):");
    hal_logf("     ortalama %s uA  ->  %lu gun = %s YIL  (B1 TAHMIN; fiziksel olcum yok)",
             b1, (unsigned long)pg_power_life_days(mis_na), b2);
    hal_log("  Enerji hasadi YOK. Birincil Li-SOCl2 hucre, sarj devresi yok.");

    if (p) {
        pg_fmt_scaled(b1, sizeof b1, (int32_t)p->vbat_mv, 1000, 3);
        pg_fmt_scaled(b2, sizeof b2, (int32_t)p->vloaded_mv, 1000, 3);
        pg_fmt_scaled(b3, sizeof b3, (int32_t)(uint32_t)(p->total_nas / 1000ull), 1000, 1);
        hal_logf("  HAL girdisi (hostta simule): OCV %s V, 50 mA yuk altinda %s V, harcanan %s uAs,"
                 " kalan %%%u%s", b1, b2, b3, (unsigned)pg_power_pct(p),
                 p->passivated ? "  [PASIVASYON]" : "");
    }
    hal_log("  ----------------------------------------------------------------");
}

"""Incident lifecycle and alarm hygiene.

Detection is the easy half.  What decides whether a condition-monitoring system
is still switched on in month twelve is what happens between "the number went
up" and "somebody's phone rang".  This module is that half, and every rule in it
exists because the absence of that rule has killed a real deployment somewhere.

Hygiene, in one list
--------------------

* **40 % hysteresis dead band.**  An alarm raised at 5.0 K clears at 3.0 K.
  Without it a joint sitting exactly on a threshold produces one incident per
  evaluation, forever.
* **N-of-M debounce, 3 of 5 daily evaluations.**  theta is a daily median; three
  qualifying days out of five is the smallest window that survives one bad day
  of data without waiting a fortnight.
* **24 h minimum dwell before escalation.**  A new incident is visible on the
  dashboard immediately and reaches a phone only after a day, unless it is ACIL.
* **Asymmetric de-escalation: seven consecutive clear days to close.**  Raising
  fast and clearing slowly is the correct asymmetry for a degradation process
  that is not repaired by the weather changing.
* **Dedup on (panel, joint, mode, severity), one notification per key per 24 h.**
* **Panel roll-up at three or more affected joints.**  Three hot joints in one
  panel is one story about the panel, not three stories about three bolts.
* **Fleet systemic roll-up above 20 % of the fleet within an hour.**  If a fifth
  of the estate lights up at once, the estate is not failing - something common
  to it is, and we say so instead of sending twenty crews.
* **Per-severity storm cap, ACIL exempt.**  A cap that could silence an ACIL is
  not a cap, it is a fault.

Two-channel dispatch
--------------------

One agreeing sensor family is a WATCH.  Two are a DISPATCH.  Only KRITIK and
ACIL reach a phone; IZLE is a queue item and never an interruption.  The family
count comes from ``rules.fusion`` and it counts *measurement principles*, not
statistics: theta and its CUSUM come from the same TMP117 and count once.

The RULED OUT block
-------------------

Every incident ships with a list naming each confounder and how it was excluded.
This is the single most persuasive thing the product does, because a
maintenance engineer's first reaction to any thermal alarm is "it is just the
load" - and the answer is already on the screen, with the numbers.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

from panogoz.contracts import assets
from panogoz.contracts.channels import (
    DISPATCH_SEVERITIES,
    MODES_BY_KEY,
    SEVERITIES,
    SEVERITY_ACTION_TR,
    SEVERITY_RANK,
    SEVERITY_TR,
)
from panogoz.contracts.live import AlarmView, JointView, PanelLive
from panogoz.rules import fusion, suppression

# --------------------------------------------------------------------------
# Hygiene constants
# --------------------------------------------------------------------------

#: One evaluation bucket.  theta is a daily statistic, so the debounce and the
#: de-escalation counters advance once per day.
EVAL_PERIOD_S = 86400.0

DEBOUNCE_N = 3          #: qualifying buckets required...
DEBOUNCE_M = 5          #: ...out of this many most recent buckets
CLEAR_DAYS = 7          #: consecutive clear buckets required to close
DWELL_S = 86400.0       #: minimum age before an incident may reach a phone
DEDUP_S = 86400.0       #: one notification per (panel, joint, mode, severity)

ROLLUP_JOINTS = 3       #: this many affected joints -> one panel-level incident
FLEET_WINDOW_S = 3600.0
FLEET_FRACTION = 0.20   #: above this share of the fleet in an hour -> systemic

#: Per-severity incidents that may be dispatched per hour, fleet-wide.
#: ACIL is deliberately absent: it is exempt.
STORM_CAP_PER_HOUR: dict[str, int] = {"BILGI": 200, "IZLE": 60, "UYARI": 24, "KRITIK": 8}

#: Panel-level (non-joint) modes are graded straight off the fused risk.
RISK_SEVERITY: tuple[tuple[float, str], ...] = (
    (0.85, "KRITIK"),
    (0.65, "UYARI"),
    (0.40, "IZLE"),
)

#: R_th,local for a 240 mm2 bolted cable lug, K/W.  Excess resistance is ALWAYS
#: an interval because this is known only to a factor of two.
R_TH_LUG_LO = 2.0
R_TH_LUG_HI = 4.0

MODE_TITLE_TR: dict[str, str] = {
    "loose_connection": "bağlantı direnci artıyor",
    "overload": "sürekli aşırı yük",
    "arc_integrity": "ark koruma bütünlüğü şüpheli",
    "thermal_runaway": "bölme sıcaklığı yükseliyor, soğutma yetersiz",
    "harmonic_neutral": "nötr harmonik yüklenmesi",
    "moisture": "yoğuşma riski",
    "insulation": "yalıtımda zayıflama işareti",
}

#: Panel states that block a dispatch outright.  Note what this is NOT: it does
#: not blank the measurement or lower the joint's grade.  A lug at 99 C during a
#: regional voltage event is still a lug at 99 C and still says so on the
#: dashboard; what the flag stops is a crew being sent while the most likely
#: explanation is upstream of the panel.  The only exemption is an absolute
#: temperature breach, which dispatches through everything.
NO_DISPATCH_FLAGS: dict[str, str] = {
    "GRID_DISTURBANCE": "Şebeke tarafında olay sürüyor (üç fazda birlikte yükselen gerilim THD'si)",
    "GRID_WINDOW": "Frekans penceresi dışında, bölgesel olay penceresi açık",
    "INRUSH": "Trafo devreye alma (inrush) sınıflandırıldı",
    "LOAD_HOLD": "Yük sıçraması sonrası 3τ ısıl bekleme süresi",
    "MAINTENANCE": "Pano bakım modunda",
    "LEARN_MODE": "Devreye alma öğrenme haftası",
    "STALE": "Veri bayat",
    "DE_ENERGISED": "Pano enerjisiz",
    "SENSITIVITY_LOW": "Görünürlük düşük, θ güvenilir değil",
}

STATE_ACIK = "ACIK"
STATE_ONAY = "ONAYLANDI"
STATE_KAPANDI = "KAPANDI"


def _pretty(label: str) -> str:
    """Asset labels are ASCII for code safety; operators read Turkish."""
    return (label.replace("Cikis", "Çıkış")
                 .replace("Ana giris", "Ana giriş")
                 .replace(" / ", " · "))


# --------------------------------------------------------------------------
# Candidates
# --------------------------------------------------------------------------

@dataclass
class Candidate:
    """One (joint, mode) or (panel, mode) proposition for this evaluation."""

    key: tuple[str, str | None, str]
    panel_key: str
    joint_key: str | None
    mode: str
    severity: str
    metric: float
    raise_level: float
    unit: str
    absolute: bool = False       #: exempt from debounce and from the family cap
    families: list[str] = field(default_factory=list)
    detail: dict = field(default_factory=dict)

    @property
    def qualifying(self) -> bool:
        return SEVERITY_RANK[self.severity] >= SEVERITY_RANK["IZLE"]

    @property
    def clear_level(self) -> float:
        return fusion.HYSTERESIS * self.raise_level


# --------------------------------------------------------------------------
# AlarmManager
# --------------------------------------------------------------------------

class AlarmManager:
    """Opens, updates and closes incidents for a fleet of panels.

    The rolling debounce and clear-day counters live in memory, keyed by
    (panel, joint, mode).  They are a five-day and a seven-day window
    respectively; on a process restart they refill from live data within a week,
    and the incident rows themselves - the thing an operator and an auditor care
    about - are in SQLite from the first cycle.
    """

    def __init__(self, store, *, eval_period_s: float = EVAL_PERIOD_S,
                 fleet_size: int = 1, ack_salt: str = "PANOGOZ") -> None:
        self.store = store
        self.eval_period_s = float(eval_period_s)
        self.fleet_size = max(1, int(fleet_size))
        self.ack_salt = ack_salt
        self._daily: dict[tuple, dict[int, dict]] = {}
        self._raise_level: dict[tuple, float] = {}
        self._last_notify: dict[tuple, float] = {}
        self._storm: dict[tuple[str, int], int] = {}
        self._fleet_events: list[tuple[float, str]] = []
        self.pending_dispatch: list[dict] = []
        self.systemic: bool = False
        self.systemic_note: str = ""

    # ------------------------------------------------------------ tokens --

    def ack_token(self, incident_id: int) -> str:
        """Deterministic 4-digit per-incident token.

        Deterministic so it can be recomputed after a restart, salted so it
        cannot be guessed from the incident id alone.  Without this, anyone who
        can send an SMS and can count could silence a KRITIK.
        """
        import hashlib

        h = hashlib.sha256(f"{self.ack_salt}|{incident_id}".encode("utf-8")).hexdigest()
        return f"{int(h[:8], 16) % 10000:04d}"

    # -------------------------------------------------------- candidates --

    def _joint_candidates(self, live: PanelLive, now: float) -> list[Candidate]:
        out: list[Candidate] = []
        skip = fusion.suppressed_joints(live)
        d = fusion.detail(live)
        fams = list(d.get("families", []))
        for j in live.joints:
            if not j.monitored or j.key in skip:
                continue
            mode = "harmonic_neutral" if j.conductor == "N" else "loose_connection"
            sev = fusion.joint_severity(j)
            metric = j.theta_k if j.theta_k is not None else 0.0
            level = fusion.THETA_RAISE.get(sev, fusion.THETA_RAISE["IZLE"])
            absolute = j.temp_c is not None and j.temp_c >= fusion.TEMP_RAISE["KRITIK"]
            if absolute:
                metric = j.temp_c
                level = fusion.TEMP_RAISE["KRITIK"]
            out.append(Candidate(
                key=(live.panel_key, j.key, mode),
                panel_key=live.panel_key, joint_key=j.key, mode=mode,
                severity=sev, metric=metric, raise_level=level,
                unit="°C" if absolute else "K",
                absolute=absolute, families=fams,
                detail={"theta_k": j.theta_k, "temp_c": j.temp_c,
                        "conductor": j.conductor, "label": j.label},
            ))
        return out

    def _panel_candidates(self, live: PanelLive, now: float) -> list[Candidate]:
        d = fusion.detail(live)
        fams = list(d.get("families", []))
        out: list[Candidate] = []
        for mode in ("overload", "arc_integrity", "thermal_runaway", "moisture", "insulation"):
            r = float(live.risks.get(mode, 0.0))
            sev = "BILGI"
            level = RISK_SEVERITY[-1][0]
            for thr, name in RISK_SEVERITY:
                if r >= thr:
                    sev, level = name, thr
                    break
            mode_fams = list(d.get("modes", {}).get(mode, {}).get("families", []))
            absolute = False

            # AN ARC TRIP IS A FACT, NOT A RISK ESTIMATE.
            #
            # Register 1300 bit 0 means a SIL-2 device has already fired its
            # trip contacts.  Grading that through a naive-Bayes risk with a
            # capped log-odds term would put it at r ~ 0.16 and it would never
            # reach anybody's phone.  So it takes the same path as an absolute
            # over-temperature: straight to the top of the ladder, exempt from
            # the debounce and from the two-channel family cap.
            #
            # It matters more here than it would elsewhere: this panel has no LV
            # incoming breaker, so the fault was cleared from the medium-voltage
            # side and the whole secondary substation is now dark.
            if mode == "arc_integrity" and live.arc.fitted and live.arc.active_trip:
                sev, level, absolute = "ACIL", 0.0, True
                if "ARC" not in mode_fams:
                    mode_fams = ["ARC", *mode_fams]

            out.append(Candidate(
                key=(live.panel_key, None, mode),
                panel_key=live.panel_key, joint_key=None, mode=mode,
                severity=sev, metric=r, raise_level=level, unit="risk",
                absolute=absolute,
                families=mode_fams or fams,
                detail={"risk": r,
                        "arc_active_trip": bool(live.arc.fitted and live.arc.active_trip)},
            ))
        return out

    # ----------------------------------------------------------- buckets --

    def _bucket(self, now: float) -> int:
        return int(now // self.eval_period_s)

    def _record(self, cand: Candidate, now: float, open_level: float | None = None) -> dict:
        """Update the rolling daily record and report the debounce verdict.

        The clear test is measured against the level that RAISED the open
        incident, not against the level the current reading would raise.  An
        incident raised at 12 K clears at 7.2 K and stays open at 9 K; letting
        the threshold follow the reading downward would defeat the dead band
        entirely and produce one incident per evaluation.
        """
        b = self._bucket(now)
        hist = self._daily.setdefault(cand.key, {})
        cur = hist.setdefault(b, {"raise": False, "clear": True})
        clear_at = (fusion.HYSTERESIS * open_level) if open_level else cand.clear_level
        if cand.qualifying:
            cur["raise"] = True
            cur["clear"] = False
        elif cand.metric > clear_at:
            # Inside the dead band: neither a raise nor a clear.  This is what
            # the 40 % hysteresis buys - a joint hovering at threshold stops
            # generating events entirely.
            cur["clear"] = False
        for k in list(hist):
            if k <= b - max(DEBOUNCE_M, CLEAR_DAYS) - 1:
                del hist[k]
        recent = [hist.get(b - i, None) for i in range(DEBOUNCE_M)]
        hits = sum(1 for r in recent if r and r["raise"])
        streak = 0
        for i in range(CLEAR_DAYS + 2):
            r = hist.get(b - i)
            if r is None or not r["clear"]:
                break
            streak += 1
        return {"bucket": b, "hits": hits, "of": DEBOUNCE_M, "clear_streak": streak,
                "clear_at": clear_at,
                "debounced": hits >= DEBOUNCE_N or cand.absolute}

    # ------------------------------------------------------------ titles --

    def _title(self, live: PanelLive, joint: JointView | None, mode: str,
               severity: str) -> str:
        # An arc TRIP and a doubt about arc protection INTEGRITY are two
        # completely different messages, and they must not share a headline.
        # "Ark koruma bütünlüğü şüpheli" on a panel that has actually arced and
        # gone dark would read, to a control-room operator at 03:00, as a
        # maintenance note about a detector.
        if mode == "arc_integrity" and live.arc.fitted and live.arc.active_trip:
            where = self._arc_location(live)
            return f"{live.panel_key} · ARK AÇMASI — {where}"
        tail = MODE_TITLE_TR.get(mode, MODES_BY_KEY[mode].label_tr)
        if joint is None:
            return f"{live.panel_key} · pano geneli — {tail}"
        return f"{_pretty(joint.label)} — {tail}"

    @staticmethod
    def _arc_location(live: PanelLive) -> str:
        """Decode the TVOC-2 detector map into words a crew can act on.

        Registers 210/211 carry a 30-bit map (X1:1-10, X2:1-10, X3:1-10) and 212
        names the trip relay.  Reporting "somewhere in the panel" when the relay
        has told us which detector saw the light would be throwing away the one
        piece of information that decides where the crew starts looking.
        """
        arc = live.arc
        names: list[str] = []
        lo, hi = arc.detector_map_lo, arc.detector_map_hi
        for b in range(10):
            if lo & (1 << b):
                names.append(f"X1:{b + 1}")
        for b in range(10, 15):
            if lo & (1 << b):
                names.append(f"X2:{b - 9}")
        for b in range(5):
            if hi & (1 << b):
                names.append(f"X2:{b + 6}")
        for b in range(5, 15):
            if hi & (1 << b):
                names.append(f"X3:{b - 4}")
        if not names:
            return "dedektör bilinmiyor"
        return "dedektör " + ", ".join(names[:4])

    # ---------------------------------------------------------- evidence --

    def build_evidence(self, live: PanelLive, joint: JointView | None, mode: str) -> dict:
        """The "why" block: every number the conclusion rests on.

        Excess contact resistance is reported as an INTERVAL and never as a
        single number, because R_th,local for a 240 mm2 lug is known only to
        2-4 K/W.  Quoting one figure would be a fabricated precision, and a
        substation engineer will spot it.
        """
        d = fusion.detail(live)
        ev: dict[str, Any] = {
            "panel": live.panel_key,
            "mode": mode,
            "mode_label_tr": MODES_BY_KEY[mode].label_tr,
            "health_index": live.health_index,
            "risk": round(float(live.risks.get(mode, 0.0)), 4),
            "load_factor": round(live.load_factor, 3),
            "sensitivity_pct": round(live.sensitivity_pct, 1),
            "families": d.get("families", []),
            "family_labels_tr": [fusion.FAMILY_LABELS_TR[f] for f in d.get("families", [])],
            "status_flags": list(live.status_flags),
        }
        an = live.analyser or {}
        env = live.env or {}
        ev["analyser"] = {
            "i_l1_a": an.get("mpr.i_l1_a"), "i_l2_a": an.get("mpr.i_l2_a"),
            "i_l3_a": an.get("mpr.i_l3_a"), "i_n_a": an.get("mpr.i_n_a"),
            "freq_hz": an.get("mpr.freq_hz"),
            "thd_v_pct": [an.get(f"mpr.thd_v_l{p}_pct") for p in (1, 2, 3)],
            "thd_i_pct": [an.get(f"mpr.thd_i_l{p}_pct") for p in (1, 2, 3)],
        }
        ev["env"] = {
            "air_c": env.get("env.air_c"), "rh_pct": env.get("env.rh_pct"),
            "dewpoint_c": env.get("env.dewpoint_c"),
            "wall_c": env.get("env.wall_c"),
            "condensation_margin_k": env.get("env.condensation_margin_k"),
        }
        ev["terms"] = [
            {k: t[k] for k in ("evidence", "label_tr", "family", "value", "unit",
                               "llr", "coupling", "delta_logodds")}
            for t in d.get("modes", {}).get(mode, {}).get("terms", [])[:8]
        ]
        if joint is not None:
            i_ref = joint.rated_a or 1.0
            theta = joint.theta_k
            ev["joint"] = {
                "key": joint.key,
                "label_tr": _pretty(joint.label),
                "conductor": joint.conductor,
                "phase_colour_tr": assets.PHASE_COLOURS.get(joint.conductor, ""),
                "rated_a": joint.rated_a,
                "current_a": joint.current_a,
                "load_factor": round(joint.load_factor, 3),
                "temp_c": joint.temp_c,
                "sibling_median_c": joint.sibling_median_c,
                "delta_t_k": (None if joint.temp_c is None or joint.sibling_median_c is None
                              else round(joint.temp_c - joint.sibling_median_c, 2)),
                "theta_k": theta,
                "theta_min_k": joint.theta_min_k,
                "cusum": joint.cusum,
                "slope_k_per_week": joint.slope_k_per_week,
                "alarm_days": joint.alarm_days,
                "changepoint_ts": joint.changepoint_ts,
            }
            if theta is not None and i_ref:
                lo = theta / (R_TH_LUG_HI * i_ref ** 2) * 1e6
                hi = theta / (R_TH_LUG_LO * i_ref ** 2) * 1e6
                ev["excess_resistance"] = {
                    "lo_uohm": round(lo, 1),
                    "hi_uohm": round(hi, 1),
                    "r_th_k_per_w": [R_TH_LUG_LO, R_TH_LUG_HI],
                    "note_tr": (
                        f"ΔR = θ / (R_th · I_ref²). Pabuç için R_th,yerel yalnız "
                        f"{R_TH_LUG_LO:g}-{R_TH_LUG_HI:g} K/W aralığında bilinir; bu yüzden "
                        f"fazla direnç tek bir sayı olarak DEĞİL, aralık olarak verilir."
                    ),
                }
            ev["thresholds"] = {
                "theta_raise_k": fusion.THETA_RAISE,
                "temp_raise_c": fusion.TEMP_RAISE,
                "hysteresis": fusion.HYSTERESIS,
                "clear_at_k": round(fusion.HYSTERESIS *
                                    fusion.THETA_RAISE.get(joint.severity,
                                                           fusion.THETA_RAISE["IZLE"]), 2),
            }
        return ev

    # --------------------------------------------------------- ruled out --

    def build_ruled_out(self, live: PanelLive, joint: JointView | None, mode: str) -> list[str]:
        """Name every confounder and say how it was excluded."""
        out: list[str] = []
        an = live.analyser or {}
        env = live.env or {}

        if joint is not None and joint.theta_k is not None:
            lf = joint.load_factor or live.load_factor or 0.0
            out.append(
                f"Yük etkisi ELENDİ — θ = [T − kardeş medyanı] / (I/I_ref)² ile normalize "
                f"edildi. Ölçüm anındaki yük faktörü %{100 * lf:.0f}, I_ref = "
                f"{joint.rated_a:.0f} A. I² bölündüğü için θ yükten bağımsızdır."
            )
            if joint.temp_c is not None and joint.sibling_median_c is not None:
                out.append(
                    f"Ortam, mevsim ve güneş etkisi ELENDİ — kardeş fazlar aynı bölmede, "
                    f"aynı anda ölçüldü. Bu iletken {joint.temp_c:.1f} °C, kardeş medyanı "
                    f"{joint.sibling_median_c:.1f} °C, fark "
                    f"{joint.temp_c - joint.sibling_median_c:+.1f} K. Fark alındığı için "
                    f"ortak ortam terimi sadeleşir (Tablo 1 dahili: ortam max 40 °C)."
                )
            spec = assets.JOINTS_BY_KEY.get(joint.key)
            group = spec.sibling_group if spec else ""
            if joint.conductor == "N":
                out.append(
                    f"Kardeş karşılaştırması YAPILDI — nötr, faz kardeşleriyle KIYASLANMAZ: "
                    f"dengesizliği ve üçün katı harmonikleri taşır. '{group}' grubunda on "
                    f"nötr pabucu birbirinin akranıdır ve H3 kuralıyla (K_N = ΔT_N/I_N²) "
                    f"değerlendirilir."
                )
            elif group:
                out.append(
                    f"Kardeş karşılaştırması YAPILDI — '{group}' grubunda üç faz aynı barada, "
                    f"aynı yaşta, aynı yüzeyde, aynı akımda. Kurulum günü geçerli bir "
                    f"referanstır; geçmiş veri gerekmez."
                )
            if joint.theta_min_k is not None:
                out.append(
                    f"Görünürlük DOĞRULANDI — θ_min = 3σ/f² = {joint.theta_min_k:.2f} K, "
                    f"ölçülen θ = {joint.theta_k:.2f} K. Ölçüm tespit tabanının üzerindedir."
                )
            out.append(
                "Yayıcılık ELENDİ — kalaylı bakır bara (ε≈0.05) hedeflenmedi. Ölçüm, kablo "
                "kılıfı ve pabuç üzerinden yapılır; termal dizide karşılaştırılan yüzeyler "
                "özdeş olduğu için ε sadeleşir."
            )

        thd_v = [an.get(f"mpr.thd_v_l{p}_pct") for p in (1, 2, 3)]
        if all(v is not None for v in thd_v):
            out.append(
                f"Şebeke tarafı KONTROL EDİLDİ — gerilim THD'si %{thd_v[0]:.1f} / "
                f"%{thd_v[1]:.1f} / %{thd_v[2]:.1f}. Üç fazda birlikte yükselme yok, "
                f"olay pano içindedir."
            )
        f = an.get("mpr.freq_hz")
        if f is not None:
            out.append(
                f"Bölgesel olay ELENDİ — frekans {f:.2f} Hz, "
                f"{suppression.FREQ_LO_HZ}-{suppression.FREQ_HI_HZ} Hz penceresi içinde."
            )
        i_n = an.get("mpr.i_n_a")
        i_ph = [an.get(f"mpr.i_l{p}_a") for p in (1, 2, 3)]
        if i_n is not None and all(v is not None for v in i_ph):
            mean_i = sum(i_ph) / 3.0
            out.append(
                f"Harmonik düzeltmesi YAPILDI — I_N = {i_n:.0f} A, faz ortalaması "
                f"{mean_i:.0f} A. Üçün katı harmonikler sıfır bileşendir ve aritmetik "
                f"toplanır (I_N = 3·h3·I1); nötr ısınması K_N = ΔT_N/I_N² üzerinden ayrı "
                f"değerlendirildi. Türkiye AG fiderlerinde %20-40 faz dengesizliği olağandır, "
                f"denge varsayılmadı."
            )
        orders = suppression.device_orders(live)
        if orders:
            out.append(
                "Sensör kalıntısı ANORMAL — " +
                "; ".join(f"{o['device']}: {o['reason']}" for o in orders) +
                ". Bu bulgu CİHAZ iş emrine yönlendirildi."
            )
        else:
            out.append(
                "Sensör kalıntısı NORMAL — MOUNT_LOST / AIM_SHIFTED / CELL_LOW yok, takılı "
                "veya sapan sensör tespit edilmedi."
            )
        cm = env.get("env.condensation_margin_k")
        if cm is not None and mode != "moisture":
            out.append(
                f"Yoğuşma ELENDİ — en soğuk yüzeye göre yoğuşma payı {cm:.1f} K "
                f"(duvar sıcaklığı, ortamın τ≈90 dk'lık birinci derece gecikmesi)."
            )
        if live.pd.qmax_db:
            out.append(
                f"RF kanalı DESTEKLEYİCİ, tek başına yönlendirici DEĞİL — {live.pd.qmax_db:.1f} dB, "
                f"sınıf {live.pd.klass_label or live.pd.klass}. 400 V'ta Paschen minimumu "
                f"327 V'un üzerinde klasik KD oluşmaz; ölçülen, gevşek bağlantı mikro-arkıdır "
                f"ve IEC 60270 izlenebilir değildir."
            )
        d = fusion.detail(live)
        fams = d.get("families", [])
        out.append(
            f"Teyit kanalı sayısı = {len(fams)} ({', '.join(fusion.FAMILY_LABELS_TR[x] for x in fams) or 'yok'}). "
            + ("İki bağımsız ölçüm ilkesi aynı sonucu veriyor → ekip yönlendirilebilir."
               if len(fams) >= 2 else
               "Tek kanal → izleme kaydı; ekip yönlendirilmez.")
        )
        return out

    # -------------------------------------------------------- reconcile ---

    def reconcile(self, live: PanelLive, now: float) -> PanelLive:
        """Fold this cycle's candidates into the incident table."""
        by_joint = {j.key: j for j in live.joints}
        cands = self._joint_candidates(live, now) + self._panel_candidates(live, now)

        opened_this_cycle: list[dict] = []
        affected_joints: list[str] = []

        for c in cands:
            existing = self.store.find_open_incident(c.panel_key, c.joint_key, c.mode)
            verdict = self._record(c, now, self._raise_level.get(c.key) if existing else None)

            if c.qualifying and verdict["debounced"]:
                if c.joint_key:
                    affected_joints.append(c.joint_key)
                joint = by_joint.get(c.joint_key) if c.joint_key else None
                if existing is None:
                    inc_id = self._open(live, joint, c, now, verdict)
                    opened_this_cycle.append({"id": inc_id, "cand": c})
                else:
                    self._update(live, joint, c, existing, now, verdict)
                self._raise_level[c.key] = c.raise_level
            elif existing is not None:
                if verdict["clear_streak"] >= CLEAR_DAYS:
                    self.store.update_incident(
                        existing["id"], state=STATE_KAPANDI, closed_at=now,
                        action=(f"Kendiliğinden kapandı: {CLEAR_DAYS} ardışık gün boyunca "
                                f"ölçüm, kaldırma eşiğinin %{100 * fusion.HYSTERESIS:.0f}'inin "
                                f"altında kaldı."),
                    )
                    self._raise_level.pop(c.key, None)
                else:
                    # Still open: below threshold but not yet seven clear days.
                    self.store.update_incident(
                        existing["id"],
                        evidence=self.build_evidence(live, by_joint.get(c.joint_key or ""), c.mode),
                    )

        self._rollup(live, affected_joints, now)
        self._fleet(live, opened_this_cycle, now)
        self.store.commit()
        self._publish(live, now)
        return live

    # ------------------------------------------------------------ open/update --

    def _open(self, live: PanelLive, joint: JointView | None, c: Candidate,
              now: float, verdict: dict) -> int:
        mode = MODES_BY_KEY[c.mode]
        evidence = self.build_evidence(live, joint, c.mode)
        evidence["debounce"] = verdict
        ruled = self.build_ruled_out(live, joint, c.mode)
        title = self._title(live, joint, c.mode, c.severity)
        action = mode.action_tr
        if c.mode == "arc_integrity" and live.arc.fitted and live.arc.active_trip:
            action = (
                "Ark açması gerçekleşti. Pano büyük olasılıkla enerjisizdir "
                "(AG girişinde kesici yoktur, açma OG tarafından yapılır). "
                "Ekibi yönlendirin, açma öncesi kayıtları ve TVOC-2 açma "
                "kaydını (reg 100-147) alın, enerji vermeden önce pano içini "
                "gözle kontrol ettirin."
            )
        inc_id = self.store.open_incident(
            panel_key=c.panel_key, joint_key=c.joint_key, mode=c.mode,
            severity=c.severity, state=STATE_ACIK, opened_at=now, updated_at=now,
            title=title, evidence=evidence, ruled_out=ruled, action=action,
            dispatched=0,
        )
        self.store.update_incident(inc_id, ack_token=self.ack_token(inc_id))
        self.store.audit("rules.alarms", "incident.open", f"incident:{inc_id}",
                         {"panel": c.panel_key, "joint": c.joint_key, "mode": c.mode,
                          "severity": c.severity, "metric": c.metric})
        self._maybe_dispatch(live, inc_id, c, now, opened_at=now)
        return inc_id

    def _update(self, live: PanelLive, joint: JointView | None, c: Candidate,
                existing: dict, now: float, verdict: dict) -> None:
        # Asymmetric: severity may rise at once, and may never fall while open.
        old = existing["severity"]
        sev = c.severity if SEVERITY_RANK[c.severity] > SEVERITY_RANK[old] else old
        evidence = self.build_evidence(live, joint, c.mode)
        evidence["debounce"] = verdict
        self.store.update_incident(
            existing["id"], severity=sev, evidence=evidence,
            ruled_out=self.build_ruled_out(live, joint, c.mode),
            title=self._title(live, joint, c.mode, sev),
        )
        if sev != old:
            self.store.audit("rules.alarms", "incident.escalate", f"incident:{existing['id']}",
                             {"from": old, "to": sev})
        c.severity = sev
        self._maybe_dispatch(live, existing["id"], c, now,
                             opened_at=float(existing["opened_at"]),
                             already=bool(existing["dispatched"]))

    # ------------------------------------------------------------ dispatch --

    def _maybe_dispatch(self, live: PanelLive, inc_id: int, c: Candidate, now: float,
                        *, opened_at: float, already: bool = False) -> None:
        """Decide whether this incident is allowed to reach a phone.

        Order matters and every gate is a separate refusal with its own reason,
        because "we did not call you and here is which rule stopped us" is a
        supportable answer and "the alarm did not fire" is not.
        """
        reasons: list[str] = []
        if c.severity not in DISPATCH_SEVERITIES:
            reasons.append(f"{SEVERITY_TR[c.severity]} seviyesi telefona çıkmaz — "
                           f"{SEVERITY_ACTION_TR[c.severity]}")
        if len(c.families) < 2 and not c.absolute:
            reasons.append(f"Tek kanal teyidi ({', '.join(c.families) or 'yok'}) — "
                           f"iki bağımsız ölçüm ilkesi gerekir")
        if c.severity != "ACIL" and (now - opened_at) < DWELL_S:
            reasons.append(f"24 saat bekleme süresi dolmadı "
                           f"({(now - opened_at) / 3600.0:.1f}/24 saat)")
        dedup_key = (c.panel_key, c.joint_key, c.mode, c.severity)
        last = self._last_notify.get(dedup_key)
        if last is not None and (now - last) < DEDUP_S:
            reasons.append(f"Aynı anahtar için 24 saat içinde bildirim yapıldı "
                           f"({(now - last) / 3600.0:.1f} saat önce)")
        hour = int(now // 3600)
        cap = STORM_CAP_PER_HOUR.get(c.severity)
        if cap is not None and self._storm.get((c.severity, hour), 0) >= cap:
            reasons.append(f"Alarm fırtınası sınırı: {SEVERITY_TR[c.severity]} için saatte "
                           f"{cap} bildirim üst sınırı doldu (ACİL bu sınırdan muaftır)")
        if self.systemic and c.severity != "ACIL":
            reasons.append("Filo genelinde sistemik olay — tekil ekip yönlendirmesi durduruldu")
        if not c.absolute:
            for flag in live.status_flags:
                why = NO_DISPATCH_FLAGS.get(flag)
                if why:
                    reasons.append(f"{why} ({flag})")

        if reasons:
            self.store.add_suppression(
                panel_key=c.panel_key, joint_key=c.joint_key, mode=c.mode,
                reason="Bildirim yapılmadı: " + " | ".join(reasons),
                detail={"code": "NO_DISPATCH", "incident": inc_id, "severity": c.severity},
            )
            return
        self.store.update_incident(inc_id, dispatched=1)
        self._last_notify[dedup_key] = now
        self._storm[(c.severity, hour)] = self._storm.get((c.severity, hour), 0) + 1
        row = self.store.one("SELECT * FROM incident WHERE id=?", (inc_id,))
        if row is not None and not already:
            self.pending_dispatch.append(row)

    # -------------------------------------------------------------- rollup --

    def _rollup(self, live: PanelLive, affected: list[str], now: float) -> None:
        uniq = sorted(set(affected))
        key = (live.panel_key, None, "thermal_runaway")
        existing = self.store.find_open_incident(live.panel_key, None, "thermal_runaway")
        if len(uniq) < ROLLUP_JOINTS:
            return
        title = (f"{live.panel_key} · {len(uniq)} bağlantıda eş zamanlı ısınma — "
                 f"pano seviyesinde inceleme")
        ev = self.build_evidence(live, None, "thermal_runaway")
        ev["affected_joints"] = uniq
        ev["rollup_tr"] = (
            f"{len(uniq)} bağlantı aynı anda eşiği aştı. Üç veya daha fazla bağlantı, üç "
            f"ayrı cıvata hikâyesi değil, pano hakkında tek bir hikâyedir: havalandırma, "
            f"ortak yük veya ortak montaj hatası önce elenmelidir."
        )
        if existing is None:
            inc_id = self.store.open_incident(
                panel_key=live.panel_key, joint_key=None, mode="thermal_runaway",
                severity="UYARI", state=STATE_ACIK, opened_at=now, updated_at=now,
                title=title, evidence=ev,
                ruled_out=self.build_ruled_out(live, None, "thermal_runaway"),
                action="Bölme havalandırmasını, filtreleri ve ortak montaj torkunu kontrol edin",
                dispatched=0,
            )
            self.store.update_incident(inc_id, ack_token=self.ack_token(inc_id))
        else:
            self.store.update_incident(existing["id"], title=title, evidence=ev)

    def _fleet(self, live: PanelLive, opened: list[dict], now: float) -> None:
        """Systemic roll-up: a fifth of the fleet inside an hour is one event."""
        if opened:
            self._fleet_events.append((now, live.panel_key))
        self._fleet_events = [(t, p) for t, p in self._fleet_events
                              if now - t <= FLEET_WINDOW_S]
        panels = {p for _, p in self._fleet_events}
        share = len(panels) / float(self.fleet_size)
        self.systemic = share > FLEET_FRACTION and len(panels) >= 2
        if self.systemic:
            self.systemic_note = (
                f"Son {FLEET_WINDOW_S / 60:.0f} dakikada filonun %{100 * share:.0f}'i "
                f"({len(panels)}/{self.fleet_size} pano) alarm üretti. Bu, filonun bozulması "
                f"değil, filoya ortak bir şeyin olmasıdır: şebeke olayı, sıcak hava dalgası "
                f"veya bizim tarafımızda bir hata. Tekil ekip yönlendirmesi durduruldu, "
                f"tek bir sistemik olay açıldı."
            )
        else:
            self.systemic_note = ""

    # ------------------------------------------------------------- publish --

    def _publish(self, live: PanelLive, now: float) -> None:
        rows = self.store.query(
            "SELECT * FROM incident WHERE panel_key=? AND state != ? ORDER BY id",
            (live.panel_key, STATE_KAPANDI),
        )
        views: list[AlarmView] = []
        for r in rows:
            try:
                ev = json.loads(r["evidence"]) if r["evidence"] else {}
            except (json.JSONDecodeError, TypeError):
                ev = {}
            try:
                ro = json.loads(r["ruled_out"]) if r["ruled_out"] else []
            except (json.JSONDecodeError, TypeError):
                ro = []
            views.append(AlarmView(
                id=r["id"], panel_key=r["panel_key"], joint_key=r["joint_key"],
                mode=r["mode"], mode_label=MODES_BY_KEY[r["mode"]].label_tr,
                severity=r["severity"], state=r["state"], title=r["title"],
                opened_at=r["opened_at"], updated_at=r["updated_at"],
                acked_at=r["acked_at"], acked_by=r["acked_by"],
                action=r["action"], evidence=ev, ruled_out=ro,
                dispatched=bool(r["dispatched"]),
            ))
        live.alarms = views

    # ----------------------------------------------------------------- ack --

    def ack(self, incident_id: int, by: str, token: str | None = None) -> bool:
        """Acknowledge an incident.  Token is mandatory when one was issued.

        Returning False rather than raising is deliberate: the caller is often
        an SMS handler processing an untrusted message, and an exception path
        there is one bad refactor away from a crash loop.
        """
        row = self.store.one("SELECT * FROM incident WHERE id=?", (incident_id,))
        if row is None:
            return False
        expected = row["ack_token"]
        if expected:
            if token is None or str(token).strip() != str(expected):
                self.store.audit("rules.alarms", "ack.reject", f"incident:{incident_id}",
                                 {"by": by, "reason": "bad_token"})
                self.store.commit()
                return False
        if row["state"] == STATE_KAPANDI:
            return False
        now = time.time()
        self.store.update_incident(incident_id, state=STATE_ONAY, acked_at=now, acked_by=by)
        self.store.audit("rules.alarms", "ack", f"incident:{incident_id}", {"by": by})
        self.store.commit()
        return True


# --------------------------------------------------------------------------
# Self-test
# --------------------------------------------------------------------------

if __name__ == "__main__":  # pragma: no cover
    import os
    import tempfile

    from panogoz.rules.fusion import _demo_live
    from panogoz.store.db import Store

    print("=" * 78)
    print("PANO GOZ · alarms self-test")
    print("=" * 78)

    tmp = os.path.join(tempfile.mkdtemp(prefix="panogoz-alarm-"), "t.db")
    store = Store(tmp)
    mgr = AlarmManager(store, fleet_size=20)

    T0 = 1_760_000_000.0
    DAY = 86400.0
    TARGET = "C07-L2-PABUC"

    def cycle(day: int, theta: float, temp: float | None) -> PanelLive:
        live = _demo_live()
        live.ts = T0 + day * DAY
        j = [x for x in live.joints if x.key == TARGET][0]
        j.theta_k = theta
        j.temp_c = temp
        j.cusum = max(0.0, (theta - 2.0) * 2.0)
        j.slope_k_per_week = 0.4 if theta > 3 else 0.0
        j.theta_min_k = 0.9
        fusion.set_negative_evidence(live, {})
        fusion.apply(live)
        mgr.reconcile(live, T0 + day * DAY)
        return live

    print()
    print("[debounce 3-of-5 · gunluk degerlendirme]")
    for d in range(4):
        live = cycle(d, 13.5, 98.0)
        n = len(store.query("SELECT id FROM incident WHERE state!='KAPANDI'"))
        print(f"  gun {d}: theta=13.5 K  T=98 °C  acik olay={n}  "
              f"HI={live.health_index:5.1f}  {live.severity}")
    inc = store.one("SELECT * FROM incident WHERE joint_key=? ORDER BY id LIMIT 1", (TARGET,))
    assert inc is not None, "debounce never fired"
    print()
    print(f"  baslik : {inc['title']}")
    print(f"  seviye : {inc['severity']}   yonlendirildi: {bool(inc['dispatched'])}")
    print(f"  aksiyon: {inc['action']}")
    print(f"  token  : {inc['ack_token']}")
    print(f"  kuyruga alinan bildirim: {len(mgr.pending_dispatch)}")

    print()
    print("[RULED OUT blogu]")
    for line in json.loads(inc["ruled_out"]):
        print(f"  · {line}")

    ev = json.loads(inc["evidence"])
    print()
    print("[kanit · fazla direnc ARALIK olarak]")
    print("  " + json.dumps(ev.get("excess_resistance", {}), ensure_ascii=False))
    print()
    print("[kanit · en guclu terimler]")
    for t in ev["terms"][:5]:
        print(f"  {t['family']:<5} {t['evidence']:<20} llr={t['llr']:+.2f} "
              f"x{t['coupling']:.2f} = {t['delta_logodds']:+.2f}")

    lvl = fusion.THETA_RAISE[inc["severity"]]
    print()
    print(f"[hysteresis · 40 % olu bant]  kaldirma {lvl:.1f} K -> temizlenme "
          f"{fusion.HYSTERESIS * lvl:.1f} K")
    for d in range(4, 10):
        cycle(d, 9.0, 60.0)     # below the raise level, above the clear level
    row = store.one("SELECT * FROM incident WHERE id=?", (inc["id"],))
    print(f"  theta=9.0 K ile 6 gun: durum={row['state']}  seviye={row['severity']}")
    print("  (kaldirma esiginin altinda ama olu bandin icinde -> ne kapanir ne tekrar bildirilir)")
    assert row["state"] == STATE_ACIK
    assert row["severity"] == inc["severity"], "seviye acikken dusemez"

    print()
    print("[asimetrik geri cekilme · 7 ardisik temiz gun]")
    for d in range(10, 19):
        cycle(d, 1.0, 42.0)
        row = store.one("SELECT * FROM incident WHERE id=?", (inc["id"],))
        print(f"  temiz gun {d - 9}: durum = {row['state']}")
        if row["state"] == STATE_KAPANDI:
            break
    row = store.one("SELECT * FROM incident WHERE id=?", (inc["id"],))
    assert row["state"] == STATE_KAPANDI, row["state"]
    assert row["closed_at"] is not None
    print(f"  kapanis: {row['action']}")

    print()
    print("[pano seviyesinde toplama · >= 3 baglanti]")
    hot = ("C08-L1-PABUC", "C08-L2-PABUC", "C08-L3-PABUC", "C09-L1-PABUC")
    for d in range(30, 34):
        live = _demo_live()
        live.ts = T0 + d * DAY
        for jk in hot:
            j = [x for x in live.joints if x.key == jk][0]
            j.theta_k, j.temp_c, j.theta_min_k, j.cusum = 6.5, 88.0, 0.9, 9.0
        fusion.set_negative_evidence(live, {})
        fusion.apply(live)
        mgr.reconcile(live, T0 + d * DAY)
    roll = store.one("SELECT * FROM incident WHERE joint_key IS NULL AND mode='thermal_runaway' "
                     "ORDER BY id DESC LIMIT 1")
    assert roll is not None
    print(f"  {roll['title']}")
    print(f"  etkilenen: {json.loads(roll['evidence'])['affected_joints']}")

    print()
    print("[ack · kimlik dogrulamali]")
    open_inc = store.one("SELECT * FROM incident WHERE state='ACIK' AND joint_key IS NOT NULL "
                         "ORDER BY id DESC LIMIT 1")
    print(f"  olay #{open_inc['id']}  token={open_inc['ack_token']}")
    print(f"  yanlis token '0000' -> {mgr.ack(open_inc['id'], 'saha.ekibi', '0000')}")
    print(f"  token yok           -> {mgr.ack(open_inc['id'], 'saha.ekibi', None)}")
    print(f"  dogru token         -> {mgr.ack(open_inc['id'], 'saha.ekibi', open_inc['ack_token'])}")
    after = store.one("SELECT * FROM incident WHERE id=?", (open_inc["id"],))
    assert after["state"] == STATE_ONAY
    print(f"  durum={after['state']}  onaylayan={after['acked_by']}")
    print(f"  denetim zinciri: {store.verify_chain()}")

    print()
    print("[firtina siniri]")
    for sev, cap in STORM_CAP_PER_HOUR.items():
        print(f"  {SEVERITY_TR[sev]:<7} saatte en fazla {cap} bildirim")
    print("  Acil    sinirsiz (muaf)")

    sup = store.suppressions(since=0)
    print()
    print(f"[bildirim yapilmama gerekceleri] {len(sup)} satir")
    seen = set()
    for r in sup:
        tag = r["reason"][:60]
        if tag in seen:
            continue
        seen.add(tag)
        print(f"  · {r['reason'][:170]}")

    print()
    print("OK")

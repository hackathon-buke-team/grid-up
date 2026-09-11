"""Explainable PRPD classifier for the PANO GOZ RF / micro-arc channel.

HONESTY POSITION - read this before quoting anything from this module
=====================================================================
At 400 V **classical partial discharge does not occur**.  The Paschen minimum
in air is about 327 V, so a low-voltage panel simply does not have the field to
sustain a self-extinguishing gas discharge in a void.  What this channel really
measures is **micro-arcing across a loose or degrading bolted joint** - a series
arc that extinguishes and reignites every half cycle.

Three consequences, all of which we state on the operator's screen:

1. The HF coupling path from a micro-arc in a phase loop to an HFCT clamped on
   the PE stud is **unquantified**.  It depends on the loop geometry, on the
   cable screen bonding and on where the arc sits relative to the earth
   reference.  We never claim to know it.
2. An on-line measurement through an unknown path is **not IEC 60270
   traceable**.  IEC 60270 needs a calibrated injection into the terminals of a
   de-energised object; we cannot de-energise this panel at all, because there
   is no LV incoming breaker ("direk bara baglanti", Madde 2.2.10.2.vi).  So we
   report a **relative dB trend** and a **pC-EQUIVALENT**, never a traceable pC.
3. Therefore, at LV, **PD alone is never a dispatch**.  :func:`severity` is hard
   capped at ``UYARI``; only the fusion layer, and only with a thermal finding
   on the same joint, may raise a PD observation into ``KRITIK``/``ACIL``.
   Real, traceable PD monitoring belongs on the MV side of the substation.

Companion standard: **IEC TS 62478**, "High voltage test techniques - Measurement
of partial discharge by electromagnetic and acoustic methods".  That is the
document that covers exactly what we do - UHF/HF electromagnetic and acoustic
detection, explicitly non-conventional and explicitly not charge-calibrated.
We deliberately do **not** cite IEC/TS 61934: that one is about insulating
material under *repetitive impulse* stress from inverter drives, and only
marginally applies to a 50 Hz LV busbar joint.

Phase discrimination - the thing that makes the classes separable
-----------------------------------------------------------------
* Voltage-driven discharge (void, surface, corona) clusters on the **rising
  slopes of the voltage**, 0-90 deg and 180-270 deg, ahead of the peaks.
* A **series micro-arc** across a joint clusters on the **current zero
  crossings**, at ``phi`` and ``180+phi`` for a load of angle ``phi``.  It is
  NOT tied to the current peaks.

Unknown phase reference
-----------------------
The node's phase reference comes from the "Ic Ihtiyac" socket and may be on any
of the three phases, so every record carries an unknown 0/120/240 deg rotation.
:func:`features` therefore **de-rotates to a canonical frame** first: the second
circular harmonic of the pulse-density profile gives the axis of the 180-deg
lobe pair, and the record is rolled so that axis lands on 90 deg, in the middle
of the positive half cycle.  Every feature below is computed in that frame and
is invariant to the residual 180 deg flip.  The absolute phase can only be
recovered when the MPR-53CS cos phi and the socket's phase are both known; when
they are, ``prpd.current_zero_phase_deg`` says where the current zeros are.

Everything here works on the 64 x 32 histogram, because that is the only thing
the node ever transmits.  Passing a raw pulse list is accepted and is binned
first, so both paths give identical numbers.
"""

from __future__ import annotations

import math

import numpy as np

from panogoz.contracts import channels
from panogoz.sim import prpd

# ---------------------------------------------------------------------------

FEATURES = ("rate", "ndom", "asymmetry_n", "asymmetry_q", "sigma_phi", "cv",
            "cross_corr", "phase_entropy", "r_pq", "regularity", "qmax", "nqn")

#: Human-readable, Turkish, one line each.  The UI shows these next to the
#: numbers so an operator can argue with the classifier instead of trusting it.
FEATURE_LABELS_TR = {
    "rate": "Darbe hızı (1/s)",
    "ndom": "Çevrim başına baskın darbe",
    "asymmetry_n": "Yarım dalga sayı asimetrisi",
    "asymmetry_q": "Yarım dalga genlik asimetrisi",
    "sigma_phi": "Faz yayılımı (°)",
    "cv": "Genlik değişkenlik katsayısı",
    "cross_corr": "İki yarım dalga benzerliği",
    "phase_entropy": "Faz entropisi (0-1)",
    "r_pq": "Genlik-faz bağlaşımı",
    "regularity": "Genlik tekrarlılığı (0-1)",
    "qmax": "Tepe genlik (pC eşdeğeri)",
    "nqn": "Normalize gürültü sayısı",
}

#: Amplitude window, below the record peak, that defines the "dominant" pulse
#: population.  20 dB = a factor of ten in charge.
GATE_DB = 20.0
#: Canonical position of the lobe-pair axis after de-rotation: the middle of the
#: positive half cycle, as far from the 0/180 deg boundary as it can be.
CANON_AXIS_DEG = 90.0

_LV_CAVEAT_TR = (
    " Not: 400 V'ta klasik kısmi deşarj oluşmaz (Paschen minimumu 327 V); bu "
    "kanal gevşek bağlantı mikro-arkını ölçer, değer pC EŞDEĞERİDİR ve IEC "
    "60270 izlenebilir DEĞİLDİR. AG tarafında bu kanal tek başına ekip "
    "yönlendirmez, yalnız ısıl bulguyu destekler."
)


# ---------------------------------------------------------------------------
# small weighted helpers (the histogram cells are the samples, counts the
# weights - a few hundred cells, so this is cheap and exact)
# ---------------------------------------------------------------------------

def _wsum(w) -> float:
    return float(np.sum(w))


def _wmean(x, w) -> float:
    s = _wsum(w)
    return float(np.sum(x * w) / s) if s > 0 else 0.0


def _wstd(x, w) -> float:
    s = _wsum(w)
    if s <= 0:
        return 0.0
    m = _wmean(x, w)
    return float(math.sqrt(max(float(np.sum(w * (x - m) ** 2)) / s, 0.0)))


def _circ_std_deg(phi_deg, w) -> float:
    s = _wsum(w)
    if s <= 0:
        return 0.0
    r = np.radians(phi_deg)
    c = float(np.sum(w * np.cos(r)) / s)
    sn = float(np.sum(w * np.sin(r)) / s)
    R = min(1.0, math.hypot(c, sn))
    return math.degrees(math.sqrt(max(-2.0 * math.log(max(R, 1e-9)), 0.0)))


def _wpercentile(x, w, p: float) -> float:
    x = np.asarray(x, dtype=float)
    w = np.asarray(w, dtype=float)
    if x.size == 0 or x.shape != w.shape:
        return 0.0
    order = np.argsort(x)
    xs, ws = x[order], np.asarray(w, dtype=float)[order]
    cum = np.cumsum(ws)
    if cum[-1] <= 0:
        return float(xs[-1])
    idx = int(np.searchsorted(cum, p / 100.0 * cum[-1]))
    return float(xs[min(idx, xs.size - 1)])


def _wcorr(x, y, w) -> float:
    s = _wsum(w)
    if s <= 0:
        return 0.0
    mx, my = _wmean(x, w), _wmean(y, w)
    sx, sy = _wstd(x, w), _wstd(y, w)
    if sx <= 1e-12 or sy <= 1e-12:
        return 0.0
    return float(np.sum(w * (x - mx) * (y - my)) / s / (sx * sy))


# ---------------------------------------------------------------------------
# canonical de-rotation
# ---------------------------------------------------------------------------

def canonical_rotation_bins(hist: np.ndarray, gate_db: float = GATE_DB) -> int:
    """How many phase bins to roll so the lobe-pair axis lands on 90 deg.

    Uses the second circular harmonic of the *dominant* pulse-density profile
    (the pattern is a 180-deg-periodic lobe pair for every real class), falling
    back to all pulses when the dominant set is too thin.  The 180 deg residual
    ambiguity is deliberately left alone - every feature below is blind to it.
    """
    h = np.asarray(hist, dtype=float)
    if h.sum() <= 0:
        return 0
    amax = _amax_db(h)
    dom = h[:, prpd.AMP_CENTRES_DB > (amax - gate_db)].sum(axis=1)
    prof = dom if dom.sum() >= 50 else h.sum(axis=1)
    ang = np.radians(prpd.PHASE_CENTRES_DEG)
    z2 = complex(float(np.sum(prof * np.cos(2 * ang))),
                 float(np.sum(prof * np.sin(2 * ang))))
    if abs(z2) < 1e-9:
        return 0
    axis = (math.degrees(math.atan2(z2.imag, z2.real)) / 2.0) % 180.0
    return int(round((CANON_AXIS_DEG - axis) / prpd.DEG_PER_PHASE_BIN)) % prpd.N_PHASE


def _amax_db(h: np.ndarray) -> float:
    """99.5th percentile amplitude of the record, in dB(pC)."""
    marg = h.sum(axis=0)
    return _wpercentile(prpd.AMP_CENTRES_DB, marg, 99.5)


# ---------------------------------------------------------------------------
# features
# ---------------------------------------------------------------------------

def features(hist_or_pulses, cycles: int = prpd.DEFAULT_CYCLES,
             f_hz: float = prpd.F_NOMINAL_HZ, gate_db: float = GATE_DB,
             derotate: bool = True) -> dict[str, float]:
    """The twelve PRPD features, computed in the canonical (de-rotated) frame.

    Accepts either a 64 x 32 histogram (what the node sends) or a list of
    ``(phase_deg, amplitude_dB)`` pairs (what :func:`prpd.sensor_model` returns);
    a pulse list is binned first so both paths are numerically identical.

    ``cycles``/``f_hz`` only set the record duration, which turns counts into
    ``rate`` (1/s) and ``ndom`` (per cycle).

    ``derotate=False`` skips the canonicalisation.  It exists so the test can
    measure what the unknown 0/120/240 deg phase reference costs us; nothing in
    production should ever turn it off.
    """
    h = np.asarray(hist_or_pulses)
    # A histogram is (n_phase, n_amp); a pulse list is (n_pulses, 2).  n_amp is
    # 32, so the two shapes can never collide in practice.
    is_hist = h.ndim == 2 and h.size and h.shape[1] != 2
    if not is_hist:
        h = prpd.histogram(list(hist_or_pulses))
    h = np.asarray(h, dtype=float)

    out = {k: 0.0 for k in FEATURES}
    total = h.sum()
    if total <= 0:
        return out

    if derotate:
        h = np.roll(h, canonical_rotation_bins(h, gate_db), axis=0)

    phi_c, amp_c = prpd.PHASE_CENTRES_DEG, prpd.AMP_CENTRES_DB
    pi, ai = np.nonzero(h)
    w = h[pi, ai]
    phi, adb = phi_c[pi], amp_c[ai]
    q = 10.0 ** (adb / 20.0)                      # pC-equivalent

    duration_s = cycles / float(f_hz)
    out["rate"] = float(total) / duration_s

    amax_db = _amax_db(h)
    out["qmax"] = 10.0 ** (amax_db / 20.0)
    out["nqn"] = float((h * (np.arange(prpd.N_AMP) + 1)).sum()) / cycles

    # ---- whole-population phase statistics --------------------------------
    prof = h.sum(axis=1)
    p = prof / prof.sum()
    nz = p[p > 0]
    out["phase_entropy"] = float(-(nz * np.log(nz)).sum() / math.log(prpd.N_PHASE))

    pos_all = phi < 180.0
    out["sigma_phi"] = 0.5 * (_circ_std_deg(phi[pos_all], w[pos_all])
                              + _circ_std_deg(phi[~pos_all], w[~pos_all]))

    # amplitude vs |sin(phase)|: positive when the discharge magnitude follows
    # the instantaneous voltage (surface tracking), ~0 for a narrow lobe.
    out["r_pq"] = _wcorr(np.abs(np.sin(np.radians(phi))), adb, w)

    # ---- dominant population ----------------------------------------------
    gate = adb > (amax_db - gate_db)
    if not gate.any():
        gate = np.ones_like(adb, dtype=bool)
    dphi, dq, ddb, dw = phi[gate], q[gate], adb[gate], w[gate]
    dpos = dphi < 180.0
    n1, n2 = _wsum(dw[dpos]), _wsum(dw[~dpos])
    n_dom = n1 + n2
    out["ndom"] = n_dom / cycles
    out["asymmetry_n"] = (n1 - n2) / max(n1 + n2, 1.0)

    if n1 > 0 and n2 > 0:
        m1, m2 = _wmean(dq[dpos], dw[dpos]), _wmean(dq[~dpos], dw[~dpos])
        out["asymmetry_q"] = (m1 - m2) / max(m1 + m2, 1e-9)
        cv1 = _wstd(dq[dpos], dw[dpos]) / max(m1, 1e-9)
        cv2 = _wstd(dq[~dpos], dw[~dpos]) / max(m2, 1e-9)
        out["cv"] = 0.5 * (cv1 + cv2)
    else:
        side = dpos if n1 > 0 else ~dpos
        m = _wmean(dq[side], dw[side])
        out["cv"] = _wstd(dq[side], dw[side]) / max(m, 1e-9)

    # mirror symmetry of the two half cycles, on the dominant population
    dprof = np.zeros(prpd.N_PHASE)
    np.add.at(dprof, pi[gate], dw)
    a, b = dprof[: prpd.N_PHASE // 2], dprof[prpd.N_PHASE // 2:]
    if a.std() > 0 and b.std() > 0:
        out["cross_corr"] = float(np.corrcoef(a, b)[0, 1])

    # amplitude repeatability: a floating electrode / loose joint breaks the
    # SAME gap down every cycle, so successive events have the same energy.
    # Robust dB spread -> 1 at perfect repeatability, 0.37 at 6 dB of spread.
    lo = _wpercentile(ddb, dw, 25.0)
    hi = _wpercentile(ddb, dw, 75.0)
    sigma_db = max(hi - lo, 0.0) / 1.349
    out["regularity"] = math.exp(-sigma_db / 6.0)

    return out


# ---------------------------------------------------------------------------
# rules
# ---------------------------------------------------------------------------

def _conf(margins: list[float]) -> float:
    """Confidence from how far past its thresholds the winning rule sits."""
    if not margins:
        return 0.50
    m = sum(max(0.0, x) for x in margins) / len(margins)
    return round(min(0.99, max(0.50, 0.55 + 0.44 * math.tanh(1.6 * m))), 3)


#: Each rule: (id, class, predicate, margin function, explanation builder).
#: Order matters - the first rule that fires wins.  Thresholds are read off the
#: class-conditional feature distributions printed by ``tests/test_prpd.py``.
RULE_NOTES = {
    "R1": "Faz entropisi yüksek + asimetri yok + tepe genlik küçük -> gürültü",
    "R2": "Tek yarım dalgada yoğunlaşma + dar genlik dağılımı + küçük genlik -> korona",
    "R3": "Çevrim başına az, çok tekrarlı ve çok büyük darbe -> yüzen elektrot / gevşek bağlantı",
    "R4": "Geniş faz yayılımı + genlik-faz bağlaşımı -> yüzey kaçağı",
    "R5": "İki yarım dalga aynası + orta faz yayılımı + orta genlik saçılımı -> iç boşluk",
    "R9": "Hiçbir imzaya uymadı -> ihtiyatla gürültü sayılır",
}


def classify(feat: dict[str, float]) -> dict:
    """Five explicit rules, no machine learning.

    Returns ``{"klass", "label_tr", "confidence", "rule", "explain_tr"}``.
    ``klass`` is always one of ``channels.PRPD_CLASSES`` so it can be written
    straight into ``live.PdView`` and the SCADA ``PD_CLASS`` register.
    """
    f = {k: float(feat.get(k, 0.0)) for k in FEATURES}
    qmax_db = 20.0 * math.log10(max(f["qmax"], 1e-3))

    # -- R1  noise / healthy ------------------------------------------------
    if (f["phase_entropy"] > 0.985 and abs(f["asymmetry_n"]) < 0.25
            and f["rate"] < 400.0 and f["qmax"] < 60.0 and f["cross_corr"] < 0.45):
        return _out("GURULTU", "R1", _conf([
            (f["phase_entropy"] - 0.985) / 0.010,
            (400.0 - f["rate"]) / 400.0,
            (60.0 - f["qmax"]) / 60.0]),
            f"Faz entropisi {f['phase_entropy']:.3f} (neredeyse düzgün dağılım), "
            f"yarım dalga asimetrisi {f['asymmetry_n']:+.2f}, darbe hızı "
            f"{f['rate']:.0f}/s, tepe genlik {f['qmax']:.0f} pC eşd. "
            f"({qmax_db:.0f} dB). Faz ile ilişkili bir kümelenme yok; desen "
            f"ortam RF gürültüsüyle uyumlu, pano sağlıklı kabul edilir.")

    # -- R2  corona ---------------------------------------------------------
    if (abs(f["asymmetry_n"]) > 0.50 and f["cv"] < 0.35 and f["qmax"] < 120.0):
        return _out("KORONA", "R2", _conf([
            (abs(f["asymmetry_n"]) - 0.50) / 0.30,
            (0.35 - f["cv"]) / 0.35,
            (120.0 - f["qmax"]) / 120.0]),
            f"Baskın darbelerin {100 * abs(f['asymmetry_n']):.0f}% fazlası tek "
            f"yarım dalgada (asimetri {f['asymmetry_n']:+.2f}); genlikler dar "
            f"dağılımlı (CV {f['cv']:.2f}) ve küçük ({f['qmax']:.0f} pC eşd.), "
            f"darbe hızı {f['rate']:.0f}/s. Bu tek kutuplu Trichel darbe "
            f"imzasıdır. AG panosunda genellikle pano dışı bir RF kaynağı veya "
            f"nemli ortamda sivri bir uç anlamına gelir; bara üzerinde korona "
            f"400 V'ta beklenmez.")

    # -- R3  floating electrode / loose joint -------------------------------
    if (f["cv"] < 0.35 and f["ndom"] < 30.0 and f["qmax"] > 400.0
            and f["regularity"] > 0.55):
        return _out("YUZEN", "R3", _conf([
            (0.35 - f["cv"]) / 0.35,
            (f["qmax"] - 400.0) / 800.0,
            (f["regularity"] - 0.55) / 0.40]),
            f"Çevrim başına yalnız {f['ndom']:.1f} baskın darbe, ama her biri "
            f"çok büyük ({f['qmax']:.0f} pC eşd., {qmax_db:.0f} dB) ve genlikleri "
            f"neredeyse sabit (CV {f['cv']:.2f}, tekrarlılık "
            f"{f['regularity']:.2f}); iki yarım dalga birbirinin aynası "
            f"(r={f['cross_corr']:.2f}). Aynı aralık her çevrimde aynı şekilde "
            f"deliniyor: yüzen metal parça ya da GEVŞEK BAĞLANTI üzerinde seri "
            f"mikro-ark. Darbeler akım sıfır geçişleri çevresinde kümelenir "
            f"(akım tepelerinde değil). Aynı fiderde ısıl bulgu varsa tork "
            f"kontrolü için iş emri açın.")

    # -- R4  surface tracking ----------------------------------------------
    if (f["sigma_phi"] > 38.0 and (f["r_pq"] > 0.30 or abs(f["asymmetry_q"]) > 0.10)):
        return _out("YUZEY", "R4", _conf([
            (f["sigma_phi"] - 38.0) / 15.0,
            max(f["r_pq"] - 0.30, abs(f["asymmetry_q"]) - 0.10) / 0.20]),
            f"Faz yayılımı geniş ({f['sigma_phi']:.0f}°) ve genlik faz ile "
            f"birlikte büyüyor (bağlaşım r={f['r_pq']:+.2f}, yarım dalga genlik "
            f"asimetrisi {f['asymmetry_q']:+.2f}); tepe genlik {f['qmax']:.0f} pC "
            f"eşd. Yüzey kaçağı / kirlenme izi imzası. Yoğuşma payını ve kablo "
            f"kanalı sızdırmazlığını kontrol edin; alt bölme tabanı açıktır "
            f"(Madde 2.2.8.6 Not:2) ve nemli kanal üzerine bakar.")

    # -- R5  internal void --------------------------------------------------
    if (f["cross_corr"] > 0.45 and 10.0 < f["sigma_phi"] <= 38.0
            and 0.25 < f["cv"] < 0.90):
        return _out("BOSLUK", "R5", _conf([
            (f["cross_corr"] - 0.45) / 0.40,
            (38.0 - f["sigma_phi"]) / 20.0,
            min(f["cv"] - 0.25, 0.90 - f["cv"]) / 0.30]),
            f"İki yarım dalga birbirinin aynası (r={f['cross_corr']:.2f}), faz "
            f"yayılımı orta ({f['sigma_phi']:.0f}°), genlik saçılımı orta "
            f"(CV {f['cv']:.2f}), tepe genlik {f['qmax']:.0f} pC eşd. Yalıtım "
            f"içi boşluk deşarjı imzası: gerilimin yükselen kenarlarında "
            f"ateşlenir. AG'de nadirdir; önce kablo başlığı ve buşing "
            f"yalıtımını değerlendirin.")

    # -- R9  no signature matched ------------------------------------------
    return _out("GURULTU", "R9", 0.50,
                f"Desen bilinen hiçbir imzaya uymadı (entropi "
                f"{f['phase_entropy']:.3f}, faz yayılımı {f['sigma_phi']:.0f}°, "
                f"CV {f['cv']:.2f}, tepe {f['qmax']:.0f} pC eşd.). İhtiyatlı "
                f"davranılıp gürültü olarak işaretlendi; sınıf değişimi tetiği "
                f"için kayda alınır.")


def _out(klass: str, rule: str, confidence: float, explain: str) -> dict:
    assert klass in channels.PRPD_CLASSES, klass
    if klass != "GURULTU":
        explain = explain + _LV_CAVEAT_TR
    return {
        "klass": klass,
        "label_tr": channels.PRPD_LABELS_TR[klass],
        "confidence": float(confidence),
        "rule": rule,
        "explain_tr": explain,
    }


# ---------------------------------------------------------------------------
# trend
# ---------------------------------------------------------------------------

def trend_db(history: list[dict], days: int = 30) -> float:
    """Change in peak amplitude, in dB, over the last ``days``.

    ``history`` is a list of ``{"ts": <unix seconds>, "qmax_db": <dB>}`` (or
    ``"qmax"`` in pC-equivalent, or ``"nqn"`` - whichever key is present, in
    that order).  The slope is a **Theil-Sen** median of pairwise slopes, so a
    single switching-noise outlier cannot manufacture a trend, and the returned
    number is that slope extrapolated over the whole window.

    A relative dB trend is the only quantity this channel is entitled to
    report: the coupling path is unknown, so absolute charge is not.
    """
    pts: list[tuple[float, float]] = []
    for row in history or []:
        ts = row.get("ts")
        if ts is None:
            continue
        if "qmax_db" in row:
            val = float(row["qmax_db"])
        elif "qmax" in row:
            val = 20.0 * math.log10(max(float(row["qmax"]), 1e-3))
        elif "nqn" in row:
            val = 20.0 * math.log10(max(float(row["nqn"]), 1e-3))
        else:
            continue
        pts.append((float(ts) / 86400.0, val))     # days, dB
    if len(pts) < 3:
        return 0.0
    pts.sort()
    t_end = pts[-1][0]
    pts = [p for p in pts if p[0] >= t_end - days]
    if len(pts) < 3:
        return 0.0
    slopes = []
    for i in range(len(pts)):
        for j in range(i + 1, len(pts)):
            dt = pts[j][0] - pts[i][0]
            if dt > 1e-6:
                slopes.append((pts[j][1] - pts[i][1]) / dt)
    if not slopes:
        return 0.0
    span = min(days, t_end - pts[0][0])
    return round(float(np.median(slopes)) * span, 2)


# ---------------------------------------------------------------------------
# alarm triggers and severity
# ---------------------------------------------------------------------------

#: The four things that make a PD observation worth telling someone about.
#: A 6 dB rise is a factor of two in amplitude - the smallest change that is
#: unambiguously above this channel's own reproducibility.
TRIGGER_TREND_DB = 6.0
TRIGGER_RATE_STEP = 5.0
TRIGGER_RULES_TR = {
    "TREND_QMAX": "Tepe genlik 30 günde ≥6 dB (×2) yükseldi",
    "TREND_NQN": "Normalize gürültü sayısı 30 günde ≥6 dB (×2) yükseldi",
    "CLASS_CHANGE": "PRPD sınıfı değişti",
    "RATE_STEP": "Darbe hızında ×5 sıçrama",
    "TWO_CHANNEL": "İkinci kanal (TEV / ultrasonik) aynı yönde değişti",
}


def triggers(prev: dict | None, cur: dict, trend_db_30d: float = 0.0,
             nqn_trend_db_30d: float = 0.0, second_channel_agrees: bool = False
             ) -> list[str]:
    """Which alarm triggers fired.  Returns trigger keys, most specific first.

    ``prev``/``cur`` are snapshots holding at least ``klass``, ``rate`` and
    ``qmax``.  This is deliberately separate from :func:`severity`: the trigger
    says *why we looked*, the severity says *what it is worth*.
    """
    fired: list[str] = []
    if trend_db_30d >= TRIGGER_TREND_DB:
        fired.append("TREND_QMAX")
    if nqn_trend_db_30d >= TRIGGER_TREND_DB:
        fired.append("TREND_NQN")
    if prev:
        if prev.get("klass") and cur.get("klass") and prev["klass"] != cur["klass"]:
            fired.append("CLASS_CHANGE")
        p_rate = float(prev.get("rate", 0.0))
        c_rate = float(cur.get("rate", 0.0))
        if p_rate > 1.0 and c_rate >= TRIGGER_RATE_STEP * p_rate:
            fired.append("RATE_STEP")
    if second_channel_agrees:
        fired.append("TWO_CHANNEL")
    return fired


def pd_view_fields(hist, cycles: int = prpd.DEFAULT_CYCLES,
                   f_hz: float = prpd.F_NOMINAL_HZ,
                   history: list[dict] | None = None,
                   tev_db: float = 0.0, ultrasonic_db: float = 0.0) -> dict:
    """Everything ``live.PdView`` needs, straight from one PRPD histogram.

    Returns a dict whose keys are exactly ``PdView`` field names, so the fusion
    layer can do ``PdView(**pd_view_fields(h))`` without knowing anything about
    this module.  ``caveat`` is left at the ``PdView`` default - that text is
    part of the contract, not ours to reword.

    The rule id, the confidence and the Turkish explanation do NOT fit in
    ``PdView``; put those in the alarm's ``evidence`` where an operator can
    read the reasoning next to the numbers.
    """
    import base64

    h = np.asarray(hist)
    f = features(h, cycles=cycles, f_hz=f_hz)
    r = classify(f)
    return {
        "rate_per_s": round(f["rate"], 1),
        "qmax_db": round(20.0 * math.log10(max(f["qmax"], 1e-3)), 1),
        "nqn": round(f["nqn"], 1),
        "tev_db": float(tev_db),
        "ultrasonic_db": float(ultrasonic_db),
        "klass": r["klass"],
        "klass_label": r["label_tr"],
        "features": {k: round(v, 4) for k, v in f.items()},
        "trend_db_30d": trend_db(history or []),
        "hist_b64": base64.b64encode(prpd.pack(h)).decode("ascii"),
    }


#: Base severity per class, before any trend bump.
_BASE_SEVERITY = {
    "GURULTU": "BILGI",
    "KORONA": "IZLE",
    "YUZEY": "IZLE",
    "BOSLUK": "IZLE",
    "YUZEN": "UYARI",     # loose-joint micro-arc is the one we actually hunt
}

#: Hard cap.  See the module docstring: at LV this channel is corroboration,
#: never a dispatch.  ``channels.DISPATCH_SEVERITIES`` is ("KRITIK","ACIL"), so
#: capping at UYARI is what mechanically guarantees the honesty rule.
SEVERITY_CAP = "UYARI"
assert SEVERITY_CAP not in channels.DISPATCH_SEVERITIES


def severity(klass: str, qmax_db: float, trend_db_30d: float, rate: float) -> str:
    """Severity of a PD observation, capped so PD alone can never dispatch."""
    base = _BASE_SEVERITY.get(klass, "BILGI")
    rank = channels.SEVERITY_RANK[base]
    if trend_db_30d >= TRIGGER_TREND_DB:
        rank += 1
    if trend_db_30d >= 2 * TRIGGER_TREND_DB:
        rank += 1
    if qmax_db >= 60.0 and klass != "GURULTU":          # >= 1000 pC-equivalent
        rank += 1
    if rate >= 5000.0 and qmax_db >= 50.0 and klass != "GURULTU":
        rank += 1
    if klass == "GURULTU":
        rank = min(rank, channels.SEVERITY_RANK["IZLE"])
    rank = min(rank, channels.SEVERITY_RANK[SEVERITY_CAP])
    return channels.SEVERITIES[max(0, rank)]


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":  # pragma: no cover
    import time

    EXPECT = ("GURULTU", "BOSLUK", "YUZEY", "KORONA", "YUZEN")
    SEEDS = 20
    t0 = time.time()

    print("PANO GOZ - PRPD classifier self-test")
    print("=" * 78)

    conf = {a: {b: 0 for b in EXPECT} for a in EXPECT}
    rules: dict[str, int] = {}
    feats: dict[str, list[dict]] = {k: [] for k in EXPECT}
    for truth in EXPECT:
        for s in range(SEEDS):
            h = prpd.record(truth, seed=s)
            f = features(h)
            r = classify(f)
            feats[truth].append(f)
            conf[truth][r["klass"]] += 1
            rules[r["rule"]] = rules.get(r["rule"], 0) + 1

    hdr = "truth \\ pred " + "".join(f"{c:>10}" for c in EXPECT)
    print(hdr)
    ok = tot = 0
    for a in EXPECT:
        row = "".join(f"{conf[a][b]:>10}" for b in EXPECT)
        print(f"{a:<13}{row}")
        ok += conf[a][a]
        tot += sum(conf[a].values())
    print(f"\naccuracy {ok}/{tot} = {100 * ok / tot:.1f}%   rules fired: {rules}")

    print("\nclass-conditional feature medians")
    print(f"{'feature':<14}" + "".join(f"{c:>11}" for c in EXPECT))
    for k in FEATURES:
        vals = [np.median([f[k] for f in feats[c]]) for c in EXPECT]
        print(f"{k:<14}" + "".join(f"{v:>11.3f}" for v in vals))

    print("\nworked example - one YUZEN record")
    f = features(prpd.record("YUZEN", seed=3))
    r = classify(f)
    print(f"  rule {r['rule']}  klass {r['klass']} ({r['label_tr']})  "
          f"confidence {r['confidence']}")
    print("  " + r["explain_tr"])

    print("\ntrend + severity")
    hist = [{"ts": d * 86400.0, "qmax_db": 40.0 + 0.25 * d} for d in range(31)]
    tr = trend_db(hist)
    print(f"  0.25 dB/day over 31 days -> trend_db(30) = {tr:+.2f} dB")
    hist_noisy = list(hist)
    hist_noisy[13]["qmax_db"] = 78.0            # one switching-noise outlier
    print(f"  with one 78 dB outlier          -> {trend_db(hist_noisy):+.2f} dB "
          "(Theil-Sen is not moved by it)")
    for k, q, t, rt in (("GURULTU", 20, 0, 60), ("YUZEN", 64, 0, 350),
                        ("YUZEN", 64, 7, 350), ("YUZEN", 70, 14, 9000),
                        ("YUZEY", 52, 0, 3000)):
        print(f"  severity({k:<8} qmax {q:>2} dB, trend {t:>2} dB, "
              f"rate {rt:>4}/s) = {severity(k, q, t, rt)}")
    caps = {severity(k, 80, 40, 20000) for k in EXPECT}
    print(f"  worst case over every class = {caps} (cap {SEVERITY_CAP}, "
          f"dispatch levels {channels.DISPATCH_SEVERITIES} unreachable)")

    _prev = {"klass": "GURULTU", "rate": 60.0, "qmax": 30.0}
    _cur = {"klass": "YUZEN", "rate": 400.0, "qmax": 1500.0}
    print("\ntriggers:", triggers(_prev, _cur, 7.5, second_channel_agrees=True))
    print(f"elapsed {time.time() - t0:.1f} s")
    assert ok / tot >= 0.95, f"accuracy {ok}/{tot} below the 95% target"
    print("OK")

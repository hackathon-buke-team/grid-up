"""PANO GOZ - PRPD channel test.

Run standalone::

    cd C:/Users/darkb/Desktop/grid-up-v2
    PYTHONIOENCODING=utf-8 python -m tests.test_prpd

Prints the confusion matrix over 5 classes x 20 seeds, the measured accuracy,
the packed histogram sizes, an ASCII PRPD per class, and the evidence that the
phase discriminator is anchored on the CURRENT ZERO CROSSINGS for the series
micro-arc class and on the VOLTAGE RISING SLOPES for the voltage-driven ones.
"""

from __future__ import annotations

import math
import time

import numpy as np

from panogoz.contracts import channels
from panogoz.detector import prpd_classify as pc
from panogoz.sim import prpd

CLASSES = ("GURULTU", "BOSLUK", "YUZEY", "KORONA", "YUZEN")
SEEDS = 20

_failures: list[str] = []


def check(cond: bool, what: str) -> bool:
    print(f"  [{'PASS' if cond else 'FAIL'}] {what}")
    if not cond:
        _failures.append(what)
    return bool(cond)


def rule(title: str) -> None:
    print()
    print(title)
    print("-" * len(title))


# ---------------------------------------------------------------------------
# 1. contracts
# ---------------------------------------------------------------------------

def test_contracts() -> None:
    rule("1. contracts")
    check(set(prpd.CLASSES) == set(channels.PRPD_CLASSES),
          "prpd.CLASS_PARAMS covers exactly channels.PRPD_CLASSES")
    check(len(pc.FEATURES) == 12, f"12 features declared ({len(pc.FEATURES)})")
    f = pc.features(prpd.record("BOSLUK", seed=0))
    check(tuple(sorted(f)) == tuple(sorted(pc.FEATURES)),
          "features() returns exactly the declared FEATURES keys")
    r = pc.classify(f)
    check(set(r) == {"klass", "label_tr", "confidence", "rule", "explain_tr"},
          "classify() returns the declared keys")
    check(all(pc.classify(pc.features(prpd.record(c, seed=1)))["klass"]
              in channels.PRPD_CLASSES for c in CLASSES),
          "every predicted class is a channels.PRPD_CLASSES member")
    check(prpd.CLASS_ALIASES["floating"] == "YUZEN"
          and prpd.resolve_class("void") == "BOSLUK",
          "English research-phase aliases still resolve")


# ---------------------------------------------------------------------------
# 2. phase discriminator - the corrected physics
# ---------------------------------------------------------------------------

def test_phase_anchor() -> None:
    rule("2. phase discriminator (the correction)")
    zero = prpd.current_zero_phase_deg(0.95)
    peak = (zero + 90.0) % 360.0
    print(f"  cos phi = 0.95 lagging -> current zero at {zero:.2f} deg, "
          f"current PEAK at {peak:.2f} deg")

    check(abs(zero - 18.19) < 0.02, "current zero = acos(0.95) = 18.19 deg")

    yz = prpd.CLASS_PARAMS["YUZEN"]
    check(yz["anchor"] == "current_zero",
          "YUZEN (series micro-arc / loose joint) is anchored on current_zero")
    first = yz["lobes"][0]["mu_deg"]
    d_zero, d_peak = abs(first - zero), abs(first - peak)
    print(f"  first (largest) comb lobe at {first:.1f} deg: "
          f"{d_zero:.1f} deg from the current zero, {d_peak:.1f} deg from the peak")
    check(d_zero < d_peak and d_zero <= 15.0,
          "first comb lobe sits just after the current zero, not at the peak")
    combs = [lb["mu_deg"] for lb in yz["lobes"][:6]]
    steps = {round(b - a, 3) for a, b in zip(combs, combs[1:])}
    check(steps == {prpd.REIGNITION_STEP_DEG},
          f"comb is evenly spaced at {prpd.REIGNITION_STEP_DEG} deg {combs}")
    check(all(abs(yz["lobes"][6 + k]["mu_deg"] - (combs[k] + 180.0)) < 1e-6
              for k in range(6)),
          "the second comb mirrors the first, 180 deg later (second current zero)")
    amps = [lb["alpha_pc"] for lb in yz["lobes"][:6]]
    check(amps == sorted(amps, reverse=True),
          "reignition amplitude decays along the comb")

    for k in ("BOSLUK", "YUZEY"):
        lobes = prpd.CLASS_PARAMS[k]["lobes"]
        rising = all(0.0 < lb["mu_deg"] < 90.0 or 180.0 < lb["mu_deg"] < 270.0
                     for lb in lobes)
        check(prpd.CLASS_PARAMS[k]["anchor"] == "voltage_rising" and rising,
              f"{k} sits on the voltage RISING slopes (0-90 / 180-270 deg)")

    # regression guard on the wording itself
    import pathlib
    root = pathlib.Path(__file__).resolve().parents[1]
    txt = ""
    for p in ("panogoz/sim/prpd.py", "panogoz/detector/prpd_classify.py"):
        txt += (root / p).read_text(encoding="utf-8").lower()
    bad = [s for s in ("follow the current peak", "at the current peak",
                       "akım tepelerini takip", "akım tepelerinde kümelen")
           if s in txt]
    check(not bad and "current zero crossing" in txt,
          f"no text claims micro-arcs follow the current peaks {bad}")


# ---------------------------------------------------------------------------
# 3. wire format
# ---------------------------------------------------------------------------

def test_pack() -> None:
    rule("3. wire format (sparse RLE + varint)")
    print(f"  {'class':<9}{'cells':>7}{'raw B':>8}{'packed B':>10}{'ratio':>8}"
          f"{'B/cell':>9}")
    ok = True
    sizes = []
    for c in CLASSES:
        h = prpd.record(c, seed=11)
        blob = prpd.pack(h)
        ok &= bool(np.array_equal(prpd.unpack(blob), h))
        cells = int((h > 0).sum())
        sizes.append(len(blob))
        print(f"  {c:<9}{cells:>7}{h.size * 2:>8}{len(blob):>10}"
              f"{h.size * 2 / len(blob):>7.1f}x{len(blob) / max(cells, 1):>9.2f}")
    check(ok, "pack/unpack round-trips exactly for all five classes")
    check(prpd.unpack(prpd.pack(prpd.histogram([]))).sum() == 0,
          "an empty record packs and unpacks to an empty histogram")
    print(f"  60 s record: {min(sizes)}..{max(sizes)} B "
          f"(healthy panel at the low end, surface tracking at the high end)")
    short = [len(prpd.pack(prpd.record(c, cycles=600, seed=11))) for c in CLASSES]
    print(f"  12 s record: {min(short)}..{max(short)} B")
    check(min(sizes) < 600, "a healthy 60 s record packs into a few hundred bytes")
    check(max(sizes) < 2048, "even the busiest record beats the 4096 B raw array")
    sat = prpd.histogram([(10.0, 40.0)] * 70000)
    check(int(sat.max()) == 65535, "the 16-bit accumulator saturates, never wraps")


# ---------------------------------------------------------------------------
# 4. classification
# ---------------------------------------------------------------------------

def test_classify() -> None:
    rule(f"4. classification, {len(CLASSES)} classes x {SEEDS} seeds")
    conf = {a: {b: 0 for b in CLASSES} for a in CLASSES}
    rules: dict[str, int] = {}
    feats: dict[str, list[dict]] = {c: [] for c in CLASSES}
    wrong: list[str] = []
    t0 = time.time()
    for truth in CLASSES:
        for s in range(SEEDS):
            f = pc.features(prpd.record(truth, seed=s))
            r = pc.classify(f)
            feats[truth].append(f)
            conf[truth][r["klass"]] += 1
            rules[r["rule"]] = rules.get(r["rule"], 0) + 1
            if r["klass"] != truth:
                wrong.append(f"{truth} seed {s} -> {r['klass']} ({r['rule']})")

    print("  confusion matrix (rows = truth, columns = prediction)")
    print("    " + " " * 12 + "".join(f"{c:>10}" for c in CLASSES))
    ok = tot = 0
    for a in CLASSES:
        print(f"    {a:<12}" + "".join(f"{conf[a][b]:>10}" for b in CLASSES))
        ok += conf[a][a]
        tot += sum(conf[a].values())
    acc = 100.0 * ok / tot
    print(f"  accuracy {ok}/{tot} = {acc:.1f}%   rules fired {rules}   "
          f"({time.time() - t0:.1f} s)")
    for w in wrong:
        print(f"    miss: {w}")
    check(acc >= 95.0, f"accuracy {acc:.1f}% >= 95% target")

    print("\n  class-conditional feature medians")
    print(f"  {'feature':<14}" + "".join(f"{c:>11}" for c in CLASSES))
    for k in pc.FEATURES:
        vals = [float(np.median([f[k] for f in feats[c]])) for c in CLASSES]
        print(f"  {k:<14}" + "".join(f"{v:>11.3f}" for v in vals))

    print("\n  confidence per class (min / median)")
    for c in CLASSES:
        cs = [pc.classify(f)["confidence"] for f in feats[c]]
        print(f"    {c:<10} min {min(cs):.2f}  median {float(np.median(cs)):.2f}")

    # the de-rotation earns its place
    rule("4b. what the unknown 0/120/240 deg phase reference costs")
    ok2 = tot2 = 0
    for truth in CLASSES:
        for s in range(SEEDS):
            h = prpd.record(truth, seed=s)
            r = pc.classify(pc.features(h, derotate=False))
            ok2 += r["klass"] == truth
            tot2 += 1
    print(f"  without canonical de-rotation: {ok2}/{tot2} = "
          f"{100.0 * ok2 / tot2:.1f}%")
    print(f"  with    canonical de-rotation: {ok}/{tot} = {acc:.1f}%")
    check(ok >= ok2, "de-rotation does not hurt, and is what makes the "
                     "half-cycle features meaningful")


def test_paths_agree() -> None:
    rule("5. the histogram is the only thing the node sends")
    pulses = prpd.sensor_model(prpd.generate("YUZEY", seed=4), seed=4)
    f_pulses = pc.features(pulses)
    f_hist = pc.features(prpd.histogram(pulses))
    same = all(abs(f_pulses[k] - f_hist[k]) < 1e-9 for k in pc.FEATURES)
    check(same, "features(pulse list) == features(histogram) to 1e-9")
    blob = prpd.pack(prpd.histogram(pulses))
    f_wire = pc.features(prpd.unpack(blob))
    check(all(abs(f_wire[k] - f_hist[k]) < 1e-9 for k in pc.FEATURES),
          "features survive the pack/unpack wire round-trip unchanged")


# ---------------------------------------------------------------------------
# 6. robustness
# ---------------------------------------------------------------------------

def test_robustness() -> None:
    rule("6. robustness sweeps")
    for cyc in (600, 1500, 3000):
        ok = tot = 0
        for truth in CLASSES:
            for s in range(8):
                f = pc.features(prpd.record(truth, cycles=cyc, seed=100 + s),
                                cycles=cyc)
                ok += pc.classify(f)["klass"] == truth
                tot += 1
        print(f"  record length {cyc:>5} cycles ({cyc / 50.0:>5.1f} s): "
              f"{ok}/{tot} = {100.0 * ok / tot:.0f}%")
        check(ok / tot >= 0.90, f"{cyc}-cycle records still >= 90%")

    for nr in (2.0, 5.0, 12.0, 25.0):
        ok = tot = 0
        for truth in CLASSES:
            for s in range(8):
                f = pc.features(prpd.record(truth, seed=200 + s, noise_rate=nr))
                ok += pc.classify(f)["klass"] == truth
                tot += 1
        print(f"  ambient background {nr:>5.1f}/cycle: {ok}/{tot} = "
              f"{100.0 * ok / tot:.0f}%")
        check(ok / tot >= 0.85, f"background {nr}/cycle still >= 85%")

    # a defect on any of the three phases must classify the same way
    for off in (0.0, 120.0, 240.0):
        ok = tot = 0
        for truth in CLASSES:
            for s in range(6):
                f = pc.features(prpd.record(truth, seed=300 + s,
                                            phase_offset_deg=off,
                                            offset_choices=(0.0,)))
                ok += pc.classify(f)["klass"] == truth
                tot += 1
        print(f"  defect on a phase {off:>5.0f} deg away: {ok}/{tot}")
        check(ok == tot, f"classification is invariant to a {off:.0f} deg rotation")


# ---------------------------------------------------------------------------
# 7. trend and severity
# ---------------------------------------------------------------------------

def test_trend_severity() -> None:
    rule("7. trend, triggers and the severity cap")
    flat = [{"ts": d * 86400.0, "qmax_db": 45.0} for d in range(31)]
    rising = [{"ts": d * 86400.0, "qmax_db": 45.0 + 0.2 * d} for d in range(31)]
    print(f"  flat 30 d           -> {pc.trend_db(flat):+.2f} dB")
    print(f"  +0.2 dB/day 30 d    -> {pc.trend_db(rising):+.2f} dB")
    check(abs(pc.trend_db(flat)) < 0.5, "a flat history trends to ~0 dB")
    check(abs(pc.trend_db(rising) - 6.0) < 0.5,
          "0.2 dB/day over 30 days = the 6 dB (x2) alarm threshold")
    spiky = [dict(r) for r in rising]
    spiky[7]["qmax_db"] = 79.0
    spiky[19]["qmax_db"] = 5.0
    print(f"  same, two outliers  -> {pc.trend_db(spiky):+.2f} dB (Theil-Sen)")
    check(abs(pc.trend_db(spiky) - 6.0) < 1.0,
          "two gross outliers do not manufacture or destroy a trend")
    check(pc.trend_db([{"ts": 0.0, "qmax_db": 10.0}]) == 0.0,
          "too little history returns 0.0, not a guess")
    check(abs(pc.trend_db([{"ts": d * 86400.0, "qmax": 10.0 ** ((45 + 0.2 * d) / 20)}
                           for d in range(31)]) - 6.0) < 0.5,
          "a pC-equivalent history gives the same dB trend as a dB history")

    print("\n  severity ladder")
    for k, q, t, r in (("GURULTU", 20.0, 0.0, 60.0),
                       ("GURULTU", 20.0, 9.0, 60.0),
                       ("KORONA", 24.0, 0.0, 7500.0),
                       ("YUZEY", 55.0, 0.0, 3100.0),
                       ("BOSLUK", 41.0, 7.0, 1250.0),
                       ("YUZEN", 66.0, 0.0, 360.0),
                       ("YUZEN", 72.0, 20.0, 12000.0)):
        print(f"    {k:<8} qmax {q:>5.1f} dB  trend {t:>5.1f} dB  "
              f"rate {r:>7.0f}/s  -> {pc.severity(k, q, t, r)}")
    worst = {pc.severity(k, 80.0, 60.0, 50000.0) for k in CLASSES}
    check(not (worst & set(channels.DISPATCH_SEVERITIES)),
          f"NO input can push a PD-only observation into "
          f"{channels.DISPATCH_SEVERITIES}: worst case {sorted(worst)}")
    check(pc.severity("GURULTU", 20.0, 0.0, 60.0) == "BILGI",
          "a healthy noise record is BILGI")

    prev = {"klass": "GURULTU", "rate": 62.0, "qmax": 12.0}
    cur = {"klass": "YUZEN", "rate": 360.0, "qmax": 2050.0}
    t = pc.triggers(prev, cur, trend_db_30d=7.0, second_channel_agrees=True)
    print(f"  triggers on a GURULTU -> YUZEN step: {t}")
    for key in t:
        print(f"    {key}: {pc.TRIGGER_RULES_TR[key]}")
    check(set(t) == {"TREND_QMAX", "CLASS_CHANGE", "RATE_STEP", "TWO_CHANNEL"},
          "all four alarm triggers fire on a genuine step change")
    check(pc.triggers(prev, prev, 0.0) == [],
          "a quiet, unchanged channel fires nothing")


def test_live_view() -> None:
    rule("7b. live.PdView integration")
    from dataclasses import fields as dc_fields

    from panogoz.contracts.live import PdView

    h = prpd.record("YUZEN", seed=9)
    hist = [{"ts": d * 86400.0, "qmax_db": 60.0 + 0.2 * d} for d in range(31)]
    d = pc.pd_view_fields(h, history=hist, tev_db=18.0, ultrasonic_db=12.0)
    names = {f.name for f in dc_fields(PdView)}
    check(set(d) <= names, f"pd_view_fields keys are all PdView fields "
                           f"{sorted(set(d) - names)}")
    view = PdView(**d)
    check(view.klass in channels.PRPD_CLASSES, "PdView(**fields) constructs")
    print(f"  klass {view.klass} ({view.klass_label})  rate {view.rate_per_s}/s  "
          f"Qmax {view.qmax_db} dB  NQN {view.nqn}  trend {view.trend_db_30d} dB")
    print(f"  hist_b64 {len(view.hist_b64)} chars "
          f"({len(prpd.pack(h))} B packed, 4096 B raw)")
    check(channels.validate("pd.qmax_db", view.qmax_db)
          and channels.validate("pd.rate_per_s", view.rate_per_s)
          and channels.validate("pd.nqn", view.nqn),
          "every value is inside its channels.CHANNELS plausible range")
    check(channels.PRPD_CLASSES.index(view.klass) is not None,
          "klass encodes into the SCADA PD_CLASS register")


# ---------------------------------------------------------------------------
# 8. the pictures
# ---------------------------------------------------------------------------

def show_patterns() -> None:
    rule("8. ASCII PRPD - the patterns really are different")
    for c in CLASSES:
        h = prpd.record(c, seed=5, offset_choices=(0.0,))
        f = pc.features(h)
        r = pc.classify(f)
        spec = prpd.CLASS_PARAMS[c]
        print(f"\n  {c} - {spec['label_tr']}   (anchor: {spec['anchor']})")
        print(f"  rate {f['rate']:.0f}/s   Qmax {f['qmax']:.0f} pC eşd. "
              f"({20 * math.log10(max(f['qmax'], 1e-3)):.0f} dB)   NQN {f['nqn']:.0f}   "
              f"-> {r['rule']} {r['klass']} @ {r['confidence']:.2f}")
        for line in prpd.ascii_prpd(h, height=10).splitlines():
            print("  " + line)
        print(f"  TR: {spec['note_tr']}")


# ---------------------------------------------------------------------------

def main() -> int:
    print("PANO GOZ - PRPD / micro-arc channel test")
    print("=" * 78)
    t0 = time.time()
    test_contracts()
    test_phase_anchor()
    test_pack()
    test_classify()
    test_paths_agree()
    test_robustness()
    test_trend_severity()
    test_live_view()
    show_patterns()
    print()
    print("=" * 78)
    if _failures:
        print(f"FAILED {len(_failures)} check(s):")
        for f in _failures:
            print(f"  - {f}")
        return 1
    print(f"ALL CHECKS PASSED in {time.time() - t0:.1f} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

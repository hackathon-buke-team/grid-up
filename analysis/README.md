# `analysis/` — supplied-data forensics

One module. It reads the workbook that came with the hackathon
(`Hackathon Verileri-…/Hackathon Verileri/İstenen Veriler.xlsx`), characterises
it, compares it against a physically realistic series from the project's own
load model, and reports what the PANO GÖZ detector does when it is pointed at
the real file.

Every number is **computed from the file**. Nothing here is quoted.

```
cd C:/Users/darkb/Desktop/grid-up-v2
PYTHONIOENCODING=utf-8 python -m analysis.supplied_data          # report + self-test
PYTHONIOENCODING=utf-8 python -m analysis.supplied_data --json   # machine-readable
```

The Turkish write-up for the submission pack is `docs/09-VERI-ANALIZI.md`.

---

## Why this module exists

Three reasons, in increasing order of importance.

1. **To settle a rendering question.** `openpyxl` makes column A look like two
   datasets — a `datetime.time` block and a `1900-01-01` block. It is one ramp.
   We read the raw `<v>` values out of `xl/worksheets/sheet1.xml` to prove it.

2. **To characterise the current column.** It is uniform pseudo-random integers
   on [15, 90], consistent with `=RANDBETWEEN(15;90)` evaluated once and pasted.
   Nine independent tests agree. The sheet's own B1 cell already says
   *"Sentetik Data"*; we make that statement quantitative.

3. **To say what that means for a detector.** This is the part that matters.
   "Your data is fake" wins nothing. The useful question is *what can any system
   see at this loading?* — and the answer is measured, not asserted: at
   3.9–23.4 % of the panel's 2312 A rating every thermal signature is multiplied
   by (I/In)² ≤ 0.055, which puts a 5 K defect at 0.09–0.27 K, at or under the
   0.2 K sibling-pair noise floor. Run over the supplied file the detector
   raises **no thermal alarm** and flags `SENSITIVITY_LOW` on **100 %** of
   samples. That refusal is the correct answer and the system says so on screen.

---

## Public API

```python
from analysis.supplied_data import report, render, main

rep = report()          # dict, JSON-serialisable; served at /api/analysis/supplied-data
print(render(rep))      # the human-readable report
main()                  # render() + the self-test, returns an exit code
```

`report()` is pure: no clock, no randomness beyond a fixed seed, no file writes.
Two calls on the same workbook return identical values, so it is safe to cache
and safe to snapshot in a test.

### `report()` top-level keys

| Key | Contents |
|---|---|
| `workbook` | path, four sheet descriptors, header rows 1–6, the D/E formulas |
| `timestamps` | raw serials, the single 900 s step, the span, where and why the render switches type |
| `tests` | `ma`, `amps`, `acf`, `var_ratio`, `durbin_watson`, `runs_median`, `runs_updown`, `turning_points`, `ljung_box{,_5,_10}`, `chi2`, `ks`, `anova`, `day_shape`, `periodogram` |
| `shape` | the side-by-side table: supplied vs realistic-152 vs realistic-30d vs criterion |
| `detector_consequence` | sigma rules, dI/dt rules, load factors, θ arithmetic, the lug case |
| `scaling` | the 20.0 vs 6.0 A/mA contradiction, both re-scalings, the question for the organisers |
| `verdict` | conclusion (TR + EN) and the decisive evidence rows |

---

## What it computes

**Structure** — all four sheets, header rows, formulas; the `Sıcaklık_Nem`
sheet is completely empty, which is itself a finding (that whole chain had to be
rebuilt from the specification's Tablo 1 and from Magnus–Tetens).

**Timestamps** — 152 rows, one monotone serial ramp, a single 900.000 s =
15.000 min = 1/96 day step, 37.75 h span; the apparent second block is
`openpyxl` returning `datetime.time` below serial 1.0 and `datetime.datetime` at
or above it.

**Descriptives** — min, max, mean, median, sample and population sd, CV, skew,
excess kurtosis, nine percentiles, IQR — for mA and for primary amps (mA × 6).

**Dependence** — ACF at lags 1, 2, 4, 7, 48, 96 with the ±1.96/√n band;
var(diff)/var(series); Durbin–Watson and the von Neumann ratio with their
white-noise moments; runs about the median; up/down runs; turning points; and
Ljung–Box at m = 5, 10, 20 — each with its z or p.

**Distribution** — χ² over the 76 possible integers, and KS against U(14.5, 90.5).

**Structure in time** — one-way ANOVA by hour of day, day-over-day shape
correlation at identical clock time, and a periodogram with Fisher's g test.

**Comparison** — the same fingerprint computed on a series from
`panogoz.sim.load.LoadModel`, at matched length (152) and at 30 days, scored
against the acceptance criteria.

**Detector consequence** — 1σ/2σ/3σ current alarms, dI/dt rules at 10/20/50 %,
load factors against the 2312 A rating, θ arithmetic with σ_m = 0.2 K, a 50 μΩ
lug worked through to a temperature interval, and — for contrast — what a
*healthy* lug's absolute rise above ambient is at the same loading (0.8–2.0 K,
against a degraded one's 1.0–2.8 K; the difference is the size of the sensor
noise, which is why absolute temperature is useless here).

**Scaling contradiction** — the header's cascade (20.0 A/mA) against column D's
formula (6.0 A/mA), the 750 A vs 600 A full-scale mismatch, and both re-scalings
of the same data.

---

## Design decisions worth knowing

**No scipy.** Every distribution used (χ², F, KS, Fisher's g) is implemented
here from `math` — incomplete gamma by series and continued fraction,
incomplete beta by continued fraction. scipy is installed and would have worked;
doing it in-module keeps the file self-contained, auditable line by line, and
free of a dependency that a judge would have to trust. Cross-checked against
scipy once, outside the module:

| Quantity | this module | scipy |
|---|---:|---:|
| χ² sf(76.0, 75) | 0.44603036 | 0.44603036 |
| χ² 95 % point, df 75 | 96.216671 | 96.216671 |
| F sf(1.3755, 23, 128) | 0.13524060 | 0.13524060 |
| χ² sf(36.6158, 20) | 0.01300636 | 0.01300636 |
| KS p at D = 0.0526, n = 152 | 0.783793 *(asymptotic)* | 0.774118 *(exact)* |

The KS p-value is the asymptotic Kolmogorov limit and is labelled as such in the
output; the exact one-sample distribution gives 0.774. Neither is near
rejection, and the decision is taken on D = 0.0526 against the 0.1103 critical
value, not on the p.

**Criteria live in one place.** The nine primary criteria are copied from
`tests/test_sim_acceptance.CRITERIA`, and the self-test imports that module and
asserts the two tables are identical. If the simulator's acceptance band moves
and this file does not, the self-test fails.

**Three criterion groups, not one.**

* *Primary* (9) — the simulator's own acceptance contract, hard pass/fail.
* *Supporting* (4) — day-shape correlation, hour ANOVA, runs z, Ljung–Box.
  Discriminating, but never part of that contract.
* *Diagnostic* (2) — excess kurtosis and skew, **reported and explicitly not
  scored**. A real two-peaked daily profile is platykurtic too (our 30-day
  realistic series gives g2 = −1.08), so kurtosis alone does not separate
  uniform noise from a real feeder. Presenting it as a criterion would be
  dishonest. Its value here is corroborative: the measured −1.2129 sits on the
  exact 76-point discrete-uniform theory value of −1.2004, well inside the
  √(24/n) = 0.397 standard error of a kurtosis estimate on 152 points.

**Window-dependent statistics are marked and judged fairly.** `acf_96`,
`load_factor`, `min_over_max`, `cv`, `excess_kurtosis` and `skew` all depend on
how long the window is. The realistic series is judged on 30 days — the window
the criteria were written for — and the 152-sample value is shown beside it. The
supplied file has one window of 1.57 days and no way to extend it, which is part
of the finding rather than something to correct for.

**Two numbers that do not fit the story are printed anyway.**

* *Ljung–Box is marginal.* Q = 12.79 / 21.00 / 36.62 at m = 5 / 10 / 20,
  p = 0.0255 / 0.0211 / 0.0130. It rejects independence at 5 % at every lag
  count and at none of them at 1 %. Rather than pick a lag count that behaves,
  we print all three and explain: n = 152 with 5–20 simultaneous lags inflates
  the χ² approximation, and — more to the point — the dominant term is
  **r₄ = −0.2184, negative**. A real feeder gives r₄ ≈ +0.95, so the one test
  that mildly rejects independence does it in the wrong direction for a load
  profile. Fisher's g on the periodogram (p = 0.0149, peak at 1.65 h) is the
  same single anomaly seen a second time, not independent corroboration.
* *The supplied series passes one primary criterion.* Load factor mean/max =
  0.5792 lands inside the 0.55–0.70 band. Coincidence: a uniform on [15, 90] has
  mean/max = 52.5/90 = 0.583. Load factor is a *level* statistic and says
  nothing about *shape*. Printed with that explanation rather than dropped.

**The lug case uses the feeder current, not the panel current.** The file is the
panel's L1 incomer (its own header says `L1 Fazı için` and it is scaled through
the 2500/5), so one outgoing lug carries a proportional share:
I_feeder = I_panel × 400 / 3250, where 3250 A is the sum of the ten non-spare
way ratings. That is the same assumption `panogoz/detector/engine.py` makes for
the 34 IR-only lugs. Feeding the panel current straight into a 400 A lug would
have overstated the rise by 8× and contradicted the θ arithmetic three lines
above it.

**The scaling contradiction is framed as a question.** Both readings are
computed and both are shown. A cascade of 2500/5 and 5 A → 125 mA is 20.0 A/mA;
column D applies 6.0 A/mA; they differ by 10/3. Which one is intended decides
whether this panel is at 13.5 % or 45.1 % of In. We ask; we do not accuse.

---

## Self-test

`python -m analysis.supplied_data` ends with 33 assertions covering the row
count, the step, the span, the type-switch point, the integer support, every
headline statistic, the pass/fail tallies on both series, the detector
arithmetic, the lug interval, the scaling factor, the agreement with
`tests/test_sim_acceptance.CRITERIA`, and JSON-serialisability of `report()`.

Current state: **33 passed, 0 failed** in ~1.1 s wall clock (0.80 s of that is
`report()` itself, dominated by the 2880-sample 30-day realistic series).

---

## Files this module reads and does not modify

* `Hackathon Verileri-…/Hackathon Verileri/İstenen Veriler.xlsx` — via
  `glob.glob('Hackathon*/Hackathon Verileri/*.xlsx')[0]`. The real filename
  contains `İ`, which breaks shell globbing on a cp1254 console; `glob` handles
  it. Never resolve this path with a bash glob.
* `panogoz/sim/load.py` — `LoadModel` for the comparison series.
* `panogoz/sim/thermal.py` — `ThermalModel.steady_air_rise_k` for the panel air
  rise, so this analysis and the simulator cannot disagree about it.
* `tests/test_sim_acceptance.py` — `CRITERIA`, for the drift check only.

It writes nothing.

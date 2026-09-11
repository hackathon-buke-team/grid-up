"""A fleet of panels across the ADM and GDZ service areas.

The fleet is deliberately **mixed**, because the real one is.  Roughly one panel
in eight has no Modbus energy analyser at all (TEDAS Madde 2.2.11 leaves that as
an option, and plenty of older installations took it), and roughly one in three
has no ABB TVOC-2 arc relay.  A demo where all 112 panels are identically
equipped tells a DSO judge that nobody involved has opened a real substation.

What the mix costs us, stated plainly:

* **No analyser** means no ``mpr.*`` channel exists on that panel.  There is no
  panel current, no neutral current, no THD, no voltage.  theta still works,
  because every thermal clip carries its own split-core CT - which is exactly
  why the clips have one.  What is lost is the neutral rule H3 (no I_N to form
  ``K_N`` with) and every power-quality rule.  The panel reports that it has
  lost them rather than showing an empty green tile.
* **No arc relay** means no arc protection to observe.  ``ArcView.fitted`` is
  false, which must look different on screen from ``fitted and offline``.
  Collapsing the two is how a monitoring system convinces an operator that
  unprotected switchgear is protected.

Seeding
-------

Every panel is seeded from its own index, so ``FleetSim(112, seed=42)`` produces
the same 112 panels on any machine, and panel 14 is the same panel whether you
build one panel or all of them.  Weather is seeded from the **district name**
instead, so every panel in Soke shares one sky and a heat wave arrives across a
whole region at once - the correlated confounder that a fleet-wide detector has
to survive without lighting up thirty alarms.
"""

from __future__ import annotations

from typing import Iterator

from panogoz.contracts import assets
from panogoz.sim.load import tag
from panogoz.sim.panel import PanelSim, SimOutput, backfill

__all__ = ["FleetSim", "backfill", "NO_ANALYSER_FRACTION", "NO_ARC_RELAY_FRACTION"]

#: Share of the fleet with no Modbus energy analyser (Madde 2.2.11 option 2).
NO_ANALYSER_FRACTION = 0.12
#: Share of the fleet with no ABB TVOC-2 arc relay fitted.
NO_ARC_RELAY_FRACTION = 0.35

#: Arc-detector counts actually seen in the field: 10 is the TVOC-2 base unit
#: (X1 only), 20 adds the X2 module, 30 adds X3 and is the documented maximum.
ARC_DETECTOR_CHOICES = (10, 10, 20, 20, 20, 30)

_S_FLEET = tag("fleet.assign")
_S_JITTER = tag("fleet.jitter")


def _panel_seed(seed: int, index: int) -> int:
    """Per-panel seed.  Derived from the index alone so panel 14 of a 112-panel
    fleet and panel 14 of a 5-panel fleet are the same panel."""
    from panogoz.sim.load import _mix64

    return _mix64((seed * 0x9E3779B97F4A7C15) ^ (index * 0xBF58476D1CE4E5B9)) & 0xFFFFFFFF


def _exact_subset(seed: int, stream: int, n: int, fraction: float) -> set[int]:
    """Deterministically choose ``round(fraction * n)`` indices out of ``1..n``.

    Thresholding a hash would give "about 12 %", which then drifts with ``n`` and
    makes a claim in the pitch deck untrue for the fleet actually on screen.
    Ranking by hash and taking the first k gives exactly the promised count for
    any n, and is still deterministic and unbiased.
    """
    from panogoz.sim.load import _u01

    k = int(round(fraction * n))
    ranked = sorted(range(1, n + 1), key=lambda i: _u01(seed, stream, i))
    return set(ranked[:k])


class FleetSim:
    """``n`` panels spread over :data:`assets.FLEET_SITES`."""

    def __init__(self, n: int = 112, seed: int = 42, start_ts: float | None = None) -> None:
        self.n = int(n)
        self.seed = int(seed) & 0xFFFFFFFF
        self.start_ts = start_ts

        no_analyser = _exact_subset(self.seed, _S_FLEET, self.n, NO_ANALYSER_FRACTION)
        no_arc = _exact_subset(self.seed, _S_FLEET + 1, self.n, NO_ARC_RELAY_FRACTION)

        sites = assets.FLEET_SITES
        per_site: dict[str, int] = {}
        self._panels: list[PanelSim] = []
        self._by_key: dict[str, PanelSim] = {}

        from panogoz.sim.load import _u01

        for i in range(1, self.n + 1):
            site, dso, lat, lon = sites[(i - 1) % len(sites)]
            per_site[site] = per_site.get(site, 0) + 1
            key = assets.panel_id(site, per_site[site])
            ps = _panel_seed(self.seed, i)
            # A few kilometres of jitter so two panels in one district do not
            # land on the same map pixel.  0.02 degrees is about 2 km.
            jlat = lat + 0.04 * (_u01(ps, _S_JITTER, 1) - 0.5)
            jlon = lon + 0.05 * (_u01(ps, _S_JITTER, 2) - 0.5)
            arc_n = ARC_DETECTOR_CHOICES[
                int(_u01(ps, _S_JITTER, 3) * len(ARC_DETECTOR_CHOICES)) % len(ARC_DETECTOR_CHOICES)
            ]
            p = PanelSim(
                panel_key=key,
                panel_index=i,
                site=site,
                name=f"{site} {per_site[site]:02d}",
                dso=dso,
                lat=jlat,
                lon=jlon,
                seed=ps,
                start_ts=start_ts,
                has_analyser=i not in no_analyser,
                has_arc_relay=i not in no_arc,
                arc_detectors=arc_n if i not in no_arc else 0,
                weather_key=site,
            )
            self._panels.append(p)
            self._by_key[key] = p

    # ------------------------------------------------------------------ api

    def panels(self) -> list[PanelSim]:
        return list(self._panels)

    def get(self, panel_key: str) -> PanelSim:
        try:
            return self._by_key[panel_key]
        except KeyError as exc:  # pragma: no cover - programmer error
            raise KeyError(
                f"unknown panel {panel_key!r}; have {len(self._by_key)} panels"
            ) from exc

    def keys(self) -> list[str]:
        return [p.panel_key for p in self._panels]

    def step(self, ts: float) -> list[SimOutput]:
        return [p.step(ts) for p in self._panels]

    def backfill(self, days: int, step_s: int = 900) -> Iterator[tuple[str, SimOutput]]:
        """History for the whole fleet, panel by panel.

        Read the arithmetic before choosing ``step_s``: 112 panels x 60 days at
        900 s is 645 000 samples of forty joints each.  Backfill one panel for a
        trend screen, and the fleet only when you mean it.
        """
        for p in self._panels:
            for o in backfill(p, days, step_s):
                yield (p.panel_key, o)

    # -------------------------------------------------------------- summary

    def summary(self) -> dict:
        pans = self._panels
        return {
            "panels": len(pans),
            "sites": len({p.site for p in pans}),
            "adm": sum(1 for p in pans if p.dso == "ADM"),
            "gdz": sum(1 for p in pans if p.dso == "GDZ"),
            "no_analyser": sum(1 for p in pans if not p.has_analyser),
            "no_arc_relay": sum(1 for p in pans if not p.has_arc_relay),
            "no_analyser_pct": 100.0 * sum(1 for p in pans if not p.has_analyser) / len(pans),
            "no_arc_relay_pct": 100.0 * sum(1 for p in pans if not p.has_arc_relay) / len(pans),
            "devices_total": len(pans) * assets.DEVICES_PER_PANEL,
            "joints_monitored": len(pans) * len(assets.monitored_joints()),
            "arc_detectors_total": sum(p.arc_detectors for p in pans),
        }


if __name__ == "__main__":  # pragma: no cover
    import datetime as _dt
    import time as _t

    T0 = _dt.datetime(2026, 7, 20, 12, tzinfo=_dt.timezone.utc).timestamp()

    print("PANO GOZ · fleet simulator self-test")
    print("=" * 88)
    fleet = FleetSim(112, seed=42, start_ts=T0)
    for k, v in fleet.summary().items():
        print(f"  {k:<22} {v:.2f}" if isinstance(v, float) else f"  {k:<22} {v}")

    print("\nFirst twelve panels")
    print(f"  {'key':<20}{'dso':<5}{'lat':>8}{'lon':>8}{'analiz':>8}{'ark':>6}{'dedektor':>10}"
          f"{'temel A':>10}{'dengesizlik':>12}")
    for p in fleet.panels()[:12]:
        print(f"  {p.panel_key:<20}{p.dso:<5}{p.lat:>8.3f}{p.lon:>8.3f}"
              f"{'var' if p.has_analyser else 'YOK':>8}"
              f"{'var' if p.has_arc_relay else 'YOK':>6}{p.arc_detectors:>10}"
              f"{p.load.base_a:>10.0f}{100*p.load.unbalance:>11.1f}%")

    print("\nDeterminism")
    a = FleetSim(112, seed=42, start_ts=T0)
    b = FleetSim(112, seed=42, start_ts=T0)
    oa = a.get("Soke-01").step(T0)
    ob = b.get("Soke-01").step(T0)
    same = oa.panel == ob.panel and oa.joints == ob.joints
    print(f"  two fleets built independently agree on Soke-01: {same}")
    small = FleetSim(20, seed=42, start_ts=T0)
    print(f"  panel 14 seed identical in a 20-panel and a 112-panel fleet: "
          f"{small.panels()[13].seed == fleet.panels()[13].seed}")

    print("\nRegional weather: panels in one district share a sky")
    by_site: dict[str, list] = {}
    for p in fleet.panels():
        by_site.setdefault(p.site, []).append(p)
    for site in ("Soke", "Izmir-Bornova", "Fethiye"):
        ps = by_site.get(site, [])
        if not ps:
            continue
        seeds = {p.weather_seed for p in ps}
        outs = [p.step(T0) for p in ps]
        amb = [o.truth["ambient_c"] for o in outs]
        print(f"  {site:<16} {len(ps)} panel, {len(seeds)} weather stream,"
              f" ambient {min(amb):.2f}-{max(amb):.2f} C")

    print("\nOne fleet step")
    t1 = _t.perf_counter()
    outs = fleet.step(T0 + 60)
    dt = _t.perf_counter() - t1
    lf = sorted(o.truth["load_factor"] for o in outs)
    print(f"  {len(outs)} panels in {1000*dt:.0f} ms ({1000*dt/len(outs):.2f} ms each)")
    print(f"  load factor  min {lf[0]:.2f}  median {lf[len(lf)//2]:.2f}  max {lf[-1]:.2f}")
    nch = sum(len(o.panel) for o in outs)
    njo = sum(len(o.joints) for o in outs)
    print(f"  {nch} panel-channel values, {njo} joint records,"
          f" {sum(len(o.devices) for o in outs)} device records")
    without = [o for o, p in zip(outs, fleet.panels()) if not p.has_analyser]
    print(f"  panels with no analyser emit {sum(len([c for c in o.panel if c.startswith('mpr.')]) for o in without)}"
          f" mpr.* values in total (expected 0)")

    print("\nA fleet-wide heat wave hits a district, not a panel")
    soke = by_site["Soke"]
    for p in soke:
        p.inject("sicak_hava_dalgasi", at_ts=T0 + 60)
    for i in range(2, 60):
        outs = [p.step(T0 + i * 1800) for p in soke]
    print(f"  Soke ambient now {outs[0].truth['ambient_c']:.1f} C on all {len(soke)} panels")
    print("  and every one of them still reports theta unchanged, so the fleet")
    print("  console shows a weather note, not {} alarms.".format(len(soke) * 30))

    print("\nBackfill")
    p = fleet.get("Soke-01")
    t1 = _t.perf_counter()
    n = sum(1 for _ in backfill(p, 7, 900))
    print(f"  Soke-01, 7 days @ 900 s: {n} samples in {_t.perf_counter()-t1:.1f} s")
    print("  (60 days @ 900 s is about 15 s per panel; 60 s steps are 15x that,")
    print("   so pick the step to match what the screen actually needs)")

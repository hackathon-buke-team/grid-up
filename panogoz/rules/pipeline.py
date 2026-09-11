"""The rule pipeline, and why its order is fixed.

::

    suppression  ->  fusion  ->  alarms

**Suppression first.**  This is the ordering decision that matters, and it is
worth defending because the obvious alternative - fuse everything, then decide
what to hide - is wrong in a way that is invisible until the fleet is large.

If fusion ran first, a regional voltage disturbance would drive
``risk(insulation)`` to 0.9 on ninety panels, the health index would collapse
fleet-wide, the incidents would open, and suppression would then be reduced to
deleting alarms that the engine had already convinced itself of.  Every
downstream number - the health index, the SCADA risk registers, the fleet map -
would be a number computed from evidence we do not believe.  Hiding a
conclusion is not the same as never having drawn it.

Running suppression first means the explained-away evidence never enters the
likelihood at all: it arrives as negative log-odds *before* ``sigmoid``, joints
attributed to a faulty clip are removed from the peer statistics *before* the
worst-joint search, and the health index that reaches SCADA is the health index
we actually stand behind.

**Fusion second**, because alarms need risks, the health index and the family
count, and it is fusion that produces all three.

**Alarms last**, because incident hygiene - debounce, dwell, hysteresis, dedup,
roll-up, storm cap - is a function of a *decided* state, not of raw evidence.
An incident that is opened and then suppressed has already consumed an incident
id, an audit row and, if the dispatcher is quick, a text message.

Notification is deliberately NOT part of this function's required signature.
``run`` returns a live image and leaves ``AlarmManager.pending_dispatch``
populated; the caller decides whether a phone rings.  A pipeline that can send
an SMS as a side effect of a unit test is a pipeline nobody will run in CI.
"""

from __future__ import annotations

import time
from typing import Any

from panogoz.contracts.live import PanelLive
from panogoz.rules import alarms, fusion, suppression

#: One AlarmManager per store, because the debounce and clear-day windows are
#: per-process state and must not be rebuilt on every cycle.
_MANAGERS: dict[int, alarms.AlarmManager] = {}

ORDER: tuple[str, ...] = ("suppression", "fusion", "alarms")


def get_manager(store, **kw: Any) -> alarms.AlarmManager:
    key = id(store)
    mgr = _MANAGERS.get(key)
    if mgr is None:
        mgr = alarms.AlarmManager(store, **kw)
        _MANAGERS[key] = mgr
    return mgr


def set_manager(store, mgr: alarms.AlarmManager) -> None:
    _MANAGERS[id(store)] = mgr


def reset() -> None:
    """Drop every cached manager.  Used by the demo reset button and by tests."""
    _MANAGERS.clear()


def run(live: PanelLive, store, history: dict, now: float,
        *, notifier: Any = None) -> PanelLive:
    """One full rule cycle for one panel.

    ``history`` is the caller's per-panel context dictionary (see
    ``rules.suppression`` for its documented keys); ``run`` hands it straight
    through and lets suppression keep its own bookkeeping in it.

    ``notifier`` is optional.  When supplied, every incident the alarm layer
    has cleared for dispatch is handed to it after the cycle completes, so the
    ordering "decide, then tell" is also enforced in time and not only in code.
    """
    history = history if history is not None else {}
    history.setdefault("now", now)
    history["now"] = now
    live.ts = live.ts or now

    # 1. suppression - explain away what is not about this panel
    suppression.apply(live, store, history)

    # 2. fusion - risks, health index, severity, joint grades
    fusion.apply(live)

    # 3. alarms - incident lifecycle and hygiene
    mgr = get_manager(store)
    before = len(mgr.pending_dispatch)
    mgr.reconcile(live, now)

    if notifier is not None:
        for incident in mgr.pending_dispatch[before:]:
            notifier.on_incident(dict(incident), live, now)

    setattr(live, "_panogoz_pipeline", {
        "order": ORDER,
        "now": now,
        "systemic": mgr.systemic,
        "systemic_note": mgr.systemic_note,
        "pending_dispatch": len(mgr.pending_dispatch),
    })
    return live


def summary(live: PanelLive) -> dict:
    """A compact "what did the engine decide and why" block for the UI."""
    d = fusion.detail(live)
    return {
        "panel_key": live.panel_key,
        "health_index": live.health_index,
        "severity": live.severity,
        "severity_reasoning": d.get("severity", {}),
        "families": d.get("families", []),
        "risks": live.risks,
        "hi_waterfall": live.hi_waterfall,
        "status_flags": live.status_flags,
        "alarms": len(live.alarms),
        "suppressed": len(live.suppressed),
        "device_orders": suppression.device_orders(live),
        "pipeline": getattr(live, "_panogoz_pipeline", {}),
    }


if __name__ == "__main__":  # pragma: no cover
    import json
    import os
    import tempfile

    from panogoz.rules.fusion import _demo_live
    from panogoz.store.db import Store

    print("=" * 78)
    print("PANO GOZ · pipeline self-test")
    print("=" * 78)
    print()
    print("Sabit sira:", " -> ".join(ORDER))

    tmp = os.path.join(tempfile.mkdtemp(prefix="panogoz-pipe-"), "t.db")
    store = Store(tmp)
    reset()
    T0 = 1_760_000_000.0
    hist: dict = {}

    print()
    print("[A] Gercek bir baglanti kusuru, sebeke sakin")
    for d in range(4):
        live = _demo_live()
        live.ts = T0 + d * 86400
        j = [x for x in live.joints if x.key == "C07-L2-PABUC"][0]
        j.theta_k, j.temp_c, j.cusum, j.slope_k_per_week, j.theta_min_k = 14.0, 99.0, 20.0, 0.8, 0.9
        run(live, store, hist, T0 + d * 86400)
    s = summary(live)
    print(f"  HI={s['health_index']:.1f}  severity={s['severity']}  "
          f"kanallar={s['families']}  alarm={s['alarms']}")
    print(f"  risk(loose)={s['risks']['loose_connection']:.3f}")
    hi_a, sev_a = s["health_index"], s["severity"]

    print()
    print("[B] Ayni olcumler, ama uc fazda birlikte yukselen gerilim THD'si")
    store2 = Store(os.path.join(tempfile.mkdtemp(prefix="panogoz-pipe2-"), "t.db"))
    reset()
    hist2: dict = {}
    for d in range(4):
        live2 = _demo_live()
        live2.ts = T0 + d * 86400
        j = [x for x in live2.joints if x.key == "C07-L2-PABUC"][0]
        j.theta_k, j.temp_c, j.cusum, j.slope_k_per_week, j.theta_min_k = 14.0, 99.0, 20.0, 0.8, 0.9
        live2.analyser.update({"mpr.thd_v_l1_pct": 6.5, "mpr.thd_v_l2_pct": 6.2,
                               "mpr.thd_v_l3_pct": 6.8})
        run(live2, store2, hist2, T0 + d * 86400)
    s2 = summary(live2)
    print(f"  HI={s2['health_index']:.1f}  severity={s2['severity']}  "
          f"bayraklar={s2['status_flags']}")
    print(f"  risk(loose)={s2['risks']['loose_connection']:.3f} "
          f"(A'da {s['risks']['loose_connection']:.3f})")
    print(f"  bastirma satiri: {len(live2.suppressed)}")
    print(f"  yonlendirilen alarm: "
          f"{sum(1 for a in live2.alarms if a.dispatched)} (A'da "
          f"{sum(1 for a in live.alarms if a.dispatched)})")
    assert not any(a.dispatched for a in live2.alarms), "grid event must not dispatch"
    assert (s2["risks"]["loose_connection"] < s["risks"]["loose_connection"]), (
        "suppression must reduce the risk, not merely hide the alarm")
    assert s2["health_index"] > hi_a, "the health index that reaches SCADA must recover too"
    print("  ASSERT OK: bastirma riski DUSURUR, alarmi gizlemekle yetinmez")

    print()
    print("[C] Mutlak limit ogrenme haftasinda da aktif")
    store3 = Store(os.path.join(tempfile.mkdtemp(prefix="panogoz-pipe3-"), "t.db"))
    reset()
    live3 = _demo_live()
    live3.learn_until = T0 + 5 * 86400
    j = [x for x in live3.joints if x.key == "C07-L2-PABUC"][0]
    j.theta_k, j.temp_c, j.theta_min_k = 22.0, 136.0, 0.9
    run(live3, store3, {}, T0)
    print(f"  bayraklar={live3.status_flags}")
    print(f"  HI={live3.health_index:.1f}  severity={live3.severity}  "
          f"alarm={len(live3.alarms)}")
    assert live3.severity == "ACIL"
    assert any(a.severity == "ACIL" for a in live3.alarms), "absolute breach must open at once"
    print("  ASSERT OK: mutlak limit debounce'i atlar ve ogrenme haftasinda alarm uretir")
    print(f"  baslik: {live3.alarms[0].title}")

    print()
    print("[ozet JSON anahtarlari]", sorted(summary(live).keys()))
    print()
    print("OK")

"""`python -m panogoz.run_local --panels N --port PORT [--backfill-days D]`

N sentetik panoyu (gerçek CT verisi + θ/rules çekirdeği, bkz.
panogoz/sim/demo_fleet.py `build_fleet`) monitoring API'sinin (panogoz/api/app.py)
arkasında yerel olarak ayağa kaldırır -- K2 2.4 yük testinin ve elle
gösterim/geliştirmenin ortak giriş noktası.

`--backfill-days`: gerçek L1 serisi yalnızca ~1,5 gün (organizatörün verdiği
tek seri); bu bayrak verilirse desen o kadar güne ulaşana kadar tekrarlanır
(bkz. demo_fleet._tile_l1_series docstring'i -- uydurma veri değil, gerçek
desenin tekrarı). Verilmezse ham ~1,5 günlük gerçek seri kullanılır.
"""
from __future__ import annotations

import argparse

from panogoz.api.app import create_app
from panogoz.sim.demo_fleet import build_fleet


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--panels", type=int, default=8, help="sentetik pano sayısı (varsayılan 8)")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--backfill-days", type=float, default=None, help="gerçek L1 desenini bu kadar güne tekrarla")
    parser.add_argument("--fault-fraction", type=float, default=0.12, help="rastgele arıza enjekte edilecek pano oranı")
    args = parser.parse_args()

    fleet = build_fleet(args.panels, backfill_days=args.backfill_days, fault_fraction=args.fault_fraction)
    n_fault = sum(1 for tl in fleet if any(e.severity for e in tl.severity))
    print(f"[panogoz.run_local] {len(fleet)} pano üretildi ({n_fault} en az bir kez UYARI+ üstü), http://0.0.0.0:{args.port}")

    app = create_app(fleet)
    app.run(host="0.0.0.0", port=args.port, debug=False)


if __name__ == "__main__":
    main()

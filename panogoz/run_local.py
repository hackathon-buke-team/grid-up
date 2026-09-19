"""`python -m panogoz.run_local [--port 8080] [--modbus-port 5020] [--panels N]`

Alarm konsolu (frontend/) + monitoring API'si + canlı Modbus TCP slave'i tek komutla yerelde
ayağa kaldırır:

- `/` ......... Alarm Konsolu (22 senaryolu pano filosu, panogoz/api/fleet_service.py)
- `/kanit.html`  Kanıt ekranı (θ + CUSUM, eski 2 panolu demo filosu)
- Modbus TCP .. ICD v2.0, `--modbus-port` (varsayılan 5020; 0 = kapalı), salt okunur
- Filo, arka planda ısıtılır (ilk kurulum ≈15 sn); konsol "hazırlanıyor" gösterir.

`--panels N`: K2 2.4 yük testi için eski N-panolu `build_fleet` (`/api/connections`); konsol
filosundan bağımsızdır. `--backfill-days`: gerçek L1 serisi yalnızca ~1,5 gün, bu bayrak deseni
o kadar güne tekrarlar (bkz. demo_fleet._tile_l1_series -- uydurma değil, tekrar).
"""
from __future__ import annotations

import argparse
import threading

from panogoz.api.app import create_app
from panogoz.sim.demo_fleet import build_fleet


def start_background_services(app, *, modbus_port: int, modbus_host: str = "0.0.0.0", warm: bool = True):
    """Filoyu arka planda ısıtır ve (istenirse) Modbus sunucusunu başlatır.
    Döner: (thread, holder) -- `holder["modbus"]` sunucu hazır olunca dolar."""
    holder: dict = {}
    getter = app.config["FLEET_GETTER"]

    def run() -> None:
        service = getter()
        if modbus_port:
            from panogoz.scada.fleet_modbus import FleetModbusServer

            holder["modbus"] = FleetModbusServer(service, host=modbus_host, port=modbus_port).start()
            print(f"[panogoz.run_local] Modbus TCP (ICD v2.0, FC04, salt okunur) :{modbus_port}")
        print(f"[panogoz.run_local] filo hazır: {len(service.panels)} pano, gün {service.clock_state()['day']:.1f}")

    thread = threading.Thread(target=run, daemon=True, name="panogoz-fleet-warmup")
    if warm:
        thread.start()
    return thread, holder


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--panels", type=int, default=8, help="eski N-panolu yük testi filosu (varsayılan 8)")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--modbus-port", type=int, default=5020, help="canlı Modbus TCP portu (0 = kapalı)")
    parser.add_argument("--no-fleet", action="store_true", help="konsol filosunu ısıtma (yalnız eski API)")
    parser.add_argument("--no-demo-controls", action="store_true", help="demo kontrol uçlarını kapat")
    parser.add_argument("--backfill-days", type=float, default=None, help="gerçek L1 desenini bu kadar güne tekrarla")
    parser.add_argument("--fault-fraction", type=float, default=0.12, help="rastgele arıza enjekte edilecek pano oranı")
    args = parser.parse_args()

    fleet = build_fleet(args.panels, backfill_days=args.backfill_days, fault_fraction=args.fault_fraction)
    n_fault = sum(1 for tl in fleet if any(e.severity for e in tl.severity))
    print(f"[panogoz.run_local] {len(fleet)} pano üretildi ({n_fault} en az bir kez UYARI+ üstü), http://0.0.0.0:{args.port}")

    app = create_app(fleet, demo_controls=not args.no_demo_controls)
    start_background_services(app, modbus_port=args.modbus_port, warm=not args.no_fleet)
    app.run(host="0.0.0.0", port=args.port, debug=False, threaded=True)


if __name__ == "__main__":
    main()

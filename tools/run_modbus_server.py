"""Gerçek CT verisi + arıza simülasyonundan üretilen anlık durumu Modbus TCP üzerinden yayınlar.

SCADA/RTU entegrasyonu için istenen "Modbus Haritalama" gösterimidir — gerçek bir
RTU'ya bağlanmak gerekmiyor, herhangi bir Modbus master (ör. modpoll, QModMaster)
ile 127.0.0.1:5020 adresine bağlanıp Input Register'ları (function code 04)
okuyarak haritalamayı doğrulayabilirsiniz. Register düzeni için bkz.
docs/modbus-haritalama.md.

Kullanım: python -m tools.run_modbus_server
"""
from __future__ import annotations

from panogoz.scada.adapters import snapshot_at
from panogoz.scada.modbus_server import run_standalone
from panogoz.sim.demo_fleet import build_demo_fleet


def main() -> None:
    fleet = build_demo_fleet()
    snapshots = {index: snapshot_at(timeline) for index, timeline in enumerate(fleet)}

    print("Modbus TCP sunucusu 0.0.0.0:5020 üzerinde dinliyor (Ctrl+C ile durdurun)")
    for index, timeline in enumerate(fleet):
        print(f"  Bağlantı {index} (register {index * 8}-{index * 8 + 7}) = {timeline.connection_id}")
    run_standalone(snapshots, host="0.0.0.0", port=5020)


if __name__ == "__main__":
    main()

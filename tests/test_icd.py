"""K2 2.5 + K3 3.4: ICD v2 tutarlılığı (nokta listesi <-> Modbus <-> doküman <-> CSV <-> konsol).

Canlı Modbus testleri GERÇEK pymodbus istemcisiyle gerçek TCP soketi üzerinden çalışır.
"""
import csv
import io
from pathlib import Path

import pytest
from pymodbus.client import ModbusTcpClient

from panogoz.api.app import create_app
from panogoz.api.fleet_service import DAY_S
from panogoz.scada import icd
from panogoz.scada.fleet_bridge import all_registers, panel_values, scada_view
from panogoz.scada.fleet_modbus import FleetModbusServer
from tests.test_fleet_service import make

ROOT = Path(__file__).resolve().parents[1]


def norm(text: str) -> str:
    return text.replace("\r\n", "\n")


# ---------------------------------------------------------------- nokta listesi
def test_point_list_is_contiguous_unique_and_fills_the_block():
    assert [p.offset for p in icd.POINTS] == list(range(icd.BLOCK_SIZE))
    assert len({p.name for p in icd.POINTS}) == icd.BLOCK_SIZE
    assert {p.dtype for p in icd.POINTS} <= {"u16", "s16", "bits"}
    assert icd.POINTS[-1].name == "ICD_VERSION"


def test_block_base_and_capacity():
    assert icd.block_base(0) == 0 and icd.block_base(199) == 199 * 32
    with pytest.raises(ValueError):
        icd.block_base(200)
    assert icd.total_registers() == 200 * 32 <= 65535


def test_encode_decode_roundtrip_signed_unsigned_and_saturation():
    s16 = icd.point("JOINT_TEMP_L1_X10")
    assert icd.decode(s16, icd.encode(s16, -23.4)) == pytest.approx(-23.4)
    assert icd.encode(s16, -5000) == 0x8000  # -32768'e doyar
    assert icd.encode(s16, 5000) == 0x7FFF
    u16 = icd.point("CURRENT_L1_X10")
    assert icd.decode(u16, icd.encode(u16, 274.3)) == pytest.approx(274.3)
    assert icd.encode(u16, -1.0) == 0 and icd.encode(u16, 99999.0) == 0xFFFF
    assert icd.encode(u16, None) == 0
    ratio = icd.point("OVERLOAD_RATIO_X100")
    assert icd.decode(ratio, icd.encode(ratio, 1.27)) == pytest.approx(1.27)


def test_build_block_rejects_unknown_points_and_autofills_version():
    with pytest.raises(KeyError, match="ICD'de olmayan"):
        icd.build_block({"YOK_BOYLE_NOKTA": 1})
    regs = icd.build_block({"SEVERITY_CODE": 3})
    assert len(regs) == 32 and regs[0] == 3 and regs[31] == 200
    assert icd.decode_block(regs)["ICD_VERSION"] == 200
    with pytest.raises(ValueError):
        icd.decode_block([0] * 31)


def test_flag_bits_roundtrip():
    value = icd.set_flags("STALE", "ARC_TRIP_LATCHED", "ALARM_PAGED")
    assert icd.flag_names(value) == ["STALE", "ARC_TRIP_LATCHED", "ALARM_PAGED"]
    assert icd.flag_names(0) == []
    with pytest.raises(KeyError):
        icd.set_flags("OLMAYAN_BAYRAK")


# --------------------------------------------------------- doküman / CSV tutarlılığı
def test_icd_markdown_on_disk_matches_what_the_code_generates():
    on_disk = norm((ROOT / "docs" / "PANOGOZ-ICD-v2.0.md").read_text(encoding="utf-8"))
    assert on_disk == norm(icd.markdown_doc()), "docs/PANOGOZ-ICD-v2.0.md eski: `python -m tools.gen_icd` çalıştırın"


def test_csv_point_list_on_disk_matches_code_and_is_machine_readable():
    text = (ROOT / "docs" / "data" / "panogoz-icd-v2.0-points.csv").read_text(encoding="utf-8")
    assert norm(text) == norm(icd.csv_point_list())
    rows = list(csv.DictReader(io.StringIO(text)))
    assert len(rows) == 32 and rows[3]["name"] == "FLAGS" and rows[9]["type"] == "s16" and rows[9]["unit"] == "°C"
    assert {r["name"] for r in rows} == {p.name for p in icd.POINTS}


def test_markdown_documents_every_point_and_flag_bit():
    doc = icd.markdown_doc()
    for p in icd.POINTS:
        assert f"`{p.name}`" in doc
    for _, (name, _) in icd.FLAG_BITS.items():
        assert f"`{name}`" in doc


# ------------------------------------------------ köprü: filo -> register (Modbus'suz)
def test_bridge_values_equal_console_state_for_every_panel():
    svc = make()
    svc.advance_to(34.6 * DAY_S)
    for row in svc.panels_summary():
        panel = svc.panels[row["id"]]
        regs = icd.build_block(panel_values(svc, panel))
        decoded = icd.decode_block(regs)
        assert icd.SEVERITY_TEXT[decoded["SEVERITY_CODE"]] == row["severity_label"]
        assert decoded["ALARMS_OPEN"] == row["open_alarms"]
        assert decoded["ICD_VERSION"] == 200
        i = svc.now_index
        assert decoded["CURRENT_L2_X10"] == pytest.approx(panel.data.current_a[list(panel.data.current_a)[1]][i], abs=0.06)
        assert decoded["HUMIDITY_X10"] == pytest.approx(row["humidity_rh"], abs=0.06)
        assert decoded["AMBIENT_TEMP_X10"] == pytest.approx(row["ambient_c"], abs=0.06)


def test_flags_reflect_real_conditions():
    svc = make()
    svc.advance_to(35.3 * DAY_S)  # P06: ark TRIP (onset 35)
    flags = icd.flag_names(icd.decode_block(icd.build_block(panel_values(svc, svc.panels["P06"])))["FLAGS"])
    assert "ARC_TRIP_LATCHED" in flags and "ALARM_PAGED" in flags
    svc.advance_to(38.5 * DAY_S)  # P05: veri kaybı 38-40
    flags = icd.flag_names(icd.decode_block(icd.build_block(panel_values(svc, svc.panels["P05"])))["FLAGS"])
    assert "STALE" in flags
    age = icd.decode_block(icd.build_block(panel_values(svc, svc.panels["P05"])))["DATA_AGE_S"]
    assert age > 3 * 900  # 3 x periyot sonrası
    svc.advance_to(44 * DAY_S)  # P03: PD tek başına
    flags = icd.flag_names(icd.decode_block(icd.build_block(panel_values(svc, svc.panels["P03"])))["FLAGS"])
    assert "PD_ADVISORY" in flags and "ALARM_PAGED" not in flags


def test_scada_view_maps_every_register_to_a_screen_element():
    svc = make()
    svc.advance_to(34.6 * DAY_S)
    view = scada_view(svc, "P02")
    assert view["base_address"] == 1 * 32 and view["function_code"] == 4 and len(view["registers"]) == 32
    assert [r["address"] for r in view["registers"]] == list(range(32, 64))
    assert all(r["screen"] != "—" for r in view["registers"] if not r["name"].startswith("RESERVED"))
    row = next(r for r in view["registers"] if r["name"] == "SEVERITY_CODE")
    assert row["hex"] == f"0x{row['raw']:04X}" and view["severity_text"] in ("NORMAL", "UYARI", "ALARM", "KRİTİK")


def test_scada_api_endpoints_and_csv_download():
    svc = make()
    client = create_app(fleet_service=svc).test_client()
    body = client.get("/api/fleet/scada?panel=P01").get_json()
    assert body["panel_id"] == "P01" and len(body["registers"]) == 32
    assert client.get("/api/fleet/scada?panel=P99").status_code == 404
    csv_resp = client.get("/api/fleet/scada/points.csv")
    assert csv_resp.status_code == 200 and csv_resp.mimetype == "text/csv" and b"SEVERITY_CODE" in csv_resp.data


# ---------------------------------------------- GERÇEK Modbus TCP (pymodbus istemcisi)
@pytest.fixture()
def live():
    svc = make()
    svc.advance_to(34.6 * DAY_S)
    port = 15031
    server = FleetModbusServer(svc, host="127.0.0.1", port=port).start()
    client = ModbusTcpClient("127.0.0.1", port=port)
    assert client.connect()
    yield svc, client
    client.close()
    server.stop()


def read_block(client, panel_index):
    rr = client.read_input_registers(icd.block_base(panel_index), count=icd.BLOCK_SIZE, device_id=1)
    assert not rr.isError(), rr
    return list(rr.registers)


def test_modbus_master_reads_exactly_what_the_console_shows(live):
    svc, client = live
    for idx, pid in enumerate(svc.panels):
        regs = read_block(client, idx)
        assert regs == icd.build_block(panel_values(svc, svc.panels[pid])), f"{pid} register bloğu konsoldan farklı"
    p01 = icd.decode_block(read_block(client, 0))
    assert p01["SEVERITY_CODE"] == 2 and p01["ALARMS_OPEN"] == 1 and p01["ICD_VERSION"] == 200
    assert p01["THETA_MAX_X10"] > 30.0  # θ ALARM eşiğinin üstünde


def test_modbus_multi_panel_read_within_the_125_register_protocol_limit(live):
    svc, client = live
    rr = client.read_input_registers(0, count=3 * icd.BLOCK_SIZE, device_id=1)  # FC04 tek istekte en çok 125 register
    assert not rr.isError() and list(rr.registers) == all_registers(svc)[: 3 * icd.BLOCK_SIZE]
    rest = client.read_input_registers(3 * icd.BLOCK_SIZE, count=3 * icd.BLOCK_SIZE, device_id=1)
    assert list(rest.registers) == all_registers(svc)[3 * icd.BLOCK_SIZE :]


def test_modbus_values_follow_the_simulation_clock_live(live):
    svc, client = live
    before = icd.decode_block(read_block(client, 5))  # P06 ark
    assert before["SEV_ARC"] == 0 and "ARC_TRIP_LATCHED" not in icd.flag_names(before["FLAGS"])
    svc.advance_to(35.3 * DAY_S)  # ark TRIP (gün 35) oluşur
    after = icd.decode_block(read_block(client, 5))
    assert after["SEV_ARC"] == 3 and after["SEVERITY_CODE"] == 3
    assert "ARC_TRIP_LATCHED" in icd.flag_names(after["FLAGS"])


def test_modbus_is_strictly_read_only(live):
    svc, client = live
    before = read_block(client, 0)
    write = client.write_register(icd.block_base(0), 0, device_id=1)
    assert write.isError() and write.exception_code == 1  # Illegal Function
    assert client.write_registers(0, [1, 2, 3], device_id=1).isError()
    assert client.read_holding_registers(0, count=2, device_id=1).isError()  # FC03 tanımsız
    assert client.read_coils(0, count=2, device_id=1).isError()
    assert read_block(client, 0) == before  # hiçbir şey değişmedi


def test_modbus_out_of_range_address_is_an_exception_not_garbage(live):
    svc, client = live
    beyond = len(svc.panels) * icd.BLOCK_SIZE
    assert client.read_input_registers(beyond, count=1, device_id=1).isError()


def test_latched_arc_trip_stays_visible_in_registers_until_acknowledged(live):
    svc, client = live
    svc.advance_to(35.6 * DAY_S)  # sinyal 35.0'da 1 saat sürdü ve döndü
    regs = icd.decode_block(read_block(client, 5))
    assert regs["SEVERITY_CODE"] == 3 and regs["SEV_ARC"] == 3 and regs["ALARMS_OPEN"] >= 1
    assert "ARC_TRIP_LATCHED" in icd.flag_names(regs["FLAGS"])
    trip = next(r for r in svc.alarms(panel_id="P06") if r["kind"] == "arc_trip")
    import re

    token = next(re.search(r"ONAY \S+ (\d{4})", m["text"]).group(1) for m in svc.notifications(500) if m["alarm_id"] == trip["id"] and m["kind"] == "first")
    svc.ack(trip["id"], token, "Ayşe Y.")
    after = icd.decode_block(read_block(client, 5))
    assert after["SEV_ARC"] == 0 and "ARC_TRIP_LATCHED" not in icd.flag_names(after["FLAGS"])  # onay = kapanış

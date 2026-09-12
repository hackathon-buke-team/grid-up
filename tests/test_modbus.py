import pytest
from pymodbus.client import ModbusTcpClient

from panogoz.scada.modbus_server import run_in_background_thread, stop_background_server
from panogoz.scada.register_map import (
    ConnectionSnapshot,
    Register,
    REGISTERS_PER_CONNECTION,
    connection_base_address,
    decode_signed_x10,
    decode_unsigned_x10,
)

TEST_PORT = 15020


def test_encode_decode_roundtrip_for_negative_theta():
    from panogoz.scada.register_map import decode_signed_x10, encode_signed_x10

    raw = encode_signed_x10(-23.4)
    assert decode_signed_x10(raw) == pytest.approx(-23.4)


def test_connection_snapshot_produces_expected_register_count():
    snapshot = ConnectionSnapshot(
        severity_code=2,
        theta=-12.5,
        current_l1_a=250.0,
        current_l2_a=251.2,
        current_l3_a=248.9,
        surface_temp_l1_c=45.0,
        surface_temp_l2_c=46.1,
        surface_temp_l3_c=44.8,
    )
    registers = snapshot.to_registers()
    assert len(registers) == REGISTERS_PER_CONNECTION


@pytest.fixture
def running_server():
    snapshots = {
        0: ConnectionSnapshot(
            severity_code=0,
            theta=1.2,
            current_l1_a=180.0,
            current_l2_a=181.0,
            current_l3_a=179.5,
            surface_temp_l1_c=42.0,
            surface_temp_l2_c=42.3,
            surface_temp_l3_c=41.8,
        ),
        1: ConnectionSnapshot(
            severity_code=3,
            theta=-98.1,
            current_l1_a=250.0,
            current_l2_a=252.0,
            current_l3_a=249.0,
            surface_temp_l1_c=60.0,
            surface_temp_l2_c=95.4,
            surface_temp_l3_c=59.9,
        ),
    }
    server, thread, loop = run_in_background_thread(snapshots, host="127.0.0.1", port=TEST_PORT)
    yield snapshots
    stop_background_server(server, thread, loop)


def test_real_modbus_tcp_client_reads_expected_registers(running_server):
    snapshots = running_server
    client = ModbusTcpClient("127.0.0.1", port=TEST_PORT)
    assert client.connect(), "gerçek Modbus TCP istemcisi sunucuya bağlanamadı"
    try:
        for index, snapshot in snapshots.items():
            base = connection_base_address(index)
            result = client.read_input_registers(base, count=REGISTERS_PER_CONNECTION, device_id=1)
            assert not result.isError()
            regs = result.registers

            assert regs[Register.SEVERITY_CODE] == snapshot.severity_code
            assert decode_signed_x10(regs[Register.THETA_X10]) == pytest.approx(snapshot.theta, abs=0.05)
            assert decode_unsigned_x10(regs[Register.CURRENT_L1_X10]) == pytest.approx(snapshot.current_l1_a, abs=0.05)
            assert decode_signed_x10(regs[Register.SURFACE_TEMP_L2_X10]) == pytest.approx(
                snapshot.surface_temp_l2_c, abs=0.05
            )
    finally:
        client.close()

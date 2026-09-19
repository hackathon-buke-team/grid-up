"""K2 2.3: IEC 60870-5-104 slave.

Üç katman: (A) kodlayıcı, standardın bilinen baytlarına karşı; (B) bağımsız üçüncü taraf master
(Fraunhofer `c104`) ile birlikte çalışma; (C) ham soket protokol testleri (pencere, zamanlayıcılar,
hata durumları).
"""
import datetime as dt
import socket
import time

import pytest

from panogoz.scada import icd
from panogoz.scada import iec104_codec as c
from panogoz.scada.fleet_bridge import all_registers
from panogoz.scada.iec104 import Iec104Server

# ============================================================ A) kodlayıcı
def test_u_frames_match_standard_bytes():
    assert c.encode_u(c.STARTDT_ACT) == bytes.fromhex("680407000000")
    assert c.encode_u(c.STARTDT_CON) == bytes.fromhex("68040B000000")
    assert c.encode_u(c.STOPDT_ACT) == bytes.fromhex("680413000000")
    assert c.encode_u(c.TESTFR_ACT) == bytes.fromhex("680443000000")
    assert c.encode_u(c.TESTFR_CON) == bytes.fromhex("680483000000")


def test_s_frame_and_i_frame_sequence_numbers():
    assert c.encode_s(5) == bytes.fromhex("68040100 0A00".replace(" ", ""))
    frame = c.encode_i(200, 300, b"")
    assert frame[2] == (200 & 0x7F) << 1 and frame[3] == 200 >> 7
    apdu = c.decode_apdu(c.encode_i(200, 300, b"\x64\x01"))
    assert (apdu.kind, apdu.ns, apdu.nr, apdu.asdu) == ("I", 200, 300, b"\x64\x01")
    assert c.decode_apdu(c.encode_s(32767)).nr == 32767
    assert c.decode_apdu(c.encode_u(c.TESTFR_ACT)).u == c.TESTFR_ACT


def test_general_interrogation_activation_is_the_textbook_frame():
    asdu = c.Asdu(c.C_IC_NA_1, c.COT_ACT, 1, [(0, b"\x14")]).encode()
    assert asdu.hex() == "64010600010000000014"
    assert c.encode_i(0, 0, asdu).hex() == "680e0000000064010600010000000014"


def test_asdu_roundtrip_sq0_and_sq1_and_flags():
    objs = [(101, c.me_nb(-5, c.QDS_OV)), (102, c.me_nb(1234))]
    a = c.decode_asdu(c.Asdu(c.M_ME_NB_1, c.COT_SPONTANEOUS, 7, objs).encode())
    assert (a.type_id, a.cot, a.ca, a.sq, a.negative) == (c.M_ME_NB_1, 3, 7, False, False) and a.objects == objs
    seq = [(1000 + i, c.me_nb(i)) for i in range(5)]
    b = c.decode_asdu(c.Asdu(c.M_ME_NB_1, c.COT_INTERROGATED, 1, seq, sq=True).encode())
    assert b.sq and b.objects == seq
    n = c.decode_asdu(c.Asdu(c.C_IC_NA_1, c.COT_ACT_CON, 1, [(0, b"\x14")], negative=True).encode())
    assert n.negative and n.cot == 7


def test_scaled_value_is_int16_little_endian_with_quality():
    assert c.me_nb(453, 0) == bytes.fromhex("C50100")
    assert c.me_nb(-1, c.QDS_NT) == bytes.fromhex("FFFF40")


def test_cp56time2a_known_encoding_and_roundtrip():
    ts = dt.datetime(2026, 9, 19, 21, 30, 45, 123000, tzinfo=dt.timezone.utc)  # Cumartesi
    b = c.cp56(ts)
    assert b.hex() == "43b01e15d3091a"  # ms=45123, dk=30, sa=21, (6<<5)|19, ay=9, yıl=26
    assert c.decode_cp56(b) == ts


@pytest.mark.parametrize(
    "bad",
    [b"", b"\x68", b"\x67\x04\x07\x00\x00\x00", b"\x68\x05\x07\x00\x00\x00", b"\x68\x03\x07\x00\x00"],
)
def test_malformed_frames_are_rejected(bad):
    with pytest.raises(c.FrameError):
        c.decode_apdu(bad)


def test_asdu_limits():
    with pytest.raises(c.FrameError):
        c.Asdu(c.M_ME_NB_1, 3, 1, []).encode()
    with pytest.raises(c.FrameError):
        c.encode_i(0, 0, b"\x00" * 250)
    with pytest.raises(c.FrameError):
        c.decode_asdu(b"\x0b\x81\x14\x00\x01\x00\x01\x00\x00")  # SQ=1, N=1 ama gövde kısa


# ============================================================ ortak yardımcılar
def synthetic_regs(n_panels=3, overrides=None):
    overrides = overrides or {}
    regs = []
    for p in range(n_panels):
        vals = {"SEVERITY_CODE": p % 4, "CURRENT_L1_X10": 200.0 + p, "JOINT_TEMP_L1_X10": 55.5, "THETA_MAX_X10": 12.3 * p}
        vals.update(overrides.get(p, {}))
        regs.extend(icd.build_block(vals))
    return regs


class RawMaster:
    """Ham soket üzerinde el yapımı IEC 104 master (kodlayıcıyı kullanır, sunucu kodunu değil)."""

    def __init__(self, port, timeout=3.0):
        self.sock = socket.create_connection(("127.0.0.1", port), timeout=timeout)
        self.sock.settimeout(timeout)
        self.buf = b""

    def send(self, data):
        self.sock.sendall(data)

    def recv_frame(self):
        while True:
            if len(self.buf) >= 2 and len(self.buf) >= 2 + self.buf[1]:
                frame, self.buf = self.buf[: 2 + self.buf[1]], self.buf[2 + self.buf[1] :]
                return c.decode_apdu(frame)
            chunk = self.sock.recv(4096)
            if not chunk:
                raise ConnectionError("bağlantı kapandı")
            self.buf += chunk

    def start(self):
        self.send(c.encode_u(c.STARTDT_ACT))
        f = self.recv_frame()
        assert f.kind == "U" and f.u == c.STARTDT_CON

    def collect_i(self, until_asdu_cot=None, limit=400, timeout=3.0):
        frames = []
        end = time.time() + timeout
        while time.time() < end and len(frames) < limit:
            try:
                f = self.recv_frame()
            except (socket.timeout, TimeoutError):
                break
            if f.kind == "I":
                frames.append(f)
                if until_asdu_cot is not None and c.decode_asdu(f.asdu).cot == until_asdu_cot:
                    break
        return frames

    def close(self):
        self.sock.close()


@pytest.fixture()
def static_server():
    srv = Iec104Server(host="127.0.0.1", port=0, snapshot_fn=lambda: synthetic_regs(3), poll_s=0.1).start()
    yield srv
    srv.stop()


# ============================================================ C) ham soket protokol testleri
def test_startdt_testfr_stopdt_handshakes(static_server):
    m = RawMaster(static_server.port)
    m.send(c.encode_u(c.TESTFR_ACT))
    assert m.recv_frame().u == c.TESTFR_CON
    m.start()
    m.send(c.encode_u(c.STOPDT_ACT))
    assert m.recv_frame().u == c.STOPDT_CON
    m.close()


def test_general_interrogation_full_sequence_and_values(static_server):
    m = RawMaster(static_server.port)
    m.start()
    m.send(c.encode_i(0, 0, c.Asdu(c.C_IC_NA_1, c.COT_ACT, 1, [(0, b"\x14")]).encode()))
    frames = m.collect_i(until_asdu_cot=c.COT_ACT_TERM)
    asdus = [c.decode_asdu(f.asdu) for f in frames]
    assert asdus[0].type_id == c.C_IC_NA_1 and asdus[0].cot == c.COT_ACT_CON and not asdus[0].negative
    assert asdus[-1].type_id == c.C_IC_NA_1 and asdus[-1].cot == c.COT_ACT_TERM
    data = [a for a in asdus[1:-1]]
    assert all(a.cot == c.COT_INTERROGATED for a in data)
    assert len(data) == 3 * 2  # her pano: 32'lik ölçüm dizisi + 7 bayrak biti
    p1 = next(a for a in data if a.type_id == c.M_ME_NB_1 and a.objects[0][0] == icd.ioa_measurand(1, 0))
    assert len(p1.objects) == 32
    values = {ioa: int.from_bytes(el[:2], "little", signed=True) for ioa, el in p1.objects}
    assert values[icd.ioa_measurand(1, 0)] == 1  # SEVERITY_CODE
    assert values[icd.ioa_measurand(1, 5)] == 2010  # 201.0 A x10
    assert values[icd.ioa_measurand(1, 9)] == 555  # 55.5 °C x10
    assert values[icd.ioa_measurand(1, 31)] == 200  # ICD sürümü
    flags = [a for a in data if a.type_id == c.M_SP_NA_1]
    assert len(flags) == 3 and all(len(a.objects) == 7 for a in flags)
    m.close()


def test_control_commands_are_rejected_read_only(static_server):
    m = RawMaster(static_server.port)
    m.start()
    single_cmd = bytes([45, 0x01, c.COT_ACT, 0, 1, 0]) + (5000).to_bytes(3, "little") + b"\x01"  # C_SC_NA_1
    m.send(c.encode_i(0, 0, single_cmd))
    f = m.recv_frame()
    assert f.kind == "I"
    raw = f.asdu
    assert raw[0] == 45 and (raw[2] & 0x3F) == c.COT_UNKNOWN_TYPE and raw[2] & c.PN_NEGATIVE  # yansıtıldı, negatif
    m.close()


def test_wrong_common_address_and_wrong_cot_and_bad_qualifier_are_negative(static_server):
    m = RawMaster(static_server.port)
    m.start()
    m.send(c.encode_i(0, 0, c.Asdu(c.C_IC_NA_1, c.COT_ACT, 9, [(0, b"\x14")]).encode()))
    r = m.recv_frame().asdu
    assert (r[2] & 0x3F) == c.COT_UNKNOWN_CA and r[2] & c.PN_NEGATIVE
    m.send(c.encode_i(1, 1, c.Asdu(c.C_IC_NA_1, c.COT_REQUEST, 1, [(0, b"\x14")]).encode()))
    r = m.recv_frame().asdu
    assert (r[2] & 0x3F) == c.COT_UNKNOWN_COT and r[2] & c.PN_NEGATIVE
    m.send(c.encode_i(2, 2, c.Asdu(c.C_IC_NA_1, c.COT_ACT, 1, [(0, b"\x15")]).encode()))  # QOI 21 (grup 1): desteklenmiyor
    r = m.recv_frame().asdu
    assert (r[2] & 0x3F) == c.COT_ACT_CON and r[2] & c.PN_NEGATIVE
    m.close()


def test_read_command_returns_point_or_unknown_ioa(static_server):
    m = RawMaster(static_server.port)
    m.start()
    ioa = icd.ioa_measurand(2, 5)
    m.send(c.encode_i(0, 0, c.Asdu(c.C_RD_NA_1, c.COT_REQUEST, 1, [(ioa, b"")]).encode()))
    a = c.decode_asdu(m.recv_frame().asdu)
    assert a.type_id == c.M_ME_NB_1 and a.cot == c.COT_REQUEST and a.objects[0][0] == ioa
    assert int.from_bytes(a.objects[0][1][:2], "little", signed=True) == 2020
    m.send(c.encode_i(1, 1, c.Asdu(c.C_RD_NA_1, c.COT_REQUEST, 1, [(9999, b"")]).encode()))
    r = m.recv_frame().asdu
    assert (r[2] & 0x3F) == c.COT_UNKNOWN_IOA and r[2] & c.PN_NEGATIVE
    m.close()


def test_clock_sync_sets_server_time_offset_and_is_confirmed(static_server):
    m = RawMaster(static_server.port)
    m.start()
    target = dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=2)
    m.send(c.encode_i(0, 0, c.Asdu(c.C_CS_NA_1, c.COT_ACT, 1, [(0, c.cp56(target))]).encode()))
    a = c.decode_asdu(m.recv_frame().asdu)
    assert a.type_id == c.C_CS_NA_1 and a.cot == c.COT_ACT_CON and not a.negative
    assert static_server.clock_syncs == 1
    assert abs((static_server.now() - target).total_seconds()) < 2.0
    m.close()


def test_i_frame_with_wrong_sequence_number_closes_the_connection(static_server):
    m = RawMaster(static_server.port)
    m.start()
    m.send(c.encode_i(5, 0, c.Asdu(c.C_TS_NA_1, c.COT_ACT, 1, [(0, b"\xaa\x55")]).encode()))  # N(S)=5, beklenen 0
    with pytest.raises((ConnectionError, ConnectionResetError, socket.timeout, TimeoutError)):
        for _ in range(5):
            m.recv_frame()
    m.close()


def test_garbage_start_byte_closes_the_connection(static_server):
    m = RawMaster(static_server.port)
    m.send(b"\x00\x04\x07\x00\x00\x00")
    with pytest.raises((ConnectionError, ConnectionResetError, socket.timeout, TimeoutError)):
        m.recv_frame()
    m.close()


def test_i_frames_before_startdt_are_ignored(static_server):
    m = RawMaster(static_server.port, timeout=0.6)
    m.send(c.encode_i(0, 0, c.Asdu(c.C_IC_NA_1, c.COT_ACT, 1, [(0, b"\x14")]).encode()))
    with pytest.raises((socket.timeout, TimeoutError)):
        m.recv_frame()  # DURDURULMUŞ durumda yanıt yok
    m.close()


def test_send_window_k_stops_the_server_until_the_master_acknowledges():
    srv = Iec104Server(host="127.0.0.1", port=0, snapshot_fn=lambda: synthetic_regs(10), k=3, w=100, t1=30.0, t2=30.0, t3=60.0).start()
    try:
        m = RawMaster(srv.port, timeout=0.7)
        m.start()
        m.send(c.encode_i(0, 0, c.Asdu(c.C_IC_NA_1, c.COT_ACT, 1, [(0, b"\x14")]).encode()))
        first = m.collect_i(timeout=1.2)
        assert len(first) == 3  # k=3: onay gelmeden daha fazlası gönderilmez
        assert [f.ns for f in first] == [0, 1, 2]
        m.send(c.encode_s(3))  # 3 çerçeve onaylandı -> pencere açılır
        more = m.collect_i(timeout=1.2)
        assert len(more) == 3 and more[0].ns == 3
        m.close()
    finally:
        srv.stop()


def test_server_sends_s_frame_ack_after_w_received_i_frames():
    srv = Iec104Server(host="127.0.0.1", port=0, snapshot_fn=lambda: synthetic_regs(1), w=2, t2=30.0, t3=60.0, t1=30.0).start()
    try:
        m = RawMaster(srv.port, timeout=2.0)
        m.start()
        ts = c.Asdu(c.C_TS_NA_1, c.COT_ACT, 1, [(0, b"\xaa\x55")]).encode()
        m.send(c.encode_i(0, 0, ts) + c.encode_i(1, 0, ts))
        seen = []
        while True:
            f = m.recv_frame()
            seen.append(f)
            if f.kind == "S":
                assert f.nr == 2  # w=2 alınan I çerçevesi sonrası N(R)=2
                break
            assert len(seen) < 6
        m.close()
    finally:
        srv.stop()


def test_idle_connection_gets_testfr_and_is_dropped_when_master_stays_silent():
    srv = Iec104Server(host="127.0.0.1", port=0, snapshot_fn=lambda: synthetic_regs(1), t3=0.4, t1=0.8, t2=5.0).start()
    try:
        m = RawMaster(srv.port, timeout=3.0)
        m.start()
        f = m.recv_frame()
        assert f.kind == "U" and f.u == c.TESTFR_ACT  # t3 sonrası sunucu test çerçevesi yollar
        with pytest.raises((ConnectionError, ConnectionResetError, socket.timeout, TimeoutError)):
            for _ in range(3):
                m.recv_frame()  # yanıtsız kalınca t1 sonunda bağlantı kapanır
        m.close()
    finally:
        srv.stop()


def test_spontaneous_events_carry_severity_changes_and_timestamped_flag_changes():
    state = {"regs": synthetic_regs(2)}
    srv = Iec104Server(host="127.0.0.1", port=0, snapshot_fn=lambda: list(state["regs"]), poll_s=0.1).start()
    try:
        m = RawMaster(srv.port, timeout=3.0)
        m.start()
        time.sleep(0.4)  # ilk anlık görüntü alınsın
        new = synthetic_regs(2, {1: {"SEVERITY_CODE": 3, "ALARMS_OPEN": 1, "FLAGS": icd.set_flags("ARC_TRIP_LATCHED")}})
        state["regs"] = new
        events = [c.decode_asdu(f.asdu) for f in m.collect_i(limit=2, timeout=3.0)]
        by_type = {a.type_id: a for a in events}
        me = by_type[c.M_ME_NB_1]
        assert me.cot == c.COT_SPONTANEOUS
        changed = {ioa: int.from_bytes(el[:2], "little", signed=True) for ioa, el in me.objects}
        assert changed[icd.ioa_measurand(1, 0)] == 3 and changed[icd.ioa_measurand(1, 1)] == 1
        sp = by_type[c.M_SP_TB_1]
        (ioa, el), = sp.objects
        assert ioa == icd.ioa_flag(1, 2) and el[0] & 1 == 1  # ARC_TRIP_LATCHED bit 2
        assert abs((c.decode_cp56(el[1:]) - dt.datetime.now(dt.timezone.utc)).total_seconds()) < 5
        m.close()
    finally:
        srv.stop()


def test_stale_panel_measurands_carry_not_topical_quality_and_overflow_is_flagged():
    regs = synthetic_regs(2, {0: {"FLAGS": icd.set_flags("STALE"), "DATA_AGE_S": 70000}})
    srv = Iec104Server(host="127.0.0.1", port=0, snapshot_fn=lambda: regs).start()
    try:
        m = RawMaster(srv.port)
        m.start()
        m.send(c.encode_i(0, 0, c.Asdu(c.C_IC_NA_1, c.COT_ACT, 1, [(0, b"\x14")]).encode()))
        asdus = [c.decode_asdu(f.asdu) for f in m.collect_i(until_asdu_cot=c.COT_ACT_TERM)]
        p0 = next(a for a in asdus if a.type_id == c.M_ME_NB_1 and a.objects[0][0] == 1)
        els = dict(p0.objects)
        assert els[icd.ioa_measurand(0, 5)][2] & c.QDS_NT  # STALE -> güncel değil
        age = els[icd.ioa_measurand(0, 26)]
        assert int.from_bytes(age[:2], "little", signed=True) == 32767 and age[2] & c.QDS_OV  # u16 doyar, OV
        sp = next(a for a in asdus if a.type_id == c.M_SP_NA_1 and a.objects[0][0] == icd.ioa_flag(0, 0))
        assert sp.objects[0][1][0] == 0x81  # STALE=1 + IV
        m.close()
    finally:
        srv.stop()


# ============================================================ B) bağımsız master: Fraunhofer c104
c104 = pytest.importorskip("c104")


@pytest.fixture()
def fleet_and_server():
    from tests.test_fleet_service import DAY_S, make

    svc = make()
    svc.advance_to(34.6 * DAY_S)
    srv = Iec104Server(svc, host="127.0.0.1", port=0, poll_s=0.2).start()
    yield svc, srv
    srv.stop()


def as_number(value):
    """c104 ölçekli değerleri `c104.Int16` sarmalayıcısı olarak verir; tekil bilgi bool'dur."""
    return value if isinstance(value, bool) else int(value)


def connect_master(port, ioas, types=None):
    client = c104.Client(tick_rate_ms=100, command_timeout_ms=4000)
    conn = client.add_connection(ip="127.0.0.1", port=port, init=c104.Init.NONE)
    station = conn.add_station(common_address=1)
    points = {}
    for ioa, typ in ioas:
        points[ioa] = station.add_point(io_address=ioa, type=typ)
    client.start()
    conn.connect()
    deadline = time.time() + 5
    while not conn.is_connected and time.time() < deadline:
        time.sleep(0.05)
    assert conn.is_connected
    return client, conn, station, points


def test_independent_c104_master_general_interrogation_matches_icd_registers(fleet_and_server):
    svc, srv = fleet_and_server
    regs = icd.decode_block(all_registers(svc)[0 : icd.BLOCK_SIZE])
    want = [("SEVERITY_CODE", 0), ("THETA_MAX_X10", 4), ("CURRENT_L2_X10", 6), ("JOINT_TEMP_L2_X10", 10), ("HUMIDITY_X10", 15), ("ICD_VERSION", 31)]
    ioas = [(icd.ioa_measurand(0, off), c104.Type.M_ME_NB_1) for _, off in want] + [(icd.ioa_flag(0, 6), c104.Type.M_SP_NA_1)]
    client, conn, station, points = connect_master(srv.port, ioas)
    try:
        assert conn.interrogation(common_address=1, cause=c104.Cot.ACTIVATION, qualifier=c104.Qoi.STATION, wait_for_response=True)
        time.sleep(0.6)
        for name, off in want:
            pt = icd.point(name)
            got = as_number(points[icd.ioa_measurand(0, off)].value)
            expected = regs[name] * pt.scale if pt.scale != 1 else regs[name]
            assert got == pytest.approx(expected, abs=0.5), f"{name}: c104 {got} != ICD {expected}"
        assert as_number(points[icd.ioa_flag(0, 6)].value) is True  # ALARM_PAGED (P01 alarmda)
    finally:
        client.stop()


def test_independent_master_read_and_clock_sync(fleet_and_server):
    svc, srv = fleet_and_server
    ioa = icd.ioa_measurand(0, 0)
    client, conn, station, points = connect_master(srv.port, [(ioa, c104.Type.M_ME_NB_1)])
    try:
        assert points[ioa].read()  # C_RD_NA_1 -> COT 5 yanıtı
        time.sleep(0.5)
        assert as_number(points[ioa].value) == 2  # P01 şiddeti ALARM
        assert conn.clock_sync(common_address=1, wait_for_response=True)
        assert srv.clock_syncs == 1
    finally:
        client.stop()


def test_independent_master_receives_spontaneous_alarm_events_when_fleet_state_changes(fleet_and_server):
    from tests.test_fleet_service import DAY_S

    svc, srv = fleet_and_server
    sev_ioa = icd.ioa_measurand(5, 0)  # P06 (ark TRIP senaryosu)
    arc_flag = icd.ioa_flag(5, 2)  # ARC_TRIP_LATCHED
    events = []
    client, conn, station, points = connect_master(srv.port, [(sev_ioa, c104.Type.M_ME_NB_1), (arc_flag, c104.Type.M_SP_TB_1)])
    try:
        def on_rx(point: c104.Point, previous_info: c104.Information, message: c104.IncomingMessage) -> c104.ResponseState:
            events.append((point.io_address, as_number(point.value)))
            return c104.ResponseState.SUCCESS

        for p in points.values():
            p.on_receive(on_rx)
        time.sleep(0.6)
        svc.advance_to(35.3 * DAY_S)  # ark TRIP gün 35'te
        deadline = time.time() + 6
        while time.time() < deadline and not (any(i == sev_ioa and v == 3 for i, v in events) and any(i == arc_flag and v is True for i, v in events)):
            time.sleep(0.1)
        assert any(i == sev_ioa and v == 3 for i, v in events), events
        assert any(i == arc_flag and v is True for i, v in events), events
    finally:
        client.stop()


def test_independent_master_control_command_is_denied(fleet_and_server):
    svc, srv = fleet_and_server
    client = c104.Client(tick_rate_ms=100, command_timeout_ms=2500)
    conn = client.add_connection(ip="127.0.0.1", port=srv.port, init=c104.Init.NONE)
    station = conn.add_station(common_address=1)
    cmd = station.add_point(io_address=5000, type=c104.Type.C_SC_NA_1, command_mode=c104.CommandMode.DIRECT)
    client.start()
    conn.connect()
    deadline = time.time() + 5
    while not conn.is_connected and time.time() < deadline:
        time.sleep(0.05)
    try:
        cmd.value = True
        assert cmd.transmit(cause=c104.Cot.ACTIVATION) is False  # sunucu reddeder (yalnız izleme)
        assert conn.is_connected  # bağlantı bozulmadı
    finally:
        client.stop()

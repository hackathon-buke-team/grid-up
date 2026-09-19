"""IEC 60870-5-104 slave (kontrol istasyonuna izleme verisi): genel tarama, kendiliğinden bildirim, saat senkronu.

Aynı ICD v2 bloğunu (panogoz/scada/icd.py) Modbus'un yanında ikinci SCADA protokolü olarak yayınlar
(K2 2.3). YALNIZ İZLEME: kontrol yönündeki (45…69) komutlar reddedilir. Bağımsız doğrulama:
tests/test_iec104.py Fraunhofer `c104` kütüphanesini (üçüncü taraf, tam istemci/sunucu) master olarak
kullanır; kodlayıcı testleri standart baytlarına karşıdır (panogoz/scada/iec104_codec.py).

Bilinen sınırlar (dürüstçe): TLS (IEC 62351-3) yok; yalnız tek ortak adres; k/w/t1/t2/t3 zamanlayıcıları
uygulanmıştır ama sahadaki farklı üretici master'larla interoperabilite denenmemiştir.
"""
from __future__ import annotations

import asyncio
import datetime as _dt
import threading
import time
from collections import deque
from typing import Callable

from panogoz.scada import icd
from panogoz.scada import iec104_codec as c

EVENT_OFFSETS = tuple([0, 1, 2] + list(range(20, 26)))  # şiddet, alarm sayaçları, SEV_* (kendiliğinden bildirilenler)
FLAGS_OFFSET = icd.point("FLAGS").offset
MODULO = 32768


def scaled_element(pt: icd.Point, raw: int, stale: bool) -> bytes:
    if pt.dtype == "s16":
        value, overflow = (raw - 0x10000 if raw >= 0x8000 else raw), False
    elif pt.dtype == "bits":
        value, overflow = raw & 0x7FFF, raw > 0x7FFF
    else:
        value, overflow = min(raw, 32767), raw > 32767
    return c.me_nb(value, (c.QDS_OV if overflow else 0) | (c.QDS_NT if stale else 0))


def _is_stale(regs: list[int], panel: int) -> bool:
    return bool(regs[panel * icd.BLOCK_SIZE + FLAGS_OFFSET] & (1 << 0))


class _Conn:
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        self.reader, self.writer = reader, writer
        self.started = False
        self.vs = 0
        self.vr = 0
        self.unacked: deque[tuple[int, float]] = deque()
        self.outq: asyncio.Queue[bytes] = asyncio.Queue()
        self.wake = asyncio.Event()
        self.rx_since_ack = 0
        self.ack_due_since: float | None = None
        self.last_rx = self.last_tx = time.monotonic()
        self.testfr_since: float | None = None
        self.closing = False

    def peer(self) -> str:
        info = self.writer.get_extra_info("peername")
        return f"{info[0]}:{info[1]}" if info else "?"


class Iec104Server:
    def __init__(
        self,
        service=None,
        *,
        host: str = "0.0.0.0",
        port: int = 2404,
        common_address: int = icd.IEC104_COMMON_ADDRESS,
        k: int = 12,
        w: int = 8,
        t1: float = 15.0,
        t2: float = 10.0,
        t3: float = 20.0,
        poll_s: float = 0.5,
        snapshot_fn: Callable[[], list[int]] | None = None,
    ) -> None:
        if snapshot_fn is None:
            if service is None:
                raise ValueError("service veya snapshot_fn gerekli")
            from panogoz.scada.fleet_bridge import all_registers

            snapshot_fn = lambda: all_registers(service)  # noqa: E731
        self.snapshot_fn = snapshot_fn
        self.host, self.port, self.ca = host, port, common_address
        self.k, self.w, self.t1, self.t2, self.t3, self.poll_s = k, w, t1, t2, t3, poll_s
        self.time_offset = _dt.timedelta(0)
        self.clock_syncs = 0
        self._last: list[int] | None = None
        self._conns: set[_Conn] = set()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._server: asyncio.AbstractServer | None = None
        self._poll_task: asyncio.Task | None = None
        self._main_task: asyncio.Task | None = None
        self._handlers: set[asyncio.Task] = set()
        self.log: list[str] = []

    # ------------------------------------------------------------ yaşam döngüsü
    def start(self, timeout: float = 5.0) -> "Iec104Server":
        ready = threading.Event()
        error: list[BaseException] = []

        async def main() -> None:
            try:
                self._server = await asyncio.start_server(self._handle, self.host, self.port)
                self.port = self._server.sockets[0].getsockname()[1]
                self._poll_task = asyncio.create_task(self._poll_loop())
            except BaseException as exc:  # noqa: BLE001
                error.append(exc)
                ready.set()
                return
            self._main_task = asyncio.current_task()
            ready.set()
            try:
                await self._server.serve_forever()
            except asyncio.CancelledError:
                pass
            finally:
                self._server.close()
                if self._handlers:
                    await asyncio.wait(list(self._handlers), timeout=3.0)

        def run() -> None:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            try:
                self._loop.run_until_complete(main())
            finally:
                self._loop.close()

        self._thread = threading.Thread(target=run, daemon=True, name="panogoz-iec104")
        self._thread.start()
        if not ready.wait(timeout):
            raise RuntimeError("IEC 104 sunucusu zaman aşımında başlamadı")
        if error:
            raise error[0]
        return self

    def stop(self, timeout: float = 5.0) -> None:
        if self._loop is None:
            return

        async def shutdown() -> None:
            if self._poll_task:
                self._poll_task.cancel()
            for conn in list(self._conns):
                conn.closing = True
                conn.writer.close()
            if self._main_task:
                self._main_task.cancel()

        asyncio.run_coroutine_threadsafe(shutdown(), self._loop).result(timeout=timeout)
        if self._thread:
            self._thread.join(timeout=timeout)

    def now(self) -> _dt.datetime:
        return _dt.datetime.now(_dt.timezone.utc) + self.time_offset

    # ------------------------------------------------------------ bağlantı
    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        conn = _Conn(reader, writer)
        me = asyncio.current_task()
        if me is not None:
            self._handlers.add(me)
            me.add_done_callback(self._handlers.discard)
        self._conns.add(conn)
        self.log.append(f"bağlandı {conn.peer()}")
        tasks = [asyncio.create_task(f(conn)) for f in (self._read_loop, self._write_loop, self._timer_loop)]
        try:
            await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        finally:
            for t in tasks:
                t.cancel()
            conn.closing = True
            self._conns.discard(conn)
            try:
                writer.close()
            except Exception:  # noqa: BLE001
                pass
            self.log.append(f"kapandı {conn.peer()}")

    def _send_raw(self, conn: _Conn, data: bytes) -> None:
        conn.writer.write(data)
        conn.last_tx = time.monotonic()

    async def _read_loop(self, conn: _Conn) -> None:
        try:
            while True:
                head = await conn.reader.readexactly(2)
                if head[0] != c.START or not 4 <= head[1] <= 253:
                    self.log.append("geçersiz APCI, bağlantı kapatılıyor")
                    return
                frame = head + await conn.reader.readexactly(head[1])
                conn.last_rx = time.monotonic()
                try:
                    apdu = c.decode_apdu(frame)
                except c.FrameError:
                    return
                if apdu.kind == "U":
                    self._on_u(conn, apdu.u)
                elif apdu.kind == "S":
                    if not self._ack(conn, apdu.nr):
                        return
                else:
                    if not conn.started:
                        continue  # DURDURULMUŞ durumda I çerçeveleri yok sayılır
                    if apdu.ns != conn.vr:
                        self.log.append(f"sıra numarası hatası ns={apdu.ns} beklenen={conn.vr}")
                        return
                    conn.vr = (conn.vr + 1) % MODULO
                    if not self._ack(conn, apdu.nr):
                        return
                    conn.rx_since_ack += 1
                    if conn.ack_due_since is None:
                        conn.ack_due_since = time.monotonic()
                    if conn.rx_since_ack >= self.w:
                        self._send_s(conn)
                    await self._on_asdu(conn, apdu.asdu)
        except (asyncio.IncompleteReadError, ConnectionError, OSError):
            return

    def _send_s(self, conn: _Conn) -> None:
        self._send_raw(conn, c.encode_s(conn.vr))
        conn.rx_since_ack = 0
        conn.ack_due_since = None

    def _on_u(self, conn: _Conn, code: int) -> None:
        if code == c.STARTDT_ACT:
            conn.started = True
            self._send_raw(conn, c.encode_u(c.STARTDT_CON))
            conn.wake.set()
        elif code == c.STOPDT_ACT:
            conn.started = False
            self._send_raw(conn, c.encode_u(c.STOPDT_CON))
        elif code == c.TESTFR_ACT:
            self._send_raw(conn, c.encode_u(c.TESTFR_CON))
        elif code == c.TESTFR_CON:
            conn.testfr_since = None

    def _ack(self, conn: _Conn, nr: int) -> bool:
        outstanding = (conn.vs - nr) % MODULO
        if outstanding > len(conn.unacked):
            self.log.append(f"geçersiz N(R)={nr}")
            return False
        while len(conn.unacked) > outstanding:
            conn.unacked.popleft()
        conn.wake.set()
        return True

    async def _write_loop(self, conn: _Conn) -> None:
        try:
            while True:
                asdu = await conn.outq.get()
                while not (conn.started and len(conn.unacked) < self.k):
                    conn.wake.clear()
                    await conn.wake.wait()
                self._send_raw(conn, c.encode_i(conn.vs, conn.vr, asdu))
                conn.unacked.append((conn.vs, time.monotonic()))
                conn.vs = (conn.vs + 1) % MODULO
                conn.rx_since_ack = 0
                conn.ack_due_since = None  # N(R) gönderilen I çerçevesiyle taşındı
                await conn.writer.drain()
        except (ConnectionError, OSError):
            return

    async def _timer_loop(self, conn: _Conn) -> None:
        try:
            while True:
                await asyncio.sleep(min(0.2, self.t2 / 4, self.t3 / 4))
                now = time.monotonic()
                if conn.ack_due_since is not None and now - conn.ack_due_since >= self.t2:
                    self._send_s(conn)
                if conn.unacked and now - conn.unacked[0][1] >= self.t1:
                    self.log.append("t1: onay gelmedi, bağlantı kapatılıyor")
                    return
                if conn.testfr_since is not None and now - conn.testfr_since >= self.t1:
                    self.log.append("t1: TESTFR yanıtsız, bağlantı kapatılıyor")
                    return
                if conn.testfr_since is None and now - max(conn.last_rx, conn.last_tx) >= self.t3:
                    self._send_raw(conn, c.encode_u(c.TESTFR_ACT))
                    conn.testfr_since = now
        except (ConnectionError, OSError):
            return

    # ------------------------------------------------------------ ASDU işleme
    def _queue(self, conn: _Conn, asdu: c.Asdu) -> None:
        conn.outq.put_nowait(asdu.encode())

    def _mirror(self, conn: _Conn, raw: bytes, cot: int, negative: bool) -> None:
        data = bytearray(raw)
        data[2] = (cot & 0x3F) | (c.PN_NEGATIVE if negative else 0) | (data[2] & 0x80)
        conn.outq.put_nowait(bytes(data))

    async def _on_asdu(self, conn: _Conn, raw: bytes) -> None:
        try:
            a = c.decode_asdu(raw)
        except c.FrameError:
            return
        if a.type_id not in (c.C_IC_NA_1, c.C_CS_NA_1, c.C_RD_NA_1, c.C_TS_NA_1):
            self._mirror(conn, raw, c.COT_UNKNOWN_TYPE, True)  # kontrol komutları dahil: yalnız izleme
            return
        if a.ca not in (self.ca, 0xFFFF):
            self._mirror(conn, raw, c.COT_UNKNOWN_CA, True)
            return
        loop = asyncio.get_running_loop()
        if a.type_id == c.C_IC_NA_1:
            if a.cot != c.COT_ACT:
                self._mirror(conn, raw, c.COT_UNKNOWN_COT, True)
                return
            qoi = a.objects[0][1][0] if a.objects and a.objects[0][1] else 0
            if qoi != 20:
                self._mirror(conn, raw, c.COT_ACT_CON, True)  # yalnız istasyon genel taraması (QOI 20)
                return
            self._mirror(conn, raw, c.COT_ACT_CON, False)
            regs = await loop.run_in_executor(None, self.snapshot_fn)
            for asdu in self._interrogation_asdus(regs):
                self._queue(conn, asdu)
            self._mirror(conn, raw, c.COT_ACT_TERM, False)
        elif a.type_id == c.C_CS_NA_1:
            if a.cot != c.COT_ACT:
                self._mirror(conn, raw, c.COT_UNKNOWN_COT, True)
                return
            master = c.decode_cp56(a.objects[0][1])
            self.time_offset = master - _dt.datetime.now(_dt.timezone.utc)
            self.clock_syncs += 1
            self._mirror(conn, raw, c.COT_ACT_CON, False)
        elif a.type_id == c.C_TS_NA_1:
            self._mirror(conn, raw, c.COT_ACT_CON, False)
        elif a.type_id == c.C_RD_NA_1:
            regs = await loop.run_in_executor(None, self.snapshot_fn)
            ioa = a.objects[0][0]
            asdu = self._read_asdu(regs, ioa)
            if asdu is None:
                self._mirror(conn, raw, c.COT_UNKNOWN_IOA, True)
            else:
                self._queue(conn, asdu)

    # ------------------------------------------------------------ veri üretimi
    def _panels(self, regs: list[int]) -> int:
        return len(regs) // icd.BLOCK_SIZE

    def _interrogation_asdus(self, regs: list[int]) -> list[c.Asdu]:
        out: list[c.Asdu] = []
        for p in range(self._panels(regs)):
            stale = _is_stale(regs, p)
            base = p * icd.BLOCK_SIZE
            measurands = [(icd.ioa_measurand(p, pt.offset), scaled_element(pt, regs[base + pt.offset], stale)) for pt in icd.POINTS]
            out.append(c.Asdu(c.M_ME_NB_1, c.COT_INTERROGATED, self.ca, measurands, sq=True))
            flags = regs[base + FLAGS_OFFSET]
            bits = [(icd.ioa_flag(p, b), c.siq(bool(flags & (1 << b)), iv=stale)) for b in range(icd.FLAG_BIT_COUNT)]
            out.append(c.Asdu(c.M_SP_NA_1, c.COT_INTERROGATED, self.ca, bits, sq=True))
        return out

    def _read_asdu(self, regs: list[int], ioa: int) -> c.Asdu | None:
        n = self._panels(regs)
        if 1 <= ioa <= n * icd.BLOCK_SIZE:
            p, offset = divmod(ioa - 1, icd.BLOCK_SIZE)
            pt = icd.POINTS[offset]
            return c.Asdu(c.M_ME_NB_1, c.COT_REQUEST, self.ca, [(ioa, scaled_element(pt, regs[p * icd.BLOCK_SIZE + offset], _is_stale(regs, p)))])
        if icd.IEC104_FLAG_IOA_BASE < ioa <= icd.IEC104_FLAG_IOA_BASE + n * 8:
            p, bit = divmod(ioa - icd.IEC104_FLAG_IOA_BASE - 1, 8)
            if bit < icd.FLAG_BIT_COUNT:
                state = bool(regs[p * icd.BLOCK_SIZE + FLAGS_OFFSET] & (1 << bit))
                return c.Asdu(c.M_SP_NA_1, c.COT_REQUEST, self.ca, [(ioa, c.siq(state, iv=_is_stale(regs, p)))])
        return None

    def spontaneous_asdus(self, old: list[int], new: list[int], now: _dt.datetime) -> list[c.Asdu]:
        """İki anlık görüntü arasındaki olay tipi değişimleri (COT 3)."""
        out: list[c.Asdu] = []
        analog: list[tuple[int, bytes]] = []
        events: list[tuple[int, bytes]] = []
        for p in range(min(self._panels(old), self._panels(new))):
            base = p * icd.BLOCK_SIZE
            stale = _is_stale(new, p)
            for off in EVENT_OFFSETS:
                if old[base + off] != new[base + off]:
                    analog.append((icd.ioa_measurand(p, off), scaled_element(icd.POINTS[off], new[base + off], stale)))
            changed = old[base + FLAGS_OFFSET] ^ new[base + FLAGS_OFFSET]
            for bit in range(icd.FLAG_BIT_COUNT):
                if changed & (1 << bit):
                    state = bool(new[base + FLAGS_OFFSET] & (1 << bit))
                    events.append((icd.ioa_flag(p, bit), c.siq(state) + c.cp56(now)))
        for i in range(0, len(analog), 40):
            out.append(c.Asdu(c.M_ME_NB_1, c.COT_SPONTANEOUS, self.ca, analog[i : i + 40]))
        for i in range(0, len(events), 20):
            out.append(c.Asdu(c.M_SP_TB_1, c.COT_SPONTANEOUS, self.ca, events[i : i + 20]))
        return out

    async def _poll_loop(self) -> None:
        loop = asyncio.get_running_loop()
        try:
            while True:
                regs = await loop.run_in_executor(None, self.snapshot_fn)
                if self._last is not None and len(regs) == len(self._last):
                    asdus = self.spontaneous_asdus(self._last, regs, self.now())
                    if asdus:
                        for conn in list(self._conns):
                            if conn.started:
                                for asdu in asdus:
                                    self._queue(conn, asdu)
                self._last = regs
                await asyncio.sleep(self.poll_s)
        except asyncio.CancelledError:
            return

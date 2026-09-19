"""IEC 60870-5-104 çerçeve (APCI) ve ASDU kodlayıcı/çözücü -- saf fonksiyonlar, ağ yok.

Standart (IEC 60870-5-104:2006) baytları:
- APCI: 0x68, uzunluk (kontrol 4 bayt + ASDU), 4 kontrol baytı.
  I biçimi: cf1 bit0=0, N(S)=15 bit (cf1[7:1], cf2), N(R)=15 bit (cf3[7:1], cf4).
  S biçimi: cf1=0x01, cf2=0, N(R).  U biçimi: cf1 = 0x07/0x0B (STARTDT), 0x13/0x23 (STOPDT), 0x43/0x83 (TESTFR).
- ASDU: tip(1), VSQ(1: SQ biti + N), COT(2: neden 6 bit + P/N bit6 + T bit7, köken), ortak adres(2, LE), nesneler.
  Bilgi nesnesi adresi IOA 3 bayt LE.
"""
from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field

START = 0x68
MAX_ASDU = 249

# tip kimlikleri
M_SP_NA_1 = 1
M_ME_NB_1 = 11
M_SP_TB_1 = 30
C_IC_NA_1 = 100
C_CI_NA_1 = 101
C_RD_NA_1 = 102
C_CS_NA_1 = 103
C_TS_NA_1 = 104

# iletim nedenleri
COT_PERIODIC, COT_SPONTANEOUS, COT_REQUEST = 1, 3, 5
COT_ACT, COT_ACT_CON, COT_ACT_TERM = 6, 7, 10
COT_INTERROGATED = 20
COT_UNKNOWN_TYPE, COT_UNKNOWN_COT, COT_UNKNOWN_CA, COT_UNKNOWN_IOA = 44, 45, 46, 47
PN_NEGATIVE = 0x40

# U-biçimi
STARTDT_ACT, STARTDT_CON = 0x07, 0x0B
STOPDT_ACT, STOPDT_CON = 0x13, 0x23
TESTFR_ACT, TESTFR_CON = 0x43, 0x83

QDS_OV = 0x01
QDS_NT = 0x40
QDS_IV = 0x80


class FrameError(ValueError):
    pass


@dataclass(frozen=True)
class Apdu:
    kind: str  # "I" | "S" | "U"
    ns: int = 0
    nr: int = 0
    u: int = 0
    asdu: bytes = b""


def encode_i(ns: int, nr: int, asdu: bytes) -> bytes:
    if len(asdu) > MAX_ASDU:
        raise FrameError("ASDU 249 baytı aşıyor")
    ctrl = bytes([(ns & 0x7F) << 1, (ns >> 7) & 0xFF, (nr & 0x7F) << 1, (nr >> 7) & 0xFF])
    return bytes([START, 4 + len(asdu)]) + ctrl + asdu


def encode_s(nr: int) -> bytes:
    return bytes([START, 4, 0x01, 0x00, (nr & 0x7F) << 1, (nr >> 7) & 0xFF])


def encode_u(code: int) -> bytes:
    return bytes([START, 4, code, 0, 0, 0])


def decode_apdu(frame: bytes) -> Apdu:
    """Tam bir APDU'yu (0x68 dahil) çözer."""
    if len(frame) < 6 or frame[0] != START:
        raise FrameError("geçersiz başlangıç")
    if frame[1] != len(frame) - 2 or not 4 <= frame[1] <= 253:
        raise FrameError("geçersiz uzunluk")
    c1, c2, c3, c4 = frame[2:6]
    if c1 & 0x01 == 0:
        return Apdu("I", ns=(c1 >> 1) | (c2 << 7), nr=(c3 >> 1) | (c4 << 7), asdu=bytes(frame[6:]))
    if c1 & 0x03 == 0x01:
        return Apdu("S", nr=(c3 >> 1) | (c4 << 7))
    if c1 & 0x03 == 0x03:
        return Apdu("U", u=c1)
    raise FrameError("bilinmeyen kontrol alanı")


# ---------------------------------------------------------------- ASDU
@dataclass
class Asdu:
    type_id: int
    cot: int
    ca: int
    objects: list[tuple[int, bytes]] = field(default_factory=list)  # (IOA, öğe baytları)
    sq: bool = False
    negative: bool = False
    test: bool = False
    originator: int = 0

    def encode(self) -> bytes:
        n = len(self.objects)
        if n == 0 or n > 127:
            raise FrameError("nesne sayısı 1..127 olmalı")
        cot = (self.cot & 0x3F) | (PN_NEGATIVE if self.negative else 0) | (0x80 if self.test else 0)
        head = bytes([self.type_id, (0x80 if self.sq else 0) | n, cot, self.originator & 0xFF]) + self.ca.to_bytes(2, "little")
        if self.sq:
            first_ioa = self.objects[0][0]
            body = first_ioa.to_bytes(3, "little") + b"".join(e for _, e in self.objects)
        else:
            body = b"".join(ioa.to_bytes(3, "little") + e for ioa, e in self.objects)
        return head + body


_ELEMENT_LEN = {M_SP_NA_1: 1, M_ME_NB_1: 3, M_SP_TB_1: 8, C_IC_NA_1: 1, C_CI_NA_1: 1, C_RD_NA_1: 0, C_CS_NA_1: 7, C_TS_NA_1: 2}


def decode_asdu(data: bytes) -> Asdu:
    if len(data) < 6:
        raise FrameError("ASDU başlığı kısa")
    type_id, vsq, cot_b, org = data[0], data[1], data[2], data[3]
    ca = int.from_bytes(data[4:6], "little")
    sq, n = bool(vsq & 0x80), vsq & 0x7F
    asdu = Asdu(type_id, cot_b & 0x3F, ca, [], sq, bool(cot_b & PN_NEGATIVE), bool(cot_b & 0x80), org)
    elem = _ELEMENT_LEN.get(type_id)
    if elem is None:
        asdu.objects = [(0, data[6:])]  # bilinmeyen tip: ham gövde (yansıtma için)
        return asdu
    pos = 6
    if sq:
        if len(data) < pos + 3 + n * elem:
            raise FrameError("SQ=1 gövde kısa")
        base = int.from_bytes(data[pos : pos + 3], "little")
        pos += 3
        asdu.objects = [(base + i, data[pos + i * elem : pos + (i + 1) * elem]) for i in range(n)]
    else:
        step = 3 + elem
        if len(data) < pos + n * step:
            raise FrameError("SQ=0 gövde kısa")
        asdu.objects = [
            (int.from_bytes(data[pos + i * step : pos + i * step + 3], "little"), data[pos + i * step + 3 : pos + (i + 1) * step])
            for i in range(n)
        ]
    return asdu


# ---------------------------------------------------------------- öğe kodlayıcılar
def me_nb(value: int, qds: int = 0) -> bytes:
    """M_ME_NB_1 öğesi: ölçekli değer (int16 LE) + QDS."""
    return int(value).to_bytes(2, "little", signed=True) + bytes([qds & 0xFF])


def siq(state: bool, iv: bool = False) -> bytes:
    return bytes([(1 if state else 0) | (0x80 if iv else 0)])


def cp56(ts: _dt.datetime) -> bytes:
    """CP56Time2a (7 bayt), UTC, yaz saati biti 0."""
    ms = ts.second * 1000 + ts.microsecond // 1000
    return bytes(
        [ms & 0xFF, (ms >> 8) & 0xFF, ts.minute & 0x3F, ts.hour & 0x1F, (ts.isoweekday() << 5) | (ts.day & 0x1F), ts.month & 0x0F, ts.year % 100]
    )


def decode_cp56(b: bytes) -> _dt.datetime:
    if len(b) != 7:
        raise FrameError("CP56Time2a 7 bayt olmalı")
    ms = b[0] | (b[1] << 8)
    year = 2000 + (b[6] & 0x7F)
    return _dt.datetime(year, b[5] & 0x0F, b[4] & 0x1F, b[3] & 0x1F, b[2] & 0x3F, ms // 1000, (ms % 1000) * 1000, tzinfo=_dt.timezone.utc)

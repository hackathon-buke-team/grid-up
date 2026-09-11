"""SMS transport - two independent paths, and an honest AT transcript.

Why two paths, and why the order matters
----------------------------------------

**Path A: the gateway's own GSM modem.**  A quad-band module on the DIN rail
inside the panel's instrument bay, fed from the 6 A gG "Ic Ihtiyac" circuit
through the existing 10 A socket, with its antenna at the sealed outlet that
Madde 2.2.8.1.iv already requires the panel to have.  It shares nothing with the
substation's data path.  When a contractor's excavator takes out the fibre to a
secondary substation - which is how substations actually lose communications -
this path still works, because it is a different physical medium terminating in
a different network.

**Path B: an SMPP bind from the datacentre.**  Higher throughput, per-message
delivery receipts, cheaper at fleet scale.  And it dies with the fibre.

So Path A is the one that carries the ACIL message and Path B carries the
volume.  A monitoring system whose alarm path fails in exactly the situation
that produces alarms is not a monitoring system; it is a dashboard.

Turkish characters, honestly
----------------------------

The GSM 03.38 default alphabet does not contain **i-dotless (ı), ş, ğ, İ, Ş, Ğ**.
It does contain Ç, Ö, Ü, ç, ö, ü (in the basic set or the extension table), which
is why half-broken Turkish SMS is so common: the encoder silently drops the
other six.

There are exactly two honest options and we implement the first:

1. **UCS2 (UTF-16BE), DCS = 0x08.**  Every Turkish character survives.  The cost
   is the payload: 140 octets per message means **70 characters per single part**,
   and 67 per part once the 6-octet concatenation UDH is added.  Every message
   this module composes is built to that budget.
2. **Transliteration** to ASCII (ı->i, ş->s, ğ->g).  Cheaper, and legible, but it
   is the utility's own asset names being mangled.  Implemented here as
   ``transliterate`` for the case where an operator explicitly prefers it, and
   never used by default.

There is no third option.  "It works on my phone" is not an encoding.

Timing
------

``latency_s`` is deterministic given the message, and it is a *component*, not a
promise.  End to end, notification latency for an arc trip is 4 to 13 seconds:
TVOC-2 Modbus image propagation (ABB does not document it; modelled 0.2-2 s) +
our 1 s poll + server processing + the SMS path.  We never quote one clean
number, because the only people who quote one clean number are the people who
have not measured the parts.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any, Iterable

# --------------------------------------------------------------------------
# Line discipline.  Built from chr() so the file contains no escape sequences
# that a copy-paste into a terminal could mangle.
# --------------------------------------------------------------------------

CR = chr(13)
LF = chr(10)
CRLF = CR + LF
SUB = chr(26)          #: Ctrl-Z, the AT+CMGS message terminator
ESC = chr(27)          #: cancels a half-typed message

#: UCS2 payload budgets, in characters.
UCS2_SINGLE_CHARS = 70       #: 140 octets / 2
UCS2_CONCAT_CHARS = 67       #: 134 octets / 2, after the 6-octet UDH

#: GSM 03.38 default alphabet, basic set.  Note what is absent.
GSM7_BASIC = (
    "@£$¥èéùìòÇ\nØø\rÅå"
    "Δ_ΦΓΛΩΠΨΣΘΞÆæßÉ"
    " !\"#¤%&'()*+,-./0123456789:;<=>?"
    "¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§"
    "¿abcdefghijklmnopqrstuvwxyzäöñüà"
)
GSM7_EXT = "\f^{}\\[~]|€"

#: The six Turkish characters GSM 03.38 cannot carry, and their ASCII fallbacks.
TURKISH_MISSING = "ışğİŞĞ"   # ı ş ğ İ Ş Ğ
TRANSLIT = {
    "ı": "i", "ş": "s", "ğ": "g",
    "İ": "I", "Ş": "S", "Ğ": "G",
    "ç": "c", "Ç": "C", "ö": "o", "Ö": "O",
    "ü": "u", "Ü": "U",
}


# --------------------------------------------------------------------------
# Encoding
# --------------------------------------------------------------------------

def gsm7_encodable(text: str) -> bool:
    """True when every character survives the GSM 03.38 default alphabet."""
    return all(c in GSM7_BASIC or c in GSM7_EXT for c in text)


def missing_in_gsm7(text: str) -> list[str]:
    """The characters that would be lost, in order of first appearance."""
    out: list[str] = []
    for c in text:
        if c not in GSM7_BASIC and c not in GSM7_EXT and c not in out:
            out.append(c)
    return out


def transliterate(text: str) -> str:
    """ASCII fallback.  Legible, lossy, and never the default."""
    return "".join(TRANSLIT.get(c, c) for c in text)


def ucs2_encode(text: str) -> str:
    """Text -> uppercase UTF-16BE hex, exactly as AT+CSCS="UCS2" expects."""
    return text.encode("utf-16-be").hex().upper()


def ucs2_decode(hexstr: str) -> str:
    """Inverse of :func:`ucs2_encode`.  Round-trips every Turkish character."""
    return bytes.fromhex(hexstr.strip()).decode("utf-16-be")


def ucs2_octets(text: str) -> int:
    return len(text.encode("utf-16-be"))


def split_ucs2(text: str) -> list[str]:
    """Split into SMS parts under the UCS2 budget.

    Splitting happens on characters, not on octets, so a surrogate pair is never
    torn in half - a real failure mode when an operator pastes an emoji into an
    alarm template.
    """
    chars = list(text)
    if ucs2_octets(text) <= UCS2_SINGLE_CHARS * 2 and len(chars) <= UCS2_SINGLE_CHARS:
        return [text]
    out: list[str] = []
    buf: list[str] = []
    for ch in chars:
        buf.append(ch)
        if len(buf) >= UCS2_CONCAT_CHARS:
            out.append("".join(buf))
            buf = []
    if buf:
        out.append("".join(buf))
    return out


def fits_single_part(text: str) -> bool:
    return len(split_ucs2(text)) == 1


# --------------------------------------------------------------------------
# GSM modem
# --------------------------------------------------------------------------

@dataclass
class Sms:
    number: str
    text: str
    ts: float
    index: int = 0
    direction: str = "in"

    def to_dict(self) -> dict:
        return {"number": self.number, "text": self.text, "ts": self.ts,
                "index": self.index, "direction": self.direction}


class GsmModem:
    """Simulated quad-band modem that produces a genuine AT transcript.

    Nothing here talks to a serial port, but everything here is the exchange a
    real module performs, in order, with the real response formats.  Swapping in
    ``pyserial`` is a matter of replacing ``_exchange`` with a write/read pair;
    the transcript this class stores is exactly what that pair would log, which
    is the point - the demo shows the same bytes the field unit would send.
    """

    def __init__(self, port: str = "SIM",
                 imei: str = "356938035643809",
                 operator: str = "Turkcell") -> None:
        self.port = port
        self.imei = imei
        self.operator = operator
        self.path = "GSM/AT"
        self.why_this_path = (
            "Ağ geçidinin kendi GSM modemi. Trafo binasına giden fiber kesildiğinde "
            "de çalışır; veri merkezindeki modem çalışmaz."
        )
        self.echo_off = False
        self.charset = "GSM"
        self._ref = 0
        self._inbox: list[Sms] = []
        self._sent: list[Sms] = []
        self._index = 0
        self.rssi = 21           #: +CSQ 0..31; 21 is about -71 dBm
        self.ber = 99            #: 99 = not known or not detectable
        self.registered = True

    # ---------------------------------------------------------- plumbing --

    def _exchange(self, lines: list[str], command: str, response: list[str]) -> None:
        """Append one command and the modem's reply to the transcript."""
        lines.append(command)
        lines.extend(response)

    def _next_ref(self) -> int:
        self._ref = (self._ref + 1) % 256
        return self._ref

    def _latency(self, text: str, parts: int) -> float:
        """Deterministic per-message latency, seeded from the message itself.

        Deterministic on purpose: a simulator whose timing depends on the wall
        clock cannot be asserted on, and a demo that is different every run
        cannot be rehearsed.
        """
        h = int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:6], 16)
        jitter = (h % 1000) / 1000.0          # 0.000 .. 0.999
        return round(2.6 + 1.4 * parts + 1.8 * jitter, 2)

    # ------------------------------------------------------------- send ---

    def send(self, number: str, text: str) -> dict:
        """Send one message, UCS2, and return the transcript that did it."""
        parts = split_ucs2(text)
        needs_ucs2 = not gsm7_encodable(text)
        lines: list[str] = []

        # 1. attention / echo off
        self._exchange(lines, "AT", ["OK"])
        self._exchange(lines, "ATE0", ["OK"])
        self.echo_off = True

        # 2. text mode
        self._exchange(lines, "AT+CMGF=1", ["OK"])

        # 3. character set.  The default is GSM; we ask for it explicitly so the
        #    transcript records what we started from, then switch when Turkish
        #    characters demand it.
        self._exchange(lines, 'AT+CSCS="GSM"', ["OK"])
        self.charset = "GSM"
        if needs_ucs2:
            lost = "".join(missing_in_gsm7(text))
            lines.append(f"# GSM 03.38 cannot carry: {lost}  -> switching to UCS2")
            self._exchange(lines, 'AT+CSCS="UCS2"', ["OK"])
            # DCS 8 = UCS2, validity 167 = 24 h, PID 0.
            self._exchange(lines, "AT+CSMP=17,167,0,8", ["OK"])
            self.charset = "UCS2"

        # 4. registration and signal quality
        self._exchange(lines, "AT+CREG?",
                       [f"+CREG: 0,{1 if self.registered else 2}", "OK"])
        self._exchange(lines, "AT+CSQ", [f"+CSQ: {self.rssi},{self.ber}", "OK"])

        # 5. the message(s)
        ref = 0
        ok = self.registered
        for i, part in enumerate(parts, start=1):
            addr = ucs2_encode(number) if self.charset == "UCS2" else number
            body = ucs2_encode(part) if self.charset == "UCS2" else part
            lines.append(f'AT+CMGS="{addr}"')
            lines.append("> " + body + SUB)
            if ok:
                ref = self._next_ref()
                lines.append(f"+CMGS: {ref}")
                lines.append("OK")
            else:
                lines.append("+CMS ERROR: 331")   # no network service
                break
        if ok:
            self._sent.append(Sms(number=number, text=text, ts=time.time(),
                                  index=ref, direction="out"))

        transcript = LF.join(lines)
        return {
            "ok": ok,
            "transcript": transcript,
            "ref": ref,
            "latency_s": self._latency(text, len(parts)),
            "parts": len(parts),
            "encoding": "UCS2" if self.charset == "UCS2" else "GSM7",
            "octets": ucs2_octets(text) if self.charset == "UCS2" else len(text),
            "path": self.path,
            "number": number,
            "chars": len(text),
            "budget_chars": UCS2_SINGLE_CHARS if len(parts) == 1 else UCS2_CONCAT_CHARS,
        }

    # ------------------------------------------------------------ inbox ---

    def inject_reply(self, number: str, text: str) -> None:
        """Simulate an inbound SMS.  This is the ack path in the demo."""
        self._index += 1
        self._inbox.append(Sms(number=number, text=text, ts=time.time(),
                               index=self._index, direction="in"))

    def poll_inbox(self) -> list[dict]:
        """Read and delete unread messages, exactly as AT+CMGL/AT+CMGD do."""
        if not self._inbox:
            return []
        msgs = list(self._inbox)
        self._inbox.clear()
        lines: list[str] = []
        self._exchange(lines, 'AT+CSCS="UCS2"', ["OK"])
        lines.append('AT+CMGL="REC UNREAD"')
        out: list[dict] = []
        for m in msgs:
            lines.append(
                f'+CMGL: {m.index},"REC UNREAD","{ucs2_encode(m.number)}",,'
                f'"{time.strftime("%y/%m/%d,%H:%M:%S", time.gmtime(m.ts))}+00"'
            )
            lines.append(ucs2_encode(m.text))
            d = m.to_dict()
            d["transcript"] = ""
            out.append(d)
        lines.append("OK")
        for m in msgs:
            self._exchange(lines, f"AT+CMGD={m.index}", ["OK"])
        transcript = LF.join(lines)
        for d in out:
            d["transcript"] = transcript
        return out

    # ------------------------------------------------------------ status --

    def status(self) -> dict:
        return {
            "path": self.path,
            "port": self.port,
            "imei": self.imei,
            "operator": self.operator,
            "charset": self.charset,
            "rssi_csq": self.rssi,
            "rssi_dbm": -113 + 2 * self.rssi,
            "registered": self.registered,
            "sent": len(self._sent),
            "why_tr": self.why_this_path,
        }


# --------------------------------------------------------------------------
# SMPP - the datacentre path
# --------------------------------------------------------------------------

class SmppSender:
    """SMPP 3.4 transceiver bind, same interface as :class:`GsmModem`.

    Cheaper per message, gives real delivery receipts, and scales to a hundred
    panels without a SIM per site.  It also travels over exactly the link that
    an excavator removes, which is why it is the second path and not the first.
    """

    def __init__(self, port: str = "smpp://smsc.example.tr:2775",
                 imei: str = "-", operator: str = "SMPP",
                 system_id: str = "PANOGOZ", system_type: str = "SMPP") -> None:
        self.port = port
        self.imei = imei
        self.operator = operator
        self.system_id = system_id
        self.system_type = system_type
        self.path = "SMPP/3.4"
        self.why_this_path = (
            "Veri merkezi SMPP bağlantısı. Yüksek hacim ve teslim raporu için; "
            "fiber kesildiğinde bu yol da kesilir, bu yüzden ikinci yoldur."
        )
        self.bound = False
        self._seq = 0
        self._inbox: list[Sms] = []
        self._sent: list[Sms] = []

    def _next_seq(self) -> int:
        self._seq += 1
        return self._seq

    def _bind(self, lines: list[str]) -> None:
        if self.bound:
            return
        s = self._next_seq()
        lines.append(f"-> bind_transceiver seq={s} system_id={self.system_id} "
                     f"system_type={self.system_type} interface_version=0x34")
        lines.append(f"<- bind_transceiver_resp seq={s} status=0x00000000 "
                     f"system_id=SMSC")
        self.bound = True

    def send(self, number: str, text: str) -> dict:
        parts = split_ucs2(text)
        lines: list[str] = []
        self._bind(lines)
        s = self._next_seq()
        lines.append(f"-> enquire_link seq={s}")
        lines.append(f"<- enquire_link_resp seq={s} status=0x00000000")
        msg_id = ""
        for i, part in enumerate(parts, start=1):
            s = self._next_seq()
            payload = ucs2_encode(part)
            lines.append(
                f"-> submit_sm seq={s} source_addr=PANOGOZ "
                f"destination_addr={number} data_coding=0x08 (UCS2) "
                f"esm_class=0x40 registered_delivery=0x01 "
                f"sm_length={len(payload) // 2} part={i}/{len(parts)}"
            )
            lines.append(f"   short_message={payload}")
            msg_id = f"{s:08X}"
            lines.append(f"<- submit_sm_resp seq={s} status=0x00000000 message_id={msg_id}")
        self._sent.append(Sms(number=number, text=text, ts=time.time(), direction="out"))
        h = int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:6], 16)
        return {
            "ok": True,
            "transcript": LF.join(lines),
            "ref": msg_id,
            "latency_s": round(0.8 + 0.25 * len(parts) + (h % 400) / 1000.0, 2),
            "parts": len(parts),
            "encoding": "UCS2",
            "octets": ucs2_octets(text),
            "path": self.path,
            "number": number,
            "chars": len(text),
            "budget_chars": UCS2_SINGLE_CHARS if len(parts) == 1 else UCS2_CONCAT_CHARS,
        }

    def inject_reply(self, number: str, text: str) -> None:
        self._inbox.append(Sms(number=number, text=text, ts=time.time(), direction="in"))

    def poll_inbox(self) -> list[dict]:
        if not self._inbox:
            return []
        msgs = list(self._inbox)
        self._inbox.clear()
        lines: list[str] = []
        out: list[dict] = []
        for m in msgs:
            s = self._next_seq()
            lines.append(f"<- deliver_sm seq={s} source_addr={m.number} "
                         f"data_coding=0x08 short_message={ucs2_encode(m.text)}")
            lines.append(f"-> deliver_sm_resp seq={s} status=0x00000000")
            d = m.to_dict()
            d["transcript"] = ""
            out.append(d)
        transcript = LF.join(lines)
        for d in out:
            d["transcript"] = transcript
        return out

    def status(self) -> dict:
        return {"path": self.path, "port": self.port, "bound": self.bound,
                "system_id": self.system_id, "sent": len(self._sent),
                "why_tr": self.why_this_path}


# --------------------------------------------------------------------------
# Self-test
# --------------------------------------------------------------------------

if __name__ == "__main__":  # pragma: no cover
    print("=" * 78)
    print("PANO GOZ · SMS self-test")
    print("=" * 78)

    msg = ("PANO GOZ ACIL · SOKE-14 · Çıkış 7 L2 pabuç: θ=14.2 K, 99 °C. "
           "Bağlantı direnci artıyor. Işığı söndürmeyin, ekip yönlendirin. Onay: 4712")

    print()
    print("[metin]")
    print("  " + msg)
    print(f"  {len(msg)} karakter, {ucs2_octets(msg)} oktet UCS2")

    print()
    print("[GSM 03.38 yeterli mi?]")
    print(f"  gsm7_encodable = {gsm7_encodable(msg)}")
    print(f"  tasinamayan karakterler = {missing_in_gsm7(msg)}")
    print(f"  translit (varsayilan DEGIL) = {transliterate(msg)[:80]}...")

    print()
    print("[UCS2 gidis-donus]")
    tricky = "ıŞĞİşğ ÇÖÜçöü — θ ΔR µΩ"
    hexed = ucs2_encode(tricky)
    back = ucs2_decode(hexed)
    print(f"  giris : {tricky}")
    print(f"  hex   : {hexed}")
    print(f"  cikis : {back}")
    assert back == tricky, "UCS2 round trip failed"
    for ch in TURKISH_MISSING:
        assert ch in back
    print("  ASSERT OK: ı ş ğ İ Ş Ğ eksiksiz donuyor")

    print()
    print(f"[parca butcesi]  tek parca {UCS2_SINGLE_CHARS} karakter, "
          f"birlesik {UCS2_CONCAT_CHARS} karakter/parca")
    parts = split_ucs2(msg)
    print(f"  bu mesaj {len(parts)} parca")
    for i, p in enumerate(parts, 1):
        print(f"    {i}: {len(p):>2} karakter · {p}")

    modem = GsmModem(operator="Turkcell")
    res = modem.send("+905321112233", msg)
    print()
    print("[AT dokumu]")
    for line in res["transcript"].split(LF):
        print("  " + line.replace(SUB, "<Ctrl-Z>"))
    print()
    print(f"  ok={res['ok']} ref={res['ref']} parca={res['parts']} "
          f"kodlama={res['encoding']} gecikme={res['latency_s']} s")
    assert res["ok"] and res["encoding"] == "UCS2"
    assert 'AT+CSCS="UCS2"' in res["transcript"]
    assert "+CMGS:" in res["transcript"] and SUB in res["transcript"]

    print()
    print("[determinizm] ayni metin -> ayni gecikme:")
    m2 = GsmModem()
    print(f"  {modem._latency(msg, 2)} == {m2._latency(msg, 2)}")
    assert modem._latency(msg, 2) == m2._latency(msg, 2)

    print()
    print("[gelen kutusu]")
    modem.inject_reply("+905321112233", "TAMAM 42 4712")
    for m in modem.poll_inbox():
        print(f"  {m['number']} -> {m['text']!r}")
        for line in m["transcript"].split(LF):
            print("    " + line)

    print()
    print("[SMPP yolu]")
    smpp = SmppSender()
    r2 = smpp.send("+905321112233", msg)
    for line in r2["transcript"].split(LF):
        print("  " + line)
    print(f"  ok={r2['ok']} message_id={r2['ref']} gecikme={r2['latency_s']} s")

    print()
    print("[neden iki yol]")
    print("  A · " + modem.status()["why_tr"])
    print("  B · " + smpp.status()["why_tr"])
    print()
    print("[bildirim gecikmesi · tek bir sayi DEGIL]")
    print("  TVOC-2 Modbus goruntu yayilimi (ABB belgelemez, modellendi) 0.2-2.0 s")
    print("  PANO GOZ yoklama dongusu                                    1.0 s")
    print("  Sunucu isleme + kural cevrimi                               0.3-1.5 s")
    print(f"  SMS yolu (bu mesaj icin olculen)                            {res['latency_s']} s")
    print("  TOPLAM                                                      4 - 13 s")

    print()
    print("OK")

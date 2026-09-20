"""The real GSM modem path (AT commands over a serial port), tested against a fake.

What these tests prove: the PDU bytes are what 3GPP TS 23.040 says they are (one
vector is derived by hand below, independent of the encoder), the AT dialogue is in
the right order, and every failure comes back as ``ok=False`` instead of an
exception.  What they cannot prove: that a particular modem accepts the dialogue.
That needs hardware and is stated as unverified in docs/12-BILDIRIM-KANALLARI.md.
"""

from __future__ import annotations

import re
import sys
import time

import pytest

from panogoz.notify import gsm_serial as gs
from panogoz.notify.sms import UCS2_CONCAT_CHARS, ucs2_decode, ucs2_encode


class FakeModem:
    """Just enough of a Hayes modem to answer the dialogue, byte-for-byte."""

    def __init__(self, *, cmgs_error: str | None = None, prompt: bool = True,
                 inbox: list[tuple[str, str]] | None = None, registered: bool = True) -> None:
        self.cmgs_error = cmgs_error
        self.prompt = prompt
        self.inbox = list(inbox or [])
        self.registered = registered
        self.written: list[str] = []
        self.pdus: list[str] = []
        self.commands: list[str] = []
        self._out = b""
        self._pending_len: int | None = None
        self._ref = 0
        self.is_open = True
        self.timeout = 0.05

    # -- the pyserial surface the driver uses ---------------------------------
    def write(self, data: bytes) -> int:
        s = data.decode("latin-1")
        self.written.append(s)
        if self._pending_len is not None and s.endswith("\x1a"):
            self.pdus.append(s[:-1])
            self._pending_len = None
            if self.cmgs_error:
                self._say(f"+CMS ERROR: {self.cmgs_error}")
            else:
                self._ref += 1
                self._say(f"+CMGS: {self._ref}", "", "OK")
            return len(data)
        if s == "\x1b":
            self._pending_len = None
            return 1
        for cmd in filter(None, s.split("\r")):
            self._command(cmd)
        return len(data)

    @property
    def in_waiting(self) -> int:
        return len(self._out)

    def read(self, n: int = 1) -> bytes:
        chunk, self._out = self._out[:n], self._out[n:]
        return chunk

    def reset_input_buffer(self) -> None:
        self._out = b""

    def close(self) -> None:
        self.is_open = False

    # -- the modem ------------------------------------------------------------
    def _say(self, *lines: str) -> None:
        self._out += ("\r\n" + "\r\n".join(lines) + "\r\n").encode("latin-1")

    def _command(self, cmd: str) -> None:
        self.commands.append(cmd)
        if cmd in ("AT", "ATE0") or cmd.startswith(("AT+CMGF", "AT+CSCS", "AT+CMGD", "AT+CNMI")):
            self._say("OK")
        elif cmd == "AT+CPIN?":
            self._say("+CPIN: READY", "", "OK")
        elif cmd == "AT+CREG?":
            self._say(f"+CREG: 0,{1 if self.registered else 2}", "", "OK")
        elif cmd == "AT+CSQ":
            self._say("+CSQ: 21,99", "", "OK")
        elif cmd == "AT+COPS?":
            self._say('+COPS: 0,0,"Turkcell"', "", "OK")
        elif cmd.startswith("AT+CMGS="):
            self._pending_len = int(cmd.split("=")[1])
            if self.prompt:
                self._out += b"\r\n> "
        elif cmd.startswith("AT+CMGL"):
            lines = []
            for i, (num, text) in enumerate(self.inbox, start=1):
                lines.append(f'+CMGL: {i},"REC UNREAD","{ucs2_encode(num)}",,"26/09/20,14:47:00+12"')
                lines.append(ucs2_encode(text))
            self.inbox.clear()
            self._say(*lines, "", "OK")
        else:
            self._say("ERROR")


@pytest.fixture()
def modem():
    fm = FakeModem()
    return gs.SerialGsmModem("COM_TEST", serial_factory=lambda **kw: fm), fm


# ------------------------------------------------------------------ the PDU --

def test_pdu_matches_a_hand_derived_vector():
    """+905321112233, "Hi", UCS2.

    SMSC 00 | first octet 01 (SUBMIT, no validity) | MR 00 | DA length 0C (12 digits)
    | type 91 (international) | 90 53 21 11 22 33 with each pair swapped
    = 09 35 12 11 22 33 | PID 00 | DCS 08 (UCS2) | UDL 04 | 0048 0069
    TPDU length (SMSC octet excluded) = 17.
    """
    pdu, tpdu_len = gs.encode_submit_pdu("+905321112233", "Hi")
    assert pdu == "00" "01" "00" "0C" "91" "093512112233" "00" "08" "04" "00480069"
    assert tpdu_len == 17


def test_national_and_international_numbers_encode_identically():
    a = gs.encode_submit_pdu("+90 532 111 22 33", "x")
    b = gs.encode_submit_pdu("0532 111 22 33", "x")
    c = gs.encode_submit_pdu("905321112233", "x")
    assert a == b == c


def test_long_text_becomes_concatenated_parts_that_reassemble():
    text = "PANO GÖZ KRİTİK · SOKE-14 · Ç7·L2·pabuç θ=14.2K 99°C · bağlantıyı torkla · " \
           "KRITIK'e 21 g (13-32) · onay: TAMAM 1284 4712"
    assert len(text) > 70
    parts = gs.encode_submit_pdus("+905321112233", text, ref=0x2A)
    assert len(parts) == 2
    decoded = [gs.decode_submit_pdu(p[0]) for p in parts]
    assert {d["udh_ref"] for d in decoded} == {0x2A}
    assert [d["udh_seq"] for d in decoded] == [1, 2] and {d["udh_total"] for d in decoded} == {2}
    assert all(d["first_octet"] == 0x41 for d in decoded)
    assert all(len(d["text"]) <= UCS2_CONCAT_CHARS for d in decoded)
    assert "".join(d["text"] for d in decoded) == text
    for pdu, tpdu_len in parts:
        assert tpdu_len == len(pdu) // 2 - 1


def test_a_short_text_is_a_single_plain_part():
    parts = gs.encode_submit_pdus("+905321112233", "kısa mesaj")
    assert len(parts) == 1 and gs.decode_submit_pdu(parts[0][0])["first_octet"] == 0x01


def test_turkish_characters_survive_the_round_trip():
    txt = "ıŞĞİşğ ÇÖÜçöü θ"
    (pdu, _), = gs.encode_submit_pdus("+905321112233", txt)
    assert gs.decode_submit_pdu(pdu)["text"] == txt


# ------------------------------------------------------------ the dialogue --

def test_send_runs_the_dialogue_in_order(modem):
    m, fm = modem
    res = m.send("+905321112233", "PANO GÖZ test")
    assert res["ok"] is True and res["parts"] == 1 and res["ref"]
    order = [c for c in fm.commands if c.startswith(("AT+CMGF", "AT+CMGS"))]
    assert order == ["AT+CMGF=0", "AT+CMGS=" + str(len(fm.pdus[0]) // 2 - 1)]
    assert fm.written[-1].endswith("\x1a"), "PDU must end with Ctrl-Z"
    assert "AT+CMGS=" in res["transcript"] and "+CMGS:" in res["transcript"]
    assert gs.decode_submit_pdu(fm.pdus[0])["text"] == "PANO GÖZ test"


def test_long_message_sends_every_part(modem):
    m, fm = modem
    res = m.send("+905321112233", "x" * 130)
    assert res["ok"] and res["parts"] == 2 and len(fm.pdus) == 2


def test_network_refusal_is_a_failed_result(modem):
    _, fm = modem
    fm.cmgs_error = "331"
    m = gs.SerialGsmModem("COM_TEST", serial_factory=lambda **kw: fm)
    res = m.send("+905321112233", "x")
    assert res["ok"] is False and "331" in res["error"]


def test_missing_prompt_cancels_the_half_typed_message():
    fm = FakeModem(prompt=False)
    m = gs.SerialGsmModem("COM_TEST", serial_factory=lambda **kw: fm, prompt_timeout_s=0.3)
    res = m.send("+905321112233", "x")
    assert res["ok"] is False and "prompt" in res["error"].lower()
    assert "\x1b" in fm.written, "ESC must cancel a half-typed message"


def test_an_unplugged_modem_fails_softly():
    def boom(**kw):
        raise OSError("could not open port 'COM9'")

    m = gs.SerialGsmModem("COM9", serial_factory=boom)
    res = m.send("+905321112233", "x")
    assert res["ok"] is False and "COM9" in res["error"]
    assert m.status()["ok"] is False


def test_missing_pyserial_names_the_fix(monkeypatch):
    monkeypatch.setitem(sys.modules, "serial", None)
    res = gs.SerialGsmModem("COM5").send("+905321112233", "x")
    assert res["ok"] is False and "pyserial" in res["error"]


def test_sim_pin_is_entered_when_asked_for():
    class PinModem(FakeModem):
        def _command(self, cmd):
            if cmd == "AT+CPIN?":
                self.commands.append(cmd)
                self._say("+CPIN: SIM PIN", "", "OK")
            elif cmd.startswith("AT+CPIN="):
                self.commands.append(cmd)
                self._say("OK")
            else:
                super()._command(cmd)

    fm = PinModem()
    m = gs.SerialGsmModem("COM_TEST", serial_factory=lambda **kw: fm, sim_pin="1234")
    assert m.send("+905321112233", "x")["ok"]
    assert 'AT+CPIN="1234"' in fm.commands


# ------------------------------------------------------------------- inbox --

def test_inbox_is_decoded_and_deleted():
    fm = FakeModem(inbox=[("+905321112233", "TAMAM 42 4712")])
    m = gs.SerialGsmModem("COM_TEST", serial_factory=lambda **kw: fm)
    msgs = m.poll_inbox()
    assert len(msgs) == 1
    assert msgs[0]["number"] == "+905321112233" and msgs[0]["text"] == "TAMAM 42 4712"
    assert "AT+CMGD=1" in fm.commands
    assert m.poll_inbox() == []


def test_empty_inbox_is_quiet():
    fm = FakeModem()
    m = gs.SerialGsmModem("COM_TEST", serial_factory=lambda **kw: fm)
    assert m.poll_inbox() == []


# ------------------------------------------------------------------ status --

def test_status_reads_signal_and_operator_and_is_cached(modem):
    m, fm = modem
    st = m.status()
    assert st["ok"] and st["registered"] is True
    assert st["rssi_csq"] == 21 and st["rssi_dbm"] == -71
    assert st["operator"] == "Turkcell" and st["simulated"] is False
    n = fm.commands.count("AT+CSQ")
    m.status()
    assert fm.commands.count("AT+CSQ") == n, "status must not hammer the serial port"


def test_status_is_not_blocked_by_a_send_in_progress(modem):
    """The runtime asks for status on every detector pass; it must never queue
    behind a send that is holding the port."""
    m, fm = modem
    m.status()                                   # populate the cache
    assert m._io.acquire(timeout=1)              # simulate a send holding the port
    try:
        t0 = time.time()
        st = m.status()
        assert time.time() - t0 < 0.5 and st["ok"]
    finally:
        m._io.release()

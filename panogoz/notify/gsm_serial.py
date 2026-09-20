"""A real GSM modem on a serial port - the path ``sms.GsmModem`` only pretends to be.

``sms.GsmModem`` writes the AT transcript a modem would produce and sends nothing.
This class produces the same dialogue **and puts it on a wire**.  Same interface
(``send`` / ``poll_inbox`` / ``status``), so the escalation ladder cannot tell the
difference - the point of the simulator was always that swapping this in would be
a change of one object.

Why PDU mode, not text mode
---------------------------

Turkish alarm text needs UCS2 (``sms.py``: GSM 03.38 has no ı ş ğ İ Ş Ğ).  UCS2
gives 70 characters per message, and the composer's budget is two *concatenated*
parts of 67.  Concatenation needs a User Data Header, and text mode cannot carry
one; only PDU mode can.  So sending is PDU mode (``AT+CMGF=0``) and every message
is UCS2, always: a single encoding means a single behaviour to reason about.
Reading replies is text mode with ``AT+CSCS="UCS2"``, exactly as the simulator's
transcript shows, because replies are short ("TAMAM 42 4712") and never split.

Robustness rules
----------------

* One lock around the port.  Two AT dialogues interleaved on one wire corrupt each
  other, so ``send`` and ``poll_inbox`` serialise.
* ``status()`` never waits for that lock.  The runtime asks for status on every
  detector pass, and a send can hold the port for seconds; ``status`` serves a
  cached answer (refreshed at most every 30 s) instead of queueing behind it.
* The port opens lazily.  A modem that is unplugged at start-up must not stop the
  system booting; ``status()`` says so and each send fails softly.
* Nothing raises out of ``send``/``poll_inbox``: every failure is ``ok=False`` with
  an ``error`` and a transcript, because the escalation ladder repeats an
  unacknowledged KRITIK every five minutes and a raised exception would only
  break the loop that does the repeating.
* A missing ``>`` prompt sends ESC (0x1B) so a half-typed message is cancelled
  instead of being glued onto the next one.

What is NOT verified: this driver has been exercised against a fake modem that
answers the dialogue byte-for-byte (``tests/test_gsm_serial.py``).  No physical
modem has been connected.  Modems differ in small ways (echo, prompt timing, SMSC
handling); ``python -m panogoz.notify.gsm_serial --probe COM5`` is the first thing
to run on real hardware.
"""

from __future__ import annotations

import re
import threading
import time
from typing import Any, Callable

from panogoz.notify.sms import (
    UCS2_CONCAT_CHARS, UCS2_SINGLE_CHARS, split_ucs2, ucs2_decode, ucs2_encode, ucs2_octets,
)

CTRL_Z = "\x1a"
ESC = "\x1b"

_FINAL = re.compile(r"(?:^|\r\n)(OK|ERROR|\+CME ERROR:[^\r\n]*|\+CMS ERROR:[^\r\n]*)\r\n")
_STATUS_CACHE_S = 30.0


class ModemError(RuntimeError):
    """The modem answered, and the answer was an error."""


# --------------------------------------------------------------------------
# PDU (3GPP TS 23.040, SMS-SUBMIT)
# --------------------------------------------------------------------------

def _address(number: str) -> tuple[int, str, int]:
    """``(type-of-address, swapped semi-octets, digit count)`` for a destination."""
    digits = re.sub(r"\D", "", number or "")
    if digits.startswith("0") and len(digits) == 11:        # 0532 111 22 33
        digits = "90" + digits[1:]
    if not 5 <= len(digits) <= 15:
        raise ValueError(f"gecersiz telefon numarasi: {number!r}")
    padded = digits + ("F" if len(digits) % 2 else "")
    swapped = "".join(padded[i + 1] + padded[i] for i in range(0, len(padded), 2))
    return 0x91, swapped, len(digits)                       # 0x91 = international


def encode_submit_pdu(number: str, text: str, *, ref: int = 0, part: int = 1,
                      total: int = 1) -> tuple[str, int]:
    """One SMS-SUBMIT PDU (UCS2) as upper-case hex, and the length ``AT+CMGS`` wants.

    The SMSC field is ``00`` (use the SIM's SMSC), so the reported length excludes
    that leading octet, as the standard requires.
    """
    toa, addr, ndigits = _address(number)
    body = text.encode("utf-16-be")
    if total > 1:
        udh = bytes([0x05, 0x00, 0x03, ref & 0xFF, total, part])
        first = 0x41                                        # SUBMIT + UDHI
        ud = udh + body
    else:
        first = 0x01
        ud = body
    if len(ud) > 140:
        raise ValueError(f"UCS2 parca 140 oktetten buyuk: {len(ud)}")
    tpdu = (f"{first:02X}" "00" f"{ndigits:02X}{toa:02X}{addr}" "00" "08"
            f"{len(ud):02X}" + ud.hex().upper())
    return "00" + tpdu, len(tpdu) // 2


def encode_submit_pdus(number: str, text: str, ref: int | None = None) -> list[tuple[str, int]]:
    """Split with the composer's own 70/67 budget and encode each part."""
    parts = split_ucs2(text)
    ref = 0 if ref is None else ref
    if len(parts) == 1:
        return [encode_submit_pdu(number, parts[0])]
    return [encode_submit_pdu(number, p, ref=ref, part=i, total=len(parts))
            for i, p in enumerate(parts, start=1)]


def decode_submit_pdu(pdu_hex: str) -> dict:
    """Inverse of :func:`encode_submit_pdu` - for tests and for the transcript."""
    b = bytes.fromhex(pdu_hex)
    i = 1 + b[0]                                            # skip SMSC
    first = b[i]; i += 2                                    # first octet, MR
    n = b[i]; i += 1
    toa = b[i]; i += 1
    alen = (n + 1) // 2
    swapped = b[i:i + alen].hex().upper(); i += alen
    digits = "".join(swapped[k + 1] + swapped[k] for k in range(0, len(swapped), 2)).rstrip("F")
    i += 1                                                  # PID
    dcs = b[i]; i += 1
    udl = b[i]; i += 1
    ud = b[i:i + udl]
    out: dict[str, Any] = {"first_octet": first, "number": ("+" if toa == 0x91 else "") + digits,
                           "dcs": dcs, "udl": udl}
    if first & 0x40:
        hl = ud[0]
        udh = ud[1:1 + hl]
        out.update(udh_ref=udh[2], udh_total=udh[3], udh_seq=udh[4])
        ud = ud[1 + hl:]
    out["text"] = ud.decode("utf-16-be")
    return out


# --------------------------------------------------------------------------
# The modem
# --------------------------------------------------------------------------

def _default_factory(**kw: Any) -> Any:
    try:
        import serial  # type: ignore[import-not-found]
    except ImportError as exc:
        raise ImportError("pyserial kurulu degil: python -m pip install pyserial") from exc
    return serial.Serial(**kw)


class SerialGsmModem:
    """AT-command modem on ``port``.  Drop-in for :class:`panogoz.notify.sms.GsmModem`."""

    simulated = False
    path = "GSM/AT (seri)"

    def __init__(self, port: str, *, baud: int = 115200, sim_pin: str | None = None,
                 serial_factory: Callable[..., Any] | None = None,
                 prompt_timeout_s: float = 8.0, send_timeout_s: float = 60.0,
                 command_timeout_s: float = 5.0) -> None:
        self.port = port
        self.baud = baud
        self.sim_pin = sim_pin
        self._factory = serial_factory or _default_factory
        self.prompt_timeout_s = prompt_timeout_s
        self.send_timeout_s = send_timeout_s
        self.command_timeout_s = command_timeout_s
        self.why_this_path = (
            "Ağ geçidinin kendi GSM modemi, seri portta. Trafo binasına giden fiber "
            "kesildiğinde de çalışır; veri merkezindeki bir yol çalışmaz.")
        self._io = threading.Lock()
        self._port: Any = None
        self._ref = 0
        self._status: dict | None = None
        self._status_at = 0.0
        self.sent = 0

    def __repr__(self) -> str:
        return f"SerialGsmModem(port={self.port!r})"

    # ------------------------------------------------------------ plumbing --

    def _ensure_port(self) -> Any:
        if self._port is None or not getattr(self._port, "is_open", True):
            self._port = self._factory(port=self.port, baudrate=self.baud, timeout=0.2)
        return self._port

    def _drop_port(self) -> None:
        try:
            if self._port is not None:
                self._port.close()
        except Exception:  # noqa: BLE001
            pass
        self._port = None

    @staticmethod
    def _read_until(port: Any, done: Callable[[str], bool], timeout: float) -> str:
        buf = b""
        end = time.time() + timeout
        while time.time() < end:
            chunk = port.read(getattr(port, "in_waiting", 0) or 1)
            if chunk:
                buf += chunk
                text = buf.decode("latin-1")
                if done(text):
                    return text
            else:
                time.sleep(0.005)
        raise TimeoutError(f"modem yanit vermedi ({timeout:.0f} s): {buf.decode('latin-1')!r}")

    def _cmd(self, port: Any, cmd: str, lines: list[str], timeout: float | None = None) -> str:
        port.write((cmd + "\r").encode("latin-1"))
        resp = self._read_until(port, lambda t: bool(_FINAL.search(t)),
                                timeout or self.command_timeout_s)
        lines.append(cmd)
        lines.extend(x for x in resp.replace("\r", "").split("\n") if x.strip())
        m = _FINAL.search(resp)
        if m and m.group(1) != "OK":
            raise ModemError(m.group(1))
        return resp

    def _prepare(self, port: Any, lines: list[str], text_mode: bool = False) -> None:
        self._cmd(port, "AT", lines)
        self._cmd(port, "ATE0", lines)
        resp = self._cmd(port, "AT+CPIN?", lines)
        if "SIM PIN" in resp:
            if not self.sim_pin:
                raise ModemError("SIM PIN isteniyor ve sim_pin ayarlanmamis")
            self._cmd(port, f'AT+CPIN="{self.sim_pin}"', lines)
        if text_mode:
            self._cmd(port, "AT+CMGF=1", lines)
            self._cmd(port, 'AT+CSCS="UCS2"', lines)
        else:
            self._cmd(port, "AT+CMGF=0", lines)

    def _send_pdu(self, port: Any, pdu: str, tpdu_len: int, lines: list[str]) -> str:
        cmd = f"AT+CMGS={tpdu_len}"
        port.write((cmd + "\r").encode("latin-1"))
        try:
            self._read_until(port, lambda t: "> " in t or bool(_FINAL.search(t)),
                             self.prompt_timeout_s)
        except TimeoutError as exc:
            port.write(ESC.encode("latin-1"))
            raise ModemError("modemden '>' istemi (prompt) gelmedi") from exc
        lines.append(cmd)
        lines.append("> " + pdu + "<Ctrl-Z>")
        port.write((pdu + CTRL_Z).encode("latin-1"))
        resp = self._read_until(port, lambda t: bool(_FINAL.search(t)), self.send_timeout_s)
        m = _FINAL.search(resp)
        lines.extend(x for x in resp.replace("\r", "").split("\n") if x.strip())
        if m and m.group(1) != "OK":
            raise ModemError(m.group(1))
        ref = re.search(r"\+CMGS:\s*(\d+)", resp)
        return ref.group(1) if ref else ""

    # ---------------------------------------------------------------- send --

    def send(self, number: str, text: str) -> dict:
        t0 = time.time()
        lines: list[str] = []
        self._ref = (self._ref + 1) & 0xFF
        ref, error = "", None
        parts: list[tuple[str, int]] = []
        try:
            parts = encode_submit_pdus(number, text, ref=self._ref)
            with self._io:
                try:
                    port = self._ensure_port()
                    self._prepare(port, lines)
                    for pdu, n in parts:
                        ref = self._send_pdu(port, pdu, n, lines)
                except Exception:
                    self._drop_port()
                    raise
        except Exception as exc:  # noqa: BLE001 - see module docstring: never raise
            error = str(exc) or type(exc).__name__
            lines.append(f"# HATA: {error}")
        ok = error is None
        if ok:
            self.sent += 1
        return {
            "ok": ok, "error": error, "transcript": "\n".join(lines), "ref": ref,
            "latency_s": round(time.time() - t0, 2), "parts": len(parts), "encoding": "UCS2",
            "octets": ucs2_octets(text), "path": self.path, "number": number,
            "chars": len(text),
            "budget_chars": UCS2_SINGLE_CHARS if len(parts) <= 1 else UCS2_CONCAT_CHARS,
        }

    # --------------------------------------------------------------- inbox --

    def poll_inbox(self) -> list[dict]:
        """Read and delete unread messages.  ``[]`` on any failure (see status)."""
        lines: list[str] = []
        out: list[dict] = []
        try:
            with self._io:
                try:
                    port = self._ensure_port()
                    self._prepare(port, lines, text_mode=True)
                    resp = self._cmd(port, 'AT+CMGL="REC UNREAD"', lines)
                    rows = resp.replace("\r", "").split("\n")
                    seen: list[int] = []
                    for k, row in enumerate(rows):
                        h = re.match(r'\+CMGL:\s*(\d+),"[^"]*","([0-9A-Fa-f]*)"', row)
                        if not h or k + 1 >= len(rows):
                            continue
                        idx = int(h.group(1))
                        seen.append(idx)
                        out.append({"number": _hex_text(h.group(2)), "text": _hex_text(rows[k + 1]),
                                    "ts": time.time(), "index": idx, "direction": "in"})
                    for idx in seen:
                        self._cmd(port, f"AT+CMGD={idx}", lines)
                except Exception:
                    self._drop_port()
                    raise
        except Exception as exc:  # noqa: BLE001
            self._status = {**(self._status or {}), "ok": False, "error": str(exc)}
            return []
        transcript = "\n".join(lines)
        for d in out:
            d["transcript"] = transcript
        return out

    # -------------------------------------------------------------- status --

    def status(self) -> dict:
        now = time.time()
        if self._status is not None and now - self._status_at < _STATUS_CACHE_S:
            return dict(self._status)
        if not self._io.acquire(blocking=False):            # a send holds the port
            return dict(self._status or self._blank(error="modem mesgul"))
        try:
            lines: list[str] = []
            try:
                port = self._ensure_port()
                self._cmd(port, "AT", lines)
                self._cmd(port, "ATE0", lines)
                reg = self._cmd(port, "AT+CREG?", lines)
                csq = self._cmd(port, "AT+CSQ", lines)
                cops = self._cmd(port, "AT+COPS?", lines)
                r = re.search(r"\+CREG:\s*\d+,(\d+)", reg)
                q = re.search(r"\+CSQ:\s*(\d+),(\d+)", csq)
                o = re.search(r'\+COPS:\s*\d+,\d+,"([^"]*)"', cops)
                rssi = int(q.group(1)) if q else 99
                st = self._blank()
                st.update(ok=True, registered=bool(r and r.group(1) in ("1", "5")),
                          rssi_csq=rssi, rssi_dbm=(-113 + 2 * rssi) if rssi != 99 else None,
                          operator=o.group(1) if o else "", error=None)
            except Exception as exc:  # noqa: BLE001
                self._drop_port()
                st = self._blank(error=str(exc) or type(exc).__name__)
            self._status, self._status_at = st, now
            return dict(st)
        finally:
            self._io.release()

    def _blank(self, error: str | None = None) -> dict:
        return {"path": self.path, "port": self.port, "ok": False, "registered": False,
                "rssi_csq": None, "rssi_dbm": None, "operator": "", "simulated": False,
                "sent": self.sent, "error": error, "why_tr": self.why_this_path}


def _hex_text(s: str) -> str:
    """UCS2 hex -> text; anything that is not UCS2 hex is returned as it came."""
    s = s.strip()
    try:
        return ucs2_decode(s) if s and len(s) % 4 == 0 else s
    except (ValueError, UnicodeDecodeError):
        return s


# --------------------------------------------------------------------------
# Hardware smoke test:  python -m panogoz.notify.gsm_serial --probe COM5
# --------------------------------------------------------------------------

def _main(argv: list[str] | None = None) -> int:  # pragma: no cover - needs hardware
    import argparse
    import json

    ap = argparse.ArgumentParser(description="PANO GOZ GSM modem yoklama araci")
    ap.add_argument("--list", action="store_true", help="seri portlari listele")
    ap.add_argument("--probe", metavar="PORT", help="modemi sorgula (SMS GONDERMEZ)")
    ap.add_argument("--send", nargs=3, metavar=("PORT", "NUMARA", "METIN"),
                    help="GERCEK bir SMS gonderir (operator ucretlendirir)")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--pin", default=None, help="SIM PIN")
    a = ap.parse_args(argv)
    if a.list:
        try:
            from serial.tools import list_ports  # type: ignore[import-not-found]
        except ImportError:
            print("pyserial kurulu degil: python -m pip install pyserial")
            return 2
        for p in list_ports.comports():
            print(f"{p.device:<8} {p.description}")
        return 0
    if a.probe:
        m = SerialGsmModem(a.probe, baud=a.baud, sim_pin=a.pin)
        print(json.dumps(m.status(), indent=2, ensure_ascii=False))
        return 0
    if a.send:
        port, number, text = a.send
        m = SerialGsmModem(port, baud=a.baud, sim_pin=a.pin)
        res = m.send(number, text)
        print(res["transcript"])
        print(f"\nok={res['ok']} parca={res['parts']} sure={res['latency_s']} s "
              f"{'HATA: ' + res['error'] if res['error'] else ''}")
        return 0 if res["ok"] else 1
    ap.print_help()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_main())

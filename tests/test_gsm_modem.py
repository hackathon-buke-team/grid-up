"""K4 4.1: on-prem GSM modem SMS kanalı -- AT protokol akışı SAHTE seri portla (gerçek modem yok)."""
import pytest

from panogoz.notify.escalation import Recipient, RoutedDispatcher
from panogoz.notify.gsm_modem import SMS_MAX_CHARS, GsmModemChannel, ModemError, sms_safe


class FakeModem:
    """AT komutlarına yanıt veren minimal modem: gönderilen her şeyi kaydeder."""

    def __init__(self, *, sim_pin_required=False, cms_error=None, silent=False):
        self.written: list[bytes] = []
        self._queue = b""
        self.closed = False
        self.sim_pin_required = sim_pin_required
        self.cms_error = cms_error
        self.silent = silent

    def write(self, data: bytes):
        self.written.append(data)
        if self.silent:
            return
        cmd = data.decode("ascii", "replace")
        if cmd.startswith("AT+CPIN?"):
            self._queue += b"\r\n+CPIN: SIM PIN\r\n\r\nOK\r\n" if self.sim_pin_required else b"\r\n+CPIN: READY\r\n\r\nOK\r\n"
        elif cmd.startswith("AT+CMGS="):
            self._queue += b"\r\n> "
        elif data.endswith(b"\x1a"):
            self._queue += (
                f"\r\n+CMS ERROR: {self.cms_error}\r\n".encode() if self.cms_error else b"\r\n+CMGS: 42\r\n\r\nOK\r\n"
            )
        else:
            self._queue += b"\r\nOK\r\n"

    def read_until(self, expected: bytes = b"\n") -> bytes:
        if not self._queue:
            return b""
        idx = self._queue.find(expected)
        if idx == -1:
            out, self._queue = self._queue, b""
            return out
        cut = idx + len(expected)
        out, self._queue = self._queue[:cut], self._queue[cut:]
        return out

    def close(self):
        self.closed = True


def channel(modem, **kw):
    return GsmModemChannel(serial_factory=lambda: modem, timeout_s=kw.pop("timeout_s", 2.0), **kw)


def test_sms_safe_folds_turkish_characters_and_specials_to_ascii():
    text = "[KRİTİK] F02 — Gevşek cıvatalı bağlantı (θ) · 45.2 K"
    out = sms_safe(text)
    assert out == "[KRITIK] F02 - Gevsek civatali baglanti (theta) | 45.2 K"
    assert all(ord(c) < 127 for c in out)


def test_sms_safe_truncates_to_single_part_sms():
    out = sms_safe("a" * 300)
    assert len(out) == SMS_MAX_CHARS and out.endswith("...")
    assert sms_safe("kısa mesaj") == "kisa mesaj"


def test_send_follows_at_command_sequence_and_returns_message_reference():
    modem = FakeModem()
    ref = channel(modem).send("+905551112233", "[ALARM] F02 faz L2\nOnay: ONAY F02-0001 4271")
    cmds = [w.decode() for w in modem.written]
    assert cmds[0] == "AT\r" and cmds[1] == "AT+CMGF=1\r" and cmds[2] == 'AT+CMGS="+905551112233"\r'
    assert cmds[3].endswith("\x1a") and "ONAY F02-0001 4271" in cmds[3]  # gövde Ctrl-Z ile biter
    assert ref == "42" and modem.closed


def test_send_unlocks_sim_pin_only_when_required():
    locked = FakeModem(sim_pin_required=True)
    channel(locked, pin="1234").send("+905551112233", "x")
    assert any(w.startswith(b'AT+CPIN="1234"') for w in locked.written)
    ready = FakeModem(sim_pin_required=False)
    channel(ready, pin="1234").send("+905551112233", "x")
    assert not any(w.startswith(b'AT+CPIN="') for w in ready.written)


def test_modem_error_is_raised_and_port_is_closed():
    modem = FakeModem(cms_error=330)  # SMSC adresi bilinmiyor
    with pytest.raises(ModemError, match="330"):
        channel(modem).send("+905551112233", "x")
    assert modem.closed


def test_silent_modem_times_out_instead_of_hanging():
    modem = FakeModem(silent=True)
    with pytest.raises(TimeoutError):
        channel(modem, timeout_s=0.05).send("+905551112233", "x")
    assert modem.closed


@pytest.mark.parametrize("bad", ["05551112233", "+90 555 111", "+90abc", ""])
def test_phone_number_must_be_international_format(bad):
    with pytest.raises(ValueError, match="uluslararası"):
        channel(FakeModem()).send(bad, "x")


def test_sms_route_plugs_into_escalation_dispatcher():
    modem = FakeModem()
    ch = channel(modem)
    d = RoutedDispatcher({"sms": lambda r, t: ch.send(r.address, t)})
    d.deliver(Recipient("Ayşe", "saha nöbetçisi", "sms", "+905551112233"), "[ALARM] F02")
    assert any(b"[ALARM] F02" in w for w in modem.written)

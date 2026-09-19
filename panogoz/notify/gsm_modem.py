"""On-prem SMS kanalı: yerel GSM modem, AT komutlarıyla (3GPP TS 27.005 metin modu).

Neden: Telegram/WhatsApp mesajı sağlayıcının bulutundan geçer; şartname "Public Cloud
yok" diyor. Yerel bir GSM modem (USB/RS-232) mesajı doğrudan operatör şebekesine
verir -- bizim tarafımızda hiçbir bulut hizmeti yoktur (docs/12-BILDIRIM-ESKALASYON.md §2).

DÜRÜSTLÜK: bu ortamda gerçek modem yok. AT protokol akışı (sıra, prompt, Ctrl-Z, hata
kodları) sahte bir seri portla testlenmiştir (tests/test_gsm_modem.py); gerçek cihazda
henüz çalıştırılmadı. `serial_factory=None` ise pyserial (`pip install pyserial`) kullanılır.

SMS 7-bit GSM alfabesiyle 160 karakterdir; Türkçe karakterler (ç ğ ı ö ş ü) alfabede
yoktur, bu yüzden ASCII'ye katlanır ve tek parça SMS'e sığdırılır.
"""
from __future__ import annotations

import time
from typing import Callable, Protocol

SMS_MAX_CHARS = 160

_FOLD = str.maketrans(
    {
        "ç": "c", "Ç": "C", "ğ": "g", "Ğ": "G", "ı": "i", "İ": "I", "ö": "o", "Ö": "O",
        "ş": "s", "Ş": "S", "ü": "u", "Ü": "U", "θ": "theta", "×": "x", "°": " derece",
        "—": "-", "–": "-", "·": "|", "…": "...", "’": "'", "“": '"', "”": '"',
    }
)


def sms_safe(text: str, limit: int = SMS_MAX_CHARS) -> str:
    """Türkçe/özel karakterleri ASCII'ye katlar, tek parça SMS'e (160) keser."""
    folded = text.translate(_FOLD)
    folded = "".join(ch if (ch == "\n" or 32 <= ord(ch) < 127) else "?" for ch in folded)
    if len(folded) <= limit:
        return folded
    return folded[: limit - 3].rstrip() + "..."


class ModemError(RuntimeError):
    pass


class SerialLike(Protocol):
    def write(self, data: bytes) -> object: ...
    def read_until(self, expected: bytes = b"\n") -> bytes: ...
    def close(self) -> None: ...


class GsmModemChannel:
    """`send(to, text)` -> mesaj referansı (+CMGS: <mr>)."""

    def __init__(
        self,
        port: str = "COM3",
        baud: int = 115200,
        *,
        pin: str | None = None,
        timeout_s: float = 20.0,
        serial_factory: Callable[[], SerialLike] | None = None,
    ) -> None:
        self.port, self.baud, self.pin, self.timeout_s = port, baud, pin, timeout_s
        self._factory = serial_factory or self._default_factory

    def _default_factory(self) -> SerialLike:
        import serial  # pyserial

        return serial.Serial(self.port, self.baud, timeout=2)

    def _exchange(self, ser: SerialLike, command: bytes, *, until: bytes = b"\n", ok: tuple[bytes, ...] = (b"OK",)) -> str:
        ser.write(command)
        buf = b""
        deadline = time.monotonic() + self.timeout_s
        while time.monotonic() < deadline:
            chunk = ser.read_until(until)
            buf += chunk
            if b"ERROR" in buf:  # "ERROR" ve "+CMS ERROR: n"
                raise ModemError(buf.decode("ascii", "replace").strip())
            if any(token in buf for token in ok):
                return buf.decode("ascii", "replace")
            if not chunk:
                time.sleep(0.01)
        raise TimeoutError(f"modem yanıt vermedi: {command[:20]!r}")

    def send(self, to: str, text: str) -> str:
        if not to.startswith("+") or not to[1:].isdigit():
            raise ValueError("telefon numarası uluslararası biçimde olmalı (+90...)")
        ser = self._factory()
        try:
            self._exchange(ser, b"AT\r")
            if self.pin:
                status = self._exchange(ser, b"AT+CPIN?\r")
                if "SIM PIN" in status:
                    self._exchange(ser, f'AT+CPIN="{self.pin}"\r'.encode("ascii"))
            self._exchange(ser, b"AT+CMGF=1\r")
            self._exchange(ser, f'AT+CMGS="{to}"\r'.encode("ascii"), until=b"> ", ok=(b">",))
            reply = self._exchange(ser, sms_safe(text).encode("ascii") + b"\x1a", ok=(b"+CMGS:",))
            for line in reply.splitlines():
                if line.startswith("+CMGS:"):
                    return line.split(":", 1)[1].strip()
            return ""
        finally:
            ser.close()

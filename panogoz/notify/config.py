"""Notification configuration: the rota, the bot, the modem, the public address.

Where secrets may live
----------------------

The Telegram bot token, the field-app PINs and the SIM PIN are credentials.  They
live in **one git-ignored file** (``notify.local.json``) or in environment
variables, and nowhere else: not in a default, not in ``repr``, not in an error
message, not in a notification row, not in ``/api/notify/status``.  The repository
ships ``notify.example.json`` with placeholders only.

Live channels are opt-in per process
------------------------------------

``load()`` is only called for a process that asked for live channels:
``run_local`` sets ``PANOGOZ_NOTIFY_LIVE=1`` and nothing else does
(``factory.live_requested``).  A test, a benchmark or a helper script gets
``defaults()`` - simulated modem, no Telegram - even when ``notify.local.json``
exists on that machine, so a test run can never message a real phone.

Search order
------------

1. ``PANOGOZ_NOTIFY_CONFIG`` (a path; must exist),
2. ``notify.local.json`` in the repository root (optional),
3. the built-in demo defaults - the simulated modem, no Telegram, the three-person
   demo rota with **random per-start PINs**.

Then the environment overrides individual values: ``PANOGOZ_TELEGRAM_TOKEN``,
``PANOGOZ_TELEGRAM_API``, ``PANOGOZ_TELEGRAM_PRIVACY``, ``PANOGOZ_PUBLIC_URL``,
``PANOGOZ_SMS_PROVIDER`` and ``PANOGOZ_SMS_PORT``.

Field-app PINs
--------------

A rota member without a ``pin`` is given a random four-digit one at every start;
``generated_pins`` carries them so the launcher can print them **once, to the
console** - never to an API.  Four digits is a convenience lock for a phone on the
substation LAN, protected by lock-out (``saha.py``), not a password.
"""

from __future__ import annotations

import json
import os
import re
import secrets
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from panogoz.notify.escalation import DEFAULT_ROTA

DEFAULT_API = "https://api.telegram.org"
ROOT = Path(__file__).resolve().parents[2]
LOCAL_PATH = ROOT / "notify.local.json"
EXAMPLE_PATH = ROOT / "notify.example.json"

_PLACEHOLDER_SUFFIX = "DEGISTIR"
_PIN_RE = re.compile(r"^\d{4,8}$")


class ConfigError(ValueError):
    """A configuration problem, named by field.  Never contains a secret value."""


@dataclass(repr=False)
class NotifyConfig:
    public_url: str | None
    rota: list[dict]
    telegram: dict | None
    sms: dict
    source: str
    generated_pins: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def __repr__(self) -> str:                      # deliberately secret-free
        return (f"NotifyConfig(source={self.source!r}, telegram={'on' if self.telegram else 'off'}, "
                f"sms={self.sms.get('provider')}, rota={len(self.rota)}, "
                f"public_url={self.public_url!r})")


# --------------------------------------------------------------------------

def load(path: str | None = None, env: Mapping[str, str] | None = None) -> NotifyConfig:
    env = os.environ if env is None else env
    data: dict[str, Any] = {}
    source = "varsayilan"

    explicit = env.get("PANOGOZ_NOTIFY_CONFIG")
    candidate = path or explicit
    if candidate:
        p = Path(candidate)
        if p.exists():
            data, source = _read(p), str(p)
        elif explicit and not path:
            raise ConfigError(f"PANOGOZ_NOTIFY_CONFIG dosyasi yok: {explicit}")
    elif LOCAL_PATH.exists():
        data, source = _read(LOCAL_PATH), str(LOCAL_PATH)

    return _build(data, env, source)


def defaults() -> NotifyConfig:
    """The safe demo configuration: simulated modem, no Telegram, demo rota.

    Reads neither the config file nor the environment.  This is what a process
    gets unless it asked for live channels (see ``factory.live_requested``), so a
    test run or a helper script can never message a real phone because a developer
    happens to have ``notify.local.json`` on their machine.
    """
    return _build({}, {}, "varsayilan")


def _build(data: dict, env: Mapping[str, str], source: str) -> NotifyConfig:
    warnings: list[str] = []
    public_url = _url(env.get("PANOGOZ_PUBLIC_URL") or data.get("public_url"))
    telegram = _telegram(data.get("telegram"), env, warnings)
    sms = _sms(data.get("sms"), env)
    rota, generated = _rota(data.get("rota"))
    return NotifyConfig(public_url=public_url, rota=rota, telegram=telegram, sms=sms,
                        source=source, generated_pins=generated, warnings=warnings)


def _read(p: Path) -> dict:
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigError(f"{p.name}: gecerli JSON degil ({exc.msg}, satir {exc.lineno})") from exc
    if not isinstance(raw, dict):
        raise ConfigError(f"{p.name}: JSON bir nesne olmali")
    return {k: v for k, v in raw.items() if not str(k).startswith("_")}   # "_aciklama" = comment


def _url(value: Any) -> str | None:
    if value in (None, ""):
        return None
    v = str(value).strip().rstrip("/")
    if not re.match(r"^https?://[^\s/]+", v):
        raise ConfigError("public_url http:// veya https:// ile baslamali")
    return v


def _telegram(section: Any, env: Mapping[str, str], warnings: list[str]) -> dict | None:
    sec = dict(section) if isinstance(section, dict) else {}
    token = env.get("PANOGOZ_TELEGRAM_TOKEN") or sec.get("token")
    if not token:
        return None
    token = str(token).strip()
    if str(token).endswith(_PLACEHOLDER_SUFFIX):
        warnings.append("telegram.token ornek degerde; Telegram kapali")
        return None
    if not re.match(r"^\d+:[\w-]+$", token):
        raise ConfigError("telegram.token bicimi 'sayilar:harfler' olmali (BotFather verir)")
    privacy = env.get("PANOGOZ_TELEGRAM_PRIVACY") or sec.get("privacy") or "minimal"
    if privacy not in ("minimal", "standard"):
        raise ConfigError("telegram.privacy 'minimal' veya 'standard' olmali")
    api = (env.get("PANOGOZ_TELEGRAM_API") or sec.get("api_base") or DEFAULT_API).rstrip("/")
    return {"token": token, "privacy": privacy, "api_base": api}


def _sms(section: Any, env: Mapping[str, str]) -> dict:
    sec = dict(section) if isinstance(section, dict) else {}
    provider = env.get("PANOGOZ_SMS_PROVIDER") or sec.get("provider") or "sim"
    if provider not in ("sim", "serial"):
        raise ConfigError("sms.provider 'sim' veya 'serial' olmali")
    out: dict[str, Any] = {"provider": provider}
    if provider == "serial":
        port = env.get("PANOGOZ_SMS_PORT") or sec.get("port")
        if not port:
            raise ConfigError("sms.provider 'serial' icin sms.port gerekli (ornek COM5)")
        out.update(port=str(port), baud=int(sec.get("baud", 115200)),
                   sim_pin=(str(sec["sim_pin"]) if sec.get("sim_pin") else None))
    return out


def _rota(section: Any) -> tuple[list[dict], dict[str, str]]:
    src = section if section is not None else [dict(r) for r in DEFAULT_ROTA]
    if not isinstance(src, list) or not src:
        raise ConfigError("rota bos olmayan bir liste olmali")
    rota: list[dict] = []
    generated: dict[str, str] = {}
    names: set[str] = set()
    for i, raw in enumerate(src):
        if not isinstance(raw, dict):
            raise ConfigError(f"rota[{i}] bir nesne olmali")
        m = {k: v for k, v in raw.items() if not str(k).startswith("_")}
        name = str(m.get("name") or "").strip()
        if not name:
            raise ConfigError(f"rota[{i}].name gerekli")
        if name.lower() in names:
            raise ConfigError(f"rota[{i}].name tekrar ediyor: {name}")
        names.add(name.lower())
        try:
            m["level"] = int(m.get("level", 1))
        except (TypeError, ValueError) as exc:
            raise ConfigError(f"rota[{i}].level tam sayi olmali") from exc
        m["name"] = name
        m.setdefault("role", "")
        for key in ("telegram_chat_id", "telegram_user_id"):
            v = m.get(key)
            if v in (None, "", 0):
                m.pop(key, None)
            else:
                try:
                    m[key] = int(v)
                except (TypeError, ValueError) as exc:
                    raise ConfigError(f"rota[{i}].{key} sayi olmali") from exc
        pin = m.get("pin")
        if pin in (None, ""):
            pin = f"{secrets.randbelow(10000):04d}"
            generated[name] = pin
        elif not _PIN_RE.match(str(pin)):
            raise ConfigError(f"rota[{i}].pin 4-8 haneli rakam olmali")
        m["pin"] = str(pin)
        rota.append(m)
    return rota, generated

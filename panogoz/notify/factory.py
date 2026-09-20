"""Build the runtime's :class:`Notifier` from configuration.

The single seam between "what is configured" and "what runs".  ``Runtime`` calls
:func:`build_notifier` and does not know which channels exist; changing the modem
from simulated to real, or switching Telegram on, is a config change and never a
code change.
"""

from __future__ import annotations

import os
from typing import Any

from panogoz.notify.config import NotifyConfig, defaults, load
from panogoz.notify.escalation import Notifier
from panogoz.notify.gsm_serial import SerialGsmModem
from panogoz.notify.sms import GsmModem
from panogoz.notify.telegram import TelegramChannel


def build_modem(sms: dict) -> Any:
    if sms.get("provider") == "serial":
        return SerialGsmModem(sms["port"], baud=sms.get("baud", 115200), sim_pin=sms.get("sim_pin"))
    return GsmModem()


LIVE_ENV = "PANOGOZ_NOTIFY_LIVE"


def live_requested(env: dict | None = None) -> bool:
    """Real channels are opt-in per process: the launcher sets this, nothing else does.

    A ``Runtime`` built by a test, a benchmark or a helper script therefore gets the
    simulated modem and no Telegram even when ``notify.local.json`` exists.  The
    alternative - loading the file whenever it is present - means ``pytest`` on a
    developer's laptop sends real SMS the first time an incident dispatches.
    """
    return (os.environ if env is None else env).get(LIVE_ENV) == "1"


def build_notifier(store, config: NotifyConfig | None = None, *,
                   start_telegram: bool = True, async_dispatch: bool | None = None) -> Notifier:
    """A ready notifier.

    ``async_dispatch`` defaults to "on exactly when a real transport is configured":
    a Telegram request or a serial modem can block for seconds and must never run
    inside the detector's thread, while the simulated modem is instantaneous and
    stays synchronous (deterministic for tests and for the rehearsal).
    """
    if config is None:
        config = load() if live_requested() else defaults()
    if async_dispatch is None:
        async_dispatch = bool(config.telegram) or config.sms.get("provider") != "sim"
    telegram = None
    if config.telegram:
        telegram = TelegramChannel(config.telegram["token"], api_base=config.telegram["api_base"],
                                   privacy=config.telegram["privacy"])
    notifier = Notifier(store, modem=build_modem(config.sms), rota=config.rota,
                        telegram=telegram, public_url=config.public_url, app_enabled=True,
                        async_dispatch=async_dispatch)
    notifier.config = config                            # type: ignore[attr-defined]
    if telegram is not None and start_telegram:
        telegram.start()
    return notifier

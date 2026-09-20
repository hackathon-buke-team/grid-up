"""Configuration: where the rota, the bot token and the modem come from.

The rule under test: a secret (bot token, PIN, SIM PIN) may live in a git-ignored
file or an environment variable and nowhere else - never in a default, never in a
repr, never in an error message.
"""

from __future__ import annotations

import json

import pytest

from panogoz.notify import config as cfg
from panogoz.notify import factory
from panogoz.notify.escalation import DEFAULT_ROTA
from panogoz.notify.gsm_serial import SerialGsmModem
from panogoz.notify.sms import GsmModem
from panogoz.store.db import Store

TOKEN = "123456:TEST-TOKEN"


def write(tmp_path, data) -> str:
    p = tmp_path / "notify.local.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return str(p)


def test_no_file_and_no_env_is_the_safe_demo_default(tmp_path):
    c = cfg.load(path=str(tmp_path / "yok.json"), env={})
    assert c.telegram is None and c.sms["provider"] == "sim" and c.public_url is None
    assert [r["name"] for r in c.rota] == [r["name"] for r in DEFAULT_ROTA]
    assert c.source == "varsayilan"


def test_file_is_read_and_validated(tmp_path):
    p = write(tmp_path, {
        "public_url": "http://192.168.1.201:8080/",
        "telegram": {"token": TOKEN, "privacy": "standard"},
        "sms": {"provider": "serial", "port": "COM5", "baud": 9600, "sim_pin": "0000"},
        "rota": [{"name": "Ali", "number": "+905551112233", "level": 1,
                  "telegram_chat_id": 42, "pin": "4821"}],
    })
    c = cfg.load(path=p, env={})
    assert c.public_url == "http://192.168.1.201:8080"           # trailing slash removed
    assert c.telegram == {"token": TOKEN, "privacy": "standard", "api_base": cfg.DEFAULT_API}
    assert c.sms["provider"] == "serial" and c.sms["port"] == "COM5" and c.sms["baud"] == 9600
    assert c.rota[0]["pin"] == "4821" and c.rota[0]["telegram_chat_id"] == 42
    assert c.source.endswith("notify.local.json")


def test_environment_overrides_the_file(tmp_path):
    p = write(tmp_path, {"telegram": {"token": "1:FILE"}, "public_url": "http://a"})
    c = cfg.load(path=p, env={"PANOGOZ_TELEGRAM_TOKEN": TOKEN, "PANOGOZ_PUBLIC_URL": "http://b",
                              "PANOGOZ_SMS_PROVIDER": "serial", "PANOGOZ_SMS_PORT": "COM7"})
    assert c.telegram["token"] == TOKEN and c.public_url == "http://b"
    assert c.sms["provider"] == "serial" and c.sms["port"] == "COM7"


def test_token_alone_in_the_environment_enables_telegram(tmp_path):
    c = cfg.load(path=str(tmp_path / "yok.json"), env={"PANOGOZ_TELEGRAM_TOKEN": TOKEN})
    assert c.telegram["token"] == TOKEN and c.telegram["privacy"] == "minimal"


@pytest.mark.parametrize("data,needle", [
    ({"telegram": {"token": "no-colon"}}, "token"),
    ({"telegram": {"token": TOKEN, "privacy": "herkese-acik"}}, "privacy"),
    ({"sms": {"provider": "carrier-pigeon"}}, "provider"),
    ({"sms": {"provider": "serial"}}, "port"),
    ({"rota": [{"level": 1}]}, "name"),
    ({"rota": [{"name": "A", "level": "x"}]}, "level"),
    ({"rota": [{"name": "A", "pin": "12"}]}, "pin"),
    ({"rota": [{"name": "A"}, {"name": "A"}]}, "tekrar"),
    ({"public_url": "ftp://x"}, "public_url"),
])
def test_bad_config_names_the_field(tmp_path, data, needle):
    with pytest.raises(cfg.ConfigError) as exc:
        cfg.load(path=write(tmp_path, data), env={})
    assert needle in str(exc.value)
    assert TOKEN not in str(exc.value)


def test_invalid_json_is_a_clear_error(tmp_path):
    p = tmp_path / "notify.local.json"
    p.write_text("{ not json", encoding="utf-8")
    with pytest.raises(cfg.ConfigError) as exc:
        cfg.load(path=str(p), env={})
    assert "JSON" in str(exc.value)


def test_members_without_a_pin_get_a_random_one_that_is_never_in_the_config_repr(tmp_path):
    c = cfg.load(path=write(tmp_path, {"rota": [{"name": "A", "number": "+905551110000"}]}), env={})
    pin = c.rota[0]["pin"]
    assert len(pin) == 4 and pin.isdigit()
    assert c.generated_pins == {"A": pin}
    assert pin not in repr(c) and TOKEN not in repr(c)


def test_generated_pins_differ_between_loads(tmp_path):
    p = write(tmp_path, {"rota": [{"name": "A"}, {"name": "B"}, {"name": "C"}]})
    a = cfg.load(path=p, env={}).generated_pins
    b = cfg.load(path=p, env={}).generated_pins
    assert a != b


def test_example_file_in_the_repo_is_valid():
    c = cfg.load(path=str(cfg.EXAMPLE_PATH), env={})
    assert c.telegram is None or c.telegram["token"].endswith("DEGISTIR")  # placeholder only
    assert len(c.rota) >= 3


# ------------------------------------------------------------------ factory --

def test_factory_builds_the_simulated_default(tmp_path):
    store = Store(str(tmp_path / "f.db"))
    n = factory.build_notifier(store, cfg.load(path=str(tmp_path / "yok.json"), env={}))
    assert isinstance(n.modem, GsmModem) and n.telegram is None
    assert n.app_enabled is True
    assert n.async_dispatch is False, "the simulated modem is instantaneous: stay synchronous"
    n.close()


def test_factory_builds_telegram_and_serial_from_config(tmp_path):
    store = Store(str(tmp_path / "f.db"))
    c = cfg.load(path=write(tmp_path, {
        "telegram": {"token": TOKEN},
        "sms": {"provider": "serial", "port": "COM5"},
        "rota": [{"name": "Ali", "number": "+905551112233", "telegram_chat_id": 42}],
    }), env={})
    n = factory.build_notifier(store, c, start_telegram=False)
    assert isinstance(n.modem, SerialGsmModem) and n.modem.port == "COM5"
    assert n.telegram is not None and n.telegram.privacy == "minimal"
    assert n.on_rota("tg:42")["name"] == "Ali"
    assert n.async_dispatch is True, "a real transport can block: it must not run in the detector"
    n.close()


def test_a_process_that_did_not_ask_for_live_channels_gets_the_safe_default(tmp_path, monkeypatch):
    """pytest on a laptop with a real notify.local.json must never message a real phone."""
    real = tmp_path / "notify.local.json"
    real.write_text(json.dumps({"telegram": {"token": TOKEN}, "sms": {"provider": "serial", "port": "COM5"}}),
                    encoding="utf-8")
    monkeypatch.setattr(cfg, "LOCAL_PATH", real)
    monkeypatch.delenv(factory.LIVE_ENV, raising=False)
    monkeypatch.setenv("PANOGOZ_TELEGRAM_TOKEN", TOKEN)
    n = factory.build_notifier(Store(str(tmp_path / "f.db")))
    assert n.telegram is None and isinstance(n.modem, GsmModem)
    monkeypatch.setenv(factory.LIVE_ENV, "1")
    n2 = factory.build_notifier(Store(str(tmp_path / "g.db")), start_telegram=False)
    assert n2.telegram is not None and isinstance(n2.modem, SerialGsmModem)
    n.close(); n2.close()


def test_factory_starts_the_telegram_poller_only_when_asked(tmp_path):
    from tests.fake_telegram import FakeTelegram
    store = Store(str(tmp_path / "f.db"))
    with FakeTelegram(TOKEN) as fake:
        c = cfg.load(path=write(tmp_path, {"telegram": {"token": TOKEN, "api_base": fake.url}}), env={})
        n = factory.build_notifier(store, c, start_telegram=True)
        try:
            assert n.telegram.running
        finally:
            n.close()
        assert not n.telegram.running


def test_demo_file_gives_fixed_pins_when_there_is_no_local_file(tmp_path, monkeypatch):
    """Whoever clones the repo logs in with the documented PINs, no console needed."""
    monkeypatch.setattr(cfg, "LOCAL_PATH", tmp_path / "yok.json")
    c = cfg.load(env={})
    assert c.source == str(cfg.DEMO_PATH)
    assert c.generated_pins == {}
    assert [m["pin"] for m in c.rota] == ["1111", "2222", "3333"]
    assert any("DEMO" in w for w in c.warnings)
    assert c.telegram is None and c.sms["provider"] == "sim"       # nothing real, nothing secret
    from panogoz.notify.escalation import DEFAULT_ROTA
    assert [(m["name"], m["level"], m["number"]) for m in c.rota] == \
           [(m["name"], m["level"], m["number"]) for m in DEFAULT_ROTA]


def test_local_file_beats_the_demo_file(tmp_path, monkeypatch):
    real = tmp_path / "notify.local.json"
    real.write_text(json.dumps({"rota": [{"name": "A", "number": "+905551110000", "pin": "9876"}]}),
                    encoding="utf-8")
    monkeypatch.setattr(cfg, "LOCAL_PATH", real)
    c = cfg.load(env={})
    assert c.source == str(real)
    assert [m["pin"] for m in c.rota] == ["9876"]
    assert not any("DEMO" in w for w in c.warnings)

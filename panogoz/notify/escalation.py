"""Escalation ladder, authenticated acknowledgement, and the WhatsApp answer.

The ladder
----------

===========  ==========================================================
IZLE         Dashboard only.  Never an interruption, never a phone.
UYARI        E-mail, chat and a silent item in the field app's inbox.
             Eight business hours to acknowledge.
KRITIK       SMS + Telegram + field app, repeated (SMS, Telegram) every
             5 min until acknowledged.  Second person at 15 min, voice
             call at 30 min, manager at 45 min.
ACIL         SMS, voice, Telegram and field app simultaneously to the
             first two people, no suppression of any kind, manager at
             15 min.
===========  ==========================================================

Only KRITIK and ACIL reach a phone.  That is a contract in
``contracts.channels.DISPATCH_SEVERITIES``, not a setting, because the moment
UYARI can ring a phone the system starts being ignored, and a system that is
ignored detects nothing.

Three real channels, one ladder
-------------------------------

``SMS`` (GSM modem), ``TELEGRAM`` (bot, data-minimised) and ``MOBIL`` (the field
app, ``panogoz.notify.saha``) are independent paths to the same person.  Each is
its own ``notification`` row, each is sent on its own dispatch lane, and an
acknowledgement on any one of them stops the repeats on all of them and strikes
the button on every Telegram copy.  See docs/12-BILDIRIM-KANALLARI.md.

Authenticated acknowledgement
-----------------------------

An acknowledgement stops a KRITIK from escalating to a manager at 45 minutes.
That makes it a security-relevant action, and it is the one place in this
product where an attacker gets real value for almost no effort: guess an
incident id, text "TAMAM 42", and the alarm goes quiet.

So an SMS acknowledgement must satisfy **both** conditions:

1. the sending number is on the **active rota**, and
2. the message carries the **per-incident 4-digit token** that was included in
   the outbound message.

The token is derived as ``sha256(salt | incident_id)`` truncated to four digits.
Deterministic, so it survives a restart; salted, so it cannot be computed from
the incident id.  Four digits is not cryptography - it is a nonce that turns a
guessable identifier into an unguessable pair, on a channel that is already
restricted to a handful of known numbers.  Both gates, or no acknowledgement.

WhatsApp
--------

See :func:`whatsapp_status`.  Short version: we implement nothing, and we say
exactly why in front of the audience rather than being asked.
"""

from __future__ import annotations

import hashlib
import json
import queue
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable

from panogoz.contracts.channels import (
    SEVERITY_DATIVE_TR,
    DISPATCH_SEVERITIES,
    MODES_BY_KEY,
    SEVERITY_ACTION_TR,
    SEVERITY_RANK,
    SEVERITY_TR,
)
from panogoz.contracts.live import PanelLive
from panogoz.notify.sms import GsmModem, UCS2_SINGLE_CHARS, split_ucs2, ucs2_octets
from panogoz.notify.telegram import TelegramChannel, _esc

# --------------------------------------------------------------------------
# Rota and ladder
# --------------------------------------------------------------------------

#: Level 1 is the on-call technician, 2 the shift supervisor, 3 the manager.
DEFAULT_ROTA: list[dict] = [
    {"name": "Nöbetçi tekniker", "number": "+905321112233", "role": "birincil", "level": 1},
    {"name": "Vardiya amiri", "number": "+905321112244", "role": "ikincil", "level": 2},
    {"name": "İşletme müdürü", "number": "+905321112255", "role": "yönetici", "level": 3},
]

#: (seconds after dispatch, channel, rota level).
#:
#: SMS, TELEGRAM and MOBIL are three independent paths to the same person and
#: they fan out together at every rung: a phone with no signal still gets the
#: Telegram message over Wi-Fi, a person without the app open still gets the SMS.
#: TELEGRAM is skipped when no bot is configured and MOBIL when the field app is
#: off - a rung with no configured channel is a no-op, not an error.
#:
#: UYARI lands in the app inbox silently (MOBIL) and never rings anything: the
#: "only KRITIK and ACIL reach a phone" contract is about interruption, and an
#: inbox item does not interrupt.
LADDER: dict[str, tuple[tuple[float, str, int], ...]] = {
    "BILGI": (),
    "IZLE": ((0.0, "PANO", 0),),
    "UYARI": ((0.0, "EPOSTA", 1), (0.0, "MATRIX", 1), (0.0, "MOBIL", 1)),
    "KRITIK": ((0.0, "SMS", 1), (0.0, "TELEGRAM", 1), (0.0, "MOBIL", 1),
               (900.0, "SMS", 2), (900.0, "TELEGRAM", 2), (900.0, "MOBIL", 2),
               (1800.0, "SESLI", 1),
               (2700.0, "SMS", 3), (2700.0, "TELEGRAM", 3), (2700.0, "MOBIL", 3)),
    "ACIL": ((0.0, "SMS", 1), (0.0, "SESLI", 1), (0.0, "SMS", 2), (0.0, "SESLI", 2),
             (0.0, "TELEGRAM", 1), (0.0, "TELEGRAM", 2), (0.0, "MOBIL", 1), (0.0, "MOBIL", 2),
             (900.0, "SMS", 3), (900.0, "TELEGRAM", 3), (900.0, "MOBIL", 3)),
}

#: Repeat-until-ack interval per severity.  Absent means "do not repeat".
REPEAT_S: dict[str, float] = {"KRITIK": 300.0, "ACIL": 180.0}

#: Channels that are repeated until acknowledged.  MOBIL is absent on purpose: the
#: field app keeps sounding by itself while an unacknowledged incident is open.
REPEAT_CHANNELS: tuple[str, ...] = ("SMS", "TELEGRAM")

#: Acknowledgement deadline used only for the UI countdown.
ACK_DEADLINE_S: dict[str, float] = {
    "UYARI": 8 * 3600.0,       # eight business hours
    "KRITIK": 45 * 60.0,
    "ACIL": 15 * 60.0,
}

#: Stop repeating eventually.  An unacknowledged KRITIK after two hours of
#: five-minute texts is an organisational problem, not a messaging problem, and
#: continuing to text is how a rota learns to mute the sender.
MAX_REPEATS = 24

STATE_QUEUED = "KUYRUKTA"
STATE_SENT = "GONDERILDI"
STATE_DELIVERED = "ILETILDI"
STATE_ERROR = "HATA"

_DIGITS = re.compile(r"\d+")


def normalise_number(number: str) -> str:
    """Compare phone numbers by their last ten digits.

    +90 532 111 22 33, 0532 111 22 33 and 905321112233 are the same person, and
    a rota check that says otherwise locks the on-call technician out of
    acknowledging their own alarm at two in the morning.
    """
    digits = "".join(_DIGITS.findall(number or ""))
    return digits[-10:] if len(digits) >= 10 else digits


def ack_token(incident_id: int, salt: str = "PANOGOZ") -> str:
    h = hashlib.sha256(f"{salt}|{incident_id}".encode("utf-8")).hexdigest()
    return f"{int(h[:8], 16) % 10000:04d}"


# --------------------------------------------------------------------------
# Message composition
# --------------------------------------------------------------------------

_JOINT_RE = re.compile(r"^C(\d+)-(L[123]|N)-PABUC$")


def short_joint(joint_key: str | None) -> str:
    """``C07-L2-PABUC`` -> ``Ç7·L2·pabuç``.  Every character costs two octets."""
    if not joint_key:
        return "pano geneli"
    m = _JOINT_RE.match(joint_key)
    if not m:
        return joint_key
    return f"Ç{int(m.group(1))}·{m.group(2)}·pabuç"


def eta_text(incident: dict, live: PanelLive | None) -> str:
    """``KRITIK'e 21 g (13-32)`` or ``""`` when the horizon has no number to give."""
    if live is None:
        return ""
    jv_eta = next((j.eta for j in live.joints if j.key == incident.get("joint_key")), None)
    if jv_eta is None or jv_eta.reason or jv_eta.days is None:
        return ""
    lo = 0 if jv_eta.days_lo is None else int(jv_eta.days_lo)
    # Sonsuz ust sinir '+' ile yazilir: Unicode sonsuz isareti UCS2'de
    # yer kaplar ve bazi eski terminallerde okunmaz.
    span = f"{lo}+" if jv_eta.days_hi is None else f"{lo}-{int(jv_eta.days_hi)}"
    where = SEVERITY_DATIVE_TR.get(jv_eta.target or "", f"{jv_eta.target}'e")
    return f"{where} {int(jv_eta.days)} g ({span})"


def measurements(incident: dict) -> tuple[float | None, float | None]:
    """``(theta_k, temp_c)`` out of the incident's evidence block, either may be None."""
    ev = incident.get("evidence")
    if isinstance(ev, str):
        try:
            ev = json.loads(ev)
        except (json.JSONDecodeError, TypeError):
            ev = {}
    j = (ev.get("joint") if isinstance(ev, dict) else None) or {}
    return j.get("theta_k"), j.get("temp_c")


def compose(incident: dict, live: PanelLive | None = None,
            token: str | None = None) -> str:
    """Body of the outbound message.

    Budget: one UCS2 part, 70 characters, is not achievable while naming the
    panel, the joint, the metric, the action and the token - and dropping any
    of those five turns an actionable alert into a notification.  So the target
    is **under 140 UCS2 characters** (two parts) and the composer trims the
    action text, never the identifiers.
    """
    sev = incident.get("severity", "UYARI")
    panel = incident.get("panel_key", "?")
    joint = short_joint(incident.get("joint_key"))
    mode = incident.get("mode", "loose_connection")
    tok = token or incident.get("ack_token") or ack_token(int(incident.get("id", 0)))

    metric = ""
    ev = incident.get("evidence")
    if isinstance(ev, str):
        try:
            ev = json.loads(ev)
        except (json.JSONDecodeError, TypeError):
            ev = {}
    if isinstance(ev, dict):
        j = ev.get("joint") or {}
        theta = j.get("theta_k")
        temp = j.get("temp_c")
        bits = []
        if theta is not None:
            bits.append(f"θ={theta:.1f}K")
        if temp is not None:
            bits.append(f"{temp:.0f}°C")
        metric = " ".join(bits)
    if not metric and live is not None:
        metric = f"HI={live.health_index:.0f}"

    action = _short_action(mode, incident)

    # Ufuk satiri.  Metni kuran yer burasi; sms.py yalniz tasima katmanidir.
    #
    # Butce 160 DEGILDIR: Turkce metin GSM-7'ye girmedigi icin UCS2 gider ve tek
    # parca 70, birlesik parca 67 karakterdir.  Olculen mevcut govdeler 76-90
    # karakter, yani zaten iki parca; +24 karakter ucuncu parca acmiyor.
    eta_txt = eta_text(incident, live)
    eta_bit = f" · {eta_txt}" if eta_txt else ""

    head = f"PANO GÖZ {SEVERITY_TR[sev].upper()} · {panel} · {joint}"

    def _build() -> str:
        return (f"{head} {metric} · {action}{eta_bit} · "
                f"onay: TAMAM {incident.get('id', 0)} {tok}")

    body = _build()
    # Butce daralirsa ILK dusen sey ufuk satiridir.  Operatore "baglantiyi
    # torkla" demek, "21 gun" demekten degerlidir.
    if eta_bit and len(split_ucs2(body)) > 2:
        eta_bit = ""
        body = _build()
    # Trim the action, never the identifiers or the token.
    while len(body) > 2 * UCS2_SINGLE_CHARS and len(action) > 6:
        action = action[: max(6, len(action) - 6)].rstrip(" ,.")
        body = _build()
    return body


_TG_BADGE = {"UYARI": ("🟠", "UYARI"), "KRITIK": ("🔴", "KRİTİK"), "ACIL": ("🚨", "ACİL")}


def compose_telegram(incident: dict, live: PanelLive | None = None, *,
                     privacy: str = "minimal", public_url: str | None = None,
                     token: str | None = None, repeat: int = 0) -> tuple[str, list[list[dict]]]:
    """Telegram body (HTML) and its inline keyboard.

    ``privacy="minimal"`` is the default and the reason Telegram is allowed at all
    in an on-premise design: the text carries the panel, the joint, the severity,
    the instruction and the acknowledgement code - and **no measurement**.  The
    numbers (theta, temperature, the days-to-threshold horizon) appear only under
    ``"standard"``, which is an explicit decision to let them leave the network.
    Neither mode carries a coordinate; location is served by the field app.
    """
    sev = incident.get("severity", "KRITIK")
    icon, label = _TG_BADGE.get(sev, ("⚪", SEVERITY_TR.get(sev, sev).upper()))
    inc_id = int(incident.get("id", 0))
    tok = token or incident.get("ack_token") or ack_token(inc_id)
    mode = incident.get("mode", "loose_connection")
    joint = short_joint(incident.get("joint_key"))

    lines = [f"{icon} <b>PANO GÖZ · {label}</b>",
             f"<b>{_esc(incident.get('panel_key', '?'))}</b> · {_esc(joint)}"]
    mode_obj = MODES_BY_KEY.get(mode)
    if mode_obj is not None:
        lines.append(_esc(mode_obj.label_tr))
    lines.append(f"▶ {_esc(_short_action(mode, incident))}")
    if privacy == "standard":
        theta, temp = measurements(incident)
        bits = []
        if theta is not None:
            bits.append(f"θ={theta:.1f} K")
        if temp is not None:
            bits.append(f"{temp:.0f} °C")
        eta = eta_text(incident, live)
        if eta:
            bits.append(eta)
        if bits:
            lines.append(_esc(" · ".join(bits)))
    lines.append(f"🔑 Onay kodu: <code>{tok}</code>")
    if repeat:
        lines.append(f"⏰ Tekrar #{repeat} · onay bekleniyor")

    buttons: list[list[dict]] = [[{"text": "✅ Onayla",
                                   "callback_data": f"ack:{inc_id}:{tok}"}]]
    if public_url:
        buttons.append([{"text": "📱 Saha uygulamasında aç",
                         "url": f"{public_url.rstrip('/')}/saha/#/olay/{inc_id}"}])
    return "\n".join(lines), buttons


_SHORT_ACTION_TR: dict[str, str] = {
    "loose_connection": "bağlantıyı torkla",
    "overload": "yükü aktar",
    "arc_integrity": "ark dedektörünü kontrol et",
    # An actual trip is a different message from a doubt about the detectors.
    "arc_integrity_trip": "ARK AÇMASI · ekip yönlendir",
    "thermal_runaway": "havalandırmayı kontrol et",
    "harmonic_neutral": "nötrü ölç",
    "moisture": "kanal sızdırmazlığı",
    "insulation": "PD trendini izle",
}


def _short_action(mode: str, incident: dict | None = None) -> str:
    if (mode == "arc_integrity" and incident is not None
            and incident.get("severity") == "ACIL"):
        return _SHORT_ACTION_TR["arc_integrity_trip"]
    return _SHORT_ACTION_TR.get(mode, MODES_BY_KEY[mode].action_tr[:28])


def voice_script(incident: dict) -> str:
    """What the TTS gateway would read out.  Short, repeated twice, no jargon.

    The wording follows the failure mode.  Reading out "there is heating at the
    joint" to a crew whose substation has just arced and gone dark would send
    them looking for a warm bolt instead of an arc fault, and it is the kind of
    detail an operations manager judges a system on.
    """
    panel = incident.get("panel_key")
    tok = incident.get("ack_token")
    mode = incident.get("mode")
    if mode == "arc_integrity" and incident.get("severity") == "ACIL":
        what = "ark acmasi oldu. Pano buyuk olasilikla enerjisiz"
    elif mode == "overload":
        what = "surekli asiri yuk var"
    elif mode == "moisture":
        what = "yogusma riski var"
    elif mode == "thermal_runaway":
        what = "bolme sicakligi yukseliyor"
    else:
        what = f"{short_joint(incident.get('joint_key'))} baglantisinda isinma var"
    return (f"Pano Goz acil bildirimi. {panel} panosunda {what}. "
            f"Onay kodu {tok}. Tekrar ediyorum.")


def _voice_transcript(number: str, script: str) -> str:
    lines = [
        "AT+CLCC",
        "OK",
        f"ATD{number};",
        "OK",
        f'+COLP: "{number}",145,,,,""',
        f"# TTS: {script}",
        "# 18 s",
        "ATH",
        "OK",
        "# NOT: sesli yol bu surumde simulasyondur; sahada bir TTS ag gecidi gerekir.",
    ]
    return chr(10).join(lines)


# --------------------------------------------------------------------------
# Notifier
# --------------------------------------------------------------------------

@dataclass
class _Job:
    """One outbound message: where it goes and how to send it.

    ``run`` is a network or serial call and returns the transport's result dict
    (``ok``, ``transcript``, ...).  ``run is None`` means there is nothing to send
    over a wire - the row is the delivery (app inbox, simulated voice, e-mail).
    ``lane`` picks the dispatch worker so unrelated transports never queue behind
    each other.
    """
    channel: str
    target: str
    body: str
    run: Callable[[], dict] | None = None
    transcript: str = ""
    lane: str = "SMS"


class Notifier:
    """Drives the ladder, the repeats and the authenticated acknowledgement.

    Three real paths sit behind one ladder - the GSM modem (``SMS``), the Telegram
    bot (``TELEGRAM``) and the field app (``MOBIL``) - and they are independent:
    each is planned per rota member, recorded as its own ``notification`` row and
    sent on its own dispatch lane, so one channel failing or stalling costs the
    others nothing.

    ``async_dispatch``
        Off (default): a send happens inline, which is what the self-test and the
        unit tests want.  On: ``on_incident`` only *records* the rows (state
        ``KUYRUKTA``) and per-channel worker threads perform the network/serial
        call and settle the row to ``GONDERILDI`` or ``HATA``.  The runtime turns
        this on, because ``on_incident`` is called from the detector's thread and
        a Telegram request that hangs for eight seconds must not stall detection.
    """

    def __init__(self, store, *, modem: Any = None, rota: list[dict] | None = None,
                 salt: str = "PANOGOZ", telegram: TelegramChannel | None = None,
                 public_url: str | None = None, app_enabled: bool = False,
                 async_dispatch: bool = False) -> None:
        self.store = store
        self.modem = modem if modem is not None else GsmModem()
        self.rota = list(rota) if rota else [dict(r) for r in DEFAULT_ROTA]
        self.salt = salt
        self.telegram = telegram
        self.public_url = public_url.rstrip("/") if public_url else None
        self.app_enabled = bool(app_enabled)
        self.async_dispatch = bool(async_dispatch)
        #: incident_id -> {"first", "severity", "done", "repeats", "last_repeat", "live"}
        self._active: dict[int, dict] = {}
        self.sent_count = 0
        self.rejected_acks: list[dict] = []
        self.worker_errors: list[str] = []
        self._lock = threading.RLock()
        #: incident_id -> [(telegram chat id, message id)], so that an acknowledgement
        #: on ANY channel can strike the button on every Telegram copy.
        self._tg_messages: dict[int, list[tuple[Any, int]]] = {}
        self._lanes: dict[str, queue.Queue] = {}
        if telegram is not None:
            telegram.on_message = self.handle_inbound

    # ------------------------------------------------------------- rota ---

    def rota_for(self, level: int) -> list[dict]:
        return [r for r in self.rota if int(r.get("level", 1)) == level]

    def on_rota(self, who: str) -> dict | None:
        """Resolve a name, a phone number or a ``tg:<id>`` handle to a rota entry."""
        if who and str(who).startswith("tg:"):
            ident = str(who)[3:]
            for r in self.rota:
                for key in ("telegram_user_id", "telegram_chat_id"):
                    v = r.get(key)
                    if v not in (None, "") and str(v) == ident:
                        return r
            return None
        n = normalise_number(who)
        for r in self.rota:
            if n and r.get("number") and normalise_number(r["number"]) == n:
                return r
            if who and who.strip().lower() == str(r["name"]).strip().lower():
                return r
        return None

    # --------------------------------------------------- dispatch lanes ----

    def _submit(self, fn: Callable[[], None], lane: str = "SMS") -> None:
        """Run ``fn`` now, or on the lane's worker when ``async_dispatch`` is on."""
        if not self.async_dispatch:
            fn()
            return
        with self._lock:
            q = self._lanes.get(lane)
            if q is None:
                q = queue.Queue()
                self._lanes[lane] = q
                threading.Thread(target=self._work, args=(q,), name=f"panogoz:notify-{lane.lower()}",
                                 daemon=True).start()
        q.put(fn)

    def _work(self, q: queue.Queue) -> None:
        while True:
            fn = q.get()
            try:
                if fn is None:
                    return
                fn()
            except Exception as exc:  # noqa: BLE001 - a lane must outlive one bad job
                self.worker_errors.append(f"{type(exc).__name__}: {exc}")
                del self.worker_errors[:-20]
            finally:
                q.task_done()

    def flush(self, timeout: float = 10.0) -> bool:
        """Wait until every queued send has settled.  True when nothing is pending."""
        end = time.time() + timeout
        while time.time() < end:
            if all(q.unfinished_tasks == 0 for q in list(self._lanes.values())):
                return True
            time.sleep(0.01)
        return False

    def close(self) -> None:
        for q in list(self._lanes.values()):
            q.put(None)
        self._lanes.clear()
        if self.telegram is not None:
            self.telegram.stop()

    # ------------------------------------------------------------ send ----

    def _record(self, incident_id: int, channel: str, target: str, body: str,
                state: str, transcript: str) -> int:
        return self.store.add_notification(
            incident_id=incident_id, ts=time.time(), channel=channel, target=target,
            body=body, state=state, transcript=transcript,
        )

    def _plan(self, channel: str, person: dict, incident: dict, live: PanelLive | None,
              repeat: int) -> _Job | None:
        """What to send to one person on one channel.  ``None`` = nothing to do."""
        inc_id = int(incident["id"])
        if channel == "SMS":
            number = person.get("number")
            if not number:
                return None
            body = compose(incident, live)
            return _Job("SMS", number, body, run=lambda: self.modem.send(number, body))
        if channel == "TELEGRAM":
            chat = person.get("telegram_chat_id")
            if self.telegram is None or chat in (None, ""):
                return None
            text, buttons = compose_telegram(incident, live, privacy=self.telegram.privacy,
                                             public_url=self.public_url, repeat=repeat)

            def run() -> dict:
                res = self.telegram.send(chat, text, buttons=buttons)
                if res["ok"] and res.get("message_id") is not None:
                    with self._lock:
                        self._tg_messages.setdefault(inc_id, []).append((chat, res["message_id"]))
                return res

            return _Job("TELEGRAM", f"tg:{chat}", _plain(text), run=run, lane="TELEGRAM")
        if channel == "MOBIL":
            if not self.app_enabled:
                return None
            joint = short_joint(incident.get("joint_key"))
            return _Job("MOBIL", person["name"],
                        f"Saha uygulaması · {incident.get('panel_key', '?')} · {joint}",
                        transcript="# saha uygulaması gelen kutusuna düştü; uygulama açıldığında "
                                   "ILETILDI olur")
        if channel == "SESLI":
            number = person.get("number")
            if not number:
                return None
            script = voice_script(incident)
            return _Job("SESLI", number, script, transcript=_voice_transcript(number, script))
        if channel in ("EPOSTA", "MATRIX"):
            target = person.get("email") or person.get("number") or person["name"]
            hours = ACK_DEADLINE_S.get(incident.get("severity", "UYARI"), 0) / 3600
            return _Job(channel, target, compose(incident, live),
                        transcript=f"# {channel} · {person['name']} ({person['role']}) · "
                                   f"onay suresi {hours:.0f} saat")
        return None

    def _execute(self, job: _Job, row_id: int) -> None:
        """Perform one queued send and settle its row."""
        try:
            res = job.run()
        except Exception as exc:  # noqa: BLE001 - never let a transport bug escape
            res = {"ok": False, "transcript": f"# istisna: {type(exc).__name__}: {exc}"}
        state = STATE_SENT if res.get("ok") else STATE_ERROR
        self.store.execute("UPDATE notification SET state=?, transcript=? WHERE id=?",
                           (state, res.get("transcript") or "", row_id))
        self.store.commit()
        with self._lock:
            self.sent_count += 1

    def _send_one(self, incident: dict, channel: str, level: int, now: float,
                  live: PanelLive | None = None, repeat: int = 0) -> list[int]:
        ids: list[int] = []
        inc_id = int(incident["id"])
        if channel == "PANO":
            ids.append(self._record(
                inc_id, "PANO", "kontrol paneli", incident.get("title", ""),
                STATE_DELIVERED,
                "# IZLE seviyesi telefona cikmaz; haftalik ozet listesine girer.",
            ))
            return ids
        people = self.rota_for(level) or self.rota_for(1)
        for person in people:
            job = self._plan(channel, person, incident, live, repeat)
            if job is None:
                continue
            if job.run is None:
                ids.append(self._record(inc_id, job.channel, job.target, job.body,
                                        STATE_SENT, job.transcript))
                continue
            row_id = self._record(inc_id, job.channel, job.target, job.body, STATE_QUEUED,
                                  "# kuyrukta")
            ids.append(row_id)
            self._submit(lambda j=job, r=row_id: self._execute(j, r), lane=job.lane)
        return ids

    # ------------------------------------------------------- on_incident --

    def on_incident(self, incident: dict, live: PanelLive, now: float) -> list[int]:
        """Start the ladder for one incident.  Returns notification row ids."""
        with self._lock:
            inc_id = int(incident["id"])
            sev = incident.get("severity", "IZLE")
            if not incident.get("ack_token"):
                incident["ack_token"] = ack_token(inc_id, self.salt)
                self.store.update_incident(inc_id, ack_token=incident["ack_token"])
            st = self._active.setdefault(inc_id, {
                "first": now, "severity": sev, "done": set(), "repeats": 0,
                "last_repeat": now, "panel_key": incident.get("panel_key"), "live": live,
            })
            st["severity"] = sev
            ids: list[int] = []
            for offset, channel, level in LADDER.get(sev, ()):
                if offset > 0.0:
                    continue
                key = (offset, channel, level)
                if key in st["done"]:
                    continue
                st["done"].add(key)
                ids.extend(self._send_one(incident, channel, level, now, live=live))
            if sev not in DISPATCH_SEVERITIES:
                # Nothing further will happen; do not hold state for a queue item.
                self._active.pop(inc_id, None)
            self.store.commit()
            return ids

    # -------------------------------------------------------------- tick --

    def tick(self, now: float) -> None:
        """Advance every ladder: scheduled steps plus repeat-until-ack."""
        with self._lock:
            for inc_id in list(self._active):
                st = self._active[inc_id]
                row = self.store.one("SELECT * FROM incident WHERE id=?", (inc_id,))
                if row is None or row["state"] != "ACIK":
                    self._active.pop(inc_id, None)
                    continue
                incident = dict(row)
                sev = incident["severity"]
                st["severity"] = sev
                live = st.get("live")
                elapsed = now - st["first"]
                for offset, channel, level in LADDER.get(sev, ()):
                    key = (offset, channel, level)
                    if key in st["done"] or elapsed < offset:
                        continue
                    st["done"].add(key)
                    self._send_one(incident, channel, level, now, live=live)
                period = REPEAT_S.get(sev)
                if period and st["repeats"] < MAX_REPEATS and (now - st["last_repeat"]) >= period:
                    st["last_repeat"] = now
                    st["repeats"] += 1
                    for channel in REPEAT_CHANNELS:
                        self._send_one(incident, channel, 1, now, live=live,
                                       repeat=st["repeats"])
                elif period and st["repeats"] >= MAX_REPEATS:
                    self.store.add_suppression(
                        panel_key=incident["panel_key"], joint_key=incident["joint_key"],
                        mode=incident["mode"],
                        reason=(f"Tekrarlı SMS durduruldu: {MAX_REPEATS} deneme boyunca onay "
                                f"gelmedi. Bu bir mesajlaşma sorunu değil, bir nöbet sorunudur; "
                                f"olay açık kalır ve yönetici bildirimi yapılmıştır."),
                        detail={"code": "REPEAT_EXHAUSTED", "incident": inc_id},
                    )
                    st["repeats"] += 1
            self.store.commit()

    # --------------------------------------------------------------- ack --

    def ack(self, incident_id: int, by: str, token: str, channel: str | None = None) -> bool:
        """Both gates, always.  Returns False rather than raising.

        ``by`` may be a phone number (SMS path), a ``tg:<id>`` handle (Telegram), or
        a rota member's name (the field app, after PIN login).  A dashboard
        acknowledgement by an authenticated web session is passed as
        ``"web:<username>"`` and skips the rota check, because the web session
        has already been authenticated by something stronger than caller ID.

        ``channel`` only labels the audit record and the ``acked_by`` text; it never
        relaxes a gate.
        """
        with self._lock:
            row = self.store.one("SELECT * FROM incident WHERE id=?", (incident_id,))
            if row is None:
                self._reject(incident_id, by, "unknown_incident")
                return False
            if row["state"] == "KAPANDI":
                self._reject(incident_id, by, "already_closed")
                return False

            web = str(by).startswith("web:")
            person = None if web else self.on_rota(by)
            if not web and person is None:
                self._reject(incident_id, by, "not_on_rota")
                return False

            expected = row["ack_token"] or ack_token(incident_id, self.salt)
            if token is None or str(token).strip() != str(expected):
                self._reject(incident_id, by, "bad_token")
                return False

            via = {"telegram": "Telegram", "app": "uygulama"}.get(channel or "")
            if web:
                who = by
            elif via:
                who = f"{person['name']} · {via}"
            else:
                who = f"{person['name']} ({person['number']})"
            self.store.update_incident(incident_id, state="ONAYLANDI", acked_at=time.time(),
                                       acked_by=who)
            self.store.audit("notify.escalation", "ack", f"incident:{incident_id}",
                             {"by": who, "channel": channel or ("web" if web else "sms")})
            self._active.pop(incident_id, None)
            self.store.commit()
            self._after_ack(incident_id, who)
            return True

    def _after_ack(self, incident_id: int, who: str) -> None:
        """Strike the acknowledge button on every Telegram copy of this incident."""
        if self.telegram is None:
            return
        note = f"{who} · {time.strftime('%H:%M')}"
        for chat, mid in self._tg_messages.pop(incident_id, []):
            self._submit(lambda c=chat, m=mid: self.telegram.mark_acked(c, m, note),
                         lane="TELEGRAM")

    def _reject(self, incident_id: int, by: str, reason: str) -> None:
        self.rejected_acks.append({"incident": incident_id, "by": by, "reason": reason,
                                   "ts": time.time()})
        self.store.audit("notify.escalation", "ack.reject", f"incident:{incident_id}",
                         {"by": by, "reason": reason})
        self.store.commit()

    # ------------------------------------------------------------ inbound --

    def check_replies(self, now: float) -> int:
        """Drain the modem inbox and apply any valid acknowledgements."""
        acked = 0
        for msg in self.modem.poll_inbox():
            msg.setdefault("channel", "sms")
            if self.handle_inbound(msg):
                acked += 1
        return acked

    def handle_inbound(self, msg: dict) -> bool:
        """One inbound message from any channel.  True when it acknowledged an incident.

        SMS and Telegram share one grammar - ``TAMAM <incident> <code>`` - so a
        button tap, a typed reply and a text message all pass the same two gates.
        """
        with self._lock:
            channel = msg.get("channel") or "sms"
            number = msg.get("number", "")
            text = str(msg.get("text", ""))
            if channel == "telegram" and not msg.get("callback_id") \
                    and text.lstrip().startswith("/"):
                self._telegram_command(msg)
                return False
            nums = _DIGITS.findall(text)
            if len(nums) < 2:
                self._reject(0, number, "unparseable")
                self._feedback(msg, False, "unparseable")
                return False
            inc_id, token = int(nums[0]), nums[1]
            ok = self.ack(inc_id, number, token, channel=channel)
            reason = "" if ok else (self.rejected_acks[-1]["reason"] if self.rejected_acks else "")
            self._feedback(msg, ok, reason)
            return ok

    def _feedback(self, msg: dict, ok: bool, reason: str) -> None:
        if msg.get("channel") != "telegram" or self.telegram is None:
            return
        text = "✅ Onaylandı" if ok else _REASON_TR.get(reason, "⛔ Onay reddedildi")
        callback_id, chat = msg.get("callback_id"), msg.get("chat_id")
        if callback_id:
            self._submit(lambda: self.telegram.answer_callback(callback_id, text, alert=not ok),
                         lane="TELEGRAM")
        elif chat is not None:
            self._submit(lambda: self.telegram.reply(chat, text), lane="TELEGRAM")

    def _telegram_command(self, msg: dict) -> None:
        chat = msg.get("chat_id")
        cmd = str(msg.get("text", "")).split()[0].lower().split("@")[0]
        who = self.on_rota(msg.get("number", ""))
        if cmd in ("/durum", "/olaylar"):
            if who is None:
                reply = "⛔ Bu sohbet nöbet listesinde değil."
            else:
                rows = [r for r in self.store.incidents(state="ACIK", limit=50)
                        if r["severity"] in DISPATCH_SEVERITIES][:8]
                if not rows:
                    reply = "✅ Açık KRİTİK/ACİL olay yok."
                else:
                    reply = "<b>Açık olaylar</b>\n" + "\n".join(
                        f"#{r['id']} {SEVERITY_TR.get(r['severity'], r['severity'])} · "
                        f"{_esc(r['panel_key'])} · {_esc(short_joint(r['joint_key']))}"
                        for r in rows)
        else:                                            # /start, /id, /yardim and anything else
            lines = ["<b>PANO GÖZ bildirim botu</b>", f"Sohbet no: <code>{chat}</code>"]
            if who is not None:
                lines.append(f"✅ Nöbet listesindesiniz: <b>{_esc(who['name'])}</b> "
                             f"(seviye {who.get('level', 1)}).")
            else:
                lines.append("⛔ Bu sohbet nöbet listesinde değil. Yöneticinize yukarıdaki "
                             "sohbet numarasını verin.")
            lines.append("Onay: düğmeye basın ya da <code>TAMAM &lt;olay no&gt; &lt;kod&gt;</code> "
                         "yazın. /durum açık olayları listeler.")
            reply = "\n".join(lines)
        if self.telegram is not None and chat is not None:
            self._submit(lambda: self.telegram.reply(chat, reply), lane="TELEGRAM")

    # ------------------------------------------------------------ status --

    def pending(self) -> list[dict]:
        out = []
        with self._lock:
            active = list(self._active.items())
        for inc_id, st in active:
            row = self.store.one("SELECT * FROM incident WHERE id=?", (inc_id,))
            if row is None:
                continue
            out.append({
                "incident": inc_id, "severity": row["severity"], "title": row["title"],
                "repeats": st["repeats"], "since_s": round(time.time() - st["first"], 1),
                "deadline_s": ACK_DEADLINE_S.get(row["severity"]),
            })
        return out

    def status(self) -> dict:
        """Which channels exist and whether they work.  Never a secret."""
        sms = dict(self.modem.status()) if hasattr(self.modem, "status") else {}
        sms["simulated"] = bool(getattr(self.modem, "simulated", True))
        telegram = self.telegram.status() if self.telegram is not None else {"configured": False}
        return {
            "channels": {"sms": sms, "telegram": telegram,
                         "mobil": {"enabled": self.app_enabled}},
            "rota": [{"name": r["name"], "role": r.get("role", ""), "level": r.get("level", 1),
                      "sms": bool(r.get("number")), "telegram": bool(r.get("telegram_chat_id")),
                      "app": self.app_enabled} for r in self.rota],
            "async": self.async_dispatch,
            "pending": len(self._active),
            "sent": self.sent_count,
            "public_url": self.public_url,
        }

    def send_test(self, who: str) -> list[dict]:
        """A clearly labelled test message to one rota member, on every real channel.

        Not an incident: nothing is written to the incident table, so a rehearsal
        never appears on the alarm console as if something were wrong.
        """
        person = self.on_rota(who)
        if person is None:
            raise ValueError(f"'{who}' nöbet listesinde yok")
        out: list[dict] = []
        if person.get("number"):
            res = self.modem.send(person["number"], "PANO GOZ TEST · bildirim hattı çalışıyor. "
                                                    "Yanıt gerekmez.")
            out.append({"channel": "SMS", "target_name": person["name"], "ok": bool(res["ok"]),
                        "simulated": bool(getattr(self.modem, "simulated", True)),
                        "transcript": res.get("transcript", "")})
        chat = person.get("telegram_chat_id")
        if self.telegram is not None and chat not in (None, ""):
            res = self.telegram.send(chat, "🧪 <b>PANO GÖZ · TEST</b>\nBildirim hattı çalışıyor. "
                                           "Yanıt gerekmez.")
            out.append({"channel": "TELEGRAM", "target_name": person["name"],
                        "ok": bool(res["ok"]), "simulated": False,
                        "transcript": res.get("transcript", ""), "error": res.get("error")})
        self.store.audit("notify.escalation", "test", person["name"],
                         {"channels": [o["channel"] for o in out],
                          "ok": [o["ok"] for o in out]})
        self.store.commit()
        return out


#: What the operator is told when an acknowledgement is refused.  Deliberately
#: generic toward strangers: it says what to fix, not which of the two gates held.
_REASON_TR = {
    "not_on_rota": "⛔ Bu sohbet nöbet listesinde değil.",
    "bad_token": "⛔ Onay kodu hatalı.",
    "already_closed": "Olay zaten kapanmış.",
    "unknown_incident": "Böyle bir olay yok.",
    "unparseable": "Anlamadım. Onay için: TAMAM <olay no> <kod>",
}


def _plain(html_text: str) -> str:
    """Telegram HTML -> the plain text stored in the notification row."""
    import html as _html
    return _html.unescape(re.sub(r"<[^>]+>", "", html_text))


# --------------------------------------------------------------------------
# WhatsApp - the honest position
# --------------------------------------------------------------------------

def whatsapp_status() -> dict:
    """Why PANO GOZ ships no WhatsApp integration.

    Everybody asks.  Answering it before being asked, with the actual reasons,
    is worth more than the feature would be.
    """
    return {
        "implemented": False,
        "summary_tr": (
            "PANO GÖZ WhatsApp entegrasyonu içermez. Bu bir eksik değil, bilinçli bir "
            "karardır ve gerekçesi aşağıdadır."
        ),
        "reasons_tr": [
            "Meta, şirket içi (On-Premises) Business API'yi kullanımdan kaldırdı. "
            "Üzerine sistem kurulacak bir yol değildir.",
            "Cloud API bir kamu bulutudur. Şartnamenin şirket içi (on-premise) "
            "gereksinimiyle doğrudan çelişir; abonelerin ve varlıkların verisi "
            "yurt dışındaki bir SaaS'a çıkar.",
            "whatsapp-web.js ve Baileys gibi resmi olmayan kütüphaneler Meta'nın "
            "kullanım şartlarını ihlal eder ve numaranın kalıcı olarak yasaklanma "
            "riskini taşır. Bir dağıtım şirketinin nöbet hattını bu riske atmayız.",
        ],
        "compliant_options_tr": [
            "DMZ'de duran, veriyi asgariye indiren bir aynalama servisi: yalnız "
            "'pano + seviye + onay kodu' dışarı çıkar, ölçüm çıkmaz. KVKK 9. madde "
            "(yurt dışına aktarım) dayanağı ve bir kill switch ile birlikte.",
            "Şirket içinde barındırılan Matrix (Synapse) + köprü: mesajlaşma tamamen "
            "kurum ağında kalır, federasyon kapatılabilir.",
        ],
        "demo_path_tr": (
            "Gösterimdeki mesaj, ağ geçidinin kendi GSM SMS yolundan gider. "
            "Şirket içi mimari slaydından doksan saniye sonra kamu bulutunda bir SMS "
            "sağlayıcısı kullanmak, kendi ayağımıza sıkmak olurdu."
        ),
    }


# --------------------------------------------------------------------------
# Self-test
# --------------------------------------------------------------------------

if __name__ == "__main__":  # pragma: no cover
    import os
    import tempfile

    from panogoz.rules import fusion, pipeline
    from panogoz.rules.fusion import _demo_live
    from panogoz.store.db import Store

    print("=" * 78)
    print("PANO GOZ · escalation self-test")
    print("=" * 78)

    tmp = os.path.join(tempfile.mkdtemp(prefix="panogoz-esc-"), "t.db")
    store = Store(tmp)
    pipeline.reset()
    modem = GsmModem()
    notifier = Notifier(store, modem=modem)

    T0 = 1_760_000_000.0
    hist: dict = {}
    for d in range(4):
        live = _demo_live()
        live.ts = T0 + d * 86400
        j = [x for x in live.joints if x.key == "C07-L2-PABUC"][0]
        j.theta_k, j.temp_c, j.cusum, j.slope_k_per_week, j.theta_min_k = 14.2, 99.0, 20.0, 0.8, 0.9
        pipeline.run(live, store, hist, T0 + d * 86400, notifier=notifier)

    inc = store.one("SELECT * FROM incident WHERE joint_key IS NOT NULL ORDER BY id LIMIT 1")
    print()
    print(f"[olay] #{inc['id']}  {inc['severity']}  {inc['title']}")
    print(f"       token={inc['ack_token']}")

    body = compose(dict(inc))
    print()
    print("[mesaj govdesi]")
    print("  " + body)
    print(f"  {len(body)} karakter, {ucs2_octets(body)} oktet, "
          f"{len(split_ucs2(body))} parca (140 UCS2 karakter hedefi)")
    assert len(body) <= 2 * UCS2_SINGLE_CHARS, len(body)
    for token_part in (inc["panel_key"], "Ç7", "θ=", "onay", str(inc["ack_token"])):
        assert token_part in body, token_part
    print("  ASSERT OK: pano, baglanti, metrik, aksiyon ve onay kodu mesajda")

    notes = store.notifications(inc["id"])
    print()
    print(f"[merdiven · t=0]  {len(notes)} bildirim")
    for n in notes:
        print(f"  {n['channel']:<7} -> {n['target']:<16} {n['state']}")

    print()
    print("[tekrar-onaya kadar]")
    for step, t in enumerate((300, 600, 900, 1800, 2700), start=1):
        notifier.tick(T0 + 3 * 86400 + t)
        n = store.notifications(inc["id"], limit=999)
        chans = {}
        for r in n:
            chans[r["channel"]] = chans.get(r["channel"], 0) + 1
        print(f"  t+{t:>4} s: toplam {len(n):>2} bildirim  {chans}")

    print()
    print("[ack · iki kapi birden]")
    good_num = DEFAULT_ROTA[0]["number"]
    print(f"  rotadaki numara + YANLIS token -> "
          f"{notifier.ack(inc['id'], good_num, '0000')}")
    print(f"  ROTA DISI numara + dogru token -> "
          f"{notifier.ack(inc['id'], '+905559998877', inc['ack_token'])}")
    print(f"  rotadaki numara + dogru token  -> "
          f"{notifier.ack(inc['id'], good_num, inc['ack_token'])}")
    after = store.one("SELECT * FROM incident WHERE id=?", (inc["id"],))
    assert after["state"] == "ONAYLANDI", after["state"]
    print(f"  durum={after['state']}  onaylayan={after['acked_by']}")
    print(f"  reddedilenler: {[r['reason'] for r in notifier.rejected_acks]}")
    assert "bad_token" in [r["reason"] for r in notifier.rejected_acks]
    assert "not_on_rota" in [r["reason"] for r in notifier.rejected_acks]

    print()
    print("[SMS ile onay · gelen kutusundan]")
    inc2 = store.one("SELECT * FROM incident WHERE state='ACIK' ORDER BY id DESC LIMIT 1")
    if inc2 is None:
        inc2_id = store.open_incident(
            panel_key="SOKE-14", joint_key="C08-L1-PABUC", mode="loose_connection",
            severity="KRITIK", title="Çıkış 8 · L1 · çıkış pabucu — bağlantı direnci artıyor",
            action="Torkla")
        store.update_incident(inc2_id, ack_token=ack_token(inc2_id))
        inc2 = store.one("SELECT * FROM incident WHERE id=?", (inc2_id,))
    modem.inject_reply("+905559998877", f"TAMAM {inc2['id']} {inc2['ack_token']}")
    print(f"  rota disi gonderen -> onaylanan={notifier.check_replies(T0)}")
    modem.inject_reply(good_num, f"TAMAM {inc2['id']} 1234")
    print(f"  rotadaki, yanlis token -> onaylanan={notifier.check_replies(T0)}")
    modem.inject_reply(good_num, f"TAMAM {inc2['id']} {inc2['ack_token']}")
    n_ok = notifier.check_replies(T0)
    print(f"  rotadaki, dogru token -> onaylanan={n_ok}")
    assert n_ok == 1
    row2 = store.one("SELECT * FROM incident WHERE id=?", (inc2["id"],))
    print(f"  durum={row2['state']}  onaylayan={row2['acked_by']}")

    print()
    print("[merdiven tablosu]")
    for sev in ("IZLE", "UYARI", "KRITIK", "ACIL"):
        steps = ", ".join(f"t+{int(o) // 60}dk {c}->L{l}" for o, c, l in LADDER[sev]) or "-"
        rep = REPEAT_S.get(sev)
        print(f"  {SEVERITY_TR[sev]:<7} {steps}"
              + (f"  · her {int(rep) // 60} dk tekrar" if rep else ""))
    print(f"  Telefona cikan seviyeler (sozlesme): {DISPATCH_SEVERITIES}")

    ws = whatsapp_status()
    print()
    print("[WhatsApp]")
    print("  " + ws["summary_tr"])
    for r in ws["reasons_tr"]:
        print("  · " + r)
    print("  Uyumlu secenekler:")
    for r in ws["compliant_options_tr"]:
        print("    - " + r)
    print("  " + ws["demo_path_tr"])
    assert ws["implemented"] is False

    print()
    print(f"[denetim zinciri] {store.verify_chain()}")
    print()
    print("OK")

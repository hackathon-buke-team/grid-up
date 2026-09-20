"""The field-crew app's server side: ``/saha/`` (the app) and ``/api/saha/*``.

What this is for
----------------

The alarm console (``frontend/``) is for the control room.  A crew standing in a
substation with a phone needs something else: *which panel, which lug, what to do,
where it is, and one button to say "I've got it"*.  This module is that surface.
It is the second channel of the escalation ladder (``MOBIL``): an incident that is
sent to a rota member appears in their app inbox, and the app rings until they
acknowledge it.

Design decisions that are not obvious
-------------------------------------

* **On-premise.**  The app is served by this process and talks only to it.  There
  is no push service (FCM/APNs/Web Push relay), because every one of them routes
  through a public cloud.  The price is honest: the app alerts while it is open
  and while the page is alive in the background.  A closed app is reached by the
  other two channels (SMS, Telegram); that redundancy is the reason there are
  three.  ``docs/12-BILDIRIM-KANALLARI.md`` §4 says so.
* **The session is the credential.**  Login is a rota name plus a PIN, with
  lock-out.  Once logged in, an acknowledgement does not ask the crew to type the
  four-digit incident code: the per-incident token exists to stop a *guessed*
  incident id acknowledging an alarm over SMS, and a PIN-authenticated session is
  a stronger factor than that.  So the server applies the token itself, and the
  token is **never** sent to the phone.
* **Acknowledge before you dispatch yourself.**  "On the way / on site / done" is
  accepted only for an acknowledged incident, and only forward.  It is recorded in
  the hash-chained audit trail (``workorder.status``), which is what the alarm
  console reads back - no schema change.
* **"Done" is not "closed".**  The crew saying the job is finished does not close
  the incident; the alarm manager closes it after the sensors have read clean for
  seven days.  The app says exactly that.
* **A wrong name and a wrong PIN look identical**, and lock-out is keyed on the
  name as typed, so lock-out behaviour cannot be used to discover who is on the
  rota.  (The cost: someone can lock a colleague out for a minute.  SMS and
  Telegram acknowledgement are unaffected.)
"""

from __future__ import annotations

import hmac
import json
import secrets
import time
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote

from fastapi import APIRouter, Body, Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from panogoz.contracts.channels import DISPATCH_SEVERITIES, MODES_BY_KEY, SEVERITY_RANK, SEVERITY_TR
from panogoz.notify import escalation as esc

ROOT = Path(__file__).resolve().parents[2]
SAHA_DIR = ROOT / "saha"

SESSION_TTL_S = 12 * 3600.0          #: one shift
LOCK_AFTER_FAILS = 5
LOCK_WINDOW_S = 60.0
LOCK_FOR_S = 60.0
TEST_COOLDOWN_S = 10.0
CLOSED_VISIBLE_S = 6 * 3600.0        #: a closed incident stays in the inbox this long
WORK_STEPS = ("yolda", "sahada", "tamam")
NOTE_MAX = 500
VISIBLE_SEVERITIES = ("UYARI", "KRITIK", "ACIL")

_ACK_REASON_TR = {
    "not_on_rota": "Nöbet listesinde değilsiniz.",
    "bad_token": "Onay kodu hatalı.",
    "already_closed": "Olay zaten kapanmış.",
    "unknown_incident": "Böyle bir olay yok.",
}


def _theta_ladder() -> list[list]:
    """``[["IZLE", 2.0], ["UYARI", 5.0], ...]`` from the detector's single definition.

    The detail screen draws theta on these zones.  The thresholds live in
    ``detector.engine.THETA_ABS_LADDER`` ("whoever changes a threshold changes it in
    one place"); forwarding them keeps the phone from hard-coding a second copy.
    Empty when the detector cannot be imported - the phone then draws no scale.
    """
    try:
        from panogoz.detector.engine import THETA_ABS_LADDER
        return [[str(name), float(k)] for name, k in THETA_ABS_LADDER]
    except Exception:  # noqa: BLE001
        return []


class NoStoreFiles(StaticFiles):
    """The app shell is never cached by the browser.

    Same reasoning as the console's ``UiFiles``: this is an appliance on a LAN, a
    stale bundle on a crew's phone is a worse failure than the bytes it saves, and
    it would be invisible - the app would simply behave like the old version.  The
    service worker keeps its own offline copy and revalidates it on every load.
    """

    async def get_response(self, path: str, scope):  # type: ignore[override]
        resp = await super().get_response(path, scope)
        resp.headers["Cache-Control"] = "no-store, must-revalidate"
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["Referrer-Policy"] = "no-referrer"
        return resp


class _Sessions:
    def __init__(self, clock: Callable[[], float]) -> None:
        self._clock = clock
        self._s: dict[str, tuple[str, float]] = {}

    def create(self, name: str) -> str:
        token = secrets.token_urlsafe(32)
        self._s[token] = (name, self._clock() + SESSION_TTL_S)
        return token

    def get(self, token: str) -> str | None:
        hit = self._s.get(token)
        if hit is None:
            return None
        if self._clock() >= hit[1]:
            self._s.pop(token, None)
            return None
        return hit[0]

    def revoke(self, token: str) -> None:
        self._s.pop(token, None)


class _LockOut:
    """Five failures inside a minute lock that name for a minute."""

    def __init__(self, clock: Callable[[], float]) -> None:
        self._clock = clock
        self._fails: dict[str, list[float]] = {}
        self._locked: dict[str, float] = {}

    def retry_after(self, name: str) -> int:
        until = self._locked.get(name, 0.0)
        left = until - self._clock()
        if left <= 0:
            self._locked.pop(name, None)
            return 0
        return int(left) + 1

    def fail(self, name: str) -> None:
        now = self._clock()
        recent = [t for t in self._fails.get(name, []) if now - t < LOCK_WINDOW_S] + [now]
        self._fails[name] = recent
        if len(recent) >= LOCK_AFTER_FAILS:
            self._locked[name] = now + LOCK_FOR_S
            self._fails[name] = []

    def ok(self, name: str) -> None:
        self._fails.pop(name, None)
        self._locked.pop(name, None)


# --------------------------------------------------------------------------

def install(app: FastAPI, runtime: Any, *, clock: Callable[[], float] | None = None) -> None:
    """Mount ``/api/saha``, ``/api/notify`` and ``/saha/`` on ``app``.

    Must be called **before** the catch-all ``/`` static mount, or the console's
    file server answers ``/saha/`` first.
    """
    rt = runtime
    clock = clock or getattr(rt, "now", None) or time.time
    sessions = _Sessions(clock)
    lockout = _LockOut(clock)
    last_test = {"t": -1e18}

    # ---------------------------------------------------------------- helpers --

    def notifier() -> esc.Notifier:
        n = getattr(rt, "notifier", None)
        if n is None:
            raise HTTPException(status_code=503, detail={
                "error": "notifier_unavailable",
                "message_tr": "Bildirim katmanı çalışmıyor (bkz. /api/health degraded)."})
        return n

    def find_member(name: str) -> dict | None:
        want = (name or "").strip().lower()
        for m in notifier().rota:
            if str(m["name"]).strip().lower() == want:
                return m
        return None

    def current(request: Request) -> dict:
        auth = request.headers.get("authorization", "")
        token = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
        name = sessions.get(token) if token else None
        member = find_member(name) if name else None
        if member is None:
            raise HTTPException(status_code=401, detail={
                "error": "unauthorized", "message_tr": "Oturum yok ya da süresi doldu."})
        return {**member, "_token": token}

    def incident_row(iid: int) -> dict:
        row = rt.store.one("SELECT * FROM incident WHERE id=?", (iid,))
        if row is None:
            raise HTTPException(status_code=404, detail={
                "error": "incident_not_found", "message_tr": f"{iid} numaralı olay yok."})
        return row

    def work_steps(iid: int) -> list[dict]:
        rows = rt.store.query(
            "SELECT ts, detail FROM audit WHERE action='workorder.status' AND subject=? "
            "ORDER BY id", (f"incident:{iid}",))
        out = []
        for r in rows:
            try:
                d = json.loads(r["detail"])
            except (TypeError, json.JSONDecodeError):
                continue
            out.append({"ts": r["ts"], "durum": d.get("durum"), "by": d.get("by"),
                        "not": d.get("not", "")})
        return out

    def latest_work_all() -> dict[int, dict]:
        latest: dict[int, dict] = {}
        rows = rt.store.query(
            "SELECT subject, ts, detail FROM audit WHERE action='workorder.status' "
            "ORDER BY id DESC LIMIT 500")
        for r in reversed(rows):                         # oldest first, so the newest wins
            try:
                d = json.loads(r["detail"])
                iid = int(str(r["subject"]).split(":")[1])
            except (TypeError, ValueError, IndexError, json.JSONDecodeError):
                continue
            latest[iid] = {"durum": d.get("durum"), "by": d.get("by"), "ts": r["ts"],
                           "not": d.get("not", "")}
        return latest

    def card(row: dict, mine: dict[int, float], work: dict[int, dict]) -> dict:
        iid = int(row["id"])
        sev, state = row["severity"], row["state"]
        needs_ack = state == "ACIK" and sev in DISPATCH_SEVERITIES and bool(row.get("dispatched"))
        notified = mine.get(iid)
        mode = row.get("mode") or ""
        return {
            "id": iid, "panel_key": row["panel_key"], "joint_key": row.get("joint_key"),
            "joint_short": esc.short_joint(row.get("joint_key")),
            "severity": sev, "severity_label": SEVERITY_TR.get(sev, sev),
            "mode": mode, "mode_label": MODES_BY_KEY[mode].label_tr if mode in MODES_BY_KEY else mode,
            "title": row.get("title") or "", "action": row.get("action") or "",
            "state": state, "opened_at": row["opened_at"],
            "age_s": max(0.0, round(clock() - float(row["opened_at"]), 1)),
            "acked_by": row.get("acked_by"), "acked_at": row.get("acked_at"),
            "dispatched": bool(row.get("dispatched")),
            "notified_at": notified, "needs_ack": needs_ack,
            "sound": bool(needs_ack and notified is not None),
            "work": work.get(iid),
            #: The ladder's own number (escalation.ACK_DEADLINE_S): the inbox draws a
            #: countdown from it, and it must not be a second copy that can drift.
            "ack_deadline_s": esc.ACK_DEADLINE_S.get(sev),
        }

    def my_notified(member_name: str) -> dict[int, float]:
        rows = rt.store.query(
            "SELECT incident_id, MIN(ts) AS ts FROM notification "
            "WHERE channel='MOBIL' AND target=? GROUP BY incident_id", (member_name,))
        return {int(r["incident_id"]): float(r["ts"]) for r in rows}

    # ----------------------------------------------------------------- routes --

    api = APIRouter(prefix="/api/saha", tags=["saha"])

    @api.get("/rota")
    def rota() -> list:
        return [{"name": m["name"], "role": m.get("role", ""), "level": m.get("level", 1)}
                for m in notifier().rota]

    @api.post("/login")
    def login(body: dict = Body(default={})):
        name = str(body.get("name") or "").strip()
        pin = str(body.get("pin") or "")
        notifier()
        wait = lockout.retry_after(name.lower())
        if wait:
            return JSONResponse(status_code=429, headers={"Retry-After": str(wait)}, content={
                "error": "locked", "retry_after_s": wait,
                "message_tr": f"Çok fazla hatalı deneme. {wait} saniye sonra tekrar deneyin."})
        member = find_member(name)
        good = member is not None and hmac.compare_digest(pin, str(member.get("pin", "")))
        if not good:
            lockout.fail(name.lower())
            rt.store.audit("saha", "login.fail", "", {"name": name[:60]})
            rt.store.commit()
            return JSONResponse(status_code=401, content={
                "error": "bad_credentials", "message_tr": "Ad veya PIN hatalı."})
        lockout.ok(name.lower())
        token = sessions.create(member["name"])
        rt.store.audit("saha", "login", "", {"name": member["name"]})
        rt.store.commit()
        return {"token": token, "expires_in": int(SESSION_TTL_S),
                "member": {"name": member["name"], "role": member.get("role", ""),
                           "level": member.get("level", 1)}}

    @api.post("/logout")
    def logout(member: dict = Depends(current)) -> dict:
        sessions.revoke(member["_token"])
        return {"ok": True}

    @api.get("/olaylar")
    def olaylar(tum: int = 0, member: dict = Depends(current)) -> dict:
        now = clock()
        rows = rt.store.query(
            "SELECT * FROM incident WHERE (state IN ('ACIK','ONAYLANDI') "
            "OR (state='KAPANDI' AND closed_at IS NOT NULL AND closed_at > ?)) "
            "ORDER BY opened_at DESC LIMIT 300", (now - CLOSED_VISIBLE_S,))
        rows = [r for r in rows if r["severity"] in VISIBLE_SEVERITIES]
        mine = my_notified(member["name"])
        if not tum:
            rows = [r for r in rows if int(r["id"]) in mine]
        work = latest_work_all()
        cards = [card(r, mine, work) for r in rows]
        cards.sort(key=lambda c: (not c["needs_ack"], -SEVERITY_RANK[c["severity"]],
                                  -c["opened_at"]))
        # First sight of an app notification is the app's delivery receipt.
        ids = [c["id"] for c in cards if c["id"] in mine]
        if ids:
            marks = ",".join("?" for _ in ids)
            rt.store.execute(
                f"UPDATE notification SET state=? WHERE channel='MOBIL' AND target=? "
                f"AND state!=? AND incident_id IN ({marks})",
                [esc.STATE_DELIVERED, member["name"], esc.STATE_DELIVERED, *ids])
            rt.store.commit()
        return {"member": {"name": member["name"], "role": member.get("role", ""),
                           "level": member.get("level", 1)},
                "server_ts": now, "olaylar": cards}

    @api.get("/olay/{iid}")
    def olay(iid: int, member: dict = Depends(current)) -> dict:
        row = incident_row(iid)
        mine = my_notified(member["name"])
        work = latest_work_all()
        try:
            ev = json.loads(row.get("evidence") or "{}")
        except json.JSONDecodeError:
            ev = {}
        try:
            ruled = json.loads(row.get("ruled_out") or "[]")
        except json.JSONDecodeError:
            ruled = []
        live = None
        try:
            live = rt.panel(row["panel_key"])
        except Exception:  # noqa: BLE001 - an unknown panel must not break the detail view
            live = None

        pano: dict[str, Any] = {"panel_key": row["panel_key"], "name": None, "dso": None,
                                "site": None, "lat": None, "lon": None,
                                "maps_url": None, "geo_url": None}
        if live is not None:
            pano.update(name=live.name, dso=live.dso, site=live.site)
            if live.lat or live.lon:
                lat, lon = live.lat, live.lon
                label = quote(f"{row['panel_key']}")
                pano.update(lat=lat, lon=lon,
                            maps_url=f"https://www.google.com/maps/dir/?api=1&destination={lat},{lon}",
                            geo_url=f"geo:{lat},{lon}?q={lat},{lon}({label})")

        j = ev.get("joint") or {}
        olcum = {
            "theta_k": j.get("theta_k"), "temp_c": j.get("temp_c"),
            "sibling_median_c": j.get("sibling_median_c"), "delta_t_k": j.get("delta_t_k"),
            "current_a": j.get("current_a"), "rated_a": j.get("rated_a"),
            "load_factor": ev.get("load_factor"), "slope_k_per_week": j.get("slope_k_per_week"),
            "health_index": ev.get("health_index"),
            "excess_resistance": ev.get("excess_resistance"),
            "eta": esc.eta_text(dict(row), live) or None,
            "theta_merdiven": _theta_ladder(),
        }
        neden = {"aileler": ev.get("family_labels_tr") or [],
                 "terimler": [t.get("label_tr") for t in (ev.get("terms") or []) if t.get("label_tr")],
                 "elenenler": ruled if isinstance(ruled, list) else []}

        n = notifier()
        tl: list[dict] = [{"tip": "acilis", "ts": row["opened_at"], "metin": row.get("title") or ""}]
        for r in rt.store.notifications(iid, limit=200):
            who = n.on_rota(r["target"]) if r["channel"] in ("SMS", "SESLI", "TELEGRAM") else None
            tl.append({"tip": "bildirim", "ts": r["ts"], "kanal": r["channel"],
                       "hedef": (who or {}).get("name") or r["target"], "durum": r["state"]})
        for w in work_steps(iid):
            tl.append({"tip": "durum", "ts": w["ts"], "durum": w["durum"], "by": w["by"],
                       "not": w["not"]})
        if row.get("acked_at"):
            tl.append({"tip": "onay", "ts": row["acked_at"], "by": row.get("acked_by")})
        tl.sort(key=lambda e: e["ts"])
        return {"olay": card(row, mine, work), "pano": pano, "olcum": olcum, "neden": neden,
                "zaman_cizgisi": tl, "adimlar": list(WORK_STEPS)}

    @api.post("/olay/{iid}/onay")
    def onay(iid: int, member: dict = Depends(current)) -> dict:
        row = incident_row(iid)
        n = notifier()
        token = row.get("ack_token") or esc.ack_token(iid, n.salt)
        ok = bool(n.ack(iid, member["name"], token, channel="app"))
        reason = ""
        if not ok:
            last = n.rejected_acks[-1]["reason"] if n.rejected_acks else ""
            reason = _ACK_REASON_TR.get(last, "Onay reddedildi.")
        fresh = rt.store.one("SELECT * FROM incident WHERE id=?", (iid,)) or row
        return {"ok": ok, "reason": reason,
                "olay": card(fresh, my_notified(member["name"]), latest_work_all())}

    @api.post("/olay/{iid}/durum")
    def durum(iid: int, body: dict = Body(default={}), member: dict = Depends(current)) -> dict:
        step = str(body.get("durum") or "")
        if step not in WORK_STEPS:
            raise HTTPException(status_code=422, detail={
                "error": "bad_status", "izinli": list(WORK_STEPS),
                "message_tr": "Durum 'yolda', 'sahada' ya da 'tamam' olmalı."})
        row = incident_row(iid)
        if row["state"] != "ONAYLANDI":
            raise HTTPException(status_code=409, detail={
                "error": "not_acknowledged",
                "message_tr": ("Önce olayı onaylayın." if row["state"] == "ACIK"
                               else "Olay kapanmış; durum değiştirilemez.")})
        steps = work_steps(iid)
        if steps and WORK_STEPS.index(step) < WORK_STEPS.index(steps[-1]["durum"]):
            raise HTTPException(status_code=409, detail={
                "error": "backwards", "message_tr": "Durum geriye alınamaz."})
        note = "".join(ch for ch in str(body.get("not") or "") if ch.isprintable())[:NOTE_MAX]
        rt.store.audit("saha", "workorder.status", f"incident:{iid}",
                       {"durum": step, "by": member["name"], "not": note})
        rt.store.commit()
        return {"ok": True, "durum": step,
                "message_tr": ("İş tamamlandı olarak kaydedildi. Olay, sensörler yedi gün temiz "
                               "okuyana kadar açık kalır." if step == "tamam" else "Kaydedildi.")}

    # ------------------------------------------------------------ notify admin --

    admin = APIRouter(prefix="/api/notify", tags=["notify"])

    @admin.get("/status")
    def status() -> dict:
        n = notifier()
        st = n.status()
        st["saha_url"] = f"{n.public_url}/saha/" if n.public_url else None
        cfg = getattr(n, "config", None)
        st["config"] = ({"source": cfg.source, "warnings": list(cfg.warnings)}
                        if cfg is not None else None)
        return st

    @admin.post("/test")
    def test(body: dict = Body(default={})):
        who = str(body.get("to") or "").strip()
        if not who:
            raise HTTPException(status_code=422, detail={
                "error": "to_required",
                "message_tr": "'to' (nöbet listesindeki ad) zorunlu; herkese toplu test gönderilmez."})
        n = notifier()
        if n.on_rota(who) is None:
            raise HTTPException(status_code=404, detail={
                "error": "not_on_rota", "message_tr": f"'{who}' nöbet listesinde yok."})
        now = clock()
        if now - last_test["t"] < TEST_COOLDOWN_S:
            wait = int(TEST_COOLDOWN_S - (now - last_test["t"])) + 1
            return JSONResponse(status_code=429, headers={"Retry-After": str(wait)}, content={
                "error": "cooldown", "retry_after_s": wait,
                "message_tr": f"Test bildirimleri arasında {int(TEST_COOLDOWN_S)} saniye beklenir."})
        last_test["t"] = now
        res = n.send_test(who)
        return {"ok": all(r["ok"] for r in res) if res else False, "sonuc": res}

    @admin.get("/is-emri/{iid}")
    def is_emri(iid: int) -> dict:
        incident_row(iid)
        steps = work_steps(iid)
        return {"incident": iid, "adimlar": steps, "son": steps[-1] if steps else None}

    app.include_router(api)
    app.include_router(admin)
    SAHA_DIR.mkdir(parents=True, exist_ok=True)
    app.mount("/saha", NoStoreFiles(directory=str(SAHA_DIR), html=True), name="saha")

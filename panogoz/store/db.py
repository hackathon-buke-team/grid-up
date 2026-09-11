"""Storage layer.

ONE DRIVER: SQLite.  There is no second one, and this module used to say there
was.  ``PANOGOZ_DB`` takes a file path; a ``postgresql://`` DSN is rejected with
an error rather than quietly falling back, because a monitoring system that
silently writes somewhere other than where it was told is worse than one that
refuses to start.

TimescaleDB is the intended production path and it is not built.  What exists
towards it is ``schema.sql``, which is written in portable SQL so that it will
run on PostgreSQL unchanged.  What does NOT exist: the hypertable, compression
and continuous-aggregate statements, the bulk ``COPY`` write path, a connection
pool, and any measurement on a Timescale node.  Every scalability number quoted
for Timescale in the documents is derived from published figures, not from this
code.

The interface is deliberately narrow.  Everything the platform needs is here;
no module reaches past it to build SQL of its own.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Iterable, Sequence

SCHEMA_PATH = Path(__file__).with_name("schema.sql")
DEFAULT_PATH = Path(os.environ.get("PANOGOZ_HOME", ".")) / "panogoz.db"


class Store:
    """SQLite-backed store.

    Thread-safe by a single lock around a single connection.  At 20 samples per
    second fleet-wide this is nowhere near the bottleneck, and one connection
    keeps the WAL and the hash chain trivially consistent.
    """

    def __init__(self, path: str | Path | None = None) -> None:
        if path is not None and "://" in str(path):
            raise ValueError("Only SQLite file paths are supported; PostgreSQL/TimescaleDB is planned")
        self.path = Path(path or DEFAULT_PATH)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._con = sqlite3.connect(str(self.path), check_same_thread=False)
        self._con.row_factory = sqlite3.Row
        self._con.execute("PRAGMA synchronous = NORMAL")
        self._con.execute("PRAGMA busy_timeout = 5000")
        self.init_schema()

    # ------------------------------------------------------------ schema ---

    def init_schema(self) -> None:
        with self._lock:
            self._con.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
            self._con.commit()

    def reset(self) -> None:
        """Drop all rows but keep the schema.  Used by the demo reset button."""
        with self._lock:
            tables = [
                r["name"]
                for r in self._con.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                )
            ]
            for t in tables:
                self._con.execute(f"DELETE FROM {t}")
            self._con.commit()

    def close(self) -> None:
        with self._lock:
            self._con.close()

    # --------------------------------------------------------------- raw ---

    def execute(self, sql: str, params: Sequence[Any] = ()) -> sqlite3.Cursor:
        with self._lock:
            return self._con.execute(sql, params)

    def query(self, sql: str, params: Sequence[Any] = ()) -> list[dict]:
        with self._lock:
            return [dict(r) for r in self._con.execute(sql, params)]

    def one(self, sql: str, params: Sequence[Any] = ()) -> dict | None:
        rows = self.query(sql, params)
        return rows[0] if rows else None

    def commit(self) -> None:
        with self._lock:
            self._con.commit()

    def executemany(self, sql: str, rows: Iterable[Sequence[Any]]) -> None:
        rows = list(rows)
        if not rows:
            return
        with self._lock:
            self._con.executemany(sql, rows)

    # ------------------------------------------------------------ assets ---

    def outbox_rows(self, panel_key: str) -> list[dict]:
        return self.query("SELECT * FROM gateway_outbox WHERE panel_key=? ORDER BY id", (panel_key,))

    def outbox_add(self, panel_key: str, payload: bytes, retain: bool, capacity: int) -> int:
        with self._lock:
            n = self._con.execute("SELECT COUNT(*) FROM gateway_outbox WHERE panel_key=?",
                                  (panel_key,)).fetchone()[0]
            if n >= capacity:
                raise BufferError("Persistent gateway outbox is full; unacknowledged data retained")
            cur = self._con.execute(
                "INSERT INTO gateway_outbox(panel_key,payload,retain) VALUES (?,?,?)",
                (panel_key, payload, int(retain)))
            self._con.commit()
            return int(cur.lastrowid)

    def outbox_ack(self, row_id: int) -> None:
        with self._lock:
            self._con.execute("DELETE FROM gateway_outbox WHERE id=?", (row_id,))
            self._con.commit()

    def next_gateway_boot(self, panel_key: str, proposed: int) -> int:
        with self._lock:
            row = self._con.execute("SELECT boot FROM gateway_boot WHERE panel_key=?",
                                    (panel_key,)).fetchone()
            boot = max(proposed, int(row[0]) + 1 if row else proposed)
            self._con.execute("INSERT INTO gateway_boot(panel_key,boot) VALUES (?,?) "
                              "ON CONFLICT(panel_key) DO UPDATE SET boot=excluded.boot", (panel_key, boot))
            self._con.commit()
            return boot

    def upsert_panel(self, **kw: Any) -> None:
        cols = ", ".join(kw)
        marks = ", ".join("?" for _ in kw)
        updates = ", ".join(f"{k}=excluded.{k}" for k in kw if k != "panel_key")
        self.execute(
            f"INSERT INTO panel ({cols}) VALUES ({marks}) "
            f"ON CONFLICT(panel_key) DO UPDATE SET {updates}",
            list(kw.values()),
        )

    def upsert_joint(self, **kw: Any) -> None:
        cols = ", ".join(kw)
        marks = ", ".join("?" for _ in kw)
        updates = ", ".join(f"{k}=excluded.{k}" for k in kw if k not in ("panel_key", "joint_key"))
        self.execute(
            f"INSERT INTO joint ({cols}) VALUES ({marks}) "
            f"ON CONFLICT(panel_key, joint_key) DO UPDATE SET {updates}",
            list(kw.values()),
        )

    def upsert_device(self, **kw: Any) -> None:
        cols = ", ".join(kw)
        marks = ", ".join("?" for _ in kw)
        updates = ", ".join(f"{k}=excluded.{k}" for k in kw if k not in ("panel_key", "device_key"))
        self.execute(
            f"INSERT INTO device ({cols}) VALUES ({marks}) "
            f"ON CONFLICT(panel_key, device_key) DO UPDATE SET {updates}",
            list(kw.values()),
        )

    def panels(self) -> list[dict]:
        return self.query("SELECT * FROM panel ORDER BY panel_index")

    def panel(self, panel_key: str) -> dict | None:
        return self.one("SELECT * FROM panel WHERE panel_key = ?", (panel_key,))

    def joints(self, panel_key: str, monitored_only: bool = False) -> list[dict]:
        sql = "SELECT * FROM joint WHERE panel_key = ?"
        if monitored_only:
            sql += " AND monitored = 1"
        return self.query(sql + " ORDER BY joint_key", (panel_key,))

    def devices(self, panel_key: str | None = None) -> list[dict]:
        if panel_key:
            return self.query("SELECT * FROM device WHERE panel_key = ? ORDER BY device_key", (panel_key,))
        return self.query("SELECT * FROM device ORDER BY panel_key, device_key")

    # -------------------------------------------------------- timeseries ---

    def add_samples(self, rows: Iterable[tuple[float, str, str, float]]) -> None:
        self.executemany("INSERT INTO sample (ts, panel_key, channel, value) VALUES (?,?,?,?)", rows)

    def add_joint_samples(self, rows: Iterable[tuple[float, str, str, str, float]]) -> None:
        self.executemany(
            "INSERT INTO joint_sample (ts, panel_key, joint_key, channel, value) VALUES (?,?,?,?,?)",
            rows,
        )

    def series(self, panel_key: str, channel: str, since: float, until: float | None = None,
               limit: int = 20000) -> list[tuple[float, float]]:
        until = until if until is not None else time.time() + 1
        rows = self.query(
            "SELECT ts, value FROM sample WHERE panel_key=? AND channel=? AND ts>=? AND ts<=? "
            "ORDER BY ts LIMIT ?",
            (panel_key, channel, since, until, limit),
        )
        return [(r["ts"], r["value"]) for r in rows]

    def joint_series(self, panel_key: str, joint_key: str, channel: str, since: float,
                     until: float | None = None, limit: int = 20000) -> list[tuple[float, float]]:
        until = until if until is not None else time.time() + 1
        rows = self.query(
            "SELECT ts, value FROM joint_sample WHERE panel_key=? AND joint_key=? AND channel=? "
            "AND ts>=? AND ts<=? ORDER BY ts LIMIT ?",
            (panel_key, joint_key, channel, since, until, limit),
        )
        return [(r["ts"], r["value"]) for r in rows]

    def latest(self, panel_key: str, channel: str) -> tuple[float, float] | None:
        r = self.one(
            "SELECT ts, value FROM sample WHERE panel_key=? AND channel=? ORDER BY ts DESC LIMIT 1",
            (panel_key, channel),
        )
        return (r["ts"], r["value"]) if r else None

    def upsert_joint_daily(self, day: int, panel_key: str, joint_key: str, **kw: Any) -> None:
        kw = {"day": day, "panel_key": panel_key, "joint_key": joint_key, **kw}
        cols = ", ".join(kw)
        marks = ", ".join("?" for _ in kw)
        updates = ", ".join(f"{k}=excluded.{k}" for k in kw if k not in ("day", "panel_key", "joint_key"))
        self.execute(
            f"INSERT INTO joint_daily ({cols}) VALUES ({marks}) "
            f"ON CONFLICT(day, panel_key, joint_key) DO UPDATE SET {updates}",
            list(kw.values()),
        )

    def joint_daily(self, panel_key: str, joint_key: str, days: int = 120) -> list[dict]:
        return self.query(
            "SELECT * FROM joint_daily WHERE panel_key=? AND joint_key=? ORDER BY day DESC LIMIT ?",
            (panel_key, joint_key, days),
        )

    # ------------------------------------------------------------- state ---

    def save_joint_state(self, panel_key: str, joint_key: str, st: dict) -> None:
        kw = {"panel_key": panel_key, "joint_key": joint_key, **st, "updated_at": time.time()}
        cols = ", ".join(kw)
        marks = ", ".join("?" for _ in kw)
        updates = ", ".join(f"{k}=excluded.{k}" for k in kw if k not in ("panel_key", "joint_key"))
        self.execute(
            f"INSERT INTO joint_state ({cols}) VALUES ({marks}) "
            f"ON CONFLICT(panel_key, joint_key) DO UPDATE SET {updates}",
            list(kw.values()),
        )

    def joint_states(self, panel_key: str | None = None) -> list[dict]:
        if panel_key:
            return self.query("SELECT * FROM joint_state WHERE panel_key=? ORDER BY joint_key", (panel_key,))
        return self.query("SELECT * FROM joint_state")

    def save_panel_state(self, panel_key: str, **kw: Any) -> None:
        kw = {"panel_key": panel_key, **kw, "updated_at": time.time()}
        cols = ", ".join(kw)
        marks = ", ".join("?" for _ in kw)
        updates = ", ".join(f"{k}=excluded.{k}" for k in kw if k != "panel_key")
        self.execute(
            f"INSERT INTO panel_state ({cols}) VALUES ({marks}) "
            f"ON CONFLICT(panel_key) DO UPDATE SET {updates}",
            list(kw.values()),
        )

    def panel_states(self) -> list[dict]:
        return self.query(
            "SELECT ps.*, p.panel_index, p.site, p.name, p.dso, p.lat, p.lon "
            "FROM panel_state ps JOIN panel p USING (panel_key) ORDER BY p.panel_index"
        )

    def panel_state(self, panel_key: str) -> dict | None:
        return self.one(
            "SELECT ps.*, p.panel_index, p.site, p.name, p.dso, p.lat, p.lon "
            "FROM panel_state ps JOIN panel p USING (panel_key) WHERE panel_key = ?",
            (panel_key,),
        )

    # --------------------------------------------------------- incidents ---

    def open_incident(self, **kw: Any) -> int:
        now = time.time()
        kw.setdefault("opened_at", now)
        kw.setdefault("updated_at", now)
        for k in ("evidence", "ruled_out"):
            if k in kw and not isinstance(kw[k], str):
                kw[k] = json.dumps(kw[k], ensure_ascii=False)
        cols = ", ".join(kw)
        marks = ", ".join("?" for _ in kw)
        cur = self.execute(f"INSERT INTO incident ({cols}) VALUES ({marks})", list(kw.values()))
        return int(cur.lastrowid)

    def update_incident(self, incident_id: int, **kw: Any) -> None:
        kw["updated_at"] = time.time()
        for k in ("evidence", "ruled_out"):
            if k in kw and not isinstance(kw[k], str):
                kw[k] = json.dumps(kw[k], ensure_ascii=False)
        sets = ", ".join(f"{k}=?" for k in kw)
        self.execute(f"UPDATE incident SET {sets} WHERE id=?", [*kw.values(), incident_id])

    def find_open_incident(self, panel_key: str, joint_key: str | None, mode: str) -> dict | None:
        if joint_key is None:
            return self.one(
                "SELECT * FROM incident WHERE panel_key=? AND joint_key IS NULL AND mode=? "
                "AND state != 'KAPANDI' ORDER BY id DESC LIMIT 1",
                (panel_key, mode),
            )
        return self.one(
            "SELECT * FROM incident WHERE panel_key=? AND joint_key=? AND mode=? "
            "AND state != 'KAPANDI' ORDER BY id DESC LIMIT 1",
            (panel_key, joint_key, mode),
        )

    def incidents(self, state: str | None = None, limit: int = 500) -> list[dict]:
        if state:
            return self.query(
                "SELECT * FROM incident WHERE state=? ORDER BY opened_at DESC LIMIT ?", (state, limit)
            )
        return self.query("SELECT * FROM incident ORDER BY opened_at DESC LIMIT ?", (limit,))

    def add_suppression(self, panel_key: str, reason: str, joint_key: str | None = None,
                        mode: str | None = None, detail: dict | None = None) -> None:
        self.execute(
            "INSERT INTO suppression (ts, panel_key, joint_key, mode, reason, detail) VALUES (?,?,?,?,?,?)",
            (time.time(), panel_key, joint_key, mode, reason,
             json.dumps(detail or {}, ensure_ascii=False)),
        )

    def suppressions(self, since: float | None = None, limit: int = 500) -> list[dict]:
        since = since if since is not None else time.time() - 86400
        return self.query(
            "SELECT * FROM suppression WHERE ts >= ? ORDER BY ts DESC LIMIT ?", (since, limit)
        )

    def add_notification(self, **kw: Any) -> int:
        kw.setdefault("ts", time.time())
        cols = ", ".join(kw)
        marks = ", ".join("?" for _ in kw)
        cur = self.execute(f"INSERT INTO notification ({cols}) VALUES ({marks})", list(kw.values()))
        return int(cur.lastrowid)

    def notifications(self, incident_id: int | None = None, limit: int = 200) -> list[dict]:
        if incident_id is not None:
            return self.query(
                "SELECT * FROM notification WHERE incident_id=? ORDER BY ts DESC LIMIT ?",
                (incident_id, limit),
            )
        return self.query("SELECT * FROM notification ORDER BY ts DESC LIMIT ?", (limit,))

    # ------------------------------------------------------------- audit ---

    def audit(self, actor: str, action: str, subject: str = "", detail: dict | None = None) -> str:
        """Append one hash-chained audit row and return its hash."""
        with self._lock:
            prev = self.one("SELECT hash FROM audit ORDER BY id DESC LIMIT 1")
            prev_hash = prev["hash"] if prev else ""
            ts = time.time()
            body = json.dumps(detail or {}, ensure_ascii=False, sort_keys=True)
            payload = f"{prev_hash}|{ts:.6f}|{actor}|{action}|{subject}|{body}"
            digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
            self.execute(
                "INSERT INTO audit (ts, actor, action, subject, detail, prev_hash, hash) "
                "VALUES (?,?,?,?,?,?,?)",
                (ts, actor, action, subject, body, prev_hash, digest),
            )
            return digest

    def verify_chain(self) -> dict:
        """Recompute the whole chain.  Returns the first broken row, if any."""
        rows = self.query("SELECT * FROM audit ORDER BY id")
        prev_hash = ""
        for r in rows:
            payload = f"{prev_hash}|{r['ts']:.6f}|{r['actor']}|{r['action']}|{r['subject']}|{r['detail']}"
            digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
            if digest != r["hash"] or r["prev_hash"] != prev_hash:
                return {"ok": False, "broken_at": r["id"], "rows": len(rows)}
            prev_hash = r["hash"]
        return {"ok": True, "broken_at": None, "rows": len(rows)}

    # -------------------------------------------------------------- PRPD ---

    def add_prpd(self, ts: float, panel_key: str, device: str, klass: str,
                 features: dict, hist: bytes) -> None:
        self.execute(
            "INSERT OR REPLACE INTO prpd (ts, panel_key, device, klass, features, hist) "
            "VALUES (?,?,?,?,?,?)",
            (ts, panel_key, device, klass, json.dumps(features, ensure_ascii=False), hist),
        )

    def latest_prpd(self, panel_key: str) -> dict | None:
        return self.one(
            "SELECT * FROM prpd WHERE panel_key=? ORDER BY ts DESC LIMIT 1", (panel_key,)
        )

    def prpd_history(self, panel_key: str, limit: int = 200) -> list[dict]:
        return self.query(
            "SELECT ts, klass, features FROM prpd WHERE panel_key=? ORDER BY ts DESC LIMIT ?",
            (panel_key, limit),
        )

    # ----------------------------------------------------------- retention --

    def prune(self, raw_days: int = 90) -> dict:
        """Apply the retention policy.  Daily rollups are never pruned."""
        cutoff = time.time() - raw_days * 86400
        with self._lock:
            a = self._con.execute("DELETE FROM sample WHERE ts < ?", (cutoff,)).rowcount
            b = self._con.execute("DELETE FROM joint_sample WHERE ts < ?", (cutoff,)).rowcount
            self._con.commit()
        return {"sample": a, "joint_sample": b}

    def stats(self) -> dict:
        out = {}
        for t in ("panel", "device", "joint", "sample", "joint_sample", "joint_daily",
                  "incident", "suppression", "notification", "audit", "prpd"):
            r = self.one(f"SELECT COUNT(*) AS n FROM {t}")
            out[t] = r["n"] if r else 0
        try:
            out["bytes"] = self.path.stat().st_size
        except OSError:
            out["bytes"] = 0
        return out


_default: Store | None = None


def get_store(path: str | Path | None = None) -> Store:
    global _default
    if _default is None:
        _default = Store(path)
    return _default


def set_store(store: Store) -> None:
    global _default
    _default = store

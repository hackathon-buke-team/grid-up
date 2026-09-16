"""SQLite outbox: store-and-forward reliability on the publishing side (see
CLAUDE.md Sec.2 "QoS1 store-and-forward"). When the bus is disconnected, a
publisher enqueues envelopes here instead of losing them; once reconnected,
`pending()` replays them in sequence order and `mark_delivered()` retires
each one after a successful publish.
"""
from __future__ import annotations

import sqlite3
import threading


class Outbox:
    def __init__(self, db_path: str) -> None:
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS outbox (
                seq INTEGER PRIMARY KEY,
                topic TEXT NOT NULL,
                payload BLOB NOT NULL,
                delivered INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        self._conn.commit()

    def enqueue(self, seq: int, topic: str, payload: bytes) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR IGNORE INTO outbox (seq, topic, payload, delivered) VALUES (?, ?, ?, 0)",
                (seq, topic, payload),
            )
            self._conn.commit()

    def mark_delivered(self, seq: int) -> None:
        with self._lock:
            self._conn.execute("UPDATE outbox SET delivered = 1 WHERE seq = ?", (seq,))
            self._conn.commit()

    def pending(self) -> list[tuple[int, str, bytes]]:
        with self._lock:
            cur = self._conn.execute(
                "SELECT seq, topic, payload FROM outbox WHERE delivered = 0 ORDER BY seq ASC"
            )
            return cur.fetchall()

    def close(self) -> None:
        self._conn.close()

"""Forward-only sequence watermark: duplicate detection on the consuming
side (see CLAUDE.md Sec.2 "sira numarasi ileri-yalniz su damgasi"). QoS1
guarantees at-least-once delivery, so the same envelope can legitimately
arrive twice (e.g. redelivered after a reconnect before the original PUBACK
was received). A message whose seq is <= the highest seq already accepted
for that device is a duplicate and must be dropped; the watermark itself
only ever moves forward, never backward, even if a lower/late seq arrives.
"""
from __future__ import annotations

import sqlite3
import threading


class Watermark:
    def __init__(self, db_path: str) -> None:
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS watermark (
                device_id TEXT PRIMARY KEY,
                last_seq INTEGER NOT NULL
            )
            """
        )
        self._conn.commit()

    def should_process(self, device_id: str, seq: int) -> bool:
        """Returns True (and advances the watermark) iff seq is new."""
        with self._lock:
            cur = self._conn.execute(
                "SELECT last_seq FROM watermark WHERE device_id = ?", (device_id,)
            )
            row = cur.fetchone()
            last = row[0] if row is not None else -1
            if seq <= last:
                return False
            self._conn.execute(
                """
                INSERT INTO watermark (device_id, last_seq) VALUES (?, ?)
                ON CONFLICT(device_id) DO UPDATE SET last_seq = excluded.last_seq
                """,
                (device_id, seq),
            )
            self._conn.commit()
            return True

    def close(self) -> None:
        self._conn.close()

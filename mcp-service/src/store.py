"""Service-owned durable event store: append-first SQLite ordered log."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from threading import RLock
from typing import Iterator

from events import EventEnvelope


class DurableEventStore:
    """Append-first SQLite log with an ordered, replayable sequence."""

    def __init__(self, path: str, service: str, store_id: str) -> None:
        self.path = path
        self.service = service
        self.store_id = store_id
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._connection = sqlite3.connect(path, check_same_thread=False, timeout=10)
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA synchronous=FULL")
        self._connection.execute("PRAGMA busy_timeout=10000")
        self._create_schema()

    def _create_schema(self) -> None:
        with self._connection:
            self._connection.execute(
                """CREATE TABLE IF NOT EXISTS events (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    ref_id TEXT UNIQUE NOT NULL,
                    event_type TEXT NOT NULL,
                    ts_ms INTEGER NOT NULL,
                    envelope TEXT NOT NULL
                )"""
            )
            self._connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type)"
            )
            self._connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_events_type_ts_seq "
                "ON events(event_type, ts_ms, seq)"
            )
            self._connection.execute(
                """CREATE TABLE IF NOT EXISTS ingest_offsets (
                    path TEXT PRIMARY KEY,
                    byte_offset INTEGER NOT NULL,
                    last_window INTEGER
                )"""
            )

    def append_once(self, event: EventEnvelope) -> tuple[int, bool]:
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                row = self._connection.execute(
                    "SELECT seq FROM events WHERE ref_id = ?", (event.ref_id,)
                ).fetchone()
                if row is not None:
                    self._connection.commit()
                    return int(row[0]), False
                cursor = self._connection.execute(
                    "INSERT INTO events (ref_id, event_type, ts_ms, envelope) "
                    "VALUES (?, ?, ?, ?)",
                    (event.ref_id, event.event_type, event.ts_ms, event.to_json()),
                )
                seq = int(cursor.lastrowid)
                self._connection.commit()
                return seq, True
            except Exception:
                self._connection.rollback()
                raise

    def append(self, event: EventEnvelope) -> int:
        seq, _ = self.append_once(event)
        return seq

    def read(
        self,
        event_type: str | None = None,
        since_seq: int = 0,
        limit: int = 1000,
        start_ms: int | None = None,
        end_ms: int | None = None,
        newest_first: bool = False,
    ) -> list[EventEnvelope]:
        query = "SELECT envelope FROM events WHERE seq > ?"
        params: list[object] = [since_seq]
        if event_type is not None:
            query += " AND event_type = ?"
            params.append(event_type)
        if start_ms is not None:
            query += " AND ts_ms >= ?"
            params.append(start_ms)
        if end_ms is not None:
            query += " AND ts_ms <= ?"
            params.append(end_ms)
        query += f" ORDER BY seq {'DESC' if newest_first else 'ASC'} LIMIT ?"
        params.append(limit)
        with self._lock:
            rows = self._connection.execute(query, params).fetchall()
        return [EventEnvelope.from_json(row[0]) for row in rows]

    def replay(self, from_seq: int = 0) -> Iterator[EventEnvelope]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT envelope FROM events WHERE seq > ? ORDER BY seq ASC",
                (from_seq,),
            ).fetchall()
        yield from (EventEnvelope.from_json(row[0]) for row in rows)

    def get_ingest_offset(self, path: str) -> tuple[int, int | None] | None:
        """Return (byte_offset, last_sample_window) for a source file, or None if unseen."""
        with self._lock:
            row = self._connection.execute(
                "SELECT byte_offset, last_window FROM ingest_offsets WHERE path = ?", (path,)
            ).fetchone()
        return (int(row[0]), row[1]) if row else None

    def set_ingest_offset(self, path: str, byte_offset: int, last_window: int | None) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                "INSERT INTO ingest_offsets (path, byte_offset, last_window) VALUES (?, ?, ?) "
                "ON CONFLICT(path) DO UPDATE SET byte_offset = excluded.byte_offset, "
                "last_window = excluded.last_window",
                (path, byte_offset, last_window),
            )

    def close(self) -> None:
        with self._lock:
            self._connection.close()

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from typing import Any

from .settings import DATA_DIR, HISTORY_RETENTION_HOURS


class HistoryStore:
    def __init__(self) -> None:
        os.makedirs(DATA_DIR, exist_ok=True)
        self.path = os.path.join(DATA_DIR, "sentinel.db")
        self.lock = threading.Lock()
        self._init()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=8)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=NORMAL")
        return connection

    def _init(self) -> None:
        with self._connect() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS samples (ts REAL PRIMARY KEY, payload TEXT NOT NULL)"
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_samples_ts ON samples(ts)")

    def write(self, point: dict[str, Any]) -> None:
        now = float(point["ts"])
        cutoff = now - HISTORY_RETENTION_HOURS * 3600
        with self.lock, self._connect() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO samples(ts, payload) VALUES(?, ?)",
                (now, json.dumps(point, separators=(",", ":"))),
            )
            connection.execute("DELETE FROM samples WHERE ts < ?", (cutoff,))

    def read(self, seconds: int, max_points: int = 720) -> list[dict[str, Any]]:
        cutoff = time.time() - seconds
        with self.lock, self._connect() as connection:
            rows = connection.execute(
                "SELECT payload FROM samples WHERE ts >= ? ORDER BY ts ASC", (cutoff,)
            ).fetchall()
        points = [json.loads(row[0]) for row in rows]
        if len(points) <= max_points:
            return points
        stride = max(1, len(points) // max_points)
        sampled = points[::stride]
        if sampled[-1] != points[-1]:
            sampled.append(points[-1])
        return sampled[-max_points:]

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
            # v1.1.4：日汇总表——**永不参与 retention 裁剪**，用于自然月/自然年/流量周期累计。
            # 没有它时，"本年额度"只能从 31 天内样本算，等价于只有最近一个月；
            # samples 被裁掉后当月/当年历史就永远丢了（2026-09-29 用户要求按自然月/年实时加总）。
            connection.execute(
                "CREATE TABLE IF NOT EXISTS daily ("
                " day TEXT PRIMARY KEY,"           # 本地日期 YYYY-MM-DD
                " kwh REAL NOT NULL DEFAULT 0,"    # 当日电量
                " cost REAL NOT NULL DEFAULT 0,"   # 当日电费（分时电价折算）
                " net_bytes REAL NOT NULL DEFAULT 0,"  # 当日出+入流量合计（采样点只存了合计）
                " updated REAL NOT NULL DEFAULT 0)"
            )
            connection.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")

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

    # ===== v1.1.4：日汇总（累计口径）=====
    def meta_get(self, key: str, default: str | None = None) -> str | None:
        with self.lock, self._connect() as connection:
            row = connection.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return row[0] if row else default

    def meta_set(self, key: str, value: str) -> None:
        with self.lock, self._connect() as connection:
            connection.execute(
                "INSERT INTO meta(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )

    def daily_all(self) -> list[dict[str, Any]]:
        """全部日汇总行（按日期升序）。行数等于「有数据的天数」，与 retention 无关。"""
        with self.lock, self._connect() as connection:
            rows = connection.execute(
                "SELECT day, kwh, cost, net_bytes, updated FROM daily ORDER BY day ASC"
            ).fetchall()
        return [
            {"day": r[0], "kwh": r[1], "cost": r[2], "net_bytes": r[3], "updated": r[4]}
            for r in rows
        ]

    def rollup_into(self, integrate, now: float | None = None) -> int:
        """增量把 samples 汇入 daily，返回本次处理的样本数。

        integrate(prev_ts, prev_payload, ts, payload, acc) 由调用方注入（电价/单位换算属业务逻辑，
        留在 app 层）；acc 是 {day: {kwh, cost, net_bytes}} 累加器。
        「读样本 + 写 daily + 推进 rollup_last_ts」在同一事务里，避免重复计数。
        """
        now = time.time() if now is None else float(now)
        with self.lock, self._connect() as connection:
            raw_last = connection.execute("SELECT value FROM meta WHERE key = 'rollup_last_ts'").fetchone()
            last = float(raw_last[0]) if raw_last else 0.0
            rows = connection.execute(
                "SELECT ts, payload FROM samples WHERE ts > ? ORDER BY ts ASC", (last,)
            ).fetchall()
            if not rows:
                return 0
            prev: tuple[float, dict[str, Any]] | None = None
            if last:
                head = connection.execute(
                    "SELECT ts, payload FROM samples WHERE ts <= ? ORDER BY ts DESC LIMIT 1", (last,)
                ).fetchone()
                if head:
                    try:
                        prev = (float(head[0]), json.loads(head[1]))
                    except (TypeError, ValueError):
                        prev = None
            acc: dict[str, dict[str, float]] = {}
            newest = last
            for ts, payload in rows:
                try:
                    point = json.loads(payload)
                except (TypeError, ValueError):
                    continue
                if prev is not None:
                    integrate(prev[0], prev[1], float(ts), point, acc)
                prev = (float(ts), point)
                newest = float(ts)
            for day, a in acc.items():
                connection.execute(
                    "INSERT INTO daily(day, kwh, cost, net_bytes, updated) VALUES(?, ?, ?, ?, ?) "
                    "ON CONFLICT(day) DO UPDATE SET kwh = kwh + excluded.kwh, cost = cost + excluded.cost, "
                    "net_bytes = net_bytes + excluded.net_bytes, updated = excluded.updated",
                    (day, a.get("kwh", 0.0), a.get("cost", 0.0), a.get("net_bytes", 0.0), now),
                )
            connection.execute(
                "INSERT INTO meta(key, value) VALUES('rollup_last_ts', ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (repr(newest),),
            )
        return len(rows)

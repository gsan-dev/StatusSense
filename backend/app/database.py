"""Esquema SQLite y helpers de acceso a datos (async, via aiosqlite)."""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

import aiosqlite

from .config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS monitors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    type TEXT NOT NULL CHECK(type IN ('http', 'tcp', 'ping', 'dns')),
    target TEXT NOT NULL,
    interval_seconds INTEGER NOT NULL DEFAULT 60,
    timeout_seconds REAL NOT NULL DEFAULT 10.0,
    degradation_weight REAL NOT NULL DEFAULT 0.3,
    variance_weight REAL NOT NULL DEFAULT 0.2,
    uptime_weight REAL NOT NULL DEFAULT 0.5,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    monitor_id INTEGER NOT NULL REFERENCES monitors(id) ON DELETE CASCADE,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    success INTEGER NOT NULL,
    latency_ms REAL,
    http_status INTEGER,
    error_message TEXT
);
CREATE INDEX IF NOT EXISTS idx_checks_monitor_ts ON checks(monitor_id, timestamp);

CREATE TABLE IF NOT EXISTS health_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    monitor_id INTEGER NOT NULL REFERENCES monitors(id) ON DELETE CASCADE,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    health_score REAL NOT NULL,
    uptime_pct REAL,
    trend_slope REAL,
    variance_ratio REAL
);
CREATE INDEX IF NOT EXISTS idx_snapshots_monitor_ts ON health_snapshots(monitor_id, timestamp);

CREATE TABLE IF NOT EXISTS incidents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    monitor_id INTEGER NOT NULL REFERENCES monitors(id) ON DELETE CASCADE,
    started_at TIMESTAMP NOT NULL,
    resolved_at TIMESTAMP,
    incident_type TEXT CHECK(incident_type IN ('sudden_outage', 'progressive_degradation')),
    min_health_score REAL
);
CREATE INDEX IF NOT EXISTS idx_incidents_monitor ON incidents(monitor_id);

CREATE TABLE IF NOT EXISTS notification_channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL CHECK(type IN ('telegram', 'webhook')),
    name TEXT NOT NULL DEFAULT '',
    config_json TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1
);
"""

_db: aiosqlite.Connection | None = None


async def init_db() -> None:
    global _db
    _db = await aiosqlite.connect(settings.db_path)
    _db.row_factory = aiosqlite.Row
    await _db.execute("PRAGMA foreign_keys = ON;")
    await _db.executescript(SCHEMA)
    await _db.commit()


async def close_db() -> None:
    global _db
    if _db is not None:
        await _db.close()
        _db = None


def get_db() -> aiosqlite.Connection:
    if _db is None:
        raise RuntimeError("La base de datos no esta inicializada. Llama a init_db() primero.")
    return _db


@asynccontextmanager
async def transaction() -> AsyncIterator[aiosqlite.Connection]:
    db = get_db()
    try:
        yield db
        await db.commit()
    except Exception:
        await db.rollback()
        raise

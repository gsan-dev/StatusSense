"""Exportar/importar configuracion (monitores + canales de notificacion) para
poder migrar StatusSense entre maquinas sin perder los monitores configurados.

Deliberadamente no incluye el historico (checks/health_snapshots/incidents):
el objetivo es portar la *configuracion*, no los datos historicos.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter

from ..database import get_db
from ..models import ExportBundle, ImportResult, MonitorCreate, NotificationChannelCreate
from ..scheduler import schedule_monitor

router = APIRouter(prefix="/api", tags=["export-import"])


@router.get("/export", response_model=ExportBundle)
async def export_config():
    db = get_db()
    monitor_rows = await (await db.execute("SELECT * FROM monitors ORDER BY id")).fetchall()
    channel_rows = await (await db.execute("SELECT * FROM notification_channels ORDER BY id")).fetchall()

    monitors = [
        MonitorCreate(
            name=r["name"],
            type=r["type"],
            target=r["target"],
            interval_seconds=r["interval_seconds"],
            timeout_seconds=r["timeout_seconds"],
            degradation_weight=r["degradation_weight"],
            variance_weight=r["variance_weight"],
            uptime_weight=r["uptime_weight"],
            active=bool(r["active"]),
        )
        for r in monitor_rows
    ]
    channels = [
        NotificationChannelCreate(
            type=r["type"],
            name=r["name"],
            config=json.loads(r["config_json"]),
            active=bool(r["active"]),
        )
        for r in channel_rows
    ]

    return ExportBundle(
        exported_at=datetime.now(timezone.utc).isoformat(),
        monitors=monitors,
        notification_channels=channels,
    )


@router.post("/import", response_model=ImportResult)
async def import_config(bundle: ExportBundle):
    db = get_db()

    monitors_imported = 0
    for m in bundle.monitors:
        cursor = await db.execute(
            """INSERT INTO monitors (name, type, target, interval_seconds, timeout_seconds,
                degradation_weight, variance_weight, uptime_weight, active)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                m.name,
                m.type,
                m.target,
                m.interval_seconds,
                m.timeout_seconds,
                m.degradation_weight,
                m.variance_weight,
                m.uptime_weight,
                int(m.active),
            ),
        )
        if m.active:
            schedule_monitor(cursor.lastrowid, m.interval_seconds)
        monitors_imported += 1

    channels_imported = 0
    for c in bundle.notification_channels:
        await db.execute(
            "INSERT INTO notification_channels (type, name, config_json, active) VALUES (?, ?, ?, ?)",
            (c.type, c.name, json.dumps(c.config), int(c.active)),
        )
        channels_imported += 1

    await db.commit()
    return ImportResult(monitors_imported=monitors_imported, channels_imported=channels_imported)

"""Reglas de cuando notificar: envia un mensaje a todos los canales activos
cuando se abre o se resuelve un incidente (caida o degradacion progresiva).
"""
from __future__ import annotations

import json
from typing import Literal

from ..database import get_db
from .telegram import send_telegram
from .webhook import send_webhook

IncidentEvent = Literal["opened", "resolved"]

_TYPE_LABELS = {
    "sudden_outage": "caida subita",
    "progressive_degradation": "degradacion progresiva",
}


def _build_message(monitor_name: str, event: IncidentEvent, incident_type: str | None, health_score: float) -> str:
    label = _TYPE_LABELS.get(incident_type or "", incident_type or "incidente")
    if event == "opened":
        return f"[StatusSense] {monitor_name}: {label} detectada. Health score: {health_score}"
    return f"[StatusSense] {monitor_name}: incidente resuelto. Health score: {health_score}"


async def _send_to_channel(channel_type: str, config: dict, message: str, **extra) -> bool:
    if channel_type == "telegram":
        return await send_telegram(config.get("bot_token", ""), config.get("chat_id", ""), message)
    if channel_type == "webhook":
        return await send_webhook(config.get("url", ""), {"message": message, **extra})
    return False


async def dispatch_incident_notification(
    monitor_name: str,
    event: IncidentEvent,
    incident_type: str | None,
    health_score: float,
) -> None:
    db = get_db()
    cursor = await db.execute(
        "SELECT type, config_json FROM notification_channels WHERE active = 1"
    )
    rows = await cursor.fetchall()
    if not rows:
        return

    message = _build_message(monitor_name, event, incident_type, health_score)

    for row in rows:
        config = json.loads(row["config_json"])
        await _send_to_channel(
            row["type"],
            config,
            message,
            monitor=monitor_name,
            event=event,
            incident_type=incident_type,
            health_score=health_score,
        )


async def send_test_notification(channel_type: str, config: dict) -> bool:
    message = "[StatusSense] Notificacion de prueba: si ves esto, el canal esta bien configurado."
    return await _send_to_channel(channel_type, config, message)

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException

from ..database import get_db
from ..models import NotificationChannelCreate, NotificationChannelOut
from ..notifications import send_test_notification

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


def _row_to_out(row) -> NotificationChannelOut:
    return NotificationChannelOut(
        id=row["id"],
        type=row["type"],
        name=row["name"],
        config=json.loads(row["config_json"]),
        active=bool(row["active"]),
    )


@router.get("", response_model=list[NotificationChannelOut])
async def list_channels():
    db = get_db()
    rows = await (await db.execute("SELECT * FROM notification_channels ORDER BY id")).fetchall()
    return [_row_to_out(r) for r in rows]


@router.post("", response_model=NotificationChannelOut, status_code=201)
async def create_channel(payload: NotificationChannelCreate):
    db = get_db()
    cursor = await db.execute(
        "INSERT INTO notification_channels (type, name, config_json, active) VALUES (?, ?, ?, ?)",
        (payload.type, payload.name, json.dumps(payload.config), int(payload.active)),
    )
    await db.commit()
    row = await (
        await db.execute("SELECT * FROM notification_channels WHERE id = ?", (cursor.lastrowid,))
    ).fetchone()
    return _row_to_out(row)


@router.post("/{channel_id}/test")
async def test_channel(channel_id: int):
    db = get_db()
    row = await (
        await db.execute("SELECT * FROM notification_channels WHERE id = ?", (channel_id,))
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Canal no encontrado")
    ok = await send_test_notification(row["type"], json.loads(row["config_json"]))
    return {"success": ok}


@router.delete("/{channel_id}", status_code=204)
async def delete_channel(channel_id: int):
    db = get_db()
    row = await (
        await db.execute("SELECT id FROM notification_channels WHERE id = ?", (channel_id,))
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Canal no encontrado")
    await db.execute("DELETE FROM notification_channels WHERE id = ?", (channel_id,))
    await db.commit()
    return None

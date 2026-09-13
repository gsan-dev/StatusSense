from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..config import settings
from ..database import get_db
from ..models import MonitorCreate, MonitorOut, MonitorUpdate
from ..scheduler import run_monitor_check, schedule_monitor, unschedule_monitor

router = APIRouter(prefix="/api/monitors", tags=["monitors"])


async def _row_to_monitor_out(row) -> MonitorOut:
    db = get_db()
    snapshot = await (
        await db.execute(
            "SELECT health_score, timestamp FROM health_snapshots WHERE monitor_id = ? ORDER BY timestamp DESC LIMIT 1",
            (row["id"],),
        )
    ).fetchone()
    last_check = await (
        await db.execute(
            "SELECT success, timestamp FROM checks WHERE monitor_id = ? ORDER BY timestamp DESC LIMIT 1",
            (row["id"],),
        )
    ).fetchone()

    health_score = snapshot["health_score"] if snapshot else None
    last_check_at = last_check["timestamp"] if last_check else None

    if not row["active"]:
        status = "paused"
    elif last_check is None:
        status = "pending"
    elif not last_check["success"]:
        status = "down"
    elif health_score is not None and health_score < settings.INCIDENT_HEALTH_THRESHOLD:
        status = "degraded"
    else:
        status = "up"

    return MonitorOut(
        id=row["id"],
        name=row["name"],
        type=row["type"],
        target=row["target"],
        interval_seconds=row["interval_seconds"],
        timeout_seconds=row["timeout_seconds"],
        degradation_weight=row["degradation_weight"],
        variance_weight=row["variance_weight"],
        uptime_weight=row["uptime_weight"],
        active=bool(row["active"]),
        created_at=row["created_at"],
        health_score=health_score,
        status=status,
        last_check_at=last_check_at,
    )


@router.get("", response_model=list[MonitorOut])
async def list_monitors():
    db = get_db()
    rows = await (await db.execute("SELECT * FROM monitors ORDER BY id")).fetchall()
    return [await _row_to_monitor_out(row) for row in rows]


@router.post("", response_model=MonitorOut, status_code=201)
async def create_monitor(payload: MonitorCreate):
    db = get_db()
    cursor = await db.execute(
        """INSERT INTO monitors (name, type, target, interval_seconds, timeout_seconds,
            degradation_weight, variance_weight, uptime_weight, active)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            payload.name,
            payload.type,
            payload.target,
            payload.interval_seconds,
            payload.timeout_seconds,
            payload.degradation_weight,
            payload.variance_weight,
            payload.uptime_weight,
            int(payload.active),
        ),
    )
    await db.commit()
    monitor_id = cursor.lastrowid
    if payload.active:
        schedule_monitor(monitor_id, payload.interval_seconds)
    row = await (await db.execute("SELECT * FROM monitors WHERE id = ?", (monitor_id,))).fetchone()
    return await _row_to_monitor_out(row)


@router.get("/{monitor_id}", response_model=MonitorOut)
async def get_monitor(monitor_id: int):
    db = get_db()
    row = await (await db.execute("SELECT * FROM monitors WHERE id = ?", (monitor_id,))).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Monitor no encontrado")
    return await _row_to_monitor_out(row)


@router.put("/{monitor_id}", response_model=MonitorOut)
async def update_monitor(monitor_id: int, payload: MonitorUpdate):
    db = get_db()
    row = await (await db.execute("SELECT * FROM monitors WHERE id = ?", (monitor_id,))).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Monitor no encontrado")

    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        return await _row_to_monitor_out(row)

    fields = []
    values = []
    for key, value in updates.items():
        fields.append(f"{key} = ?")
        values.append(int(value) if isinstance(value, bool) else value)
    values.append(monitor_id)
    await db.execute(f"UPDATE monitors SET {', '.join(fields)} WHERE id = ?", values)
    await db.commit()

    updated = await (await db.execute("SELECT * FROM monitors WHERE id = ?", (monitor_id,))).fetchone()

    if updated["active"]:
        schedule_monitor(monitor_id, updated["interval_seconds"])
    else:
        unschedule_monitor(monitor_id)

    return await _row_to_monitor_out(updated)


@router.delete("/{monitor_id}", status_code=204)
async def delete_monitor(monitor_id: int):
    db = get_db()
    row = await (await db.execute("SELECT id FROM monitors WHERE id = ?", (monitor_id,))).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Monitor no encontrado")
    unschedule_monitor(monitor_id)
    await db.execute("DELETE FROM monitors WHERE id = ?", (monitor_id,))
    await db.commit()
    return None


@router.delete("/{monitor_id}/history", status_code=204)
async def reset_monitor_history(monitor_id: int):
    """Borra el historico (checks, health snapshots e incidentes) de un monitor
    sin eliminar su configuracion, para volver a partir de una linea base limpia.
    """
    db = get_db()
    row = await (await db.execute("SELECT id FROM monitors WHERE id = ?", (monitor_id,))).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Monitor no encontrado")
    await db.execute("DELETE FROM checks WHERE monitor_id = ?", (monitor_id,))
    await db.execute("DELETE FROM health_snapshots WHERE monitor_id = ?", (monitor_id,))
    await db.execute("DELETE FROM incidents WHERE monitor_id = ?", (monitor_id,))
    await db.commit()
    return None


@router.post("/{monitor_id}/check-now", response_model=MonitorOut)
async def check_monitor_now(monitor_id: int):
    """Fuerza una comprobacion inmediata sin esperar al siguiente intervalo del scheduler."""
    db = get_db()
    row = await (await db.execute("SELECT id FROM monitors WHERE id = ?", (monitor_id,))).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Monitor no encontrado")
    await run_monitor_check(monitor_id)
    updated = await (await db.execute("SELECT * FROM monitors WHERE id = ?", (monitor_id,))).fetchone()
    return await _row_to_monitor_out(updated)

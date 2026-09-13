from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..database import get_db
from ..models import IncidentOut

router = APIRouter(prefix="/api/monitors", tags=["incidents"])


@router.get("/{monitor_id}/incidents", response_model=list[IncidentOut])
async def list_incidents(monitor_id: int):
    db = get_db()
    monitor = await (await db.execute("SELECT id FROM monitors WHERE id = ?", (monitor_id,))).fetchone()
    if monitor is None:
        raise HTTPException(status_code=404, detail="Monitor no encontrado")

    rows = await (
        await db.execute(
            "SELECT * FROM incidents WHERE monitor_id = ? ORDER BY started_at DESC",
            (monitor_id,),
        )
    ).fetchall()
    return [
        IncidentOut(
            id=r["id"],
            monitor_id=r["monitor_id"],
            started_at=r["started_at"],
            resolved_at=r["resolved_at"],
            incident_type=r["incident_type"],
            min_health_score=r["min_health_score"],
        )
        for r in rows
    ]

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ..database import get_db
from ..models import CheckOut

router = APIRouter(prefix="/api/monitors", tags=["checks"])


@router.get("/{monitor_id}/checks", response_model=list[CheckOut])
async def list_checks(monitor_id: int, limit: int = Query(100, ge=1, le=1000), offset: int = Query(0, ge=0)):
    db = get_db()
    monitor = await (await db.execute("SELECT id FROM monitors WHERE id = ?", (monitor_id,))).fetchone()
    if monitor is None:
        raise HTTPException(status_code=404, detail="Monitor no encontrado")

    rows = await (
        await db.execute(
            "SELECT * FROM checks WHERE monitor_id = ? ORDER BY timestamp DESC LIMIT ? OFFSET ?",
            (monitor_id, limit, offset),
        )
    ).fetchall()
    return [
        CheckOut(
            id=r["id"],
            monitor_id=r["monitor_id"],
            timestamp=r["timestamp"],
            success=bool(r["success"]),
            latency_ms=r["latency_ms"],
            http_status=r["http_status"],
            error_message=r["error_message"],
        )
        for r in rows
    ]

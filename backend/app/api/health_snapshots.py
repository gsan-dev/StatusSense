from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ..database import get_db
from ..models import HealthSnapshotOut

router = APIRouter(prefix="/api/monitors", tags=["health-snapshots"])


@router.get("/{monitor_id}/health-snapshots", response_model=list[HealthSnapshotOut])
async def list_health_snapshots(monitor_id: int, limit: int = Query(50, ge=1, le=500)):
    db = get_db()
    monitor = await (await db.execute("SELECT id FROM monitors WHERE id = ?", (monitor_id,))).fetchone()
    if monitor is None:
        raise HTTPException(status_code=404, detail="Monitor no encontrado")

    rows = await (
        await db.execute(
            "SELECT * FROM health_snapshots WHERE monitor_id = ? ORDER BY timestamp DESC LIMIT ?",
            (monitor_id, limit),
        )
    ).fetchall()
    return [
        HealthSnapshotOut(
            id=r["id"],
            monitor_id=r["monitor_id"],
            timestamp=r["timestamp"],
            health_score=r["health_score"],
            uptime_pct=r["uptime_pct"],
            trend_slope=r["trend_slope"],
            variance_ratio=r["variance_ratio"],
        )
        for r in rows
    ]

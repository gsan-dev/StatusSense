from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter

from ..database import get_db
from ..models import PublicMonitorStatus, StatusPageOut
from .monitors import _row_to_monitor_out

router = APIRouter(prefix="/api", tags=["status-page"])


@router.get("/status-page", response_model=StatusPageOut)
async def get_status_page():
    db = get_db()
    rows = await (await db.execute("SELECT * FROM monitors WHERE active = 1 ORDER BY name")).fetchall()

    since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()

    monitors: list[PublicMonitorStatus] = []
    for row in rows:
        out = await _row_to_monitor_out(row)
        stats = await (
            await db.execute(
                "SELECT COUNT(*) as total, SUM(success) as ok FROM checks WHERE monitor_id = ? AND timestamp >= ?",
                (row["id"], since),
            )
        ).fetchone()
        total = stats["total"] or 0
        ok = stats["ok"] or 0
        uptime_pct_24h = round((ok / total) * 100, 2) if total else None

        monitors.append(
            PublicMonitorStatus(
                name=out.name,
                type=out.type,
                status=out.status or "pending",
                health_score=out.health_score,
                uptime_pct_24h=uptime_pct_24h,
            )
        )

    return StatusPageOut(generated_at=datetime.now(timezone.utc).isoformat(), monitors=monitors)

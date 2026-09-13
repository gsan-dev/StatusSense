"""Orquestacion de checks periodicos por monitor con APScheduler.

Por cada ejecucion de un monitor:
1. Corre el check (http/tcp/ping/dns) y persiste el resultado.
2. Recalcula tendencia, varianza y health score sobre la ventana movil.
3. Evalua si hay que abrir/mantener/resolver un incidente.
4. Notifica por WebSocket (siempre) y por los canales configurados (en
   apertura/cierre de incidente).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from .analysis import (
    calcular_health_score,
    calcular_tendencia,
    calcular_variance_ratio,
    calcular_varianza,
    evaluate_incident,
    normalizar_tendencia,
    normalizar_varianza,
)
from .checks import run_check
from .config import settings
from .database import get_db
from .notifications import dispatch_incident_notification
from .websocket_manager import manager

logger = logging.getLogger("statussense.scheduler")

scheduler = AsyncIOScheduler()


async def _fetch_monitor(monitor_id: int):
    db = get_db()
    cursor = await db.execute("SELECT * FROM monitors WHERE id = ?", (monitor_id,))
    return await cursor.fetchone()


async def run_monitor_check(monitor_id: int) -> None:
    db = get_db()
    monitor = await _fetch_monitor(monitor_id)
    if monitor is None or not monitor["active"]:
        return

    result = await run_check(monitor["type"], monitor["target"], monitor["timeout_seconds"])

    now = datetime.now(timezone.utc).isoformat()
    cursor = await db.execute(
        """INSERT INTO checks (monitor_id, timestamp, success, latency_ms, http_status, error_message)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (monitor_id, now, int(result.success), result.latency_ms, result.http_status, result.error_message),
    )
    await db.commit()
    check_id = cursor.lastrowid

    window = settings.ANALYSIS_WINDOW_SIZE
    rows = await (
        await db.execute(
            "SELECT success, latency_ms FROM checks WHERE monitor_id = ? ORDER BY timestamp DESC LIMIT ?",
            (monitor_id, window),
        )
    ).fetchall()
    rows = list(reversed(rows))  # orden cronologico ascendente

    total = len(rows)
    successes = sum(1 for r in rows if r["success"])
    uptime_pct = (successes / total * 100) if total else 100.0

    latencies = [r["latency_ms"] for r in rows if r["success"] and r["latency_ms"] is not None]
    trend_slope = calcular_tendencia(latencies)
    variance_actual = calcular_varianza(latencies)

    # Baseline de varianza absoluta: usamos la propia serie historica de latencias
    # estables (fuera de la ventana actual) como referencia.
    history_row = await (
        await db.execute(
            "SELECT latency_ms FROM checks WHERE monitor_id = ? AND success = 1 ORDER BY timestamp DESC LIMIT 200",
            (monitor_id,),
        )
    ).fetchall()
    history_latencies = [r["latency_ms"] for r in history_row if r["latency_ms"] is not None]
    baseline_variance = calcular_varianza(history_latencies[window:]) if len(history_latencies) > window else variance_actual
    variance_ratio = calcular_variance_ratio(variance_actual, baseline_variance)

    trend_normalized = normalizar_tendencia(trend_slope, settings.TREND_SLOPE_THRESHOLD)
    variance_normalized = normalizar_varianza(variance_ratio)

    health_score = calcular_health_score(
        uptime_pct,
        trend_normalized,
        variance_normalized,
        uptime_weight=monitor["uptime_weight"],
        degradation_weight=monitor["degradation_weight"],
        variance_weight=monitor["variance_weight"],
    )

    await db.execute(
        """INSERT INTO health_snapshots (monitor_id, timestamp, health_score, uptime_pct, trend_slope, variance_ratio)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (monitor_id, now, health_score, uptime_pct, trend_slope, variance_ratio),
    )
    await db.commit()

    await _evaluate_incident(monitor_id, monitor["name"], health_score, now)

    await manager.broadcast(
        {
            "type": "check",
            "monitor_id": monitor_id,
            "check_id": check_id,
            "success": result.success,
            "latency_ms": result.latency_ms,
            "health_score": health_score,
            "timestamp": now,
        }
    )


async def _evaluate_incident(monitor_id: int, monitor_name: str, current_score: float, now: str) -> None:
    db = get_db()

    history_rows = await (
        await db.execute(
            "SELECT health_score FROM health_snapshots WHERE monitor_id = ? ORDER BY timestamp DESC LIMIT 6",
            (monitor_id,),
        )
    ).fetchall()
    # el snapshot actual ya esta insertado y sera el primero (mas reciente)
    score_history = [r["health_score"] for r in reversed(history_rows)][:-1] if history_rows else []

    open_incident = await (
        await db.execute(
            "SELECT * FROM incidents WHERE monitor_id = ? AND resolved_at IS NULL ORDER BY started_at DESC LIMIT 1",
            (monitor_id,),
        )
    ).fetchone()

    evaluation = evaluate_incident(
        score_history,
        current_score,
        settings.INCIDENT_HEALTH_THRESHOLD,
        settings.SUDDEN_DROP_THRESHOLD,
        currently_open=open_incident is not None,
    )

    if evaluation.should_open:
        await db.execute(
            "INSERT INTO incidents (monitor_id, started_at, incident_type, min_health_score) VALUES (?, ?, ?, ?)",
            (monitor_id, now, evaluation.incident_type, current_score),
        )
        await db.commit()
        await dispatch_incident_notification(monitor_name, "opened", evaluation.incident_type, current_score)
        await manager.broadcast(
            {"type": "incident_opened", "monitor_id": monitor_id, "incident_type": evaluation.incident_type, "health_score": current_score}
        )
    elif open_incident is not None:
        new_min = min(open_incident["min_health_score"], current_score)
        await db.execute(
            "UPDATE incidents SET min_health_score = ? WHERE id = ?", (new_min, open_incident["id"])
        )
        await db.commit()
        if evaluation.should_resolve:
            await db.execute(
                "UPDATE incidents SET resolved_at = ? WHERE id = ?", (now, open_incident["id"])
            )
            await db.commit()
            await dispatch_incident_notification(monitor_name, "resolved", open_incident["incident_type"], current_score)
            await manager.broadcast(
                {"type": "incident_resolved", "monitor_id": monitor_id, "incident_type": open_incident["incident_type"]}
            )


def schedule_monitor(monitor_id: int, interval_seconds: int) -> None:
    job_id = f"monitor_{monitor_id}"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
    scheduler.add_job(
        run_monitor_check,
        "interval",
        seconds=interval_seconds,
        args=[monitor_id],
        id=job_id,
        next_run_time=datetime.now(timezone.utc),
        max_instances=1,
        coalesce=True,
    )


def unschedule_monitor(monitor_id: int) -> None:
    job_id = f"monitor_{monitor_id}"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)


async def load_all_monitors() -> None:
    db = get_db()
    rows = await (await db.execute("SELECT id, interval_seconds FROM monitors WHERE active = 1")).fetchall()
    for row in rows:
        schedule_monitor(row["id"], row["interval_seconds"])
    logger.info("Programados %d monitores activos", len(rows))

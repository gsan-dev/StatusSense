"""Punto de entrada unico para ejecutar un check segun el tipo de monitor."""
from __future__ import annotations

from .dns_check import check_dns
from .http_check import check_http
from .ping_check import check_ping
from .result import CheckResult
from .tcp_check import check_tcp

_RUNNERS = {
    "http": check_http,
    "tcp": check_tcp,
    "ping": check_ping,
    "dns": check_dns,
}


async def run_check(monitor_type: str, target: str, timeout_seconds: float) -> CheckResult:
    runner = _RUNNERS.get(monitor_type)
    if runner is None:
        return CheckResult(success=False, latency_ms=None, error_message=f"Tipo de monitor desconocido: {monitor_type}")
    try:
        return await runner(target, timeout_seconds)
    except Exception as exc:  # salvaguarda: un check nunca debe tumbar el scheduler
        return CheckResult(success=False, latency_ms=None, error_message=f"Error inesperado: {exc}")

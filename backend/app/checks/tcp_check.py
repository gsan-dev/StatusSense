"""Check TCP asincrono: intenta abrir una conexion a host:puerto."""
from __future__ import annotations

import asyncio
import time

from .result import CheckResult


async def check_tcp(target: str, timeout_seconds: float) -> CheckResult:
    try:
        host, _, port_str = target.rpartition(":")
        if not host or not port_str.isdigit():
            return CheckResult(
                success=False,
                latency_ms=None,
                error_message="Formato invalido, se espera host:puerto",
            )
        port = int(port_str)
    except ValueError:
        return CheckResult(success=False, latency_ms=None, error_message="Formato invalido")

    start = time.perf_counter()
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=timeout_seconds
        )
        latency_ms = (time.perf_counter() - start) * 1000
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        return CheckResult(success=True, latency_ms=round(latency_ms, 2))
    except asyncio.TimeoutError:
        return CheckResult(success=False, latency_ms=None, error_message="Timeout")
    except OSError as exc:
        return CheckResult(success=False, latency_ms=None, error_message=str(exc))

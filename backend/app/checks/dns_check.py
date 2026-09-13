"""Check DNS: resuelve un dominio y mide la latencia de la resolucion."""
from __future__ import annotations

import time

import dns.exception
import dns.resolver

from .result import CheckResult


def _resolve(target: str, timeout_seconds: float) -> CheckResult:
    resolver = dns.resolver.Resolver()
    resolver.timeout = timeout_seconds
    resolver.lifetime = timeout_seconds
    start = time.perf_counter()
    try:
        answer = resolver.resolve(target, "A")
        latency_ms = (time.perf_counter() - start) * 1000
        resolved = ", ".join(rdata.to_text() for rdata in answer)
        return CheckResult(success=True, latency_ms=round(latency_ms, 2), error_message=None) if resolved else CheckResult(
            success=False, latency_ms=None, error_message="Sin resultados"
        )
    except dns.resolver.NXDOMAIN:
        return CheckResult(success=False, latency_ms=None, error_message="NXDOMAIN")
    except dns.exception.Timeout:
        return CheckResult(success=False, latency_ms=None, error_message="Timeout")
    except dns.exception.DNSException as exc:
        return CheckResult(success=False, latency_ms=None, error_message=str(exc))


async def check_dns(target: str, timeout_seconds: float) -> CheckResult:
    import asyncio

    return await asyncio.to_thread(_resolve, target, timeout_seconds)

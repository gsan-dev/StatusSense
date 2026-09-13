"""Check HTTP(S) asincrono."""
from __future__ import annotations

import time

import httpx

from .result import CheckResult


async def check_http(target: str, timeout_seconds: float) -> CheckResult:
    url = target if target.startswith(("http://", "https://")) else f"http://{target}"
    start = time.perf_counter()
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=timeout_seconds) as client:
            response = await client.get(url)
        latency_ms = (time.perf_counter() - start) * 1000
        success = response.status_code < 400
        return CheckResult(
            success=success,
            latency_ms=round(latency_ms, 2),
            http_status=response.status_code,
            error_message=None if success else f"HTTP {response.status_code}",
        )
    except httpx.TimeoutException:
        return CheckResult(success=False, latency_ms=None, http_status=None, error_message="Timeout")
    except httpx.HTTPError as exc:
        return CheckResult(success=False, latency_ms=None, http_status=None, error_message=str(exc))

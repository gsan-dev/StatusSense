"""Check ICMP (ping) usando el comando 'ping' del sistema.

Se evita usar sockets raw (requieren privilegios elevados / CAP_NET_RAW en
Linux) delegando en el binario 'ping' presente en cualquier imagen base,
tanto Windows como Linux.
"""
from __future__ import annotations

import asyncio
import platform
import re
import time

from .result import CheckResult

_LATENCY_RE = re.compile(r"time[=<]([\d.]+)\s*ms", re.IGNORECASE)


async def check_ping(target: str, timeout_seconds: float) -> CheckResult:
    is_windows = platform.system().lower() == "windows"
    timeout_ms = max(int(timeout_seconds * 1000), 1)
    if is_windows:
        cmd = ["ping", "-n", "1", "-w", str(timeout_ms), target]
    else:
        timeout_s = max(int(timeout_seconds), 1)
        cmd = ["ping", "-c", "1", "-W", str(timeout_s), target]

    start = time.perf_counter()
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout_seconds + 2)
        except asyncio.TimeoutError:
            proc.kill()
            return CheckResult(success=False, latency_ms=None, error_message="Timeout")

        elapsed_ms = (time.perf_counter() - start) * 1000
        output = stdout.decode(errors="ignore")

        if proc.returncode != 0:
            return CheckResult(success=False, latency_ms=None, error_message="Host inalcanzable")

        match = _LATENCY_RE.search(output)
        latency_ms = float(match.group(1)) if match else round(elapsed_ms, 2)
        return CheckResult(success=True, latency_ms=round(latency_ms, 2))
    except FileNotFoundError:
        return CheckResult(success=False, latency_ms=None, error_message="Comando 'ping' no disponible")

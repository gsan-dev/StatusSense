from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class CheckResult:
    success: bool
    latency_ms: Optional[float]
    http_status: Optional[int] = None
    error_message: Optional[str] = None

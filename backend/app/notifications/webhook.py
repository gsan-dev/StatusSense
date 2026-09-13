"""Notificaciones via webhook HTTP generico (POST JSON)."""
from __future__ import annotations

from typing import Any

import httpx


async def send_webhook(url: str, payload: dict[str, Any]) -> bool:
    if not url:
        return False
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload)
        return response.status_code < 400
    except httpx.HTTPError:
        return False

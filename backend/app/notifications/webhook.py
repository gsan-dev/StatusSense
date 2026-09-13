"""Notificaciones via webhook HTTP generico (POST JSON).

Si la URL es un webhook de Discord, se reformatea el payload al formato
que Discord espera ({"content": "..."}) en lugar del JSON generico, para
que un canal de tipo "webhook" funcione con Discord sin configuracion
adicional: basta con pegar la URL del webhook del canal de Discord.
"""
from __future__ import annotations

from typing import Any

import httpx


def _is_discord_webhook(url: str) -> bool:
    return "discord.com/api/webhooks" in url or "discordapp.com/api/webhooks" in url


async def send_webhook(url: str, payload: dict[str, Any]) -> bool:
    if not url:
        return False
    body = {"content": payload.get("message", "StatusSense")} if _is_discord_webhook(url) else payload
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=body)
        return response.status_code < 400
    except httpx.HTTPError:
        return False

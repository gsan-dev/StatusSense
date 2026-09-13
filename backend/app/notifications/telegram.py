"""Notificaciones via Telegram Bot API."""
from __future__ import annotations

import httpx


async def send_telegram(bot_token: str, chat_id: str, text: str) -> bool:
    if not bot_token or not chat_id:
        return False
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json={"chat_id": chat_id, "text": text})
        return response.status_code == 200
    except httpx.HTTPError:
        return False

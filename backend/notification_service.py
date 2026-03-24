"""
Notification Service - Sends push notifications via ntfy.sh, Pushover, or Telegram.
Default: ntfy.sh (free, no account needed).
"""

import os
import logging
import httpx
from typing import Optional

logger = logging.getLogger("aether.notify")

NTFY_TOPIC = os.getenv("NTFY_TOPIC", "aether-ai-alerts")
NTFY_URL = os.getenv("NTFY_URL", "https://ntfy.sh")
PUSHOVER_TOKEN = os.getenv("PUSHOVER_APP_TOKEN", "")
PUSHOVER_USER = os.getenv("PUSHOVER_USER_KEY", "")


async def send_notification(
    title: str,
    message: str,
    priority: int = 3,  # 1-5 (1=min, 5=max)
    tags: Optional[list[str]] = None,
    url: Optional[str] = None,
) -> bool:
    """Send a push notification. Returns True if successful."""

    success = False

    # Try ntfy.sh (default, always available)
    try:
        success = await _send_ntfy(title, message, priority, tags, url)
    except Exception as e:
        logger.error(f"Ntfy failed: {e}")

    # Try Pushover if configured
    if PUSHOVER_TOKEN and PUSHOVER_USER:
        try:
            await _send_pushover(title, message, priority, url)
            success = True
        except Exception as e:
            logger.error(f"Pushover failed: {e}")

    return success


async def _send_ntfy(
    title: str, message: str, priority: int, tags: Optional[list[str]], url: Optional[str]
) -> bool:
    """Send notification via ntfy.sh using JSON body (supports Unicode)."""
    import json

    ntfy_priority_map = {1: 1, 2: 2, 3: 3, 4: 4, 5: 5}

    payload = {
        "topic": NTFY_TOPIC,
        "title": title,
        "message": message,
        "priority": ntfy_priority_map.get(priority, 3),
        "tags": tags if tags else ["chart_with_upwards_trend"],
    }

    if url:
        payload["click"] = url

    async with httpx.AsyncClient() as client:
        response = await client.post(
            NTFY_URL,
            content=json.dumps(payload),
            headers={"Content-Type": "application/json"},
            timeout=10.0,
        )
        if response.status_code == 200:
            logger.info(f"  Ntfy notification sent: {title}")
            return True
        else:
            logger.warning(f"Ntfy returned {response.status_code}: {response.text}")
            return False


async def _send_pushover(
    title: str, message: str, priority: int, url: Optional[str]
) -> bool:
    """Send notification via Pushover."""
    pushover_priority = min(priority - 3, 2)  # Map 1-5 to -2 to 2

    data = {
        "token": PUSHOVER_TOKEN,
        "user": PUSHOVER_USER,
        "title": title,
        "message": message,
        "priority": pushover_priority,
        "sound": "cashregister" if priority >= 4 else "pushover",
    }
    if url:
        data["url"] = url

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.pushover.net/1/messages.json",
            data=data,
            timeout=10.0,
        )
        return response.status_code == 200

"""
SkyGuard AI — Render Cloud Keep-Alive Self-Pinger Service
Prevents Render free tier instances from sleeping by dispatching
an inbound HTTP GET /api/v1/health request every 10 minutes (600 seconds).
"""
import asyncio
import logging
import os
import urllib.request

logger = logging.getLogger("skyguard.keepalive")

# Interval: 10 minutes (600 seconds) — Render sleeps after 15 minutes of inactivity
PING_INTERVAL_SECONDS = int(os.getenv("KEEP_ALIVE_INTERVAL_SECONDS", "600"))

def _ping_sync(url: str):
    """Synchronous HTTP GET ping using built-in urllib."""
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "SkyGuard-KeepAlive-Pinger/1.0", "Accept": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=25) as resp:
        return resp.status

async def start_keep_alive_loop():
    """
    Background asynchronous loop that pings the Render public endpoint
    every 10 minutes to maintain persistent 24/7 uptime.
    """
    # Render automatically sets RENDER_EXTERNAL_URL (e.g. https://skyguard-backend.onrender.com)
    external_url = os.getenv("RENDER_EXTERNAL_URL") or os.getenv("BACKEND_PUBLIC_URL") or os.getenv("BACKEND_API_URL")
    
    if not external_url:
        logger.info("[Keep-Alive] No external URL configured in environment. Pinger standing by.")
        return

    target_url = f"{external_url.rstrip('/')}/api/v1/health"
    logger.info(f"[Keep-Alive] Initialized 24/7 Anti-Sleep Pinger targeting: {target_url} (Interval: {PING_INTERVAL_SECONDS}s)")

    # Wait 60 seconds after initial boot before first ping
    await asyncio.sleep(60)

    while True:
        try:
            status = await asyncio.to_thread(_ping_sync, target_url)
            logger.info(f"[Keep-Alive] Health ping dispatched to {target_url} (Status: {status} — Inactivity timer reset)")
        except Exception as exc:
            logger.warning(f"[Keep-Alive] Ping notice: {exc}")

        await asyncio.sleep(PING_INTERVAL_SECONDS)

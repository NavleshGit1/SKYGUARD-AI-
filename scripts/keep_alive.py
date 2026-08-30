#!/usr/bin/env python3
"""
==============================================================================
 SkyGuard AI - Render Backend Keep-Alive Heartbeat Daemon
==============================================================================
 Keeps Render free-tier web services awake by sending periodic HTTP GET
 requests to /api/v1/health every 10 minutes (prevents 15-minute sleep).
==============================================================================
"""

import os
import sys
import time
import argparse
import logging
from datetime import datetime, timezone
import urllib.request
import urllib.error
import json

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("KeepAlive")


def ping_server(url: str, timeout: int = 30) -> bool:
    """Sends a GET request to the target server health endpoint."""
    health_url = url.rstrip("/")
    if not health_url.endswith("/api/v1/health") and not health_url.endswith("/health"):
        health_url += "/api/v1/health"

    req = urllib.request.Request(
        health_url,
        headers={"User-Agent": "SkyGuard-KeepAlive-Heartbeat/1.0"}
    )
    
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            latency_ms = (time.time() - t0) * 1000.0
            status_code = response.getcode()
            body = response.read().decode("utf-8")
            
            try:
                data = json.loads(body)
                service_status = data.get("status", "OK")
            except Exception:
                service_status = "OK"

            logger.info(
                f" Heartbeat Success -> {health_url} | HTTP {status_code} | "
                f"Status: {service_status} | Latency: {latency_ms:.1f}ms"
            )
            return True
            
    except urllib.error.HTTPError as e:
        latency_ms = (time.time() - t0) * 1000.0
        logger.warning(
            f" Heartbeat HTTP Error -> {health_url} | HTTP {e.code} | "
            f"Reason: {e.reason} | Latency: {latency_ms:.1f}ms"
        )
        return False
    except urllib.error.URLError as e:
        latency_ms = (time.time() - t0) * 1000.0
        logger.error(
            f" Heartbeat Connection Failed -> {health_url} | "
            f"Error: {e.reason} | Latency: {latency_ms:.1f}ms"
        )
        return False
    except Exception as e:
        logger.error(f" Heartbeat Unexpected Error -> {health_url} | Error: {e}")
        return False


def run_daemon(target_url: str, interval_minutes: int = 10, timeout: int = 30):
    """Runs a continuous keep-alive loop."""
    interval_seconds = interval_minutes * 60
    logger.info("=" * 65)
    logger.info(" SkyGuard AI Render Keep-Alive Daemon Started")
    logger.info(f" Target URL: {target_url}")
    logger.info(f" Heartbeat Interval: Every {interval_minutes} minutes ({interval_seconds}s)")
    logger.info("=" * 65)

    iteration = 1
    while True:
        logger.info(f"[Ping #{iteration}] Sending keep-alive request...")
        ping_server(target_url, timeout=timeout)
        iteration += 1

        next_time = datetime.fromtimestamp(time.time() + interval_seconds, tz=timezone.utc)
        logger.info(f" Sleeping for {interval_minutes}m. Next ping at ~{next_time.strftime('%H:%M:%S UTC')}")
        try:
            time.sleep(interval_seconds)
        except KeyboardInterrupt:
            logger.info("\n Keep-Alive daemon stopped by user.")
            sys.exit(0)


def main():
    parser = argparse.ArgumentParser(
        description="SkyGuard AI - Render Free Tier Keep-Alive Heartbeat"
    )
    parser.add_argument(
        "--url",
        type=str,
        default=os.getenv("RENDER_BACKEND_URL", "http://localhost:8000"),
        help="Backend base URL (e.g., https://skyguard-backend.onrender.com or http://localhost:8000)"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=10,
        help="Ping interval in minutes (default: 10 minutes, Render sleeps after 15m)"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=45,
        help="HTTP request timeout in seconds (default: 45s to handle Render cold starts)"
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Send a single ping and exit immediately (useful for CI/cron workflows)"
    )

    args = parser.parse_args()

    if args.once:
        success = ping_server(args.url, timeout=args.timeout)
        sys.exit(0 if success else 1)
    else:
        run_daemon(args.url, interval_minutes=args.interval, timeout=args.timeout)


if __name__ == "__main__":
    main()

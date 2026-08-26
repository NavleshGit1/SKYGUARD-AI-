import time
import threading
from typing import Dict, Any, Optional, Callable
from backend.app.core.logging import logger


class StationCache:
    """
    High-performance thread-safe in-memory cache for Station metadata, HMAC secrets, and geolocations.
    Eliminates redundant database queries during high-throughput telemetry streams (5,000+ msgs/sec).
    """
    def __init__(self, default_ttl_seconds: float = 300.0):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._timestamps: Dict[str, float] = {}
        self._ttl = default_ttl_seconds
        self._lock = threading.RLock()
        self._hits = 0
        self._misses = 0

    def get(self, station_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            now = time.time()
            if station_id in self._cache:
                if now - self._timestamps.get(station_id, 0) < self._ttl:
                    self._hits += 1
                    return self._cache[station_id]
                else:
                    # Expired
                    del self._cache[station_id]
                    if station_id in self._timestamps:
                        del self._timestamps[station_id]
            self._misses += 1
            return None

    def set(self, station_id: str, data: Dict[str, Any], ttl: Optional[float] = None):
        with self._lock:
            self._cache[station_id] = data
            self._timestamps[station_id] = time.time()

    def invalidate(self, station_id: Optional[str] = None):
        with self._lock:
            if station_id:
                self._cache.pop(station_id, None)
                self._timestamps.pop(station_id, None)
                logger.info(f"[Cache] Invalidated cache for station: {station_id}")
            else:
                self._cache.clear()
                self._timestamps.clear()
                logger.info("[Cache] Flushed entire station metadata cache")

    def get_or_set(self, station_id: str, fetch_fn: Callable[[], Optional[Dict[str, Any]]]) -> Optional[Dict[str, Any]]:
        cached = self.get(station_id)
        if cached is not None:
            return cached

        with self._lock:
            # Double-check after lock
            cached = self.get(station_id)
            if cached is not None:
                return cached

            data = fetch_fn()
            if data is not None:
                self.set(station_id, data)
            return data

    @property
    def stats(self) -> Dict[str, Any]:
        with self._lock:
            total = self._hits + self._misses
            hit_ratio = round((self._hits / total * 100), 2) if total > 0 else 100.0
            return {
                "cached_stations": len(self._cache),
                "cache_hits": self._hits,
                "cache_misses": self._misses,
                "hit_ratio_pct": hit_ratio,
                "ttl_seconds": self._ttl
            }


station_cache = StationCache(default_ttl_seconds=600.0)


# =============================================================================
# VULN-08 FIX: Redis client for JWT JTI token revocation blocklist
# =============================================================================
import os

_redis_client = None
_redis_available = False


def get_redis_client():
    """
    Lazy-initialised Redis client. Returns None gracefully if Redis is unavailable
    (system still works; revocation simply won't be enforced without Redis).
    """
    global _redis_client, _redis_available
    if _redis_client is not None:
        return _redis_client if _redis_available else None
    try:
        import redis
        _redis_client = redis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", "6379")),
            password=os.getenv("REDIS_PASSWORD") or None,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=1,
        )
        _redis_client.ping()
        _redis_available = True
        logger.info("[Redis] JWT blocklist connected successfully.")
    except Exception as e:
        logger.warning(f"[Redis] Unavailable — JWT revocation disabled. Reason: {e}")
        _redis_available = False
        _redis_client = None
    return _redis_client if _redis_available else None


def revoke_token_jti(jti: str, ttl_seconds: int = 3600) -> bool:
    """Add a JWT JTI to the Redis revocation blocklist with appropriate TTL."""
    client = get_redis_client()
    if client is None:
        logger.warning(f"[JWT Revocation] Redis unavailable — cannot revoke JTI {jti}")
        return False
    try:
        client.setex(f"blocklist:jti:{jti}", ttl_seconds, "1")
        return True
    except Exception as e:
        logger.error(f"[JWT Revocation] Failed to revoke JTI {jti}: {e}")
        return False


def is_token_revoked(jti: str) -> bool:
    """Check if a JWT JTI is in the Redis revocation blocklist."""
    client = get_redis_client()
    if client is None:
        return False  # Fail open — Redis down should not block all requests
    try:
        return client.exists(f"blocklist:jti:{jti}") == 1
    except Exception:
        return False

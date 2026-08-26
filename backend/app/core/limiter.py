"""
SkyGuard AI — Rate Limiter Singleton
Extracted to avoid circular imports between main.py and route modules.
Blueprint §14.3: SlowAPI — 5/min login, 60/min ingest per IP
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

# Global singleton — imported by main.py and all rate-limited route modules
limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])

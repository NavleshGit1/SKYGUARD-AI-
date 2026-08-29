import os
import sys
import time
from datetime import datetime, timezone
from contextlib import asynccontextmanager

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import text

from backend.app.core.config import settings
from backend.app.core.database import Base, engine, SessionLocal
from backend.app.core.limiter import limiter
from backend.app.core.logging import logger
from backend.app.core.cache import station_cache
from backend.app.core.middleware import RequestTracingMiddleware
from backend.app.core.errors import (
    SkyGuardException,
    app_exception_handler,
    http_exception_handler,
    validation_exception_handler
)
from backend.app.api.v1 import router as api_v1_router
from backend.app.models import WeatherStation, SensorReading, AnomalyEvent, User, DeadLetterRecord

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Ensure DB tables exist and prime station cache
    logger.info(f"Starting {settings.PROJECT_NAME} v{settings.VERSION} [{settings.ENVIRONMENT}]")
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("[Database] Schema tables verified & connected.")
        
        # Preload station cache & auto-seed if empty
        db = SessionLocal()
        try:
            st_count = db.query(WeatherStation).count()
            if st_count == 0:
                logger.info("[Database] Empty database detected. Auto-seeding weather stations...")
                from scripts.init_db import initialize_database
                from scripts.seed_model_registry import seed_registry
                initialize_database()
                seed_registry()

            stations = db.query(WeatherStation).all()
            for st in stations:
                station_cache.set(st.station_id, {
                    "station_id": st.station_id,
                    "name": st.name,
                    "altitude_m": st.altitude_m,
                    "latitude": st.latitude,
                    "longitude": st.longitude,
                    "api_secret_key": st.api_secret_key
                })
            logger.info(f"[Cache] Pre-warmed cache with {len(stations)} weather station profiles.")
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"[Database] Startup connection note: {e}")
        
    # Start Render 24/7 Keep-Alive Self-Pinger loop
    import asyncio
    from backend.app.services.keep_alive import start_keep_alive_loop
    keep_alive_task = asyncio.create_task(start_keep_alive_loop())

    yield
    
    # Shutdown
    keep_alive_task.cancel()
    logger.info(f"[SkyGuard Backend] Graceful shutdown complete.")

# VULN-02 FIX: Disable API docs in production — no surface exposure to attackers
_is_dev = settings.ENVIRONMENT in ("development", "dev", "local")

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Intelligent Real-Time Anomaly Detection, Quality Control & Health Monitoring for AWS Networks",
    version=settings.VERSION,
    docs_url="/docs" if _is_dev else None,
    redoc_url="/redoc" if _is_dev else None,
    openapi_url="/api/v1/openapi.json" if _is_dev else None,
    lifespan=lifespan
)

# 1. Custom Standardized Exception Handlers
app.add_exception_handler(SkyGuardException, app_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# 2. Middlewares
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(RequestTracingMiddleware)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. Mount API v1 router
app.include_router(api_v1_router, prefix=settings.API_V1_STR)

@app.get("/", tags=["Root"], summary="SkyGuard AI Service Status")
async def root_discovery():
    """Welcome endpoint for root service inspection and endpoint discovery."""
    return {
        "success": True,
        "status": "HEALTHY",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "endpoints": {
            "health": f"{settings.API_V1_STR}/health",
            "stations": f"{settings.API_V1_STR}/stations",
            "anomalies": f"{settings.API_V1_STR}/anomalies",
            "websocket": f"{settings.API_V1_STR}/ws/live-feed"
        },
        "message": "SkyGuard AI Meteorological Telemetry Backend is active and operational."
    }

@app.get("/api/v1/health", tags=["Observability & Metrics"], summary="High-Precision System Health Check")
async def health_check():
    """
    Returns real-time operational status, database round-trip ping latency,
    cache hit statistics, and environment metadata.
    """
    db_start = time.perf_counter()
    db_status = "UNKNOWN"
    db_ping_ms = 0.0
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_ping_ms = round((time.perf_counter() - db_start) * 1000.0, 2)
        db_status = "HEALTHY"
    except Exception as e:
        db_status = f"UNREACHABLE ({str(e)})"

    return {
        "status": "HEALTHY" if db_status == "HEALTHY" else "DEGRADED",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "database": {
            "status": db_status,
            "latency_ms": db_ping_ms
        },
        "cache": station_cache.stats,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

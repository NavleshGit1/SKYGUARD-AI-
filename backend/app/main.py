import os
import sys
import time
import asyncio
import secrets
from datetime import datetime, timezone
from contextlib import asynccontextmanager

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pandas as pd
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
from backend.app.core.security import get_password_hash
from backend.app.core.middleware import RequestTracingMiddleware
from backend.app.core.errors import (
    SkyGuardException,
    app_exception_handler,
    http_exception_handler,
    validation_exception_handler
)
from backend.app.api.v1 import router as api_v1_router
from backend.app.models import WeatherStation, SensorReading, AnomalyEvent, User, DeadLetterRecord
from simulator.engine import SimulatorEngine
from backend.app.api.v1.simulator import ACTIVE_INJECTIONS


def _seed_db_if_empty():
    """Ensures the 5 official AWS hub stations and default admin user exist in database"""
    db = SessionLocal()
    try:
        # Check if stations exist
        station_count = db.query(WeatherStation).count()
        if station_count == 0:
            csv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "metadata", "stations_metadata.csv")
            if os.path.exists(csv_path):
                df = pd.read_csv(csv_path)
                for _, row in df.iterrows():
                    st = WeatherStation(
                        station_id=str(row["station_id"]),
                        name=str(row["name"]),
                        latitude=float(row["latitude"]),
                        longitude=float(row["longitude"]),
                        altitude_m=float(row.get("altitude_m", 0.0)),
                        district=str(row.get("district", "")),
                        state=str(row.get("state", "")),
                        climate_zone=str(row.get("climate_zone", "")),
                        install_year=int(row["install_year"]) if pd.notna(row.get("install_year")) else 2020,
                        last_calibration_date=str(row.get("last_calibration_date", "2026-01-01")),
                        wmo_id=str(row.get("wmo_id", "")),
                        health_score=100.0,
                        health_status="HEALTHY",
                        is_active=True
                    )
                    db.add(st)
                db.commit()
                logger.info(f"[Database] Auto-seeded 5 AWS Hub stations from metadata.")

        # Check default admin
        admin = db.query(User).filter(User.email == "admin@skyguard.ai").first()
        if not admin:
            new_admin = User(
                email="admin@skyguard.ai",
                hashed_password=get_password_hash("admin123"),
                full_name="Chief Meteorologist",
                role="admin",
                is_active=True
            )
            db.add(new_admin)
            db.commit()
            logger.info("[Database] Auto-seeded default admin user (admin@skyguard.ai).")

        # Check Model Registry
        from backend.app.models.model_registry import ModelRegistry
        if db.query(ModelRegistry).count() == 0:
            models_to_reg = [
                {
                    "model_id": "iforest-v1.0-prod",
                    "model_name": "Multivariate Isolation Forest",
                    "model_type": "UNSUPERVISED_IFOREST",
                    "version": "1.0.0",
                    "checkpoint_path": "models/isolation_forest.pkl",
                    "hyperparameters": {"n_estimators": 100, "max_samples": 256, "contamination": 0.01, "random_state": 42},
                    "input_dimension": 8,
                    "f1_score": 0.996,
                    "precision": 1.000,
                    "recall": 0.992,
                    "inference_latency_ms": 1.45,
                    "is_active": True,
                    "description": "Optimized tree-based outlier isolation detector for Render/cloud deployment."
                },
                {
                    "model_id": "deep-autoencoder-v1.0-prod",
                    "model_name": "PyTorch Compression Autoencoder",
                    "model_type": "DEEP_AUTOENCODER",
                    "version": "1.0.0",
                    "checkpoint_path": "models/autoencoder.pt",
                    "hyperparameters": {"architecture": "8 -> 16 -> 8 -> 3 -> 8 -> 16 -> 8"},
                    "input_dimension": 8,
                    "latent_dimension": 3,
                    "f1_score": 0.994,
                    "precision": 1.000,
                    "recall": 0.988,
                    "inference_latency_ms": 2.10,
                    "is_active": True,
                    "description": "Deep reconstruction error bottleneck autoencoder."
                },
                {
                    "model_id": "feature-scaler-v1.0-prod",
                    "model_name": "Standard StandardScaler Pipeline",
                    "model_type": "FEATURE_SCALER",
                    "version": "1.0.0",
                    "checkpoint_path": "models/scaler.pkl",
                    "hyperparameters": {"with_mean": True, "with_std": True},
                    "input_dimension": 8,
                    "is_active": True,
                    "description": "12-Year Meteorological normalization transform."
                },
                {
                    "model_id": "hybrid-ensemble-meta-v1.0-prod",
                    "model_name": "6-Detector Meteorological Ensemble",
                    "model_type": "HYBRID_ENSEMBLE",
                    "version": "1.0.0",
                    "checkpoint_path": "backend/app/services/detectors.py",
                    "hyperparameters": {"weights": {"physics": 0.30, "flatline": 0.20, "iforest": 0.15, "autoencoder": 0.20, "cusum": 0.15}},
                    "input_dimension": 8,
                    "f1_score": 0.996,
                    "precision": 1.000,
                    "recall": 0.992,
                    "inference_latency_ms": 6.97,
                    "is_active": True,
                    "description": "Production hybrid ensemble combining physics, statistics, and deep learning."
                }
            ]
            for m in models_to_reg:
                db.add(ModelRegistry(**m))
            db.commit()
            logger.info("[Database] Auto-seeded production Model Registry checkpoints.")
            
    except Exception as e:
        logger.warning(f"[Database] Auto-seeding notice: {e}")
        db.rollback()
    finally:
        db.close()


async def _run_embedded_simulator():
    """
    In-process async background task that streams simulated AWS telemetry
    Essential for Render Free Tier (single-process web container hosting)
    """
    logger.info("[Embedded Simulator] Starting in-process telemetry streaming worker...")
    await asyncio.sleep(2)  # Short initial grace period
    
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    data_path = os.path.join(base_dir, "data", "raw", "historical_aws_training.csv")
    
    engine_sim = SimulatorEngine(data_path=data_path, secret_key=settings.TELEMETRY_HMAC_SECRET)
    stations = ["AWS-DEL-01", "AWS-MUM-01", "AWS-CHE-01", "AWS-KOL-01", "AWS-JAI-01"]
    station_idx = 0
    
    from backend.app.services.feature_eng import MeteorologicalFeatureEngine
    from backend.app.services.detectors import HybridDetectorEnsemble
    from backend.app.services.xai import ExplainabilityEngine
    from backend.app.services.imputer import ValueImputer
    from backend.app.services.health_score import SensorHealthEngine
    from backend.app.services.alert_manager import alert_manager
    from backend.app.api.v1.websocket import ws_manager
    
    feature_engine = MeteorologicalFeatureEngine("data/metadata/climate_normals.csv")
    detector_ensemble = HybridDetectorEnsemble("models")
    imputer = ValueImputer("models")
    health_engine = SensorHealthEngine()

    while True:
        try:
            # 1. Check on-demand UI injections
            active_target = None
            if ACTIVE_INJECTIONS:
                for st_id, inj in list(ACTIVE_INJECTIONS.items()):
                    engine_sim.trigger_anomaly(
                        anomaly_type=inj["type"],
                        parameter=inj["parameter"],
                        duration_ticks=inj["duration"],
                        magnitude=inj["magnitude"],
                        station_id=st_id
                    )
                    active_target = st_id
                    del ACTIVE_INJECTIONS[st_id]
                    break

            target_station = active_target if active_target else stations[station_idx % len(stations)]
            station_idx += 1

            reading_pkg = engine_sim.get_next_reading(target_station=target_station)
            if reading_pkg:
                payload = reading_pkg["payload"]
                st_id = payload["station_id"]
                
                db = SessionLocal()
                try:
                    station_meta = station_cache.get(st_id)
                    if not station_meta:
                        st = db.query(WeatherStation).filter(WeatherStation.station_id == st_id).first()
                        if st:
                            station_meta = {
                                "station_id": st.station_id,
                                "name": st.name,
                                "altitude_m": st.altitude_m,
                                "latitude": st.latitude,
                                "longitude": st.longitude,
                                "api_secret_key": st.api_secret_key
                            }
                            station_cache.set(st_id, station_meta)

                    if station_meta:
                        # 2. Physics feature extraction
                        reading_with_meta = payload.copy()
                        reading_with_meta["altitude_m"] = station_meta.get("altitude_m", 0.0)
                        feat_dict = feature_engine.extract_features(reading_with_meta)
                        
                        # 3. ML Ensemble evaluation
                        detection = detector_ensemble.detect(feat_dict)
                        is_anomaly = detection["is_anomaly"]
                        severity = detection["severity_score"]
                        attributions = detection.get("shap_attributions", {})
                        
                        # 4. Imputation
                        imputed = imputer.impute_corrected_values(feat_dict, is_anomaly, attributions)
                        
                        # 5. Health score update
                        st_obj = db.query(WeatherStation).filter(WeatherStation.station_id == st_id).first()
                        last_cal = st_obj.last_calibration_date if st_obj else "2026-01-01"
                        inst_yr = st_obj.install_year if st_obj else 2020
                        ts = datetime.fromisoformat(payload["timestamp"].replace("Z", "+00:00"))
                        
                        health_update = health_engine.update_health(
                            station_id=st_id,
                            is_anomaly=is_anomaly,
                            severity_score=severity,
                            drift_score=detection["detector_scores"].get("drift_stl_cusum", 0.0),
                            last_calibration_date=last_cal,
                            install_year=inst_yr,
                            current_month=ts.month
                        )
                        
                        # 6. Save reading to DB
                        reading_rec = SensorReading(
                            station_id=st_id,
                            timestamp=ts,
                            temperature_c=payload["temperature_c"],
                            pressure_hpa=payload["pressure_hpa"],
                            humidity_pct=payload["humidity_pct"],
                            dew_point_c=feat_dict["physics_features"]["dew_point_c"],
                            sea_level_pressure_hpa=feat_dict["physics_features"]["sea_level_pressure_hpa"],
                            is_anomaly=is_anomaly,
                            severity_score=severity,
                            is_imputed=imputed.get("is_imputed", False),
                            imputed_temperature_c=imputed.get("temperature_c"),
                            imputed_pressure_hpa=imputed.get("pressure_hpa"),
                            imputed_humidity_pct=imputed.get("humidity_pct")
                        )
                        db.add(reading_rec)

                        # Update station health in DB
                        if st_obj:
                            st_obj.health_score = health_update["health_score"]
                            st_obj.health_status = health_update["status"]
                            st_obj.last_seen = ts

                        # 7. Record anomaly if detected
                        if is_anomaly:
                            explanation = ExplainabilityEngine.generate_explanation(feat_dict, detection)
                            anom_event = AnomalyEvent(
                                event_id=f"evt-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{secrets.token_hex(3)}",
                                station_id=st_id,
                                timestamp=ts,
                                severity_score=severity,
                                confidence_score=detection.get("confidence_score", 0.95),
                                detector_scores=detection.get("detector_scores", {}),
                                root_cause=detection.get("root_cause", "MULTIVARIATE_PHYSICAL_DEVIATION"),
                                explanation=explanation,
                                shap_attributions=attributions,
                                estimated_corrected_values=imputed,
                                status="ACTIVE"
                            )
                            db.add(anom_event)

                        db.commit()

                        # 8. Broadcast over WebSocket to active frontend dashboards
                        await ws_manager.broadcast({
                            "type": "TELEMETRY_INGESTED",
                            "station_id": st_id,
                            "timestamp": payload["timestamp"],
                            "reading": {
                                "temperature_c": payload["temperature_c"],
                                "pressure_hpa": payload["pressure_hpa"],
                                "humidity_pct": payload["humidity_pct"],
                                "dew_point_c": feat_dict["physics_features"]["dew_point_c"],
                                "sea_level_pressure_hpa": feat_dict["physics_features"]["sea_level_pressure_hpa"]
                            },
                            "is_anomaly": is_anomaly,
                            "severity_score": severity,
                            "health_score": health_update["health_score"],
                            "health_status": health_update["status"],
                            "root_cause": detection.get("root_cause"),
                            "imputed": imputed
                        })
                except Exception as e:
                    db.rollback()
                    logger.warning(f"[Embedded Simulator] Ingestion tick note: {e}")
                finally:
                    db.close()

        except Exception as e:
            logger.warning(f"[Embedded Simulator] Loop error: {e}")

        await asyncio.sleep(settings.SIMULATOR_TICK_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Ensure DB tables exist, auto-seed and prime station cache
    logger.info(f"Starting {settings.PROJECT_NAME} v{settings.VERSION} [{settings.ENVIRONMENT}]")
    sim_task = None
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("[Database] Schema tables verified & connected.")
        _seed_db_if_empty()
        
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

        # Launch embedded background simulator if enabled
        if settings.ENABLE_EMBEDDED_SIMULATOR:
            sim_task = asyncio.create_task(_run_embedded_simulator())
            logger.info("[Lifespan] Embedded Telemetry Streamer background task launched.")

    except Exception as e:
        logger.warning(f"[Database] Startup connection note: {e}")
        
    # Start Render 24/7 Keep-Alive Self-Pinger & Autonomous Telemetry Stream
    import asyncio
    from backend.app.services.keep_alive import start_keep_alive_loop
    from backend.app.services.background_simulator import start_background_simulator_loop
    
    keep_alive_task = asyncio.create_task(start_keep_alive_loop())
    simulator_task = asyncio.create_task(start_background_simulator_loop())

    yield
    
    # Shutdown
    if sim_task:
        sim_task.cancel()
    logger.info(f"[SkyGuard Backend] Graceful shutdown complete.")


# VULN-02 FIX: Disable API docs in production when not debugging
_is_dev = settings.ENVIRONMENT in ("development", "dev", "local", "preview") or settings.DEBUG

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

# Dynamic CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_origin_regex=r"^https:\/\/.*\.vercel\.app$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. Mount API v1 router
app.include_router(api_v1_router, prefix=settings.API_V1_STR)


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

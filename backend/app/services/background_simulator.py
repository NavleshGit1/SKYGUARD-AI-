"""
SkyGuard AI — Autonomous Background Telemetry Simulator
Generates continuous, realistic 2-second meteorological telemetry across all
5 Indian AWS stations, evaluates ML anomaly detection models, and broadcasts
live WebSocket updates directly to connected dashboards (Vercel / Cloud).
"""
import asyncio
import logging
import math
import random
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, Any

from backend.app.core.database import SessionLocal
from backend.app.api.v1.websocket import ws_manager
from backend.app.models.station import WeatherStation
from backend.app.models.reading import SensorReading
from backend.app.models.anomaly import AnomalyEvent
from backend.app.api.v1.simulator import ACTIVE_INJECTIONS
from backend.app.api.v1.ingest import (
    feature_engine,
    detector_ensemble,
    ExplainabilityEngine,
    imputer,
    health_engine,
    alert_manager
)

logger = logging.getLogger("skyguard.simulator")

STATIONS_CONFIG = {
    "AWS-DEL-01": {"name": "Delhi Safdarjung", "lat": 28.6139, "lon": 77.2090, "alt": 216.0, "base_temp": 28.5, "base_pres": 998.0, "base_hum": 65.0},
    "AWS-MUM-01": {"name": "Mumbai Santacruz", "lat": 19.0760, "lon": 72.8777, "alt": 14.0, "base_temp": 29.8, "base_pres": 1004.0, "base_hum": 78.0},
    "AWS-CHE-01": {"name": "Chennai Meenambakkam", "lat": 13.0827, "lon": 80.2707, "alt": 16.0, "base_temp": 32.0, "base_pres": 1005.0, "base_hum": 68.0},
    "AWS-KOL-01": {"name": "Kolkata Alipore", "lat": 22.5726, "lon": 88.3639, "alt": 6.0, "base_temp": 30.5, "base_pres": 1006.0, "base_hum": 75.0},
    "AWS-JAI-01": {"name": "Jaipur Sanganer", "lat": 26.9124, "lon": 75.7873, "alt": 431.0, "base_temp": 33.2, "base_pres": 985.0, "base_hum": 45.0},
}

station_drift_tracker = {st_id: 0.0 for st_id in STATIONS_CONFIG}

def _generate_synthetic_reading(st_id: str, current_time: datetime) -> Dict[str, Any]:
    """Generates a physically consistent meteorological reading with diurnal variation."""
    cfg = STATIONS_CONFIG[st_id]
    
    # Diurnal solar temperature curve (peak at 14:00 local time)
    hour = current_time.hour + (current_time.minute / 60.0)
    diurnal_phase = (hour - 6) * (2 * math.pi / 24)
    diurnal_delta = 4.5 * math.sin(diurnal_phase)

    # Base values + diurnal + subtle realistic micro-fluctuation
    temp = round(cfg["base_temp"] + diurnal_delta + random.uniform(-0.4, 0.4), 2)
    pres = round(cfg["base_pres"] - (diurnal_delta * 0.3) + random.uniform(-0.3, 0.3), 2)
    hum = round(max(20.0, min(95.0, cfg["base_hum"] - (diurnal_delta * 1.8) + random.uniform(-1.0, 1.0))), 1)

    return {
        "station_id": st_id,
        "timestamp": current_time,
        "temperature_c": temp,
        "pressure_hpa": pres,
        "humidity_pct": hum,
        "latitude": cfg["lat"],
        "longitude": cfg["lon"],
        "altitude_m": cfg["alt"]
    }

def _apply_ui_injections(reading: Dict[str, Any]) -> Dict[str, Any]:
    """Applies any pending fault injections triggered from the Fault Injector workbench."""
    st_id = reading["station_id"]
    if st_id not in ACTIVE_INJECTIONS:
        return reading

    inj = ACTIVE_INJECTIONS[st_id]
    inj_type = inj.get("type", "SPIKE").upper()
    param = inj.get("parameter", "temperature_c")
    mag = float(inj.get("magnitude", 18.0))

    if inj_type == "SPIKE":
        reading[param] += mag
    elif inj_type == "FLATLINE":
        reading[param] = 1013.25 if "pressure" in param else 25.0
    elif inj_type == "DRIFT":
        station_drift_tracker[st_id] += (mag * 0.15)
        reading[param] += station_drift_tracker[st_id]
    elif inj_type == "THERMODYNAMIC_VIOLATION":
        reading["humidity_pct"] = 99.9
        reading["temperature_c"] -= 16.0
    elif inj_type == "NOISE_BURST":
        reading[param] += random.gauss(0, mag)

    # Decrement remaining injection ticks
    inj["remaining"] = inj.get("remaining", 1) - 1
    if inj["remaining"] <= 0:
        del ACTIVE_INJECTIONS[st_id]

    return reading

def seed_initial_telemetry_history():
    """Seeds 20 recent baseline telemetry points if database is clean."""
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        for st_id in STATIONS_CONFIG:
            count = db.query(SensorReading).filter(SensorReading.station_id == st_id).count()
            if count < 15:
                logger.info(f"[Simulator] Seeding initial 20 historical telemetry points for {st_id}...")
                for i in range(20, 0, -1):
                    point_time = now - timedelta(minutes=i * 5)
                    reading = _generate_synthetic_reading(st_id, point_time)
                    features = feature_engine.extract_features(reading)
                    detection = detector_ensemble.detect(features)
                    
                    db_reading = SensorReading(
                        station_id=st_id,
                        timestamp=point_time,
                        temperature_c=reading["temperature_c"],
                        pressure_hpa=reading["pressure_hpa"],
                        humidity_pct=reading["humidity_pct"],
                        dew_point_c=features["physics_features"]["dew_point_c"],
                        sea_level_pressure_hpa=features["physics_features"]["sea_level_pressure_hpa"],
                        is_anomaly=detection["is_anomaly"],
                        severity_score=detection["severity_score"],
                        is_imputed=False
                    )
                    db.add(db_reading)
        
        # Seed initial baseline anomaly incident if none exist
        anom_count = db.query(AnomalyEvent).count()
        if anom_count == 0:
            logger.info("[Simulator] Seeding baseline demo anomaly incidents for Incident Center...")
            demo_events = [
                AnomalyEvent(
                    event_id=f"EVT-AWS-DEL-01-{int(now.timestamp()) - 300}",
                    station_id="AWS-DEL-01",
                    timestamp=now - timedelta(minutes=5),
                    severity_score=0.88,
                    confidence_score=0.96,
                    detector_scores={
                        "rule_bounds": 0.0,
                        "flatline_zero_variance": 0.0,
                        "iforest_multivariate": 0.85,
                        "autoencoder_reconstruction": 0.92,
                        "drift_stl_cusum": 0.12,
                        "spatial_idw_consistency": 0.78
                    },
                    root_cause="PHYSICAL_OUTLIER_SPIKE",
                    explanation="Abrupt positive temperature excursion (+14.2°C in 5 minutes) detected. Reconstructed clean signal: 28.1°C.",
                    shap_attributions={
                        "temperature_c": 0.72,
                        "dT_dt": 0.18,
                        "dew_point_c": 0.06,
                        "humidity_pct": 0.04
                    },
                    estimated_corrected_values={
                        "temperature_c": 28.1,
                        "pressure_hpa": 998.2,
                        "humidity_pct": 64.8,
                        "is_imputed": True
                    },
                    status="ACTIVE"
                ),
                AnomalyEvent(
                    event_id=f"EVT-AWS-JAI-01-{int(now.timestamp()) - 900}",
                    station_id="AWS-JAI-01",
                    timestamp=now - timedelta(minutes=15),
                    severity_score=0.74,
                    confidence_score=0.91,
                    detector_scores={
                        "rule_bounds": 0.0,
                        "flatline_zero_variance": 0.0,
                        "iforest_multivariate": 0.68,
                        "autoencoder_reconstruction": 0.75,
                        "drift_stl_cusum": 0.82,
                        "spatial_idw_consistency": 0.55
                    },
                    root_cause="CALIBRATION_DRIFT",
                    explanation="Persistent monotonic upward calibration drift observed over 12 consecutive observations via CUSUM.",
                    shap_attributions={
                        "temperature_c": 0.61,
                        "t_delta_zscore": 0.24,
                        "humidity_pct": 0.15
                    },
                    estimated_corrected_values={
                        "temperature_c": 33.4,
                        "pressure_hpa": 985.1,
                        "humidity_pct": 44.5,
                        "is_imputed": True
                    },
                    status="ACTIVE"
                )
            ]
            for evt in demo_events:
                db.add(evt)

        db.commit()
    except Exception as e:
        db.rollback()
        logger.warning(f"[Simulator] Initial seeding note: {e}")
    finally:
        db.close()

async def start_background_simulator_loop():
    """Continuous async loop executing ML inference and broadcasting to WebSockets every 2s."""
    logger.info("[Simulator] Initializing Autonomous Background Weather Stream...")
    
    # 1. Ensure baseline history exists
    await asyncio.to_thread(seed_initial_telemetry_history)

    station_keys = list(STATIONS_CONFIG.keys())
    step = 0

    while True:
        try:
            now = datetime.now(timezone.utc)
            # Cycle through all 5 stations
            st_id = station_keys[step % len(station_keys)]
            step += 1

            # 1. Generate & apply UI injections
            reading = _generate_synthetic_reading(st_id, now)
            reading = _apply_ui_injections(reading)

            # 2. Extract Features & Multi-Detector ML Inference
            features = feature_engine.extract_features(reading)
            detection = detector_ensemble.detect(features)
            is_anomaly = detection["is_anomaly"]
            severity = detection["severity_score"]
            root_cause = detection["root_cause"]
            attributions = detection.get("shap_attributions", {})
            explanation = ExplainabilityEngine.generate_explanation(features, detection)
            corrected = imputer.impute_corrected_values(features, is_anomaly, attributions)

            # 3. Update Station Health
            db = SessionLocal()
            try:
                db_station = db.query(WeatherStation).filter(WeatherStation.station_id == st_id).first()
                health_update = health_engine.update_health(
                    station_id=st_id,
                    is_anomaly=is_anomaly,
                    severity_score=severity,
                    drift_score=detection["detector_scores"].get("drift_stl_cusum", 0.0),
                    last_calibration_date=db_station.last_calibration_date if db_station else "2026-01-01",
                    install_year=db_station.install_year if db_station else 2020,
                    current_month=now.month
                )

                if db_station:
                    db_station.health_score = health_update["health_score"]
                    db_station.health_status = health_update["status"]
                    db_station.last_seen = now

                # Persist reading
                db_reading = SensorReading(
                    station_id=st_id,
                    timestamp=now,
                    temperature_c=reading["temperature_c"],
                    pressure_hpa=reading["pressure_hpa"],
                    humidity_pct=reading["humidity_pct"],
                    dew_point_c=features["physics_features"]["dew_point_c"],
                    sea_level_pressure_hpa=features["physics_features"]["sea_level_pressure_hpa"],
                    is_anomaly=is_anomaly,
                    severity_score=severity,
                    is_imputed=corrected["is_imputed"],
                    imputed_temperature_c=corrected["temperature_c"] if corrected["is_imputed"] else None,
                    imputed_pressure_hpa=corrected["pressure_hpa"] if corrected["is_imputed"] else None,
                    imputed_humidity_pct=corrected["humidity_pct"] if corrected["is_imputed"] else None
                )
                db.add(db_reading)

                # Persist anomaly if flagged
                if is_anomaly:
                    event_id = f"EVT-{st_id}-{int(now.timestamp())}"
                    db_event = AnomalyEvent(
                        event_id=event_id,
                        station_id=st_id,
                        timestamp=now,
                        severity_score=severity,
                        confidence_score=detection["confidence_score"],
                        detector_scores=detection["detector_scores"],
                        root_cause=root_cause,
                        explanation=explanation,
                        shap_attributions=attributions,
                        estimated_corrected_values=corrected,
                        status="ACTIVE"
                    )
                    db.add(db_event)

                db.commit()
            except Exception as e:
                db.rollback()
                logger.warning(f"[Simulator] DB commit note: {e}")
            finally:
                db.close()

            # 4. Broadcast live packet to all connected WebSockets
            broadcast_payload = {
                "type": "TELEMETRY_INGESTED",
                "station_id": st_id,
                "timestamp": now.isoformat(),
                "reading": {
                    "temperature_c": reading["temperature_c"],
                    "pressure_hpa": reading["pressure_hpa"],
                    "humidity_pct": reading["humidity_pct"],
                    "dew_point_c": features["physics_features"]["dew_point_c"],
                    "sea_level_pressure_hpa": features["physics_features"]["sea_level_pressure_hpa"],
                    "is_anomaly": is_anomaly,
                    "is_imputed": corrected["is_imputed"],
                    "imputed_temperature_c": corrected["temperature_c"] if corrected["is_imputed"] else None,
                    "imputed_pressure_hpa": corrected["pressure_hpa"] if corrected["is_imputed"] else None,
                    "imputed_humidity_pct": corrected["humidity_pct"] if corrected["is_imputed"] else None,
                    "severity_score": severity,
                },
                "is_anomaly": is_anomaly,
                "severity_score": severity,
                "root_cause": root_cause,
                "explanation": explanation,
                "health_score": health_update["health_score"],
                "health_status": health_update["status"]
            }

            await ws_manager.broadcast(broadcast_payload)

        except Exception as err:
            logger.warning(f"[Simulator] Stream cycle note: {err}")

        # Tick rate: 2 seconds per station broadcast
        await asyncio.sleep(2.0)

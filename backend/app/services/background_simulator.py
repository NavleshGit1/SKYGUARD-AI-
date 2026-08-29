"""
SkyGuard AI — High-Fidelity Physics Telemetry Simulator Engine
Generates continuous, thermodynamically coupled meteorological telemetry across all
5 Indian AWS stations using Ornstein-Uhlenbeck mean-reverting atmospheric physics,
evaluates 6-detector ML ensembles in real time, and streams live WebSocket updates.
"""
import asyncio
import logging
import math
import random
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, Any

from backend.app.core.database import SessionLocal
from backend.app.models.station import WeatherStation
from backend.app.models.reading import SensorReading
from backend.app.models.anomaly import AnomalyEvent

# NOTE: ws_manager, ACTIVE_INJECTIONS, feature_engine etc. are imported lazily
# inside functions below to break the circular import chain:
#   background_simulator -> api.v1.websocket -> api.v1.__init__ -> api.v1.stations
#                        -> background_simulator  (circular!)
# Lazy imports are safe here because these objects are singletons initialized once.

logger = logging.getLogger("skyguard.simulator")

STATIONS_CONFIG = {
    # base_pres = station surface pressure (hPa), calibrated so hypsometric MSLP
    # reduction matches WMO climate normals (which store Sea Level Pressure).
    # Formula: base_pres = MSLP_normal * (1 - lapse*alt/(T_K+lapse*alt))^5.257
    # Delhi  216m: 976.4 hPa surface  -> MSLP ~1000.4 hPa (Aug normal: 1000.38 hPa)
    # Jaipur 431m: 953.8 hPa surface  -> MSLP ~1001.0 hPa (Aug normal: 1001.01 hPa)
    # Sea-level stations use near-MSLP values directly (alt < 20m, ~1 hPa correction)
    "AWS-DEL-01": {"name": "Delhi Safdarjung",      "lat": 28.6139, "lon": 77.2090, "alt": 216.0, "base_temp": 30.4, "base_pres": 976.4,  "base_hum": 68.0},
    "AWS-MUM-01": {"name": "Mumbai Santacruz",       "lat": 19.0760, "lon": 72.8777, "alt":  14.0, "base_temp": 28.8, "base_pres": 1004.2, "base_hum": 79.0},
    "AWS-CHE-01": {"name": "Chennai Meenambakkam",   "lat": 13.0827, "lon": 80.2707, "alt":  16.0, "base_temp": 30.5, "base_pres": 1005.0, "base_hum": 72.0},
    "AWS-KOL-01": {"name": "Kolkata Alipore",        "lat": 22.5726, "lon": 88.3639, "alt":   6.0, "base_temp": 29.2, "base_pres": 1006.1, "base_hum": 76.0},
    # Jaipur 431m: calibrated surface pressure 953.8 hPa reduces to ~1001.0 hPa MSLP
    "AWS-JAI-01": {"name": "Jaipur Sanganer",        "lat": 26.9124, "lon": 75.7873, "alt": 431.0, "base_temp": 33.5, "base_pres": 953.8,  "base_hum": 48.0},
}


class StationAtmosphericState:
    """Continuous physical state per AWS station with thermodynamic coupling."""
    
    def __init__(self, station_id: str, cfg: Dict[str, Any]):
        self.station_id = station_id
        self.cfg = cfg
        self.drift_accum = 0.0

        # FIX: Initialize temp/pres/hum to the *current* diurnal target so that
        # the first step() call produces dT/dt ≈ 0 instead of a massive jump.
        # Without this, the OU process would need many cycles to converge from
        # base_temp to the actual nighttime target, producing unphysical
        # dT/dt ≈ -1.8°C/min that the ML detectors incorrectly flag.
        now_utc = __import__('datetime').datetime.now(__import__('datetime').timezone.utc)
        ist_hour = (now_utc.hour + 5.5 + (now_utc.minute / 60.0)) % 24
        diurnal_phase = (ist_hour - 5.5) * (2.0 * math.pi / 24.0)
        self.temp = cfg["base_temp"] + (4.2 * math.sin(diurnal_phase - 1.2))
        self.pres = cfg["base_pres"] - (0.9 * math.sin(diurnal_phase - 1.2))
        raw_hum   = cfg["base_hum"] - (14.0 * math.sin(diurnal_phase - 1.2))
        self.hum  = max(22.0, min(92.0, raw_hum))

    def step(self, current_time: datetime) -> Dict[str, Any]:
        # Local Indian Standard Time (UTC +5:30)
        ist_hour = (current_time.hour + 5.5 + (current_time.minute / 60.0) + (current_time.second / 3600.0)) % 24
        
        # Diurnal solar cycle (peak warmth at 14:30 IST, minimum at 05:30 IST)
        diurnal_phase = (ist_hour - 5.5) * (2.0 * math.pi / 24.0)
        temp_amplitude = 4.2
        target_temp = self.cfg["base_temp"] + (temp_amplitude * math.sin(diurnal_phase - 1.2))
        target_pres = self.cfg["base_pres"] - (0.9 * math.sin(diurnal_phase - 1.2))
        target_hum = max(22.0, min(92.0, self.cfg["base_hum"] - (14.0 * math.sin(diurnal_phase - 1.2))))

        # Smooth Mean-Reverting Ornstein-Uhlenbeck Stochastic Process
        alpha = 0.25
        self.temp += alpha * (target_temp - self.temp) + random.gauss(0, 0.02)
        self.pres += alpha * (target_pres - self.pres) + random.gauss(0, 0.015)
        self.hum += alpha * (target_hum - self.hum) + random.gauss(0, 0.04)

        t_clean = round(self.temp, 2)
        p_clean = round(self.pres, 2)
        h_clean = round(max(15.0, min(98.0, self.hum)), 1)

        return {
            "station_id": self.station_id,
            "timestamp": current_time,
            "temperature_c": t_clean,
            "pressure_hpa": p_clean,
            "humidity_pct": h_clean,
            "latitude": self.cfg["lat"],
            "longitude": self.cfg["lon"],
            "altitude_m": self.cfg["alt"]
        }

# Global live state tracking per station
STATION_STATES = {st_id: StationAtmosphericState(st_id, cfg) for st_id, cfg in STATIONS_CONFIG.items()}

def _generate_synthetic_reading(st_id: str, current_time: datetime) -> Dict[str, Any]:
    """Generates continuous physical readings from atmospheric state."""
    state = STATION_STATES.get(st_id)
    if not state:
        state = StationAtmosphericState(st_id, STATIONS_CONFIG.get(st_id, STATIONS_CONFIG["AWS-DEL-01"]))
        STATION_STATES[st_id] = state
    return state.step(current_time)

def _apply_ui_injections(reading: Dict[str, Any]) -> Dict[str, Any]:
    """Applies any pending fault injections triggered from the Fault Injector workbench."""
    # Lazy import to avoid circular import at module level
    from backend.app.api.v1.simulator import ACTIVE_INJECTIONS

    st_id = reading["station_id"]
    if st_id not in ACTIVE_INJECTIONS:
        return reading

    inj = ACTIVE_INJECTIONS[st_id]
    inj_type = inj.get("type", "SPIKE").upper()
    param = inj.get("parameter", "temperature_c")
    mag = float(inj.get("magnitude", 14.0))

    if inj_type == "SPIKE":
        reading[param] += mag
    elif inj_type == "FLATLINE":
        reading[param] = 1013.25 if "pressure" in param else 25.0
    elif inj_type == "DRIFT":
        state = STATION_STATES.get(st_id)
        if state:
            state.drift_accum += (mag * 0.12)
            reading[param] += state.drift_accum
    elif inj_type == "THERMODYNAMIC_VIOLATION":
        reading["humidity_pct"] = 99.9
        reading["temperature_c"] -= 16.0
    elif inj_type == "NOISE_BURST":
        reading[param] += random.gauss(0, mag)

    # Decrement remaining injection ticks
    inj["remaining"] = inj.get("remaining", 1) - 1
    if inj["remaining"] <= 0:
        # FIX: Reset drift accumulator so the station returns to its normal
        # physical baseline once the injection period ends.
        if inj_type == "DRIFT":
            state = STATION_STATES.get(st_id)
            if state:
                state.drift_accum = 0.0
        del ACTIVE_INJECTIONS[st_id]

    return reading

def seed_initial_telemetry_history():
    """Seeds 40 smooth continuous historical baseline telemetry points at accelerated scale (1s = 3h, 8s = 1d)."""
    # Lazy import to avoid circular import at module level
    from backend.app.api.v1.ingest import feature_engine, detector_ensemble

    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        # Check if database has old chaotic readings or needs refresh
        total_readings = db.query(SensorReading).count()
        if total_readings < 30:
            logger.info("[Simulator] Initializing smooth physical baseline trajectory across all 5 AWS hubs...")
            for st_id, cfg in STATIONS_CONFIG.items():
                temp_state = StationAtmosphericState(st_id, cfg)
                for i in range(40, 0, -1):
                    # Accelerated scale: 3 hours per step (8 steps = 1 day)
                    point_time = now - timedelta(hours=i * 3.0)
                    reading = temp_state.step(point_time)
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
            db.commit()

        # Ensure demo anomaly incidents exist in Incident Center
        anom_count = db.query(AnomalyEvent).count()
        if anom_count == 0:
            logger.info("[Simulator] Seeding baseline demo anomaly incidents for Incident Center...")
            demo_events = [
                AnomalyEvent(
                    event_id=f"EVT-AWS-DEL-01-{int(now.timestamp()) - 180}",
                    station_id="AWS-DEL-01",
                    timestamp=now - timedelta(minutes=3),
                    severity_score=0.92,
                    confidence_score=0.97,
                    detector_scores={
                        "rule_bounds": 0.0,
                        "flatline_zero_variance": 0.0,
                        "iforest_multivariate": 0.89,
                        "autoencoder_reconstruction": 0.94,
                        "drift_stl_cusum": 0.15,
                        "spatial_idw_consistency": 0.82
                    },
                    root_cause="PHYSICAL_OUTLIER_SPIKE",
                    explanation="Sudden temperature excursion (+14.2°C in 5 min) detected on AWS-DEL-01. Imputed clean signal: 27.4°C.",
                    shap_attributions={
                        "temperature_c": 0.74,
                        "dT_dt": 0.16,
                        "dew_point_c": 0.06,
                        "humidity_pct": 0.04
                    },
                    estimated_corrected_values={
                        "temperature_c": 27.4,
                        "pressure_hpa": 998.5,
                        "humidity_pct": 67.8,
                        "is_imputed": True
                    },
                    status="ACTIVE"
                ),
                AnomalyEvent(
                    event_id=f"EVT-AWS-JAI-01-{int(now.timestamp()) - 600}",
                    station_id="AWS-JAI-01",
                    timestamp=now - timedelta(minutes=10),
                    severity_score=0.78,
                    confidence_score=0.93,
                    detector_scores={
                        "rule_bounds": 0.0,
                        "flatline_zero_variance": 0.0,
                        "iforest_multivariate": 0.72,
                        "autoencoder_reconstruction": 0.79,
                        "drift_stl_cusum": 0.88,
                        "spatial_idw_consistency": 0.60
                    },
                    root_cause="CALIBRATION_DRIFT",
                    explanation="Monotonic upward temperature drift (+0.25°C/hr) identified via CUSUM and Isolation Forest.",
                    shap_attributions={
                        "temperature_c": 0.65,
                        "t_delta_zscore": 0.22,
                        "humidity_pct": 0.13
                    },
                    estimated_corrected_values={
                        "temperature_c": 31.8,
                        "pressure_hpa": 985.4,
                        "humidity_pct": 48.0,
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
    """Continuous async loop executing ML inference and broadcasting to WebSockets at 1s = 3h, 8s = 1d scale."""
    # Lazy imports — avoids circular import at module load time
    from backend.app.api.v1.websocket import ws_manager
    from backend.app.api.v1.ingest import (
        feature_engine,
        detector_ensemble,
        ExplainabilityEngine,
        imputer,
        health_engine,
        alert_manager,
    )

    logger.info("[Simulator] Initializing High-Fidelity Background Weather Stream (1s = 3h / 8s = 1d scale)...")

    # 1. Ensure continuous baseline history
    await asyncio.to_thread(seed_initial_telemetry_history)

    station_keys = list(STATIONS_CONFIG.keys())
    step = 0
    sim_base_time = datetime.now(timezone.utc)
    loop_start_real = time.time()

    while True:
        try:
            # Scale: 1 real second = 3 simulated hours (8 real seconds = 24 simulated hours = 1 full day)
            elapsed_real_sec = time.time() - loop_start_real
            simulated_now = sim_base_time + timedelta(hours=elapsed_real_sec * 3.0)

            # Cycle through all 5 stations
            st_id = station_keys[step % len(station_keys)]
            step += 1

            # 1. Generate continuous physics reading & apply UI injections
            reading = _generate_synthetic_reading(st_id, simulated_now)
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
            # FIX: Restore top-level "imputed" key consumed by frontend App.jsx
            # (data.imputed?.is_imputed / data.imputed?.temperature_c)
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
                "imputed": corrected,
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

        # Continuous smooth stream (2s per station tick)
        await asyncio.sleep(2.0)

import uuid
import json
import csv
import io
import time
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Header, HTTPException, status, UploadFile, File, Request, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional, List

from backend.app.core.database import get_db
from backend.app.core.security import verify_telemetry_signature
from backend.app.core.cache import station_cache
from backend.app.core.logging import logger
from backend.app.core.errors import SignatureVerificationError, StationNotFoundError, InvalidTelemetryError
from backend.app.core.limiter import limiter
from backend.app.schemas.telemetry import RawTelemetryIn, TelemetryIngestResponse
from backend.app.models.station import WeatherStation
from backend.app.models.reading import SensorReading
from backend.app.models.anomaly import AnomalyEvent
from backend.app.models.dead_letter import DeadLetterRecord
from backend.app.services.feature_eng import MeteorologicalFeatureEngine
from backend.app.services.detectors import HybridDetectorEnsemble
from backend.app.services.xai import ExplainabilityEngine
from backend.app.services.imputer import ValueImputer
from backend.app.services.health_score import SensorHealthEngine
from backend.app.services.alert_manager import alert_manager
from backend.app.services.metrics import metrics
from backend.app.api.v1.websocket import ws_manager
from backend.app.api.v1.auth import get_current_user
from backend.app.models.user import User

# VULN-07 FIX: Maximum CSV upload size (50 MB)
_MAX_UPLOAD_BYTES = 50 * 1024 * 1024

router = APIRouter(tags=["Data Ingestion Pipeline"])

# Global Singleton Services
feature_engine = MeteorologicalFeatureEngine("data/metadata/climate_normals.csv")
detector_ensemble = HybridDetectorEnsemble("models")
imputer = ValueImputer("models")
health_engine = SensorHealthEngine()

def _fetch_station_from_db(db: Session, station_id: str) -> Optional[Dict[str, Any]]:
    """Helper to load and cache station metadata"""
    st = db.query(WeatherStation).filter(WeatherStation.station_id == station_id).first()
    if not st:
        return None
    return {
        "station_id": st.station_id,
        "name": st.name,
        "altitude_m": st.altitude_m,
        "latitude": st.latitude,
        "longitude": st.longitude,
        "api_secret_key": st.api_secret_key
    }

@router.post(
    "/ingest/telemetry",
    response_model=TelemetryIngestResponse,
    summary="High-Throughput Telemetry Ingestion (Assembly Line)",
    response_description="Processed reading with anomaly classification, XAI attributions, and imputed values"
)
@limiter.limit("60/minute")  # VULN-04 FIX: Rate-limit per-IP — prevents ML pipeline flooding
async def ingest_telemetry_reading(
    request: Request,
    reading: RawTelemetryIn,
    background_tasks: BackgroundTasks,
    x_station_id: Optional[str] = Header(None, alias="X-Station-ID"),
    x_station_signature: Optional[str] = Header(None, alias="X-Station-Signature"),
    db: Session = Depends(get_db)
):
    """
    Core Streaming Ingestion Pipeline (Sub-5ms Target):
    1. Cache-Accelerated Station Metadata & HMAC Auth
    2. Meteorological Feature Engineering (32 dimensions)
    3. Multi-Detector ML Ensemble Evaluation
    4. Autoencoder Value Imputation & Sensor Health Scoring
    5. Asynchronous Multi-Channel Alerting & WebSocket Broadcast
    """
    start_time = time.perf_counter()
    st_id = reading.station_id
    payload_dict = reading.model_dump()
    
    # 1. In-Memory Cache Lookup for Station Metadata (Eliminates redundant SQL query)
    cached_station = station_cache.get(st_id)
    if not cached_station:
        cached_station = _fetch_station_from_db(db, st_id)
        if cached_station:
            station_cache.set(st_id, cached_station)

    station_secret = cached_station["api_secret_key"] if cached_station else None
    altitude = cached_station["altitude_m"] if cached_station else (reading.altitude_m or 0.0)
    payload_dict["altitude_m"] = altitude

    # 2. VULN-03 FIX: Cryptographic HMAC-SHA256 — Now MANDATORY (not optional)
    # Reject any request that omits the X-Station-Signature header entirely.
    if not x_station_signature:
        dlq = DeadLetterRecord(
            station_id=st_id,
            raw_payload=json.dumps(payload_dict, default=str),
            failure_reason="MISSING_SIGNATURE",
            error_detail="X-Station-Signature header is required. Unsigned telemetry is rejected.",
            source_ip=getattr(request.client, 'host', 'unknown') if hasattr(request, 'client') else 'unknown'
        )
        db.add(dlq)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Station-Signature header is required for telemetry ingestion."
        )

    is_valid_sig = verify_telemetry_signature(
        station_id=st_id,
        timestamp_iso=reading.timestamp.isoformat(),
        payload_dict=payload_dict,
        signature=x_station_signature,
        secret_key=station_secret
    )
    if not is_valid_sig:
        # Quarantine invalid signature payload to Dead-Letter Queue
        dlq = DeadLetterRecord(
            station_id=st_id,
            raw_payload=json.dumps(payload_dict, default=str),
            failure_reason="HMAC_FAILURE",
            error_detail="HMAC-SHA256 signature verification failed — possible packet tampering or key mismatch.",
            source_ip=getattr(request.client, 'host', 'unknown') if hasattr(request, 'client') else 'stream'
        )
        db.add(dlq)
        db.commit()
        raise SignatureVerificationError(station_id=st_id, reason="Cryptographic signature mismatch.")

    # 3. Stream Feature Extraction
    t0 = time.perf_counter()
    features = feature_engine.extract_features(payload_dict)
    t_feat = (time.perf_counter() - t0) * 1000.0

    # 4. Multi-Detector ML Ensemble Evaluation
    t0 = time.perf_counter()
    detection = detector_ensemble.detect(features)
    t_detect = (time.perf_counter() - t0) * 1000.0
    
    is_anomaly = detection["is_anomaly"]
    severity = detection["severity_score"]
    root_cause = detection["root_cause"]
    attributions = detection.get("shap_attributions", {})

    # 5. Explainable AI (XAI) Narrative
    explanation = ExplainabilityEngine.generate_explanation(features, detection)

    # 6. Corrected Value Imputation
    t0 = time.perf_counter()
    corrected = imputer.impute_corrected_values(features, is_anomaly, attributions)
    t_impute = (time.perf_counter() - t0) * 1000.0

    # 7. Real-Time Health Scoring & Predictive Maintenance
    db_station = db.query(WeatherStation).filter(WeatherStation.station_id == st_id).first()
    last_cal = db_station.last_calibration_date if db_station else None
    inst_yr = db_station.install_year if db_station else 2018
    curr_mo = reading.timestamp.month

    health_update = health_engine.update_health(
        station_id=st_id,
        is_anomaly=is_anomaly,
        severity_score=severity,
        drift_score=detection["detector_scores"].get("drift_stl_cusum", 0.0),
        last_calibration_date=last_cal,
        install_year=inst_yr,
        current_month=curr_mo
    )

    if db_station:
        db_station.health_score = health_update["health_score"]
        db_station.health_status = health_update["status"]
        db_station.last_seen = datetime.now(timezone.utc)

    # 8. Persist to Database (TimescaleDB Hypertables)
    db_reading = SensorReading(
        station_id=st_id,
        timestamp=reading.timestamp,
        temperature_c=reading.temperature_c,
        pressure_hpa=reading.pressure_hpa,
        humidity_pct=reading.humidity_pct,
        dew_point_c=features["physics_features"]["dew_point_c"],
        sea_level_pressure_hpa=features["physics_features"]["sea_level_pressure_hpa"],
        is_anomaly=is_anomaly,
        severity_score=severity,
        is_imputed=corrected["is_imputed"],
        imputed_temperature_c=corrected.get("temperature_c", reading.temperature_c),
        imputed_pressure_hpa=corrected.get("pressure_hpa", reading.pressure_hpa),
        imputed_humidity_pct=corrected.get("humidity_pct", reading.humidity_pct)
    )
    db.add(db_reading)

    # Save Anomaly Event if flagged
    event_id = None
    if is_anomaly:
        event_id = f"evt-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"
        db_event = AnomalyEvent(
            event_id=event_id,
            station_id=st_id,
            timestamp=reading.timestamp,
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

        # Offload multi-channel alerting to non-blocking background task
        background_tasks.add_task(
            alert_manager.process_and_dispatch,
            {
                "event_id": event_id,
                "station_id": st_id,
                "severity_score": severity,
                "root_cause": root_cause,
                "explanation": explanation,
                "timestamp": reading.timestamp.isoformat()
            }
        )

    db.commit()

    total_latency_ms = (time.perf_counter() - start_time) * 1000.0

    # Record Telemetry Metrics
    metrics.record_ingest(
        duration_ms=total_latency_ms,
        is_anomaly=is_anomaly,
        root_cause=root_cause,
        timings={
            "feature_extraction": t_feat,
            "autoencoder": t_detect,
            "imputation": t_impute
        }
    )

    # 9. Real-Time Broadcast to Connected Dashboards via WebSocket
    broadcast_payload = {
        "type": "TELEMETRY_INGESTED",
        "station_id": st_id,
        "timestamp": reading.timestamp.isoformat() if reading.timestamp.tzinfo else f"{reading.timestamp.isoformat()}Z",
        "reading": {
            "temperature_c": reading.temperature_c,
            "pressure_hpa": reading.pressure_hpa,
            "humidity_pct": reading.humidity_pct,
            "dew_point_c": features["physics_features"]["dew_point_c"],
            "sea_level_pressure_hpa": features["physics_features"]["sea_level_pressure_hpa"],
        },
        "imputed": corrected,
        "is_anomaly": is_anomaly,
        "severity_score": severity,
        "root_cause": root_cause,
        "explanation": explanation,
        "health_score": health_update["health_score"],
        "health_status": health_update["status"]
    }
    background_tasks.add_task(ws_manager.broadcast, broadcast_payload)

    return TelemetryIngestResponse(
        status="PROCESSED",
        station_id=st_id,
        is_anomaly=is_anomaly,
        severity_score=severity,
        root_cause=root_cause,
        explanation=explanation,
        imputed_values=corrected,
        station_health_score=health_update["health_score"],
        event_id=event_id,
        pipeline_latency_ms=round(total_latency_ms, 2)
    )

# ==============================================================================
# POST /ingest/batch-csv — Optimized Bulk Historical CSV Upload
# ==============================================================================
@router.post("/ingest/batch-csv", summary="Bulk CSV Batch Telemetry Ingestion")
async def ingest_batch_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    High-speed batch processing for bulk historical AWS observation datasets.
    Executes the complete ML quality control pipeline with bulk database commits.
    """
    # VULN-07 FIX: Enforce 50MB upload cap + MIME type validation
    if file.content_type not in ("text/csv", "application/csv", "text/plain", None):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid MIME type '{file.content_type}'. Upload must be a CSV file (text/csv)."
        )

    content = await file.read(_MAX_UPLOAD_BYTES + 1)
    if len(content) > _MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="CSV upload exceeds 50MB limit. Split into smaller files."
        )
    text_data = content.decode('utf-8')
    reader = csv.DictReader(io.StringIO(text_data))

    processed = 0
    anomalies_detected = 0
    errors = []

    readings_to_save = []
    events_to_save = []

    for row_idx, row in enumerate(reader):
        try:
            st_id = row.get("station_id", "AWS-DEL-01")
            ts_str = row.get("timestamp")
            
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00")) if ts_str else datetime.now(timezone.utc)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)

            payload_dict = {
                "station_id": st_id,
                "timestamp": ts,
                "temperature_c": float(row["temperature_c"]),
                "pressure_hpa": float(row["pressure_hpa"]),
                "humidity_pct": float(row["humidity_pct"]),
                "latitude": float(row.get("latitude", 28.6139)),
                "longitude": float(row.get("longitude", 77.2090)),
                "altitude_m": float(row.get("altitude_m", 216.0)),
            }

            features = feature_engine.extract_features(payload_dict)
            detection = detector_ensemble.detect(features)
            is_anom = detection["is_anomaly"]
            severity = detection["severity_score"]
            root_cause = detection["root_cause"]
            attributions = detection.get("shap_attributions", {})
            explanation = ExplainabilityEngine.generate_explanation(features, detection)
            corrected = imputer.impute_corrected_values(features, is_anom, attributions)

            readings_to_save.append(SensorReading(
                station_id=st_id,
                timestamp=ts,
                temperature_c=payload_dict["temperature_c"],
                pressure_hpa=payload_dict["pressure_hpa"],
                humidity_pct=payload_dict["humidity_pct"],
                dew_point_c=features["physics_features"]["dew_point_c"],
                sea_level_pressure_hpa=features["physics_features"]["sea_level_pressure_hpa"],
                is_anomaly=is_anom,
                severity_score=severity,
                is_imputed=corrected["is_imputed"],
                imputed_temperature_c=corrected["temperature_c"] if corrected["is_imputed"] else None,
                imputed_pressure_hpa=corrected["pressure_hpa"] if corrected["is_imputed"] else None,
                imputed_humidity_pct=corrected["humidity_pct"] if corrected["is_imputed"] else None
            ))

            if is_anom:
                anomalies_detected += 1
                events_to_save.append(AnomalyEvent(
                    event_id=f"evt-batch-{uuid.uuid4().hex[:10]}",
                    station_id=st_id,
                    timestamp=ts,
                    severity_score=severity,
                    confidence_score=detection["confidence_score"],
                    detector_scores=detection["detector_scores"],
                    root_cause=root_cause,
                    explanation=explanation,
                    shap_attributions=attributions,
                    estimated_corrected_values=corrected,
                    status="ACTIVE"
                ))

            processed += 1

            # Chunk commit every 500 records
            if len(readings_to_save) >= 500:
                db.bulk_save_objects(readings_to_save)
                if events_to_save:
                    db.bulk_save_objects(events_to_save)
                db.commit()
                readings_to_save.clear()
                events_to_save.clear()

        except Exception as e:
            errors.append(f"Row {row_idx + 1}: {str(e)}")
            if len(errors) > 20:
                break

    # Flush remaining
    if readings_to_save:
        db.bulk_save_objects(readings_to_save)
    if events_to_save:
        db.bulk_save_objects(events_to_save)
    db.commit()

    return {
        "status": "BATCH_COMPLETE",
        "total_rows_processed": processed,
        "anomalies_detected": anomalies_detected,
        "errors_count": len(errors),
        "errors_sample": errors[:5]
    }

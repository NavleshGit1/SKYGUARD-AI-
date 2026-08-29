import math
import re
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status, Path
from sqlalchemy.orm import Session
from sqlalchemy import func, text
from typing import List, Dict, Any, Optional

from backend.app.core.database import get_db
from backend.app.core.cache import station_cache
from backend.app.core.errors import StationNotFoundError
from backend.app.models.station import WeatherStation
from backend.app.models.reading import SensorReading
from backend.app.models.anomaly import AnomalyEvent

# VULN-12 FIX: station_id format constraint — alphanumeric, dashes, max 30 chars
_STATION_ID_PATTERN = r'^[A-Za-z0-9][A-Za-z0-9\-_]{1,28}[A-Za-z0-9]$'

router = APIRouter(tags=["Stations & Telemetry Analytics"])

from backend.app.services.background_simulator import _generate_synthetic_reading, STATIONS_CONFIG

@router.get("/stations", response_model=List[Dict[str, Any]], summary="List All Weather Stations with Latest Telemetry")
def get_all_stations(db: Session = Depends(get_db)):
    """Fetch list of all weather stations with coordinates, current health score, and latest telemetry packet."""
    stations = db.query(WeatherStation).all()
    results = []
    now = datetime.now(timezone.utc)
    
    for st in stations:
        latest = db.query(SensorReading).filter(
            SensorReading.station_id == st.station_id
        ).order_by(SensorReading.timestamp.desc()).first()

        if latest:
            latest_dict = {
                "temperature_c": latest.temperature_c,
                "pressure_hpa": latest.pressure_hpa,
                "humidity_pct": latest.humidity_pct,
                "dew_point_c": latest.dew_point_c,
                "sea_level_pressure_hpa": latest.sea_level_pressure_hpa,
                "is_anomaly": latest.is_anomaly,
                "timestamp": latest.timestamp.isoformat() if latest.timestamp else now.isoformat()
            }
        else:
            # High-fidelity baseline fallback (ensures zero blank values on initial cold boot)
            st_key = st.station_id if st.station_id in STATIONS_CONFIG else "AWS-DEL-01"
            syn = _generate_synthetic_reading(st_key, now)
            latest_dict = {
                "temperature_c": syn["temperature_c"],
                "pressure_hpa": syn["pressure_hpa"],
                "humidity_pct": syn["humidity_pct"],
                "dew_point_c": round(syn["temperature_c"] - ((100 - syn["humidity_pct"]) / 5), 1),
                "sea_level_pressure_hpa": round(syn["pressure_hpa"] + (st.altitude_m / 8.3), 1),
                "is_anomaly": False,
                "timestamp": now.isoformat()
            }

        results.append({
            "station_id": st.station_id,
            "name": st.name,
            "latitude": st.latitude,
            "longitude": st.longitude,
            "altitude_m": st.altitude_m,
            "district": st.district,
            "state": st.state,
            "climate_zone": st.climate_zone,
            "health_score": st.health_score,
            "health_status": st.health_status,
            "is_active": st.is_active,
            "last_seen": st.last_seen.isoformat() if st.last_seen else now.isoformat(),
            "latest_reading": latest_dict
        })
    return results

@router.get("/stations/stats/summary", summary="Network-Wide Operational Summary")
def get_network_summary(db: Session = Depends(get_db)):
    """Computes real-time network-wide telemetry health indices and status distribution."""
    total_stations = db.query(WeatherStation).count()
    healthy_count = db.query(WeatherStation).filter(WeatherStation.health_score >= 85.0).count()
    degraded_count = db.query(WeatherStation).filter(WeatherStation.health_score >= 60.0, WeatherStation.health_score < 85.0).count()
    critical_count = db.query(WeatherStation).filter(WeatherStation.health_score < 60.0).count()
    active_anomalies = db.query(AnomalyEvent).filter(AnomalyEvent.status == "ACTIVE").count()
    
    avg_health_row = db.query(func.avg(WeatherStation.health_score)).scalar()
    avg_health = round(float(avg_health_row), 1) if avg_health_row is not None else 100.0

    return {
        "total_stations": total_stations,
        "average_health_score": avg_health,
        "healthy_stations": healthy_count,
        "degraded_stations": degraded_count,
        "critical_stations": critical_count,
        "active_anomaly_incidents": active_anomalies,
        "system_status": "OPTIMAL" if avg_health >= 85 else ("ATTENTION" if avg_health >= 60 else "CRITICAL")
    }

@router.get("/stations/{station_id}", response_model=Dict[str, Any], summary="Station Profile & Recent Stream")
def get_station_details(
    station_id: str = Path(..., pattern=_STATION_ID_PATTERN, max_length=30,  # VULN-12 FIX
                           description="Station ID (alphanumeric + dashes, max 30 chars)"),
    db: Session = Depends(get_db)
):
    """Fetch detailed profile and recent 50 readings for a specific station."""
    station = db.query(WeatherStation).filter(WeatherStation.station_id == station_id).first()
    if not station:
        raise StationNotFoundError(station_id=station_id)
        
    readings = db.query(SensorReading).filter(
        SensorReading.station_id == station_id
    ).order_by(SensorReading.timestamp.desc()).limit(50).all()
    
    if readings:
        recent_list = [
            {
                "id": r.id,
                "timestamp": r.timestamp.isoformat() if r.timestamp.tzinfo else f"{r.timestamp.isoformat()}Z",
                "temperature_c": r.temperature_c,
                "pressure_hpa": r.pressure_hpa,
                "humidity_pct": r.humidity_pct,
                "dew_point_c": r.dew_point_c,
                "sea_level_pressure_hpa": r.sea_level_pressure_hpa,
                "is_anomaly": r.is_anomaly,
                "severity_score": r.severity_score,
                "is_imputed": r.is_imputed,
                "imputed_temperature_c": r.imputed_temperature_c,
                "imputed_pressure_hpa": r.imputed_pressure_hpa,
                "imputed_humidity_pct": r.imputed_humidity_pct
            }
            for r in readings
        ]
    else:
        # Fallback baseline history points so charts immediately render smooth curves
        now = datetime.now(timezone.utc)
        from datetime import timedelta
        recent_list = []
        st_key = station_id if station_id in STATIONS_CONFIG else "AWS-DEL-01"
        for i in range(25, 0, -1):
            pt = now - timedelta(minutes=i * 3)
            syn = _generate_synthetic_reading(st_key, pt)
            recent_list.append({
                "id": i,
                "timestamp": pt.isoformat(),
                "temperature_c": syn["temperature_c"],
                "pressure_hpa": syn["pressure_hpa"],
                "humidity_pct": syn["humidity_pct"],
                "dew_point_c": round(syn["temperature_c"] - ((100 - syn["humidity_pct"]) / 5), 1),
                "sea_level_pressure_hpa": round(syn["pressure_hpa"] + (station.altitude_m / 8.3), 1),
                "is_anomaly": False,
                "severity_score": 0.0,
                "is_imputed": False,
                "imputed_temperature_c": None,
                "imputed_pressure_hpa": None,
                "imputed_humidity_pct": None
            })

    return {
        "station_id": station.station_id,
        "name": station.name,
        "latitude": station.latitude,
        "longitude": station.longitude,
        "altitude_m": station.altitude_m,
        "district": station.district,
        "state": station.state,
        "climate_zone": station.climate_zone,
        "health_score": station.health_score,
        "health_status": station.health_status,
        "is_active": station.is_active,
        "recent_readings": recent_list
    }

@router.get("/stations/{station_id}/aggregate", summary="Time-Series Downsampling & Statistical Aggregation")
@router.get("/stations/{station_id}/analytics", summary="Time-Series Analytics & Statistical Aggregation")
def get_station_aggregates(
    station_id: str = Path(..., pattern=_STATION_ID_PATTERN, max_length=30,  # VULN-12 FIX
                           description="Station ID (alphanumeric + dashes, max 30 chars)"),
    interval_minutes: int = Query(60, ge=1, le=1440, description="Bucket interval window in minutes (1, 5, 15, 60, 1440)"),
    limit_buckets: int = Query(48, ge=1, le=500, description="Maximum number of historical buckets"),
    db: Session = Depends(get_db)
):
    """
    Time-series statistical rollups: Computes min, max, avg, and sample counts
    for temperature, pressure, and humidity across downsampled bucket intervals.
    """
    station = db.query(WeatherStation).filter(WeatherStation.station_id == station_id).first()
    if not station:
        raise StationNotFoundError(station_id=station_id)

    readings = db.query(SensorReading).filter(
        SensorReading.station_id == station_id
    ).order_by(SensorReading.timestamp.desc()).limit(limit_buckets * 10).all()

    if not readings:
        return {"station_id": station_id, "interval_minutes": interval_minutes, "buckets": []}

    # Group into time buckets
    buckets = []
    bucket_size_sec = interval_minutes * 60
    current_bucket = []
    bucket_start_ts = None

    for r in reversed(readings):
        r_ts = r.timestamp.timestamp()
        if bucket_start_ts is None:
            bucket_start_ts = r_ts

        if r_ts - bucket_start_ts < bucket_size_sec:
            current_bucket.append(r)
        else:
            if current_bucket:
                temps = [x.temperature_c for x in current_bucket if x.temperature_c is not None]
                press = [x.pressure_hpa for x in current_bucket if x.pressure_hpa is not None]
                hums = [x.humidity_pct for x in current_bucket if x.humidity_pct is not None]
                anoms = sum(1 for x in current_bucket if x.is_anomaly)

                buckets.append({
                    "bucket_time": datetime.fromtimestamp(bucket_start_ts, tz=timezone.utc).isoformat(),
                    "count": len(current_bucket),
                    "anomalies_count": anoms,
                    "temperature": {
                        "min": min(temps) if temps else None,
                        "max": max(temps) if temps else None,
                        "avg": round(sum(temps) / len(temps), 2) if temps else None
                    },
                    "pressure": {
                        "min": min(press) if press else None,
                        "max": max(press) if press else None,
                        "avg": round(sum(press) / len(press), 2) if press else None
                    },
                    "humidity": {
                        "min": min(hums) if hums else None,
                        "max": max(hums) if hums else None,
                        "avg": round(sum(hums) / len(hums), 2) if hums else None
                    }
                })
            current_bucket = [r]
            bucket_start_ts = r_ts

    return {
        "station_id": station_id,
        "interval_minutes": interval_minutes,
        "total_buckets": len(buckets),
        "buckets": buckets[-limit_buckets:]
    }

@router.get("/stations/{station_id}/readings", response_model=List[Dict[str, Any]], summary="Historical Readings Query")
def get_station_historical_readings(
    station_id: str = Path(..., pattern=_STATION_ID_PATTERN, max_length=30),  # VULN-12 FIX
    from_time: Optional[str] = None,
    to_time: Optional[str] = None,
    limit: int = 100,
    skip: int = 0,
    anomalies_only: bool = False,
    db: Session = Depends(get_db)
):
    query = db.query(SensorReading).filter(SensorReading.station_id == station_id)
    if from_time:
        query = query.filter(SensorReading.timestamp >= from_time)
    if to_time:
        query = query.filter(SensorReading.timestamp <= to_time)
    if anomalies_only:
        query = query.filter(SensorReading.is_anomaly == True)

    readings = query.order_by(SensorReading.timestamp.desc()).offset(skip).limit(min(limit, 500)).all()
    return [
        {
            "id": r.id,
            "station_id": r.station_id,
            "timestamp": r.timestamp.isoformat() if r.timestamp.tzinfo else f"{r.timestamp.isoformat()}Z",
            "temperature_c": r.temperature_c,
            "pressure_hpa": r.pressure_hpa,
            "humidity_pct": r.humidity_pct,
            "dew_point_c": r.dew_point_c,
            "sea_level_pressure_hpa": r.sea_level_pressure_hpa,
            "is_anomaly": r.is_anomaly,
            "severity_score": r.severity_score,
            "is_imputed": r.is_imputed,
            "qc_flag": "IMPUTED" if r.is_imputed else ("INVALID" if r.is_anomaly else "VALID")
        }
        for r in readings
    ]

@router.get("/readings", response_model=List[Dict[str, Any]], summary="Global Telemetry Query")
def query_all_readings(
    station_id: Optional[str] = None,
    from_time: Optional[str] = None,
    to_time: Optional[str] = None,
    limit: int = 100,
    skip: int = 0,
    anomalies_only: bool = False,
    db: Session = Depends(get_db)
):
    query = db.query(SensorReading)
    if station_id:
        query = query.filter(SensorReading.station_id == station_id)
    if from_time:
        query = query.filter(SensorReading.timestamp >= from_time)
    if to_time:
        query = query.filter(SensorReading.timestamp <= to_time)
    if anomalies_only:
        query = query.filter(SensorReading.is_anomaly == True)

    readings = query.order_by(SensorReading.timestamp.desc()).offset(skip).limit(min(limit, 500)).all()
    return [
        {
            "id": r.id,
            "station_id": r.station_id,
            "timestamp": r.timestamp.isoformat(),
            "temperature_c": r.temperature_c,
            "pressure_hpa": r.pressure_hpa,
            "humidity_pct": r.humidity_pct,
            "dew_point_c": r.dew_point_c,
            "sea_level_pressure_hpa": r.sea_level_pressure_hpa,
            "is_anomaly": r.is_anomaly,
            "severity_score": r.severity_score,
            "is_imputed": r.is_imputed,
            "qc_flag": "IMPUTED" if r.is_imputed else ("INVALID" if r.is_anomaly else "VALID")
        }
        for r in readings
    ]

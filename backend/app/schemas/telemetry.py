from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, field_validator, model_validator

class RawTelemetryIn(BaseModel):
    """
    Contract B.1: Incoming telemetry reading from AWS station.
    Enforces WMO physical climatological ranges and ISO-8601 validation.
    """
    station_id: str = Field(..., description="Unique alphanumeric AWS station code", example="AWS-DEL-01")
    timestamp: datetime = Field(..., description="UTC observation timestamp in ISO-8601 format", example="2026-08-25T14:30:00Z")
    temperature_c: float = Field(..., ge=-80.0, le=65.0, description="Ambient surface temperature in Celsius", example=34.2)
    pressure_hpa: float = Field(..., ge=300.0, le=1150.0, description="Barometric pressure in hectopascals (hPa)", example=1004.8)
    humidity_pct: float = Field(..., ge=0.0, le=100.0, description="Relative humidity percentage (%)", example=68.5)
    latitude: Optional[float] = Field(None, ge=-90.0, le=90.0, description="Station latitude in decimal degrees", example=28.6139)
    longitude: Optional[float] = Field(None, ge=-180.0, le=180.0, description="Station longitude in decimal degrees", example=77.2090)
    altitude_m: Optional[float] = Field(None, ge=-500.0, le=9000.0, description="Station elevation above Mean Sea Level (m)", example=216.0)

    @field_validator("timestamp")
    @classmethod
    def ensure_utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v

    model_config = {
        "json_schema_extra": {
            "example": {
                "station_id": "AWS-DEL-01",
                "timestamp": "2026-08-25T14:30:00Z",
                "temperature_c": 32.5,
                "pressure_hpa": 1012.8,
                "humidity_pct": 65.0,
                "latitude": 28.6139,
                "longitude": 77.2090,
                "altitude_m": 216.0
            }
        }
    }

class TelemetryIngestResponse(BaseModel):
    """Standardized response envelope for streaming ingestion"""
    status: str = Field(..., example="PROCESSED")
    station_id: str = Field(..., example="AWS-DEL-01")
    is_anomaly: bool = Field(..., example=False)
    severity_score: float = Field(..., example=0.12)
    root_cause: Optional[str] = Field(None, example="NORMAL")
    explanation: Optional[str] = Field(None, example="All 6 physical detectors report nominal conditions.")
    imputed_values: Optional[Dict[str, Any]] = None
    station_health_score: float = Field(..., example=98.5)
    event_id: Optional[str] = None
    pipeline_latency_ms: float = Field(..., example=4.85)

class ValidatedTelemetry(BaseModel):
    """Contract B.2: Validated & Metadata-Enriched Telemetry"""
    station_id: str
    station_name: str
    timestamp: datetime
    temperature_c: float
    pressure_hpa: float
    humidity_pct: float
    latitude: float
    longitude: float
    altitude_m: float
    last_calibration_date: Optional[str] = None
    validation_status: str = "VALID"
    clock_drift_sec: float = 0.0

class FeatureVector(BaseModel):
    """Contract B.3: Feature-engineered payload ready for ML detectors"""
    station_id: str
    timestamp: datetime
    raw: Dict[str, float]
    rolling_stats: Dict[str, float]
    derivatives: Dict[str, float]
    physics_features: Dict[str, float]
    climatology_delta: Dict[str, float]
    missingness: Dict[str, float]

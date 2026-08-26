from datetime import datetime
from typing import Dict, Optional, Any
from pydantic import BaseModel, Field

class AnomalyEvent(BaseModel):
    """Contract B.5: Full anomaly detection event payload"""
    event_id: str = Field(..., example="evt-20260825-984321")
    station_id: str = Field(..., example="AWS-DEL-01")
    timestamp: datetime = Field(..., example="2026-08-25T14:30:00Z")
    
    # Detector Scores (0.0 - 1.0)
    detector_scores: Dict[str, float] = Field(
        default_factory=lambda: {
            "rule_physical": 0.0,
            "frozen_sensor": 0.0,
            "statistical_iforest": 0.0,
            "multivariate_autoencoder": 0.0,
            "drift_stl_cusum": 0.0,
            "spatial_cross_check": 0.0
        }
    )
    
    severity_score: float = Field(..., ge=0.0, le=1.0, example=0.91)
    confidence_score: float = Field(..., ge=0.0, le=1.0, example=0.89)
    is_anomaly: bool = Field(..., example=True)
    root_cause: str = Field(..., example="MULTIVARIATE_PHYSICAL_INCONSISTENCY")
    explanation: str = Field(..., example="Flagged because Relative Humidity severely deviated...")
    
    shap_attributions: Dict[str, float] = Field(default_factory=dict)
    estimated_corrected_values: Dict[str, Any] = Field(default_factory=dict)
    sensor_health_score: float = Field(..., ge=0.0, le=100.0, example=78.4)
    resolution_status: str = Field("ACTIVE", example="ACTIVE") # ACTIVE, ACKNOWLEDGED, RESOLVED, FALSE_POSITIVE

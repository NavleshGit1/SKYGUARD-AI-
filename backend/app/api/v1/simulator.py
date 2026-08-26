from fastapi import APIRouter, HTTPException
from typing import Dict, Any, Optional
from pydantic import BaseModel

router = APIRouter()

class AnomalyInjectRequest(BaseModel):
    station_id: str = "AWS-DEL-01"
    anomaly_type: str = "SPIKE" # SPIKE, FLATLINE, DRIFT, THERMODYNAMIC_VIOLATION, NOISE_BURST
    parameter: str = "temperature_c"
    duration_ticks: int = 15
    magnitude: float = 18.0

# In-memory registry for pending simulation injection triggers
ACTIVE_INJECTIONS: Dict[str, Any] = {}

@router.post("/simulator/inject")
def trigger_anomaly_injection(req: AnomalyInjectRequest):
    """Triggers an on-demand live anomaly injection scenario for SIH judges / demonstration"""
    ACTIVE_INJECTIONS[req.station_id] = {
        "type": req.anomaly_type.upper(),
        "parameter": req.parameter,
        "duration": req.duration_ticks,
        "remaining": req.duration_ticks,
        "magnitude": req.magnitude,
        "step_count": 0
    }
    return {
        "status": "TRIGGERED",
        "message": f"Scheduled {req.anomaly_type} injection on {req.station_id} for {req.duration_ticks} cycles.",
        "config": req.model_dump()
    }

@router.get("/simulator/active")
def get_active_injections():
    """Returns currently active simulated anomaly scenarios"""
    return ACTIVE_INJECTIONS

@router.delete("/simulator/active/{station_id}")
def clear_injection(station_id: str):
    """Clears/claims an active anomaly injection once picked up by simulator worker"""
    if station_id in ACTIVE_INJECTIONS:
        del ACTIVE_INJECTIONS[station_id]
        return {"status": "CLEARED", "station_id": station_id}
    return {"status": "NOT_FOUND"}

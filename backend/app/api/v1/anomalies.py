from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field

from backend.app.core.database import get_db
from backend.app.models.anomaly import AnomalyEvent
from backend.app.services.audit_logger import audit_logger
from backend.app.api.v1.auth import get_current_user
from backend.app.models.user import User

router = APIRouter(tags=["Anomaly & XAI Incident Center"])

class ResolveAnomalyRequest(BaseModel):
    status: str = Field(..., example="RESOLVED", description="Lifecycle status: ACKNOWLEDGED, RESOLVED, FALSE_POSITIVE")
    resolved_by: Optional[str] = Field("Operator (Web UI)", example="Operator (Web UI)")
    resolution_notes: Optional[str] = Field(None, example="Transducer recalibrated on site.")

class BulkResolveRequest(BaseModel):
    event_ids: List[str] = Field(..., min_length=1, example=["evt-20260825143000-a1b2c3"])
    status: str = Field("RESOLVED", example="RESOLVED")
    resolved_by: Optional[str] = Field("Operator (Web UI)")
    resolution_notes: Optional[str] = Field("Batch resolved via Incident Center")

@router.get("/anomalies", response_model=List[Dict[str, Any]], summary="Filter & List Detected Anomaly Incidents")
def get_anomalies(
    station_id: Optional[str] = None,
    status: Optional[str] = None,
    min_severity: float = Query(0.0, ge=0.0, le=1.0),
    limit: int = Query(50, ge=1, le=500),
    skip: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """Filter and query detected anomaly events with full SHAP attributions and XAI explanations."""
    query = db.query(AnomalyEvent).filter(AnomalyEvent.severity_score >= min_severity)
    if station_id:
        query = query.filter(AnomalyEvent.station_id == station_id)
    if status:
        query = query.filter(AnomalyEvent.status == status)
        
    events = query.order_by(AnomalyEvent.timestamp.desc()).offset(skip).limit(limit).all()
    
    return [
        {
            "event_id": e.event_id,
            "station_id": e.station_id,
            "timestamp": e.timestamp.isoformat(),
            "severity_score": e.severity_score,
            "confidence_score": e.confidence_score,
            "detector_scores": e.detector_scores,
            "root_cause": e.root_cause,
            "explanation": e.explanation,
            "shap_attributions": e.shap_attributions,
            "estimated_corrected_values": e.estimated_corrected_values,
            "status": e.status,
            "resolved_by": e.resolved_by,
            "resolved_at": e.resolved_at.isoformat() if e.resolved_at else None,
            "resolution_notes": e.resolution_notes
        }
        for e in events
    ]

@router.post("/anomalies/bulk-resolve", summary="Bulk Resolve Anomaly Incidents")
def bulk_resolve_anomalies(
    req: BulkResolveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)  # VULN-05 FIX: auth required
):
    """Resolves multiple anomaly incidents in a single atomic database transaction with audit logging."""
    events = db.query(AnomalyEvent).filter(AnomalyEvent.event_id.in_(req.event_ids)).all()
    if not events:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No matching anomaly events found")

    now = datetime.now(timezone.utc)
    actor = current_user.email  # Use authenticated identity — not client-supplied string
    for e in events:
        e.status = req.status
        e.resolved_by = actor
        e.resolved_at = now
        e.resolution_notes = req.resolution_notes

        audit_logger.log_event(
            actor=actor,
            action=f"ANOMALY_BULK_{req.status}",
            event_id=e.event_id,
            details={"station_id": e.station_id, "root_cause": e.root_cause, "status": req.status}
        )

    db.commit()

    return {
        "status": "BULK_RESOLVED",
        "resolved_count": len(events),
        "target_status": req.status
    }

@router.patch("/anomalies/{event_id}/resolve", response_model=Dict[str, Any], summary="Resolve Single Anomaly Incident")
def resolve_anomaly(
    event_id: str,
    req: ResolveAnomalyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)  # VULN-05 FIX: auth required
):
    """Update lifecycle status of an anomaly event (ACKNOWLEDGED, RESOLVED, FALSE_POSITIVE)"""
    event = db.query(AnomalyEvent).filter(AnomalyEvent.event_id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Anomaly event not found")

    actor = current_user.email  # Use authenticated identity — not client-supplied string
    event.status = req.status
    event.resolved_by = actor
    event.resolved_at = datetime.now(timezone.utc)
    event.resolution_notes = req.resolution_notes

    db.commit()
    db.refresh(event)

    # Log to Cryptographic Append-Only Audit Trail
    audit_logger.log_event(
        actor=actor,
        action=f"ANOMALY_{req.status}",
        event_id=event.event_id,
        details={
            "station_id": event.station_id,
            "root_cause": event.root_cause,
            "severity_score": event.severity_score,
            "status": req.status,
            "notes": req.resolution_notes
        }
    )

    return {
        "event_id": event.event_id,
        "status": event.status,
        "resolved_by": event.resolved_by,
        "resolved_at": event.resolved_at.isoformat()
    }

@router.get("/anomalies/{event_id}", response_model=Dict[str, Any], summary="Inspect Single Anomaly XAI Details")
def get_single_anomaly(event_id: str, db: Session = Depends(get_db)):
    """Fetch single anomaly event details with detector scores, SHAP attributions, and explanation."""
    e = db.query(AnomalyEvent).filter(AnomalyEvent.event_id == event_id).first()
    if not e:
        raise HTTPException(status_code=404, detail=f"Anomaly event '{event_id}' not found")

    return {
        "event_id": e.event_id,
        "station_id": e.station_id,
        "timestamp": e.timestamp.isoformat(),
        "severity_score": e.severity_score,
        "confidence_score": e.confidence_score,
        "detector_scores": e.detector_scores,
        "root_cause": e.root_cause,
        "explanation": e.explanation,
        "shap_attributions": e.shap_attributions,
        "estimated_corrected_values": e.estimated_corrected_values,
        "status": e.status,
        "resolved_by": e.resolved_by,
        "resolved_at": e.resolved_at.isoformat() if e.resolved_at else None,
        "resolution_notes": e.resolution_notes
    }

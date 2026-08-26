"""
SkyGuard AI — Dead-Letter Queue (DLQ) Management & Quarantine Inspection
Inspects malformed schemas, invalid cryptographic HMAC signatures, and provides replay capabilities.
"""

import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.models.dead_letter import DeadLetterRecord
from backend.app.models.user import User
from backend.app.api.v1.auth import get_current_user
from backend.app.schemas.telemetry import RawTelemetryIn

router = APIRouter()

@router.get("/dlq", tags=["Dead-Letter Queue"])
def list_dlq_records(
    limit: int = Query(50, le=500),
    skip: int = Query(0),
    station_id: Optional[str] = Query(None),
    reason: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List quarantined records with error diagnostic details.
    """
    query = db.query(DeadLetterRecord)
    if station_id:
        query = query.filter(DeadLetterRecord.station_id == station_id)
    if reason:
        query = query.filter(DeadLetterRecord.failure_reason == reason)
        
    total = query.count()
    records = query.order_by(DeadLetterRecord.received_at.desc()).offset(skip).limit(limit).all()

    return {
        "total_quarantined": total,
        "records": [
            {
                "id": r.id,
                "station_id": r.station_id,
                "received_at": r.received_at.isoformat() if r.received_at else None,
                "failure_reason": r.failure_reason,
                "error_detail": r.error_detail,
                "raw_payload": r.raw_payload,
                "source_ip": r.source_ip
            }
            for r in records
        ]
    }


@router.delete("/dlq/purge", tags=["Dead-Letter Queue"])
def purge_dlq_records(
    older_than_days: int = Query(30, ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Purge stale quarantined records older than N days.
    """
    cutoff = datetime.now(timezone.utc).timestamp() - (older_than_days * 86400)
    cutoff_dt = datetime.fromtimestamp(cutoff, tz=timezone.utc)
    
    deleted_count = db.query(DeadLetterRecord).filter(DeadLetterRecord.received_at < cutoff_dt).delete()
    db.commit()

    return {
        "status": "PURGED",
        "deleted_records": deleted_count,
        "cutoff_date": cutoff_dt.isoformat()
    }

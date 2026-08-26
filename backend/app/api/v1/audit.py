from fastapi import APIRouter, Query, Depends
from typing import List, Dict, Any
from backend.app.services.audit_logger import audit_logger
from backend.app.api.v1.auth import get_current_user
from backend.app.models.user import User

router = APIRouter()

@router.get("/audit", response_model=List[Dict[str, Any]])
@router.get("/audit/logs", response_model=List[Dict[str, Any]])
def get_audit_logs(limit: int = Query(50, le=200)):
    """Retrieves recent cryptographically chained audit events"""
    return audit_logger.get_recent_logs(limit=limit)

@router.get("/audit/verify", response_model=Dict[str, Any])
def verify_audit_integrity():
    """Validates full SHA-256 hash-chain from Genesis block to guarantee zero tampering"""
    return audit_logger.verify_integrity()

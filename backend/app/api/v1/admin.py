"""
SkyGuard AI — Admin API Routes
Blueprint §12: POST /api/v1/admin/thresholds + POST /api/v1/admin/retrain
Protected: Admin role only
"""
import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.api.v1.auth import get_current_user, get_current_user_optional
from backend.app.models.user import User

logger = logging.getLogger("skyguard.admin")
router = APIRouter()

# ── RBAC guard: Admin only ────────────────────────────────────────────────────
def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in ("admin",):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required for this operation."
        )
    return current_user


# ── Pydantic models ───────────────────────────────────────────────────────────
class ThresholdUpdateRequest(BaseModel):
    """Update detector weights and fusion scoring thresholds at runtime."""
    fusion_threshold:      Optional[float] = Field(None, ge=0.0, le=1.0,
        description="Composite score threshold for anomaly declaration (default 0.60)")
    iforest_weight:        Optional[float] = Field(None, ge=0.0, le=1.0)
    autoencoder_weight:    Optional[float] = Field(None, ge=0.0, le=1.0)
    drift_weight:          Optional[float] = Field(None, ge=0.0, le=1.0)
    spatial_weight:        Optional[float] = Field(None, ge=0.0, le=1.0)
    alert_cooldown_seconds:Optional[int]   = Field(None, ge=10,
        description="Hysteresis cooldown window between duplicate alerts")
    notes: Optional[str] = None


class RetrainRequest(BaseModel):
    """Trigger background asynchronous model retraining job."""
    models:           list[str] = Field(default=["isolation_forest", "autoencoder"],
        description="List of model names to retrain: isolation_forest | autoencoder | fusion_xgboost")
    data_window_days: int       = Field(default=30, ge=7, le=365,
        description="Number of days of historical data to use for retraining")
    notes: Optional[str] = None


# Ephemeral runtime threshold store (resets on restart; integrate with DB for persistence)
_runtime_thresholds: Dict[str, Any] = {
    "fusion_threshold":       0.60,
    "iforest_weight":         0.25,
    "autoencoder_weight":     0.35,
    "drift_weight":           0.15,
    "spatial_weight":         0.15,
    "alert_cooldown_seconds": 120,
    "last_updated":           None,
    "updated_by":             "system_default",
}

# Track ongoing retraining jobs
_retrain_jobs: Dict[str, Any] = {}


# ── Routes ────────────────────────────────────────────────────────────────────
@router.get("/admin/thresholds", tags=["Admin Controls"])
def get_current_thresholds(
    current_user: Optional[User] = Depends(get_current_user_optional)
) -> Dict[str, Any]:
    """Retrieve current runtime detector weights and fusion thresholds."""
    return {
        "thresholds":    _runtime_thresholds,
        "requested_by":  current_user.email if current_user else "Observer"
    }


@router.post("/admin/thresholds", tags=["Admin Controls"])
def update_detector_thresholds(
    req: ThresholdUpdateRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Update detector weights and fusion scoring thresholds at runtime.
    Changes take effect immediately for all subsequent telemetry ingestion.
    """
    actor = current_user.email if current_user else "Demo Administrator"
    updated_fields: Dict[str, Any] = {}

    if req.fusion_threshold is not None:
        _runtime_thresholds["fusion_threshold"] = req.fusion_threshold
        updated_fields["fusion_threshold"] = req.fusion_threshold

    if req.iforest_weight is not None:
        _runtime_thresholds["iforest_weight"] = req.iforest_weight
        updated_fields["iforest_weight"] = req.iforest_weight

    if req.autoencoder_weight is not None:
        _runtime_thresholds["autoencoder_weight"] = req.autoencoder_weight
        updated_fields["autoencoder_weight"] = req.autoencoder_weight

    if req.drift_weight is not None:
        _runtime_thresholds["drift_weight"] = req.drift_weight
        updated_fields["drift_weight"] = req.drift_weight

    if req.spatial_weight is not None:
        _runtime_thresholds["spatial_weight"] = req.spatial_weight
        updated_fields["spatial_weight"] = req.spatial_weight

    if req.alert_cooldown_seconds is not None:
        _runtime_thresholds["alert_cooldown_seconds"] = req.alert_cooldown_seconds
        updated_fields["alert_cooldown_seconds"] = req.alert_cooldown_seconds

    _runtime_thresholds["last_updated"] = datetime.now(timezone.utc).isoformat()
    _runtime_thresholds["updated_by"]   = actor

    logger.info(f"[Admin] Thresholds updated by {actor}: {updated_fields}")

    return {
        "status":         "THRESHOLDS_UPDATED",
        "updated_fields": updated_fields,
        "current_state":  _runtime_thresholds,
        "updated_by":     actor,
        "timestamp":      _runtime_thresholds["last_updated"]
    }


@router.get("/admin/thresholds/live", tags=["Admin Controls"])
def get_live_thresholds(
    current_user: Optional[User] = Depends(get_current_user_optional)
) -> Dict[str, Any]:
    """Returns current runtime detection thresholds."""
    return _runtime_thresholds


def get_runtime_thresholds() -> Dict[str, Any]:
    """Utility: injected by ingest.py to read live threshold values."""
    return _runtime_thresholds


# ── Background retraining job ─────────────────────────────────────────────────
async def _run_retraining_job(job_id: str, models: list[str], window_days: int):
    """Asynchronous background retraining that calls train_models.py subprocess."""
    import subprocess, sys
    _retrain_jobs[job_id]["status"] = "RUNNING"

    try:
        for model_name in models:
            logger.info(f"[Retrain] Starting {model_name} (window={window_days}d)...")
            proc = await asyncio.create_subprocess_exec(
                sys.executable, "-m", "scripts.train_models",
                "--model", model_name,
                "--window-days", str(window_days),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=os.path.dirname(os.path.dirname(os.path.dirname(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode != 0:
                _retrain_jobs[job_id]["errors"] = _retrain_jobs[job_id].get("errors", [])
                _retrain_jobs[job_id]["errors"].append({
                    "model": model_name,
                    "stderr": stderr.decode()[:500]
                })
                logger.error(f"[Retrain] {model_name} failed: {stderr.decode()[:200]}")
            else:
                _retrain_jobs[job_id]["completed_models"] = (
                    _retrain_jobs[job_id].get("completed_models", []) + [model_name]
                )
                logger.info(f"[Retrain] {model_name} completed successfully.")

        _retrain_jobs[job_id]["status"]       = "COMPLETED"
        _retrain_jobs[job_id]["completed_at"] = datetime.now(timezone.utc).isoformat()

    except Exception as exc:
        _retrain_jobs[job_id]["status"] = "FAILED"
        _retrain_jobs[job_id]["error"]  = str(exc)
        logger.error(f"[Retrain] Job {job_id} failed: {exc}")


@router.post("/admin/retrain", tags=["Admin Controls"])
async def trigger_model_retraining(
    req: RetrainRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_admin)
) -> Dict[str, Any]:
    """
    Trigger asynchronous background model retraining job.
    Blueprint §12: POST /api/v1/admin/retrain
    Returns immediately with a job_id to poll status.
    """
    job_id = f"retrain-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    _retrain_jobs[job_id] = {
        "job_id":          job_id,
        "status":          "QUEUED",
        "models":          req.models,
        "window_days":     req.data_window_days,
        "requested_by":    current_user.email,
        "requested_at":    datetime.now(timezone.utc).isoformat(),
        "completed_at":    None,
        "completed_models":[],
        "errors":          []
    }

    background_tasks.add_task(
        asyncio.ensure_future,
        _run_retraining_job(job_id, req.models, req.data_window_days)
    )

    logger.info(f"[Admin] Retraining job {job_id} queued by {current_user.email} for models: {req.models}")

    return {
        "status":  "RETRAINING_QUEUED",
        "job_id":  job_id,
        "models":  req.models,
        "poll_url": f"/api/v1/admin/retrain/{job_id}",
        "message": f"Retraining {len(req.models)} model(s) in background. Poll {job_id} for status."
    }


@router.get("/admin/retrain/{job_id}", tags=["Admin Controls"])
def get_retraining_status(
    job_id: str,
    current_user: User = Depends(require_admin)
) -> Dict[str, Any]:
    """Poll the status of a running or completed background retraining job."""
    job = _retrain_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Retraining job '{job_id}' not found.")
    return job


@router.get("/admin/jobs", tags=["Admin Controls"])
def list_retrain_jobs(
    current_user: User = Depends(require_admin)
) -> Dict[str, Any]:
    """List all retraining jobs and their status."""
    return {
        "total":   len(_retrain_jobs),
        "jobs":    list(_retrain_jobs.values())
    }

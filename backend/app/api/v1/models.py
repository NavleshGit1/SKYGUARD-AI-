from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from backend.app.core.database import get_db
from backend.app.models.model_registry import ModelRegistry

router = APIRouter()

@router.get("/models", response_model=List[Dict[str, Any]])
def list_models(db: Session = Depends(get_db)):
    """List all registered AI/ML models, architectures, and evaluation metrics"""
    models = db.query(ModelRegistry).order_by(ModelRegistry.trained_at.desc()).all()
    return [
        {
            "model_id": m.model_id,
            "model_name": m.model_name,
            "model_type": m.model_type,
            "version": m.version,
            "checkpoint_path": m.checkpoint_path,
            "hyperparameters": m.hyperparameters,
            "input_dimension": m.input_dimension,
            "latent_dimension": m.latent_dimension,
            "f1_score": m.f1_score,
            "precision": m.precision,
            "recall": m.recall,
            "validation_loss_mse": m.validation_loss_mse,
            "inference_latency_ms": m.inference_latency_ms,
            "is_active": m.is_active,
            "trained_at": m.trained_at.isoformat() if m.trained_at else None,
            "description": m.description
        }
        for m in models
    ]

@router.get("/models/active", response_model=List[Dict[str, Any]])
def get_active_models(db: Session = Depends(get_db)):
    """Returns currently deployed models active in the hybrid ensemble"""
    models = db.query(ModelRegistry).filter(ModelRegistry.is_active == True).all()
    return [
        {
            "model_id": m.model_id,
            "model_name": m.model_name,
            "model_type": m.model_type,
            "version": m.version,
            "f1_score": m.f1_score,
            "precision": m.precision,
            "recall": m.recall,
            "inference_latency_ms": m.inference_latency_ms
        }
        for m in models
    ]


@router.get("/models/{model_id}", response_model=Dict[str, Any])
def get_model_details(model_id: str, db: Session = Depends(get_db)):
    """Fetch detailed hyperparameters, checkpoint paths, and metrics for a specific model"""
    m = db.query(ModelRegistry).filter(ModelRegistry.model_id == model_id).first()
    if not m:
        raise HTTPException(status_code=404, detail=f"Model '{model_id}' not found in registry")

    return {
        "model_id": m.model_id,
        "model_name": m.model_name,
        "model_type": m.model_type,
        "version": m.version,
        "checkpoint_path": m.checkpoint_path,
        "hyperparameters": m.hyperparameters,
        "input_dimension": m.input_dimension,
        "latent_dimension": m.latent_dimension,
        "f1_score": m.f1_score,
        "precision": m.precision,
        "recall": m.recall,
        "validation_loss_mse": m.validation_loss_mse,
        "inference_latency_ms": m.inference_latency_ms,
        "is_active": m.is_active,
        "trained_at": m.trained_at.isoformat() if m.trained_at else None,
        "description": m.description
    }

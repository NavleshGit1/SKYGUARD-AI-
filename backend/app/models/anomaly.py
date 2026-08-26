from sqlalchemy import Column, String, Float, DateTime, Boolean, JSON, Text
from datetime import datetime, timezone
from backend.app.core.database import Base

class AnomalyEvent(Base):
    __tablename__ = "anomaly_events"

    event_id = Column(String(100), primary_key=True, index=True)
    station_id = Column(String(50), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    
    # Quantitative Scores
    severity_score = Column(Float, nullable=False)
    confidence_score = Column(Float, nullable=False)
    detector_scores = Column(JSON, nullable=False)
    
    # Qualitative Diagnostics & XAI
    root_cause = Column(String(200), nullable=False)
    explanation = Column(Text, nullable=False)
    shap_attributions = Column(JSON, nullable=True)
    
    # Imputed Replacements
    estimated_corrected_values = Column(JSON, nullable=True)
    
    # Status Lifecycle: ACTIVE, ACKNOWLEDGED, RESOLVED, FALSE_POSITIVE
    status = Column(String(50), default="ACTIVE", index=True)
    resolved_by = Column(String(100), nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    resolution_notes = Column(Text, nullable=True)

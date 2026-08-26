from sqlalchemy import Column, String, Float, Integer, Boolean, DateTime, JSON, Text
from datetime import datetime, timezone
from backend.app.core.database import Base

class ModelRegistry(Base):
    __tablename__ = "model_registry"

    model_id = Column(String(100), primary_key=True, index=True)
    model_name = Column(String(150), nullable=False) # Isolation Forest, Deep Autoencoder, etc.
    model_type = Column(String(50), nullable=False) # UNSUPERVISED_IFOREST, DEEP_AUTOENCODER, FEATURE_SCALER
    version = Column(String(50), nullable=False, default="1.0.0")
    checkpoint_path = Column(String(255), nullable=False)
    
    # Model Architecture & Hyperparameters
    hyperparameters = Column(JSON, nullable=True)
    input_dimension = Column(Integer, default=8)
    latent_dimension = Column(Integer, nullable=True)
    
    # Validation Performance Metrics
    f1_score = Column(Float, nullable=True)
    precision = Column(Float, nullable=True)
    recall = Column(Float, nullable=True)
    validation_loss_mse = Column(Float, nullable=True)
    inference_latency_ms = Column(Float, nullable=True)
    
    # Deployment State
    is_active = Column(Boolean, default=True)
    trained_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    description = Column(Text, nullable=True)

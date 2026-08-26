from sqlalchemy import Column, String, Float, DateTime, Integer, Boolean, JSON, Index
from datetime import datetime, timezone
from backend.app.core.database import Base

class SensorReading(Base):
    __tablename__ = "sensor_readings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, primary_key=True, nullable=False, index=True)
    station_id = Column(String(50), nullable=False, index=True)
    
    # Observed Raw
    temperature_c = Column(Float, nullable=False)
    pressure_hpa = Column(Float, nullable=False)
    humidity_pct = Column(Float, nullable=False)
    
    # Derived Physical
    dew_point_c = Column(Float, nullable=True)
    sea_level_pressure_hpa = Column(Float, nullable=True)
    
    # Imputed Values (if flagged anomalous)
    is_imputed = Column(Boolean, default=False)
    imputed_temperature_c = Column(Float, nullable=True)
    imputed_pressure_hpa = Column(Float, nullable=True)
    imputed_humidity_pct = Column(Float, nullable=True)
    
    # Anomaly status
    is_anomaly = Column(Boolean, default=False, index=True)
    severity_score = Column(Float, default=0.0)

    __table_args__ = (
        Index("idx_station_time", "station_id", "timestamp"),
    )

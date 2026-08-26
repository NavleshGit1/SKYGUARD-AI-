from sqlalchemy import Column, String, Float, Integer, Boolean, DateTime
from datetime import datetime, timezone
from backend.app.core.database import Base

class WeatherStation(Base):
    __tablename__ = "stations"

    station_id = Column(String(50), primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    altitude_m = Column(Float, nullable=False, default=0.0)
    district = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    climate_zone = Column(String(100), nullable=True)
    install_year = Column(Integer, nullable=True)
    last_calibration_date = Column(String(50), nullable=True)
    wmo_id = Column(String(50), nullable=True)
    api_secret_key = Column(String(255), nullable=True, comment="Per-station HMAC-SHA256 secret key")
    
    # Live Cached Health State
    is_active = Column(Boolean, default=True)
    health_score = Column(Float, default=100.0)
    health_status = Column(String(50), default="HEALTHY")
    last_seen = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

"""
SkyGuard AI — Schema Migration Script
Ensures all required columns and tables exist in TimescaleDB.
"""
from backend.app.core.database import engine, Base
from backend.app.models import WeatherStation, SensorReading, AnomalyEvent, User, DeadLetterRecord, ModelRegistry
from sqlalchemy import text

def run_migrations():
    print("[Migration] Verifying and updating PostgreSQL / TimescaleDB schema...")
    Base.metadata.create_all(bind=engine)
    
    with engine.connect() as conn:
        # Add api_secret_key to stations table if missing
        conn.execute(text("ALTER TABLE stations ADD COLUMN IF NOT EXISTS api_secret_key VARCHAR(255);"))
        conn.execute(text("UPDATE stations SET api_secret_key = 'skyguard-station-hmac-secret-key-2026' WHERE api_secret_key IS NULL;"))
        
        # Ensure dead-letter table exists
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS dead_letter_queue (
            id SERIAL PRIMARY KEY,
            received_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
            station_id VARCHAR(64),
            raw_payload TEXT NOT NULL,
            failure_reason VARCHAR(256) NOT NULL,
            error_detail TEXT,
            source_ip VARCHAR(45),
            is_replayed INTEGER DEFAULT 0,
            replayed_at TIMESTAMPTZ
        );
        """))
        
        conn.commit()
        print("[Migration] Schema migrations applied successfully!")

if __name__ == "__main__":
    run_migrations()

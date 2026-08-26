import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from backend.app.core.database import engine

def configure_storage():
    print("=" * 75)
    print("  SkyGuard AI: TimescaleDB Hypertable Optimization & Compression")
    print("=" * 75)

    with engine.connect() as conn:
        print("\n[1/3] Configuring composite primary key (id, timestamp) for partitioning...")
        try:
            conn.execute(text("""
                ALTER TABLE sensor_readings DROP CONSTRAINT IF EXISTS sensor_readings_pkey;
                ALTER TABLE sensor_readings ADD PRIMARY KEY (id, timestamp);
            """))
            print("      [+] Updated composite primary key to (id, timestamp).")
        except Exception as e:
            print(f"      [i] Primary key notice: {e}")

        # 1. Composite index for time-series station queries
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_sensor_readings_station_time 
            ON sensor_readings (station_id, timestamp DESC);
        """))
        print("      [+] Verified index: idx_sensor_readings_station_time")

        # 2. Index on anomaly severity and status
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_anomaly_events_station_status 
            ON anomaly_events (station_id, status, timestamp DESC);
        """))
        print("      [+] Verified index: idx_anomaly_events_station_status")

        # 3. Convert to TimescaleDB Hypertable & Enable Compression
        print("\n[2/3] Initializing TimescaleDB Hypertable on 'sensor_readings'...")
        try:
            conn.execute(text("""
                SELECT create_hypertable('sensor_readings', by_range('timestamp'), if_not_exists => TRUE, migrate_data => TRUE);
            """))
            print("      [+] Successfully enabled Hypertable on 'sensor_readings'.")
            
            conn.execute(text("""
                ALTER TABLE sensor_readings SET (
                    timescaledb.compress,
                    timescaledb.compress_segmentby = 'station_id',
                    timescaledb.compress_orderby = 'timestamp DESC'
                );
            """))
            print("      [+] Configured hypertable compression on sensor_readings.")
            
            conn.execute(text("""
                SELECT add_compression_policy('sensor_readings', INTERVAL '7 days', if_not_exists => TRUE);
            """))
            print("      [+] Configured 7-day automatic data compression policy.")
        except Exception as e:
            print(f"      [i] Hypertable notice: {e}")

        conn.commit()
        print("\n[3/3] TimescaleDB storage configuration completed.")
        print("=" * 75)

if __name__ == "__main__":
    configure_storage()

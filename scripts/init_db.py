import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from backend.app.core.database import Base, engine, SessionLocal
from backend.app.core.security import get_password_hash
from backend.app.models.station import WeatherStation
from backend.app.models.user import User

def initialize_database():
    print("=" * 65)
    print("  SkyGuard AI: Database Schema Initialization & Seeding")
    print("=" * 65)

    # 1. Create all tables
    print("\n[1/3] Creating relational tables and schema in TimescaleDB...")
    Base.metadata.create_all(bind=engine)
    print("      [OK] Tables created: stations, sensor_readings, anomaly_events, users")

    db = SessionLocal()
    try:
        # 2. Seed Station Metadata
        print("\n[2/3] Seeding Station Metadata Registry...")
        csv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "metadata", "stations_metadata.csv")
        if os.path.exists(csv_path):
            df = pd.read_csv(csv_path)
            for _, row in df.iterrows():
                st_id = str(row["station_id"])
                existing = db.query(WeatherStation).filter(WeatherStation.station_id == st_id).first()
                if not existing:
                    station = WeatherStation(
                        station_id=st_id,
                        name=str(row["name"]),
                        latitude=float(row["latitude"]),
                        longitude=float(row["longitude"]),
                        altitude_m=float(row.get("altitude_m", 0.0)),
                        district=str(row.get("district", "")),
                        state=str(row.get("state", "")),
                        climate_zone=str(row.get("climate_zone", "")),
                        install_year=int(row["install_year"]) if pd.notna(row.get("install_year")) else 2020,
                        last_calibration_date=str(row.get("last_calibration_date", "2026-01-01")),
                        wmo_id=str(row.get("wmo_id", "")),
                        health_score=100.0,
                        health_status="HEALTHY",
                        is_active=True
                    )
                    db.add(station)
                    print(f"      [+] Seeded Station: {st_id} ({row['name']})")
                else:
                    print(f"      [.] Station {st_id} already exists.")
            db.commit()

        # 3. Seed Default Admin User
        print("\n[3/3] Seeding default operator and administrator accounts...")
        admin_email = "admin@skyguard.ai"
        admin = db.query(User).filter(User.email == admin_email).first()
        if not admin:
            new_admin = User(
                email=admin_email,
                hashed_password=get_password_hash("admin123"),
                full_name="Chief Meteorologist",
                role="admin",
                is_active=True
            )
            db.add(new_admin)
            db.commit()
            print(f"      [+] Created default Admin account: {admin_email} (Password: admin123)")
        else:
            print(f"      [.] Admin account already exists.")

        print("\n" + "=" * 65)
        print("  [SUCCESS] DATABASE INITIALIZATION & SEEDING COMPLETED!")
        print("=" * 65)

    except Exception as e:
        db.rollback()
        print(f"\n[ERROR] Error during database seeding: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    initialize_database()

import os
import sys
import math
from datetime import datetime
import pandas as pd
import numpy as np

try:
    import meteostat as ms
    ms.config.block_large_requests = False
except ImportError:
    print("Error: 'meteostat' is not installed. Run 'pip install meteostat pandas' first.")
    sys.exit(1)

RAW_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
METADATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "metadata")
os.makedirs(RAW_DATA_DIR, exist_ok=True)
os.makedirs(METADATA_DIR, exist_ok=True)

# 5 Major Indian Meteorological AWS Stations with exact coordinates & WMO IDs
STATIONS_CONFIG = {
    "AWS-DEL-01": {"name": "Delhi Safdarjung", "lat": 28.6139, "lon": 77.2090, "alt": 216.0, "wmo": "42182"},
    "AWS-MUM-01": {"name": "Mumbai Santacruz", "lat": 19.0760, "lon": 72.8777, "alt": 14.0, "wmo": "43003"},
    "AWS-CHE-01": {"name": "Chennai Meenambakkam", "lat": 13.0827, "lon": 80.2707, "alt": 16.0, "wmo": "43279"},
    "AWS-KOL-01": {"name": "Kolkata Alipore", "lat": 22.5726, "lon": 88.3639, "alt": 6.0, "wmo": "42809"},
    "AWS-JAI-01": {"name": "Jaipur Sanganer", "lat": 26.9124, "lon": 75.7873, "alt": 431.0, "wmo": "42170"}
}


def download_25_year_historical_data(start_year: int = 2000, end_year: int = 2025):
    """
    Downloads 25 full years (2000-2025) of real hourly meteorological observations
    across all 5 primary AWS stations using NOAA / Meteostat global archives.
    """
    start = datetime(start_year, 1, 1)
    end = datetime(end_year, 12, 31, 23, 59)
    print("=" * 80)
    print(f"  SkyGuard AI: 25-Year Historical AWS Dataset Ingestion ({start_year} - {end_year})")
    print("  Quarter-Century Meteorological Training Baseline for Maximum Accuracy")
    print("=" * 80)

    all_frames = []

    for station_id, meta in STATIONS_CONFIG.items():
        print(f"\n[+] Ingesting 25-year archive for {station_id} ({meta['name']})...")

        # 1. Primary lookup using WMO ID
        station_code = meta["wmo"]
        st = ms.Station(station_code)
        ts = ms.hourly(st, start, end)
        data = ts.fetch()

        # 2. Fallback / supplementary query to nearby spatial point search if WMO is sparse
        if data.empty or len(data) < 5000:
            print(f"    Searching nearby stations for coordinates ({meta['lat']}, {meta['lon']})...")
            nearby_stations = ms.stations.nearby(ms.Point(meta["lat"], meta["lon"], meta["alt"]))
            if not nearby_stations.empty:
                for alt_id in nearby_stations.index[:5]:
                    st_alt = ms.Station(str(alt_id))
                    ts_alt = ms.hourly(st_alt, start, end)
                    alt_data = ts_alt.fetch()
                    if not alt_data.empty and len(alt_data) > len(data):
                        data = alt_data
                        print(f"    Matched regional archive ID: {alt_id} ({len(data):,} records)")
                        break

        if data.empty:
            print(f"    [WARN] No records found for {station_id}.")
            continue

        data = data.reset_index()
        data["station_id"] = station_id
        data["station_name"] = meta["name"]
        data["latitude"] = meta["lat"]
        data["longitude"] = meta["lon"]
        data["altitude_m"] = meta["alt"]

        # Rename standard columns to match SkyGuard Data Contract
        data = data.rename(columns={
            "time": "timestamp",
            "temp": "temperature_c",
            "pres": "pressure_hpa",
            "rhum": "humidity_pct",
            "dwpt": "dew_point_c"
        })

        # Columns to preserve
        cols = ["station_id", "station_name", "timestamp", "temperature_c", "pressure_hpa", "humidity_pct", "dew_point_c", "latitude", "longitude", "altitude_m"]
        existing_cols = [c for c in cols if c in data.columns]
        data = data[existing_cols]

        # Convert numeric types and perform linear interpolation on minor gaps
        numeric_cols = [c for c in ["temperature_c", "pressure_hpa", "humidity_pct", "dew_point_c"] if c in data.columns]
        for col in numeric_cols:
            data[col] = pd.to_numeric(data[col], errors="coerce")

        # Fill pressure default if missing at elevation
        if "pressure_hpa" in data.columns and data["pressure_hpa"].isna().sum() > len(data) * 0.5:
            # Barometric standard calculation based on altitude
            p_standard = 1013.25 * math.pow(1.0 - (0.0065 * meta["alt"]) / 288.15, 5.255)
            data["pressure_hpa"] = data["pressure_hpa"].fillna(round(p_standard, 2))

        data[numeric_cols] = data[numeric_cols].interpolate(method="linear").bfill().ffill()

        data["temperature_c"] = data["temperature_c"].round(2)
        if "pressure_hpa" in data.columns:
            data["pressure_hpa"] = data["pressure_hpa"].round(2)
        if "humidity_pct" in data.columns:
            data["humidity_pct"] = data["humidity_pct"].round(2)

        print(f"    [OK] Successfully compiled {len(data):,} hourly records ({start_year}-{end_year}).")
        all_frames.append(data)

    if not all_frames:
        print("\n[ERROR] No data retrieved. Check internet connection.")
        return None

    final_df = pd.concat(all_frames, ignore_index=True)
    out_path = os.path.join(RAW_DATA_DIR, "historical_aws_training.csv")
    final_df.to_csv(out_path, index=False)

    print("\n" + "=" * 80)
    print(f"[SUCCESS] Ingested {len(final_df):,} 25-Year AWS observations (2000-2025).")
    print(f"Saved dataset to: {os.path.abspath(out_path)}")
    print("=" * 80)

    # 3. Compute 25-Year Climatological Normals (Mean & Standard Deviations per Month)
    print("\n[+] Computing 25-Year Climatological Normals (WMO Baseline)...")
    final_df["dt"] = pd.to_datetime(final_df["timestamp"])
    final_df["month"] = final_df["dt"].dt.month

    normals_list = []
    for (st_id, m), group in final_df.groupby(["station_id", "month"]):
        t_mean = round(float(group["temperature_c"].mean()), 2)
        t_std = round(max(1.5, float(group["temperature_c"].std())), 2)
        p_mean = round(float(group["pressure_hpa"].mean()), 2)
        p_std = round(max(2.0, float(group["pressure_hpa"].std())), 2)
        rh_mean = round(float(group["humidity_pct"].mean()), 2)
        rh_std = round(max(5.0, float(group["humidity_pct"].std())), 2)

        normals_list.append({
            "station_id": st_id,
            "month": m,
            "t_mean_c": t_mean,
            "t_std_c": t_std,
            "p_mean_hpa": p_mean,
            "p_std_hpa": p_std,
            "rh_mean_pct": rh_mean,
            "rh_std_pct": rh_std
        })

    normals_df = pd.DataFrame(normals_list).sort_values(["station_id", "month"])
    normals_path = os.path.join(METADATA_DIR, "climate_normals.csv")
    normals_df.to_csv(normals_path, index=False)
    print(f"[OK] Generated {len(normals_df)} 25-year climatological normal profiles at: {normals_path}\n")

    return final_df


if __name__ == "__main__":
    download_25_year_historical_data(start_year=2000, end_year=2025)

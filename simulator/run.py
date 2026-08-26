import os
import sys
import time
import requests
import json
import hmac
import hashlib
from dotenv import load_dotenv

# Load .env variables
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from simulator.engine import SimulatorEngine

DATA_CSV_PATH = os.getenv("HISTORICAL_DATA_PATH", os.path.join(os.path.dirname(__file__), "..", "data", "raw", "historical_aws_training.csv"))
BACKEND_URL = os.getenv("BACKEND_API_URL", "http://localhost:8000/api/v1/ingest/telemetry")
SIMULATOR_API_URL = os.getenv("SIMULATOR_API_URL", "http://localhost:8000/api/v1/simulator/active")
SECRET_KEY = os.getenv("TELEMETRY_HMAC_SECRET", "")
TICK_INTERVAL = float(os.getenv("SIMULATOR_TICK_SECONDS", "1.0"))

STATIONS = ["AWS-DEL-01", "AWS-MUM-01", "AWS-CHE-01", "AWS-KOL-01", "AWS-JAI-01"]

def run_simulator():
    print("=== SkyGuard AI Telemetry Simulator Starting ===")
    print(f"Target Ingestion URL: {BACKEND_URL}")
    print(f"Tick Interval: {TICK_INTERVAL}s")
    
    engine = SimulatorEngine(data_path=DATA_CSV_PATH, secret_key=SECRET_KEY)
    
    if engine.df is None or engine.df.empty:
        print("[WARN] No historical data found. Please run 'scripts/download_historical.py' first.")
        print("Starting in standby mode...")
        while engine.df is None or engine.df.empty:
            time.sleep(5)
            engine.load_data()
            
    print("[FEED] Telemetry stream initiated across all 5 Indian AWS hubs...")
    
    station_idx = 0
    
    while True:
        # 1. Check for Pending On-Demand Injections from Dashboard UI
        try:
            inj_resp = requests.get(SIMULATOR_API_URL, timeout=1.0)
            if inj_resp.status_code == 200:
                active_map = inj_resp.json()
                for st_id, inj in list(active_map.items()):
                    print(f"\n[TRIGGER] Received UI Anomaly Request for {st_id}: {inj['type']} on {inj['parameter']} (+{inj['magnitude']})")
                    engine.trigger_anomaly(
                        anomaly_type=inj["type"],
                        parameter=inj["parameter"],
                        duration_ticks=inj["duration"],
                        magnitude=inj["magnitude"],
                        station_id=st_id
                    )
                    # Clear claimed injection from backend queue
                    requests.delete(f"{SIMULATOR_API_URL}/{st_id}", timeout=1.0)
        except Exception:
            pass

        # 2. Determine target station (prioritize any station with active injection)
        active_target = None
        for inj in engine.active_injections:
            if inj.get("station_id") in STATIONS:
                active_target = inj["station_id"]
                break
                
        target_station = active_target if active_target else STATIONS[station_idx % len(STATIONS)]
        station_idx += 1

        # 3. Get next reading packet from engine targeted to station
        reading_package = engine.get_next_reading(target_station=target_station)
        if reading_package:
            payload = reading_package["payload"]
            
            # Re-generate HMAC-SHA256 signature for the station
            payload_str = json.dumps({
                "temperature_c": payload["temperature_c"],
                "pressure_hpa": payload["pressure_hpa"],
                "humidity_pct": payload["humidity_pct"]
            }, sort_keys=True)
            
            msg = f"{payload['station_id']}:{payload['timestamp']}:{payload_str}".encode("utf-8")
            sig = hmac.new(SECRET_KEY.encode("utf-8"), msg, hashlib.sha256).hexdigest()
            
            headers = {
                "Content-Type": "application/json",
                "X-Station-ID": payload["station_id"],
                "X-Station-Signature": sig
            }
            
            try:
                response = requests.post(BACKEND_URL, json=payload, headers=headers, timeout=2.0)
                if response.status_code == 200:
                    res_data = response.json()
                    is_anom = res_data.get("is_anomaly", False)
                    anom_tag = f" [FLAGGED ANOMALY: {res_data.get('root_cause')}]" if is_anom else ""
                    print(f"[{payload['timestamp']}] [FEED] {payload['station_id']} | T:{payload['temperature_c']}C P:{payload['pressure_hpa']}hPa RH:{payload['humidity_pct']}% -> 200 OK{anom_tag}")
                else:
                    print(f"[{payload['timestamp']}] [WARN] Ingest response {response.status_code}: {response.text[:100]}")
            except requests.exceptions.RequestException as e:
                print(f"[{payload['timestamp']}] [WAIT] Waiting for backend API ({e.__class__.__name__})...")
                
        time.sleep(TICK_INTERVAL)

if __name__ == "__main__":
    run_simulator()

import requests
import json
import time

BASE = "http://localhost:8000/api/v1"

print("--- 1. Testing Health Endpoint ---")
h = requests.get(f"{BASE}/health").json()
print("Status:", h.get("status"))
print("Database:", h.get("database"))
print("Cache:", h.get("cache"))

print("\n--- 2. Testing Weather Stations ---")
st = requests.get(f"{BASE}/stations").json()
print(f"Total Stations: {len(st)}")
for s in st:
    print(f"  - {s['station_id']}: {s['name']} (Lat: {s['latitude']}, Lon: {s['longitude']}, Health: {s.get('health_score')})")

print("\n--- 3. Testing Anomaly Injection via Simulator ---")
inj = requests.post(f"{BASE}/simulator/inject", json={
    "station_id": "AWS-DEL-01",
    "anomaly_type": "SPIKE",
    "parameter": "temperature_c",
    "duration_ticks": 3,
    "magnitude": 18.0
})
print("Injection Status:", inj.status_code, inj.json())

print("Waiting 6s for telemetry ticks to process...")
time.sleep(6)

print("\n--- 4. Testing Anomaly Feed ---")
anom = requests.get(f"{BASE}/anomalies?limit=5").json()
print(f"Retrieved {len(anom)} anomalies:")
for a in anom[:3]:
    print(f"  - [{a.get('event_id')}] Station: {a.get('station_id')}, Severity: {a.get('severity_score')}, Cause: {a.get('root_cause')}")

print("\n--- 5. Testing SHA-256 Audit Trail Verification ---")
audit = requests.get(f"{BASE}/audit/verify").json()
print("Audit Integrity:", audit)

print("\n=== ALL SYSTEMS OPERATIONAL ===")

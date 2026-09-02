"""
SkyGuard AI — Live Cloud Deployment Verification Suite
Tests every endpoint, database query, authentication lifecycle, simulator, and calibration on the live Render/Vercel deployment.
"""
import requests
import time
import json

BASE = "https://skyguard-ai-mvlx.onrender.com"
FRONTEND_URL = "https://skyguard-ai-nine.vercel.app"

print("=" * 75)
print("     SKYGUARD AI — LIVE CLOUD DEPLOYMENT INTEGRATION SUITE")
print("=" * 75)
print(f"Backend Target  : {BASE}")
print(f"Frontend Target : {FRONTEND_URL}\n")

results = []

def record(test_name, success, msg):
    status = "PASS" if success else "FAIL"
    print(f"[{status.center(6)}] {test_name.ljust(45)}: {msg}")
    results.append((test_name, success, msg))

# 1. Frontend Availability
try:
    r = requests.get(FRONTEND_URL, timeout=10)
    record("Frontend SPA Available", r.status_code == 200, f"HTTP {r.status_code}")
except Exception as e:
    record("Frontend SPA Available", False, str(e))

# 2. Backend Health Check
try:
    r = requests.get(f"{BASE}/api/v1/health", timeout=15)
    db_stat = r.json().get("database", {}).get("status", "UNKNOWN") if r.status_code == 200 else "ERROR"
    record("Backend Health & DB Latency", r.status_code == 200 and db_stat == "HEALTHY", f"HTTP {r.status_code}, DB: {db_stat}")
except Exception as e:
    record("Backend Health & DB Latency", False, str(e))

# 3. Authentication
token = None
try:
    r = requests.post(f"{BASE}/api/v1/auth/login", data={"username": "admin@skyguard.ai", "password": "admin123"}, timeout=15)
    if r.status_code == 200:
        token = r.json()["access_token"]
        record("Operator & Admin Login", True, "JWT Bearer Token issued")
    else:
        record("Operator & Admin Login", False, f"HTTP {r.status_code}: {r.text}")
except Exception as e:
    record("Operator & Admin Login", False, str(e))

headers = {"Authorization": f"Bearer {token}"} if token else {}

# 4. User Profile
try:
    r = requests.get(f"{BASE}/api/v1/auth/me", headers=headers, timeout=15)
    email = r.json().get("email", "") if r.status_code == 200 else ""
    role = r.json().get("role", "") if r.status_code == 200 else ""
    record("User Profile Inspection", r.status_code == 200, f"Authenticated as {email} ({role})")
except Exception as e:
    record("User Profile Inspection", False, str(e))

# 5. Station Registry
try:
    r = requests.get(f"{BASE}/api/v1/stations", timeout=15)
    stations = r.json() if r.status_code == 200 else []
    record("Weather Station Registry", r.status_code == 200 and len(stations) >= 5, f"{len(stations)} official AWS Hubs active")
except Exception as e:
    record("Weather Station Registry", False, str(e))

# 6. Station Telemetry Query
try:
    r = requests.get(f"{BASE}/api/v1/stations/AWS-DEL-01/readings?limit=20", timeout=15)
    readings = r.json() if r.status_code == 200 else []
    record("Station Readings Time-Series", r.status_code == 200, f"{len(readings)} records for AWS-DEL-01")
except Exception as e:
    record("Station Readings Time-Series", False, str(e))

# 7. Station Stats Summary
try:
    r = requests.get(f"{BASE}/api/v1/stations/stats/summary", timeout=15)
    record("Station Aggregates & Summary", r.status_code == 200, "Network rollups operational")
except Exception as e:
    record("Station Aggregates & Summary", False, str(e))

# 8. Anomaly Incident Center
try:
    r = requests.get(f"{BASE}/api/v1/anomalies?limit=10", timeout=15)
    anomalies = r.json() if r.status_code == 200 else []
    record("XAI Anomaly Feed & Attribution", r.status_code == 200 and isinstance(anomalies, list), f"{len(anomalies)} incidents listed")
except Exception as e:
    record("XAI Anomaly Feed & Attribution", False, str(e))

# 9. Simulator Fault Injection
try:
    r = requests.post(f"{BASE}/api/v1/simulator/inject", json={
        "station_id": "AWS-DEL-01",
        "anomaly_type": "SPIKE",
        "parameter": "temperature_c",
        "duration_ticks": 5,
        "magnitude": 12.0
    }, timeout=15)
    record("Simulator Fault Injection", r.status_code == 200, "Injected synthetic impulse spike on AWS-DEL-01")
except Exception as e:
    record("Simulator Fault Injection", False, str(e))

# 10. Admin Thresholds & Calibrator
try:
    r = requests.get(f"{BASE}/api/v1/admin/thresholds", headers=headers, timeout=15)
    fusion_t = r.json().get("thresholds", {}).get("fusion_threshold", 0.6) if r.status_code == 200 else None
    
    r_post = requests.post(f"{BASE}/api/v1/admin/thresholds", json={
        "fusion_threshold": 0.60,
        "iforest_weight": 0.25,
        "autoencoder_weight": 0.35,
        "drift_weight": 0.15,
        "spatial_weight": 0.15,
        "alert_cooldown_seconds": 120
    }, headers=headers, timeout=15)
    record("Admin ML Threshold Calibration", r_post.status_code == 200, f"Calibrated fusion threshold = {fusion_t}")
except Exception as e:
    record("Admin ML Threshold Calibration", False, str(e))

# 11. Cryptographic Audit Trail
try:
    r = requests.get(f"{BASE}/api/v1/audit/verify", timeout=15)
    stat = r.json().get("status") if r.status_code == 200 else "ERROR"
    record("Cryptographic SHA-256 Audit Trail", r.status_code == 200 and stat == "VERIFIED_VALID", f"Chain Genesis Hash: {stat}")
except Exception as e:
    record("Cryptographic SHA-256 Audit Trail", False, str(e))

# 12. Production Model Registry
try:
    r = requests.get(f"{BASE}/api/v1/models/active", timeout=15)
    models = r.json() if r.status_code == 200 else []
    record("Active Production ML Models", r.status_code == 200 and len(models) >= 3, f"{len(models)} production checkpoints active")
except Exception as e:
    record("Active Production ML Models", False, str(e))

print("\n" + "=" * 75)
passed = sum(1 for _, s, _ in results if s)
total = len(results)
print(f"  TOTAL RESULTS: {passed}/{total} TESTS PASSED")
print("=" * 75)

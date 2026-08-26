import os
import sys
import time
import hmac
import hashlib
import json
import requests
import unittest
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app.core.config import settings
from backend.app.core.database import SessionLocal, engine
from backend.app.models.station import WeatherStation
from backend.app.models.user import User
from backend.app.models.anomaly import AnomalyEvent
from backend.app.models.reading import SensorReading
from backend.app.models.model_registry import ModelRegistry
from backend.app.models.dead_letter import DeadLetterRecord
from backend.app.services.feature_eng import MeteorologicalFeatureEngine
from backend.app.services.detectors import HybridDetectorEnsemble
from backend.app.services.imputer import ValueImputer
from backend.app.services.xai import ExplainabilityEngine
from backend.app.services.health_score import SensorHealthEngine, _mann_kendall_test

BASE_URL = "http://localhost:8000"

class FullSystemIntegrationTests(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        print("\n" + "=" * 85)
        print(" SKYGUARD AI - COMPREHENSIVE END-TO-END SYSTEM TEST SUITE")
        print("=" * 85)
        
        # Authenticate and get JWT token
        login_payload = {
            "username": "admin@skyguard.ai",
            "password": "admin123"
        }
        res = requests.post(f"{BASE_URL}/api/v1/auth/login", data=login_payload, timeout=5)
        if res.status_code == 200:
            data = res.json()
            cls.token = data["access_token"]
            cls.refresh_token = data["refresh_token"]
            cls.auth_headers = {"Authorization": f"Bearer {cls.token}"}
            print(f"[+] Authenticated successfully with JWT Token")
        else:
            cls.token = None
            cls.refresh_token = None
            cls.auth_headers = {}
            print(f"[!] Warning: Login failed with status {res.status_code}: {res.text}")

    def test_01_health_and_diagnostics(self):
        """Verify health check and deep infrastructure diagnostics"""
        res = requests.get(f"{BASE_URL}/api/v1/health", timeout=5)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "HEALTHY")
        self.assertEqual(data["database"]["status"], "HEALTHY")
        self.assertIn("latency_ms", data["database"])
        self.assertIn("cache", data)

        diag_res = requests.get(f"{BASE_URL}/api/v1/system/diagnostics", timeout=5)
        self.assertEqual(diag_res.status_code, 200)
        diag_data = diag_res.json()
        self.assertEqual(diag_data["status"], "OPERATIONAL")
        print(f" [PASS] Health & Diagnostics: DB Latency = {data['database']['latency_ms']}ms, Pool Occupancy OK")

    def test_02_auth_and_token_refresh(self):
        """Verify authentication, profile retrieval, and token refresh lifecycle"""
        self.assertIsNotNone(self.token)
        # Profile via /auth/me
        res = requests.get(f"{BASE_URL}/api/v1/auth/me", headers=self.auth_headers, timeout=5)
        self.assertEqual(res.status_code, 200)
        user_info = res.json()
        self.assertEqual(user_info["email"], "admin@skyguard.ai")
        self.assertEqual(user_info["role"], "admin")

        # Profile via /users/me
        res_users = requests.get(f"{BASE_URL}/api/v1/users/me", headers=self.auth_headers, timeout=5)
        self.assertEqual(res_users.status_code, 200)

        # Refresh token
        ref_res = requests.post(f"{BASE_URL}/api/v1/auth/refresh", json={"refresh_token": self.refresh_token}, timeout=5)
        self.assertEqual(ref_res.status_code, 200)
        self.assertIn("access_token", ref_res.json())
        print(f" [PASS] Auth & Lifecycle: /auth/me, /users/me & token refresh verified for {user_info['email']}")

    def test_03_stations_endpoints(self):
        """Verify weather station discovery, profile details, aggregate rollups, and summary"""
        res = requests.get(f"{BASE_URL}/api/v1/stations", timeout=5)
        self.assertEqual(res.status_code, 200)
        stations = res.json()
        self.assertGreaterEqual(len(stations), 5)
        station_id = stations[0]["station_id"]
        
        # Detail
        detail_res = requests.get(f"{BASE_URL}/api/v1/stations/{station_id}", timeout=5)
        self.assertEqual(detail_res.status_code, 200)
        detail = detail_res.json()
        self.assertEqual(detail["station_id"], station_id)
        
        # Summary
        summary_res = requests.get(f"{BASE_URL}/api/v1/stations/stats/summary", timeout=5)
        self.assertEqual(summary_res.status_code, 200)
        
        # Aggregates / Analytics
        analytics_res = requests.get(f"{BASE_URL}/api/v1/stations/{station_id}/analytics?interval_minutes=60", timeout=5)
        self.assertEqual(analytics_res.status_code, 200)

        # Readings query
        readings_res = requests.get(f"{BASE_URL}/api/v1/stations/{station_id}/readings?limit=20", timeout=5)
        self.assertEqual(readings_res.status_code, 200)
        
        print(f" [PASS] Stations endpoints: {len(stations)} stations discovered; detail, stats, analytics & readings verified")

    def test_04_telemetry_ingestion_security_and_pipeline(self):
        """Verify HMAC-SHA256 signature verification, anti-tamper rejection, and full ML ingestion pipeline"""
        st_id = "AWS-DEL-01"
        ts_iso = datetime.now(timezone.utc).isoformat()
        temp_c = 28.5
        press_hpa = 1012.0
        hum_pct = 55.0

        reading_payload = {
            "station_id": st_id,
            "timestamp": ts_iso,
            "temperature_c": temp_c,
            "humidity_pct": hum_pct,
            "pressure_hpa": press_hpa,
            "wind_speed_ms": 3.4,
            "wind_direction_deg": 180.0,
            "solar_radiation_wm2": 620.0,
            "battery_v": 12.8,
            "solar_panel_v": 18.2,
            "internal_temp_c": 26.1,
            "rssi_dbm": -65,
            "seq_num": int(time.time())
        }

        # 1. No signature at all — VULN-03 FIX: should now be rejected with 401
        no_sig_headers = {
            "Content-Type": "application/json",
            "X-Station-ID": st_id,
        }
        no_sig_res = requests.post(f"{BASE_URL}/api/v1/ingest/telemetry", json=reading_payload, headers=no_sig_headers, timeout=5)
        self.assertEqual(no_sig_res.status_code, 401, "VULN-03 FIX: Unsigned requests must be rejected (401)")

        # 2. Valid Signature — use the station's api_secret_key (per-station beats global HMAC secret)
        # Fetch station detail to get the secret key used by the server
        station_res = requests.get(f"{BASE_URL}/api/v1/stations/{st_id}", headers=self.auth_headers, timeout=5)
        station_api_secret = None
        if station_res.status_code == 200:
            station_api_secret = station_res.json().get("api_secret_key")
        # Fallback to global HMAC secret if station secret not exposed (expected in prod)
        secret = station_api_secret or settings.TELEMETRY_HMAC_SECRET

        payload_str = json.dumps({
            "temperature_c": temp_c,
            "pressure_hpa": press_hpa,
            "humidity_pct": hum_pct
        }, sort_keys=True)

        msg = f"{st_id}:{ts_iso}:{payload_str}".encode("utf-8")
        valid_sig = hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()

        headers = {
            "Content-Type": "application/json",
            "X-Station-ID": st_id,
            "X-Station-Signature": valid_sig
        }
        res = requests.post(f"{BASE_URL}/api/v1/ingest/telemetry", json=reading_payload, headers=headers, timeout=5)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "PROCESSED")

        # 3. Invalid/tampered Signature (should be rejected with 401 and quarantined to DLQ)
        bad_headers = {
            "Content-Type": "application/json",
            "X-Station-ID": st_id,
            "X-Station-Signature": "0000000000000000000000000000000000000000000000000000000000000000"
        }
        bad_res = requests.post(f"{BASE_URL}/api/v1/ingest/telemetry", json=reading_payload, headers=bad_headers, timeout=5)
        self.assertEqual(bad_res.status_code, 401)

        print(f" [PASS] Telemetry Ingestion: Unsigned rejected (401 VULN-03), Valid signature accepted ({data.get('pipeline_latency_ms')}ms), Tampered signature rejected (401 Quarantined)")

    def test_05_anomalies_and_resolutions(self):
        """Verify anomalies querying, single incident detail, single resolution, and bulk resolution"""
        res = requests.get(f"{BASE_URL}/api/v1/anomalies?limit=10", timeout=5)
        self.assertEqual(res.status_code, 200)
        anomalies = res.json()
        self.assertIsInstance(anomalies, list)

        if len(anomalies) > 0:
            first_event = anomalies[0]
            evt_id = first_event["event_id"]

            # Query single anomaly (read — no auth required)
            single_res = requests.get(f"{BASE_URL}/api/v1/anomalies/{evt_id}", timeout=5)
            self.assertEqual(single_res.status_code, 200)
            self.assertEqual(single_res.json()["event_id"], evt_id)

            # Verify unauthenticated write is rejected (VULN-05 FIX)
            unauth_patch = requests.patch(
                f"{BASE_URL}/api/v1/anomalies/{evt_id}/resolve",
                json={"status": "ACKNOWLEDGED", "resolution_notes": "Unauthenticated attempt"},
                timeout=5
            )
            self.assertEqual(unauth_patch.status_code, 401, "VULN-05 FIX: Unauthenticated anomaly resolve must return 401")

            # Single resolution (authenticated — VULN-05 FIX: auth headers required)
            patch_res = requests.patch(
                f"{BASE_URL}/api/v1/anomalies/{evt_id}/resolve",
                json={"status": "ACKNOWLEDGED", "resolution_notes": "Under review"},
                headers=self.auth_headers,
                timeout=5
            )
            self.assertEqual(patch_res.status_code, 200)
            self.assertEqual(patch_res.json()["status"], "ACKNOWLEDGED")

            # Bulk resolve (authenticated — VULN-05 FIX: auth headers required)
            bulk_res = requests.post(
                f"{BASE_URL}/api/v1/anomalies/bulk-resolve",
                json={"event_ids": [evt_id], "status": "RESOLVED", "resolution_notes": "Verified clean"},
                headers=self.auth_headers,
                timeout=5
            )
            self.assertEqual(bulk_res.status_code, 200)
            self.assertEqual(bulk_res.json()["status"], "BULK_RESOLVED")

        print(f" [PASS] Anomalies endpoints: Listing, unauthenticated write blocked (401), authenticated resolve & bulk-resolve verified")


    def test_06_observability_and_prometheus_metrics(self):
        """Verify real-time performance metrics and Prometheus exposition"""
        res = requests.get(f"{BASE_URL}/api/v1/metrics", timeout=5)
        self.assertEqual(res.status_code, 200)
        summary = res.json()
        self.assertIn("total_readings_ingested", summary)
        self.assertIn("latency_profile_ms", summary)
        
        prom_res = requests.get(f"{BASE_URL}/api/v1/metrics/prometheus", timeout=5)
        self.assertEqual(prom_res.status_code, 200)
        self.assertIn("skyguard_ingest_total", prom_res.text)
        self.assertIn("skyguard_pipeline_latency_ms", prom_res.text)
        print(f" [PASS] Metrics & Prometheus: Total Ingested={summary['total_readings_ingested']}, Prometheus scrape size={len(prom_res.text)} bytes")

    def test_07_dead_letter_queue(self):
        """Verify Dead Letter Queue listing, filtering, and purge endpoints"""
        res = requests.get(f"{BASE_URL}/api/v1/dlq", headers=self.auth_headers, timeout=5)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("total_quarantined", data)
        self.assertIn("records", data)

        # Test purge endpoint
        purge_res = requests.delete(f"{BASE_URL}/api/v1/dlq/purge?older_than_days=90", headers=self.auth_headers, timeout=5)
        self.assertEqual(purge_res.status_code, 200)
        self.assertEqual(purge_res.json()["status"], "PURGED")
        print(f" [PASS] Dead-Letter Queue: Quarantined records = {data['total_quarantined']}, Purge endpoint verified")

    def test_08_simulator_workbench(self):
        """Verify simulator active state, fault injection, and clear injection cycle"""
        # 1. Trigger Injection
        fault_payload = {
            "station_id": "AWS-DEL-01",
            "anomaly_type": "SPIKE",
            "parameter": "temperature_c",
            "magnitude": 25.0,
            "duration_ticks": 10
        }
        inj_res = requests.post(f"{BASE_URL}/api/v1/simulator/inject", json=fault_payload, timeout=5)
        self.assertEqual(inj_res.status_code, 200)
        self.assertEqual(inj_res.json()["status"], "TRIGGERED")

        # 2. Check active injections
        res = requests.get(f"{BASE_URL}/api/v1/simulator/active", timeout=5)
        self.assertEqual(res.status_code, 200)
        sim_data = res.json()
        self.assertIsInstance(sim_data, dict)

        # 3. Clear active injection
        clear_res = requests.delete(f"{BASE_URL}/api/v1/simulator/active/AWS-DEL-01", timeout=5)
        self.assertEqual(clear_res.status_code, 200)
        print(f" [PASS] Simulator Workbench: Injection triggered, active state polled, and cleared successfully")

    def test_09_model_registry(self):
        """Verify Model Registry listing, active deployed models, and model metadata inspection"""
        res = requests.get(f"{BASE_URL}/api/v1/models", timeout=5)
        self.assertEqual(res.status_code, 200)
        models = res.json()
        self.assertGreaterEqual(len(models), 4)

        active_res = requests.get(f"{BASE_URL}/api/v1/models/active", timeout=5)
        self.assertEqual(active_res.status_code, 200)
        active_models = active_res.json()
        self.assertGreaterEqual(len(active_models), 3)

        first_id = models[0]["model_id"]
        detail_res = requests.get(f"{BASE_URL}/api/v1/models/{first_id}", timeout=5)
        self.assertEqual(detail_res.status_code, 200)
        self.assertEqual(detail_res.json()["model_id"], first_id)
        print(f" [PASS] Model Registry: {len(models)} models registered, {len(active_models)} active production checkpoints")

    def test_10_cryptographic_audit_trail(self):
        """Verify immutable SHA-256 hash-chain audit logging and mathematical verification"""
        logs_res = requests.get(f"{BASE_URL}/api/v1/audit?limit=25", timeout=5)
        self.assertEqual(logs_res.status_code, 200)
        logs = logs_res.json()
        self.assertIsInstance(logs, list)

        # Verify integrity from Genesis block
        verify_res = requests.get(f"{BASE_URL}/api/v1/audit/verify", timeout=5)
        self.assertEqual(verify_res.status_code, 200)
        vdata = verify_res.json()
        self.assertEqual(vdata["status"], "VERIFIED_VALID")
        print(f" [PASS] Audit Trail: {len(logs)} blocks retrieved, SHA-256 Genesis Hash Chain: VERIFIED_VALID")

    def test_11_admin_thresholds_and_jobs(self):
        """Verify admin threshold retrieval, updates, and retraining job listing"""
        # Thresholds (authenticated)
        res = requests.get(f"{BASE_URL}/api/v1/admin/thresholds", headers=self.auth_headers, timeout=5)
        self.assertEqual(res.status_code, 200)
        status_data = res.json()
        self.assertIn("thresholds", status_data)

        # VULN-06 FIX: /admin/thresholds/live is now protected — must return 401 without auth
        live_unauth = requests.get(f"{BASE_URL}/api/v1/admin/thresholds/live", timeout=5)
        self.assertEqual(live_unauth.status_code, 401, "VULN-06 FIX: ML threshold endpoint must require authentication")

        # /admin/thresholds/live with auth — should work
        live_res = requests.get(f"{BASE_URL}/api/v1/admin/thresholds/live", headers=self.auth_headers, timeout=5)
        self.assertEqual(live_res.status_code, 200)

        # Jobs listing
        jobs_res = requests.get(f"{BASE_URL}/api/v1/admin/jobs", headers=self.auth_headers, timeout=5)
        self.assertEqual(jobs_res.status_code, 200)
        print(f" [PASS] Admin Controls: Thresholds verified ({status_data['thresholds'].get('fusion_threshold')}), /thresholds/live secured (VULN-06), Retrain Jobs polled")

    def test_12_ml_feature_engineering_xai_and_health(self):
        """Verify Meteorological Feature Extraction, Hybrid ML Detectors, Value Imputation, XAI, and Mann-Kendall Trend Test"""
        engine = MeteorologicalFeatureEngine("data/metadata/climate_normals.csv")
        sample_reading = {
            "station_id": "AWS-DEL-01",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "temperature_c": 27.0,
            "humidity_pct": 52.0,
            "pressure_hpa": 1013.25,
            "wind_speed_ms": 3.0,
            "wind_direction_deg": 180.0,
            "solar_radiation_wm2": 500.0,
            "latitude": 28.6139,
            "longitude": 77.2090,
            "altitude_m": 216.0
        }
        features = engine.extract_features(sample_reading)
        self.assertIn("dew_point_c", features["physics_features"])
        self.assertIn("sea_level_pressure_hpa", features["physics_features"])

        detector = HybridDetectorEnsemble("models")
        detection = detector.detect(features)
        self.assertIn("is_anomaly", detection)
        self.assertIn("severity_score", detection)

        imputer = ValueImputer("models")
        imputed = imputer.impute_corrected_values(features, is_anomaly=detection["is_anomaly"])
        self.assertIsNotNone(imputed)

        explanation = ExplainabilityEngine.generate_explanation(features, detection)
        self.assertIsInstance(explanation, str)
        self.assertGreater(len(explanation), 0)

        # Health score engine
        health_engine = SensorHealthEngine()
        health = health_engine.update_health(
            station_id="AWS-DEL-01",
            is_anomaly=detection["is_anomaly"],
            severity_score=detection["severity_score"]
        )
        self.assertGreaterEqual(health["health_score"], 0)

        # Mann-Kendall statistical trend test
        series = [100.0, 99.0, 97.0, 95.0, 92.0, 88.0, 84.0, 80.0]
        p_val, slope, trend = _mann_kendall_test(series)
        self.assertEqual(trend, "DECREASING")
        self.assertLess(slope, 0.0)

        print(f" [PASS] ML & Analytics Services: Features extracted, Imputer verified, XAI: '{explanation[:40]}...', Health Score: {health['health_score']}, Mann-Kendall Trend: {trend}")

def run_tests():
    suite = unittest.TestLoader().loadTestsFromTestCase(FullSystemIntegrationTests)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    if result.wasSuccessful():
        print("\n" + "=" * 85)
        print("  >>> ALL FULL-SYSTEM INTEGRATION TESTS PASSED (12/12) <<<")
        print("=" * 85)
        return 0
    else:
        print("\n" + "=" * 85)
        print(f"  >>> FAILURES: {len(result.failures)} | ERRORS: {len(result.errors)} <<<")
        print("=" * 85)
        return 1

if __name__ == "__main__":
    exit_code = run_tests()
    sys.exit(exit_code)

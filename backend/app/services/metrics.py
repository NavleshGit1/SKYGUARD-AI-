import time
import threading
from collections import deque
from typing import Dict, Any, List, Optional
import numpy as np

class MetricsAccumulator:
    """
    High-performance, lock-free/low-overhead telemetry & ingestion metrics accumulator.
    Computes real-time latency percentiles (P50, P95, P99), QPS throughput, and anomaly statistics.
    """
    def __init__(self, window_size: int = 5000):
        self._lock = threading.RLock()
        self._start_time = time.time()
        self._total_ingested = 0
        self._total_anomalies = 0
        self._latencies: deque = deque(maxlen=window_size)
        self._detector_timings: Dict[str, deque] = {
            "feature_extraction": deque(maxlen=1000),
            "physical_rules": deque(maxlen=1000),
            "flatline": deque(maxlen=1000),
            "isolation_forest": deque(maxlen=1000),
            "autoencoder": deque(maxlen=1000),
            "drift_cusum": deque(maxlen=1000),
            "spatial_idw": deque(maxlen=1000),
            "imputation": deque(maxlen=1000),
            "total_pipeline": deque(maxlen=window_size)
        }
        self._anomalies_by_category: Dict[str, int] = {}

    def record_ingest(
        self,
        duration_ms: float,
        is_anomaly: bool,
        root_cause: Optional[str] = None,
        timings: Optional[Dict[str, float]] = None
    ):
        with self._lock:
            self._total_ingested += 1
            self._latencies.append(duration_ms)
            if is_anomaly:
                self._total_anomalies += 1
                cat = root_cause or "UNKNOWN"
                self._anomalies_by_category[cat] = self._anomalies_by_category.get(cat, 0) + 1

            if timings:
                for k, v in timings.items():
                    if k in self._detector_timings:
                        self._detector_timings[k].append(v)
                self._detector_timings["total_pipeline"].append(duration_ms)

    def get_summary(self) -> Dict[str, Any]:
        with self._lock:
            uptime_seconds = max(1.0, time.time() - self._start_time)
            qps = round(self._total_ingested / uptime_seconds, 2)
            
            lat_arr = np.array(self._latencies) if self._latencies else np.array([0.0])
            
            p50 = float(np.percentile(lat_arr, 50)) if len(lat_arr) > 0 else 0.0
            p90 = float(np.percentile(lat_arr, 90)) if len(lat_arr) > 0 else 0.0
            p95 = float(np.percentile(lat_arr, 95)) if len(lat_arr) > 0 else 0.0
            p99 = float(np.percentile(lat_arr, 99)) if len(lat_arr) > 0 else 0.0
            mean_lat = float(np.mean(lat_arr)) if len(lat_arr) > 0 else 0.0

            detector_stats = {}
            for k, d in self._detector_timings.items():
                if d:
                    detector_stats[k] = {
                        "avg_ms": round(float(np.mean(d)), 3),
                        "p95_ms": round(float(np.percentile(d, 95)), 3),
                        "max_ms": round(float(np.max(d)), 3)
                    }

            return {
                "uptime_seconds": round(uptime_seconds, 1),
                "total_readings_ingested": self._total_ingested,
                "total_anomalies_flagged": self._total_anomalies,
                "anomaly_rate_pct": round((self._total_anomalies / max(1, self._total_ingested)) * 100, 2),
                "throughput_qps": qps,
                "latency_profile_ms": {
                    "mean": round(mean_lat, 2),
                    "p50": round(p50, 2),
                    "p90": round(p90, 2),
                    "p95": round(p95, 2),
                    "p99": round(p99, 2),
                    "sub_10ms_compliant": p95 < 10.0
                },
                "detector_timings": detector_stats,
                "anomalies_by_category": dict(self._anomalies_by_category)
            }

metrics = MetricsAccumulator()

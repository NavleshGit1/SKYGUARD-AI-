import hmac
import hashlib
import json
import time
import math
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
import pandas as pd
import numpy as np

class AnomalyInjector:
    """
    Implements 6 mathematical anomaly injection modes on live/replayed sensor streams.
    """
    
    @staticmethod
    def inject_spike(reading: Dict[str, Any], parameter: str = "temperature_c", magnitude: float = 18.0) -> Dict[str, Any]:
        """Injects a single-step or short spike (impulse)"""
        modified = reading.copy()
        if parameter in modified:
            modified[parameter] += magnitude
            modified["injected_anomaly"] = f"SPIKE_{parameter.upper()}"
        return modified

    @staticmethod
    def inject_flatline(reading: Dict[str, Any], parameter: str = "pressure_hpa", fixed_value: Optional[float] = None) -> Dict[str, Any]:
        """Injects a stuck frozen sensor reading"""
        modified = reading.copy()
        if parameter in modified:
            if fixed_value is not None:
                modified[parameter] = fixed_value
            modified["injected_anomaly"] = f"FLATLINE_{parameter.upper()}"
        return modified

    @staticmethod
    def inject_drift(reading: Dict[str, Any], step_index: int, parameter: str = "temperature_c", drift_rate: float = 0.2) -> Dict[str, Any]:
        """Injects progressive linear calibration drift"""
        modified = reading.copy()
        if parameter in modified:
            modified[parameter] += (drift_rate * step_index)
            modified["injected_anomaly"] = f"DRIFT_{parameter.upper()}"
        return modified

    @staticmethod
    def inject_thermodynamic_violation(reading: Dict[str, Any]) -> Dict[str, Any]:
        """Injects impossible thermodynamic state (dew point > ambient temperature)"""
        modified = reading.copy()
        # Set extreme humidity (100%) and lower temperature or inflate RH beyond 100%
        modified["humidity_pct"] = 99.9
        modified["temperature_c"] = modified.get("temperature_c", 25.0) - 15.0
        modified["injected_anomaly"] = "THERMODYNAMIC_INVARIANT_VIOLATION"
        return modified

    @staticmethod
    def inject_noise_burst(reading: Dict[str, Any], parameter: str = "humidity_pct", sigma: float = 15.0) -> Dict[str, Any]:
        """Injects high-variance sensor noise burst"""
        modified = reading.copy()
        if parameter in modified:
            noise = float(np.random.normal(0, sigma))
            modified[parameter] = max(0.0, min(100.0, modified[parameter] + noise))
            modified["injected_anomaly"] = f"NOISE_BURST_{parameter.upper()}"
        return modified

    @staticmethod
    def inject_spatial_discrepancy(reading: Dict[str, Any], parameter: str = "temperature_c", offset_c: float = 18.0) -> Dict[str, Any]:
        """Injects localized microclimate violation / spatial neighbor discrepancy"""
        modified = reading.copy()
        if parameter in modified:
            modified[parameter] += offset_c
            modified["injected_anomaly"] = f"SPATIAL_DISCREPANCY_{parameter.upper()}"
        return modified


class TelemetrySigner:
    """Computes HMAC-SHA256 signature for anti-tampering and authentication"""
    
    @staticmethod
    def generate_signature(secret_key: str, station_id: str, timestamp_iso: str, payload_json: str) -> str:
        message = f"{station_id}:{timestamp_iso}:{payload_json}".encode('utf-8')
        return hmac.new(secret_key.encode('utf-8'), message, hashlib.sha256).hexdigest()


class SimulatorEngine:
    """Replay engine that reads historical CSV data and streams realistic AWS telemetry"""
    
    def __init__(self, data_path: str, secret_key: str = "skyguard-station-hmac-secret-key-2026"):
        self.data_path = data_path
        self.secret_key = secret_key
        self.df: Optional[pd.DataFrame] = None
        self.current_idx = 0
        self.active_injections: List[Dict[str, Any]] = []
        self.load_data()
        
    def load_data(self):
        try:
            full_df = pd.read_csv(self.data_path)
            full_df["dt"] = pd.to_datetime(full_df["timestamp"])
            current_month = datetime.now(timezone.utc).month
            seasonal_df = full_df[full_df["dt"].dt.month == current_month].copy().reset_index(drop=True)
            if not seasonal_df.empty:
                self.df = seasonal_df
                print(f"[Simulator] Loaded {len(self.df):,} seasonal records for month {current_month} from {self.data_path}")
            else:
                self.df = full_df
                print(f"[Simulator] Loaded {len(self.df):,} historical records from {self.data_path}")
        except Exception as e:
            print(f"[Simulator] [WARN] Could not load CSV from {self.data_path}: {e}")
            self.df = None
            
    def trigger_anomaly(self, anomaly_type: str, parameter: str = "temperature_c", duration_ticks: int = 10, magnitude: float = 15.0, station_id: Optional[str] = None):
        """Schedule an on-demand anomaly injection for a specific station or any station"""
        self.active_injections.append({
            "type": anomaly_type.upper(),
            "parameter": parameter,
            "duration": duration_ticks,
            "remaining": duration_ticks,
            "magnitude": magnitude,
            "step_count": 0,
            "fixed_value": None,
            "station_id": station_id
        })
        st_tag = f" on {station_id}" if station_id else ""
        print(f"[Simulator] [TRIGGER] Anomaly Injection: {anomaly_type} on {parameter} for {duration_ticks} ticks{st_tag}")
        
    def get_next_reading(self, target_station: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Fetch next row, apply active injections if any, sign payload, and advance cursor"""
        if self.df is None or self.df.empty:
            return None
            
        row = self.df.iloc[self.current_idx].to_dict()
        self.current_idx = (self.current_idx + 1) % len(self.df)
        
        # Live UTC timestamp
        live_timestamp = datetime.now(timezone.utc).isoformat()
        st_id = target_station or str(row.get("station_id", "AWS-DEL-01"))
        
        reading = {
            "station_id": st_id,
            "timestamp": live_timestamp,
            "temperature_c": round(float(row.get("temperature_c", 25.0)), 2),
            "pressure_hpa": round(float(row.get("pressure_hpa", 1013.25)), 2),
            "humidity_pct": round(float(row.get("humidity_pct", 50.0)), 2),
            "latitude": float(row.get("latitude", 28.6139)),
            "longitude": float(row.get("longitude", 77.2090)),
            "altitude_m": float(row.get("altitude_m", 216.0))
        }
        
        # Apply active injections matching this station (or global)
        for inj in list(self.active_injections):
            inj_station = inj.get("station_id")
            if inj_station and inj_station != st_id:
                continue # Skip if this injection is targeting a different station

            inj_type = inj["type"]
            param = inj["parameter"]
            
            if inj_type == "SPIKE":
                reading = AnomalyInjector.inject_spike(reading, param, inj["magnitude"])
            elif inj_type == "FLATLINE":
                if inj["fixed_value"] is None:
                    inj["fixed_value"] = reading.get(param, 30.0)
                reading = AnomalyInjector.inject_flatline(reading, param, inj["fixed_value"])
            elif inj_type == "DRIFT":
                inj["step_count"] += 1
                reading = AnomalyInjector.inject_drift(reading, inj["step_count"], param, drift_rate=0.3)
            elif inj_type == "THERMODYNAMIC_VIOLATION":
                reading = AnomalyInjector.inject_thermodynamic_violation(reading)
            elif inj_type == "NOISE_BURST":
                reading = AnomalyInjector.inject_noise_burst(reading, param, sigma=inj["magnitude"])
                
            inj["remaining"] -= 1
            if inj["remaining"] <= 0:
                self.active_injections.remove(inj)
                print(f"[Simulator] Finished injection: {inj_type} on {st_id}")
                
        # Generate HMAC Signature
        payload_str = json.dumps({
            "temperature_c": reading["temperature_c"],
            "pressure_hpa": reading["pressure_hpa"],
            "humidity_pct": reading["humidity_pct"]
        }, sort_keys=True)
        
        signature = TelemetrySigner.generate_signature(
            self.secret_key, reading["station_id"], reading["timestamp"], payload_str
        )
        
        return {
            "payload": reading,
            "signature": signature
        }

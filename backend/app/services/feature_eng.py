import os
import math
import json
import numpy as np
import pandas as pd
from datetime import datetime, timezone
from collections import deque
from typing import Dict, Any, Optional, Tuple

class MeteorologicalFeatureEngine:
    """
    Production Meteorological Feature Engineering & Preprocessing Pipeline
    Implements mathematical transformations defined in SkyGuard AI Blueprint Section 6.
    """

    def __init__(self, normals_csv_path: Optional[str] = None):
        # Sliding circular window buffers per station
        # Key: station_id -> { 'temperature_c': deque(maxlen=24), 'pressure_hpa': deque(...), ... }
        self.buffers: Dict[str, Dict[str, deque]] = {}
        self.last_readings: Dict[str, Dict[str, Any]] = {}
        self.last_derivatives: Dict[str, Dict[str, float]] = {}
        
        # Load Climatological Normals if provided
        self.climate_normals: Dict[str, Dict[int, Dict[str, float]]] = {}
        if normals_csv_path and os.path.exists(normals_csv_path):
            self._load_climate_normals(normals_csv_path)

    def _load_climate_normals(self, csv_path: str):
        """Loads WMO 30-year monthly normals into an O(1) lookup dictionary"""
        try:
            df = pd.read_csv(csv_path)
            for _, row in df.iterrows():
                st_id = str(row["station_id"])
                month = int(row["month"])
                if st_id not in self.climate_normals:
                    self.climate_normals[st_id] = {}
                self.climate_normals[st_id][month] = {
                    "t_mean": float(row.get("t_mean_c", 25.0)),
                    "t_std": float(row.get("t_std_c", 3.0)),
                    "p_mean": float(row.get("p_mean_hpa", 1013.25)),
                    "p_std": float(row.get("p_std_hpa", 4.0)),
                    "rh_mean": float(row.get("rh_mean_pct", 60.0)),
                    "rh_std": float(row.get("rh_std_pct", 10.0)),
                }
        except Exception as e:
            print(f"[FeatureEngine] ⚠️ Warning: Failed loading climate normals: {e}")

    # =========================================================================
    # 1. Thermodynamic Dew Point (Magnus-Tetens Equation)
    # =========================================================================
    @staticmethod
    def calculate_dew_point(temp_c: float, rh_pct: float) -> Tuple[float, bool]:
        """
        Calculates thermodynamic dew point temperature (°C).
        Enforces physical invariant: T_dew <= T_ambient + 0.1°C
        Returns: (dew_point_c, is_invariant_violated)
        """
        # Clamp relative humidity to valid physical domain (0.01% - 100%)
        rh_clamped = max(0.01, min(100.0, rh_pct))
        
        # Magnus-Tetens coefficients (WMO standard for -45°C to 60°C)
        a = 17.27
        b = 237.7
        
        gamma = (a * temp_c) / (b + temp_c) + math.log(rh_clamped / 100.0)
        dew_point = (b * gamma) / (a - gamma)
        
        # Physical constraint: Dew point cannot exceed ambient dry-bulb temperature
        invariant_violated = (dew_point > temp_c + 0.1)
        
        return round(dew_point, 2), invariant_violated

    # =========================================================================
    # 2. Hypsometric Sea-Level Barometric Pressure Reduction
    # =========================================================================
    @staticmethod
    def calculate_sea_level_pressure(station_pres_hpa: float, altitude_m: float, temp_c: float) -> float:
        """
        Reduces station surface pressure to Mean Sea Level (MSL) Pressure (P_0)
        using the international standard hypsometric formula.
        """
        if altitude_m <= 0.0:
            return round(station_pres_hpa, 2)
            
        lapse_rate = 0.0065  # Standard atmospheric lapse rate (K/m)
        t_kelvin = temp_c + 273.15
        
        try:
            factor = 1.0 - (lapse_rate * altitude_m) / (t_kelvin + lapse_rate * altitude_m)
            if factor <= 0:
                return round(station_pres_hpa, 2)
            p_slp = station_pres_hpa * math.pow(factor, -5.257)
            return round(p_slp, 2)
        except Exception:
            return round(station_pres_hpa, 2)

    # =========================================================================
    # 3. Rolling Window Statistics (Mean, Std, Median Absolute Deviation)
    # =========================================================================
    @staticmethod
    def _compute_rolling_stats(values: deque) -> Dict[str, float]:
        """Calculates robust statistical dispersion metrics over sliding window"""
        arr = np.array(values, dtype=float)
        if len(arr) == 0:
            return {"mean": 0.0, "std": 0.0, "mad": 0.0, "median": 0.0}
            
        mean = float(np.mean(arr))
        std = float(np.std(arr)) if len(arr) > 1 else 0.0
        median = float(np.median(arr))
        mad = float(np.median(np.abs(arr - median)))
        
        return {
            "mean": round(mean, 2),
            "std": round(std, 3),
            "median": round(median, 2),
            "mad": round(mad, 3)
        }

    # =========================================================================
    # 4. Stream Feature Extraction Pipeline (Main Entry Point)
    # =========================================================================
    def extract_features(self, reading: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transforms a validated telemetry reading into a complete 32-feature vector
        matching SkyGuard AI Contract B.3.
        """
        st_id = str(reading["station_id"])
        ts = reading["timestamp"]
        if isinstance(ts, str):
            ts_dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        else:
            ts_dt = ts
            
        t_val = float(reading["temperature_c"])
        p_val = float(reading["pressure_hpa"])
        rh_val = float(reading["humidity_pct"])
        alt_m = float(reading.get("altitude_m", 0.0))

        # Initialize station sliding buffer if first reading
        if st_id not in self.buffers:
            self.buffers[st_id] = {
                "t_5m": deque(maxlen=5),
                "t_1h": deque(maxlen=60),
                "t_24h": deque(maxlen=1440),
                "p_1h": deque(maxlen=60),
                "rh_1h": deque(maxlen=60),
                "timestamps": deque(maxlen=60)
            }
            self.last_derivatives[st_id] = {"dT_dt": 0.0, "dP_dt": 0.0, "dRH_dt": 0.0}

        buf = self.buffers[st_id]
        buf["t_5m"].append(t_val)
        buf["t_1h"].append(t_val)
        buf["t_24h"].append(t_val)
        buf["p_1h"].append(p_val)
        buf["rh_1h"].append(rh_val)

        # 1. Physics Features
        dew_point, dew_violation = self.calculate_dew_point(t_val, rh_val)
        sea_level_pressure = self.calculate_sea_level_pressure(p_val, alt_m, t_val)

        # 2. Rolling Window Stats
        t_stats_5m = self._compute_rolling_stats(buf["t_5m"])
        t_stats_1h = self._compute_rolling_stats(buf["t_1h"])
        p_stats_1h = self._compute_rolling_stats(buf["p_1h"])
        rh_stats_1h = self._compute_rolling_stats(buf["rh_1h"])

        # 3. Derivatives (Rate-of-Change)
        last_r = self.last_readings.get(st_id)
        dt_sec = 60.0  # default 1 min
        if last_r:
            last_ts = last_r["timestamp"]
            if isinstance(last_ts, str):
                last_ts = datetime.fromisoformat(last_ts.replace("Z", "+00:00"))
            gap = (ts_dt - last_ts).total_seconds()
            if gap > 0:
                dt_sec = gap

        dT_dt = round((t_val - (last_r["temperature_c"] if last_r else t_val)) / (dt_sec / 60.0), 3)
        dP_dt = round((p_val - (last_r["pressure_hpa"] if last_r else p_val)) / (dt_sec / 60.0), 3)
        dRH_dt = round((rh_val - (last_r["humidity_pct"] if last_r else rh_val)) / (dt_sec / 60.0), 3)

        # 2nd derivative (acceleration)
        prev_dT_dt = self.last_derivatives[st_id].get("dT_dt", 0.0)
        d2T_dt2 = round((dT_dt - prev_dT_dt) / (dt_sec / 60.0), 4)

        self.last_derivatives[st_id] = {"dT_dt": dT_dt, "dP_dt": dP_dt, "dRH_dt": dRH_dt}
        self.last_readings[st_id] = reading

        # 4. Climatological Diurnal Baseline Z-Score
        month = ts_dt.month
        normals = self.climate_normals.get(st_id, {}).get(month, {
            "t_mean": 25.0, "t_std": 3.0,
            "p_mean": 1013.25, "p_std": 4.0,
            "rh_mean": 60.0, "rh_std": 10.0
        })

        t_zscore = round((t_val - normals["t_mean"]) / max(0.1, normals["t_std"]), 2)
        # FIX: Climate normals store Sea Level Pressure; compare MSLP vs MSLP normal.
        # Using raw station surface pressure (~975 hPa for Jaipur at 431m) against
        # MSLP normals (~1001 hPa) produces a permanent -9.5 sigma false outlier.
        p_zscore = round((sea_level_pressure - normals["p_mean"]) / max(0.1, normals["p_std"]), 2)
        rh_zscore = round((rh_val - normals["rh_mean"]) / max(0.1, normals["rh_std"]), 2)


        # 5. Missingness Tracker
        gap_duration = dt_sec if last_r else 0.0
        packet_loss = 1.0 if gap_duration > 300.0 else 0.0

        # Construct final Feature Vector (Contract B.3)
        return {
            "station_id": st_id,
            "timestamp": ts_dt.isoformat(),
            "raw": {
                "temperature_c": t_val,
                "pressure_hpa": p_val,
                "humidity_pct": rh_val
            },
            "rolling_stats": {
                "t_mean_5m": t_stats_5m["mean"],
                "t_std_5m": t_stats_5m["std"],
                "t_mad_5m": t_stats_5m["mad"],
                "t_mean_1h": t_stats_1h["mean"],
                "t_std_1h": t_stats_1h["std"],
                "p_mean_1h": p_stats_1h["mean"],
                "p_std_1h": p_stats_1h["std"],
                "rh_mean_1h": rh_stats_1h["mean"],
                "rh_std_1h": rh_stats_1h["std"]
            },
            "derivatives": {
                "dT_dt": dT_dt,
                "d2T_dt2": d2T_dt2,
                "dP_dt": dP_dt,
                "dRH_dt": dRH_dt
            },
            "physics_features": {
                "dew_point_c": dew_point,
                "is_dew_violation": dew_violation,
                "sea_level_pressure_hpa": sea_level_pressure
            },
            "climatology_delta": {
                "t_delta_zscore": t_zscore,
                "p_delta_zscore": p_zscore,
                "rh_delta_zscore": rh_zscore
            },
            "missingness": {
                "gap_duration_sec": gap_duration,
                "packet_loss_rate_1h": packet_loss,
                "buffer_count": len(buf["t_1h"])
            }
        }

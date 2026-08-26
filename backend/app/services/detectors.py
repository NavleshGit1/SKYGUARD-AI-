import os
import math
import joblib
import numpy as np
import torch
import torch.nn as nn
from collections import deque
from typing import Dict, Any, List, Optional, Tuple

# ==============================================================================
# PyTorch Bottleneck Compression Autoencoder Definition
# ==============================================================================
class WeatherAutoencoder(nn.Module):
    """
    Symmetric 3-layer bottleneck deep autoencoder for meteorological feature reconstruction.
    Input Dimension: 8 key continuous features -> Latent Dimension: 3
    """
    def __init__(self, input_dim: int = 8, latent_dim: int = 3):
        super(WeatherAutoencoder, self).__init__()
        # Encoder
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, 16),
            nn.BatchNorm1d(16),
            nn.LeakyReLU(0.1),
            nn.Linear(16, 8),
            nn.LeakyReLU(0.1),
            nn.Linear(8, latent_dim)
        )
        # Decoder
        self.decoder = nn.Sequential(
            nn.Linear(latent_dim, 8),
            nn.LeakyReLU(0.1),
            nn.Linear(8, 16),
            nn.BatchNorm1d(16),
            nn.LeakyReLU(0.1),
            nn.Linear(16, input_dim)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        latent = self.encoder(x)
        reconstruction = self.decoder(latent)
        return reconstruction


# ==============================================================================
# DETECTOR 1: Physical Bounds & Thermodynamic Rules (Deterministic)
# ==============================================================================
class PhysicalRuleDetector:
    """Evaluates hard WMO meteorological boundaries and thermodynamic invariants"""
    
    BOUNDS = {
        "temperature_c": (-50.0, 60.0),
        "pressure_hpa": (800.0, 1100.0),
        "humidity_pct": (0.0, 100.0)
    }

    @classmethod
    def evaluate(cls, features: Dict[str, Any]) -> Tuple[float, Optional[str]]:
        raw = features.get("raw", {})
        physics = features.get("physics_features", {})
        
        # 1. Check Hard Physical Bounds
        for param, (low, high) in cls.BOUNDS.items():
            val = raw.get(param)
            if val is not None and (val < low or val > high):
                return 1.0, f"PHYSICAL_BOUND_VIOLATION: {param} = {val} outside [{low}, {high}]"

        # 2. Check Thermodynamic Invariant Violation (Dew Point > Ambient Temperature)
        if physics.get("is_dew_violation", False):
            return 1.0, f"THERMODYNAMIC_INVARIANT_VIOLATION: Dew Point ({physics.get('dew_point_c')}°C) > Ambient Temp ({raw.get('temperature_c')}°C)"

        return 0.0, None


# ==============================================================================
# DETECTOR 2: Frozen / Flatline Sensor Detector
# ==============================================================================
class FlatlineDetector:
    """Detects zero-variance stuck sensors and run-length repeated constants"""
    
    def __init__(self, variance_threshold: float = 1e-6, max_repeat_count: int = 6):
        self.variance_threshold = variance_threshold
        self.max_repeat_count = max_repeat_count
        self.repeat_counters: Dict[str, Dict[str, Tuple[float, int]]] = {}

    def evaluate(self, features: Dict[str, Any]) -> Tuple[float, Optional[str]]:
        st_id = features.get("station_id", "DEFAULT")
        raw = features.get("raw", {})
        rolling = features.get("rolling_stats", {})

        if st_id not in self.repeat_counters:
            self.repeat_counters[st_id] = {}

        # Check rolling variance (std == 0 over 1 hour, only if buffer has accumulated >= 5 readings)
        t_std = rolling.get("t_std_1h")
        sample_count = features.get("missingness", {}).get("buffer_count", 10)
        if t_std is not None and t_std < self.variance_threshold and sample_count >= 5:
            return 0.95, "FLATLINE_ZERO_VARIANCE: Temperature constant over 1 hour"

        # Check consecutive identical float values
        for param in ["temperature_c", "pressure_hpa", "humidity_pct"]:
            val = raw.get(param)
            if val is not None:
                last_val, count = self.repeat_counters[st_id].get(param, (val, 0))
                if abs(val - last_val) < 1e-4:
                    count += 1
                else:
                    count = 1
                self.repeat_counters[st_id][param] = (val, count)

                if count >= self.max_repeat_count:
                    return 0.90, f"FLATLINE_FROZEN_VALUE: {param} repeated identical value {count} times"

        return 0.0, None


# ==============================================================================
# DETECTOR 3: Isolation Forest Statistical Point Anomaly Detector
# ==============================================================================
class IsolationForestDetector:
    """Evaluates multivariate feature vector isolation path depth"""

    def __init__(self, model_path: Optional[str] = None, scaler_path: Optional[str] = None):
        self.model = None
        self.scaler = None
        if model_path and os.path.exists(model_path):
            self.model = joblib.load(model_path)
        if scaler_path and os.path.exists(scaler_path):
            self.scaler = joblib.load(scaler_path)

    def evaluate(self, feature_vector: np.ndarray) -> Tuple[float, Optional[str]]:
        if self.model is None or self.scaler is None:
            return 0.0, None
        try:
            X_scaled = self.scaler.transform(feature_vector.reshape(1, -1))
            # decision_function: positive for inliers (normal), negative for outliers (anomalous)
            decision_val = float(self.model.decision_function(X_scaled)[0])
            # Maps positive normal values to ~0.0-0.2, negative outliers to 0.7-1.0
            anomaly_score = float(np.clip(0.5 - (decision_val * 3.5), 0.0, 1.0))
            is_anom = anomaly_score >= 0.70
            return anomaly_score, ("STATISTICAL_OUTLIER" if is_anom else None)
        except Exception:
            return 0.0, None


# ==============================================================================
# DETECTOR 4: PyTorch Deep Compression Autoencoder Detector
# ==============================================================================
class DeepAutoencoderDetector:
    """Evaluates joint multi-parameter reconstruction error MSE"""

    def __init__(self, model_path: Optional[str] = None, scaler_path: Optional[str] = None, threshold: float = 4.50):
        self.model = None
        self.scaler = None
        self.threshold = threshold
        
        if model_path and os.path.exists(model_path):
            self.model = WeatherAutoencoder(input_dim=8, latent_dim=3)
            self.model.load_state_dict(torch.load(model_path, map_location=torch.device('cpu')))
            self.model.eval()
            
        if scaler_path and os.path.exists(scaler_path):
            self.scaler = joblib.load(scaler_path)

    def evaluate(self, feature_vector: np.ndarray) -> Tuple[float, Dict[str, float], Optional[str]]:
        if self.model is None or self.scaler is None:
            return 0.0, {}, None
        try:
            X_scaled = self.scaler.transform(feature_vector.reshape(1, -1))
            tensor_in = torch.tensor(X_scaled, dtype=torch.float32)
            with torch.no_grad():
                reconstructed = self.model(tensor_in).numpy()
                
            # Compute element-wise squared errors
            diff = (X_scaled[0] - reconstructed[0]) ** 2
            mse = float(np.mean(diff))
            
            # Map MSE to normalized [0.0, 1.0] score using calibrated 3-sigma baseline (4.50)
            score = float(np.clip(mse / self.threshold, 0.0, 1.0))
            
            # Feature attribution percentage
            total_diff = max(1e-6, float(np.sum(diff)))
            attributions = {
                "temperature_c": float(diff[0] / total_diff),
                "pressure_hpa": float(diff[1] / total_diff),
                "humidity_pct": float(diff[2] / total_diff),
                "dew_point_c": float(diff[3] / total_diff),
                "sea_level_pressure_hpa": float(diff[4] / total_diff),
                "dT_dt": float(diff[5] / total_diff),
                "t_std_1h": float(diff[6] / total_diff),
                "t_delta_zscore": float(diff[7] / total_diff)
            }
            is_anom = score >= 0.80
            return score, attributions, ("MULTIVARIATE_PHYSICAL_DEVIATION" if is_anom else None)
        except Exception:
            return 0.0, {}, None


# ==============================================================================
# DETECTOR 5: Temporal Calibration Drift Detector (CUSUM on Residuals)
# ==============================================================================
class DriftDetector:
    """CUSUM (Cumulative Sum Control Chart) on climatology-adjusted residuals"""
    
    def __init__(self, drift_threshold: float = 20.0):
        self.drift_threshold = drift_threshold
        self.cusum_pos: Dict[str, float] = {}
        self.cusum_neg: Dict[str, float] = {}

    def evaluate(self, features: Dict[str, Any]) -> Tuple[float, Optional[str]]:
        st_id = features.get("station_id", "DEFAULT")
        z_score = features.get("climatology_delta", {}).get("t_delta_zscore", 0.0)

        # Diurnal slack k = 1.5 with exponential decay 0.85 to prevent normal daytime heating accumulation
        pos = max(0.0, 0.85 * self.cusum_pos.get(st_id, 0.0) + (z_score - 1.50))
        neg = max(0.0, 0.85 * self.cusum_neg.get(st_id, 0.0) - (z_score + 1.50))
        
        self.cusum_pos[st_id] = pos
        self.cusum_neg[st_id] = neg
        
        max_cusum = max(pos, neg)
        score = float(np.clip(max_cusum / self.drift_threshold, 0.0, 1.0))
        
        if score >= 0.85:
            return score, f"CALIBRATION_DRIFT_DETECTED: Persistent CUSUM bias ({max_cusum:.2f})"
        return score, None


# ==============================================================================
# DETECTOR 6: Spatial Cross-Check (Inverse Distance Weighting — IDW)
# Blueprint §7.6: k=4 nearest stations within R≤50 km, w_j = 1/d(i,j)²
# ==============================================================================
class SpatialConsistencyDetector:
    """
    Geostatistical cross-validation using Inverse Distance Weighting (IDW).
    Computes distance-weighted neighbor predictions for T, P, and RH.
    Distinguishes isolated sensor faults from genuine regional meteorological fronts.
    """

    MAX_RADIUS_KM: float = 50.0    # Maximum search radius for neighbors
    K_NEIGHBORS:   int   = 4       # Maximum neighbors to use in IDW
    FAULT_SIGMA:   float = 3.0     # σ threshold for isolated fault detection
    FRONT_SIGMA:   float = 2.0     # σ threshold for simultaneous regional shift

    def __init__(self):
        # station_id -> {"lat": float, "lon": float, "temperature_c": float,
        #                "pressure_hpa": float, "humidity_pct": float}
        self.network_cache: Dict[str, Dict[str, Any]] = {}

    def update_network(self, station_id: str, reading: Dict[str, Any]):
        """Register latest reading from a station into the spatial cache."""
        self.network_cache[station_id] = reading

    @staticmethod
    def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Haversine great-circle distance in kilometres."""
        R = 6371.0
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi  = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    def _idw_estimate(self, neighbors: List[Dict[str, Any]], param: str) -> Optional[float]:
        """Inverse Distance Weighting: x̂ = Σ(w_j·x_j) / Σ(w_j), w_j = 1/d²"""
        vals, weights = [], []
        for nb in neighbors:
            v = nb.get(param)
            d = nb.get("_dist_km", 1.0)
            if v is not None and d > 0.01:
                w = 1.0 / (d ** 2)
                vals.append(v)
                weights.append(w)
        if not vals:
            return None
        return float(np.dot(vals, weights) / np.sum(weights))

    def evaluate(self, features: Dict[str, Any]) -> Tuple[float, Optional[str]]:
        st_id  = features.get("station_id")
        raw    = features.get("raw", {})
        lat    = raw.get("latitude")
        lon    = raw.get("longitude")

        if lat is None or lon is None or len(self.network_cache) < 2:
            return 0.0, None

        # — Build sorted neighbor list by distance —
        neighbors: List[Dict[str, Any]] = []
        for sid, cache_r in self.network_cache.items():
            if sid == st_id:
                continue
            nb_lat = cache_r.get("latitude")
            nb_lon = cache_r.get("longitude")
            if nb_lat is None or nb_lon is None:
                continue
            d_km = self._haversine_km(lat, lon, nb_lat, nb_lon)
            if d_km <= self.MAX_RADIUS_KM:
                nb_copy = dict(cache_r)
                nb_copy["_dist_km"] = d_km
                neighbors.append(nb_copy)

        # Sort by distance, keep top-K
        neighbors.sort(key=lambda x: x["_dist_km"])
        neighbors = neighbors[: self.K_NEIGHBORS]

        if len(neighbors) < 2:
            return 0.0, None

        # — IDW-weighted estimates for each parameter —
        params = {
            "temperature_c": ("°C",  5.0),   # std-dev baseline for σ calculation
            "pressure_hpa":  ("hPa", 3.0),
            "humidity_pct":  ("%",   8.0)
        }
        max_score   = 0.0
        max_detail  = None
        all_deviate = True  # True only if ALL neighbours deviate simultaneously (regional front)

        for param, (unit, sigma_base) in params.items():
            obs = raw.get(param)
            if obs is None:
                continue
            idw_est = self._idw_estimate(neighbors, param)
            if idw_est is None:
                continue

            deviation = abs(obs - idw_est)
            zscore    = deviation / sigma_base  # normalised deviation in σ units

            # Check if neighbours themselves agree (low variance → isolated fault)
            nb_vals = [nb.get(param) for nb in neighbors if nb.get(param) is not None]
            nb_std  = float(np.std(nb_vals)) if len(nb_vals) >= 2 else sigma_base

            if nb_std > (sigma_base * 0.8):
                all_deviate = False  # neighbours disagree → potential regional front

            if zscore >= self.FAULT_SIGMA:
                score = float(np.clip(zscore / (self.FAULT_SIGMA * 2), 0.0, 1.0))
                if score > max_score:
                    max_score  = score
                    max_detail = (
                        f"SPATIAL_IDW_FAULT: {param}={obs:.2f}{unit} deviates "
                        f"{deviation:.2f}{unit} ({zscore:.1f}σ) from IDW estimate "
                        f"{idw_est:.2f}{unit} using {len(neighbors)} neighbours."
                    )

        if max_score > 0.0:
            if all_deviate:
                # Neighbours also shifting → genuine meteorological front, not a sensor fault
                return 0.0, None
            return max_score, max_detail

        return 0.0, None


# ==============================================================================
# MASTER HYBRID DETECTOR ENSEMBLE ORCHESTRATOR
# ==============================================================================
class HybridDetectorEnsemble:
    """Combines all 6 detectors and produces final weighted anomaly decision"""

    def __init__(self, models_dir: str = "models"):
        if_path = os.path.join(models_dir, "isolation_forest.pkl")
        ae_path = os.path.join(models_dir, "autoencoder.pt")
        scaler_path = os.path.join(models_dir, "scaler.pkl")

        self.rule_detector = PhysicalRuleDetector()
        self.flatline_detector = FlatlineDetector()
        self.iforest_detector = IsolationForestDetector(if_path, scaler_path)
        self.autoencoder_detector = DeepAutoencoderDetector(ae_path, scaler_path)
        self.drift_detector = DriftDetector()
        self.spatial_detector = SpatialConsistencyDetector()

    @staticmethod
    def _extract_model_vector(features: Dict[str, Any]) -> np.ndarray:
        """Flattens feature dictionary into standard 8-dim model vector"""
        raw = features.get("raw", {})
        phys = features.get("physics_features", {})
        deriv = features.get("derivatives", {})
        roll = features.get("rolling_stats", {})
        clim = features.get("climatology_delta", {})

        return np.array([
            raw.get("temperature_c", 25.0),
            raw.get("pressure_hpa", 1013.25),
            raw.get("humidity_pct", 50.0),
            phys.get("dew_point_c", 15.0),
            phys.get("sea_level_pressure_hpa", 1013.25),
            deriv.get("dT_dt", 0.0),
            roll.get("t_std_1h", 0.0),
            clim.get("t_delta_zscore", 0.0)
        ], dtype=float)

    def detect(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes all 6 detectors in parallel, computes ensemble score,
        and generates explainable root-cause diagnosis.
        """
        vec = self._extract_model_vector(features)

        # 1. Evaluate Detectors
        score_rule, diag_rule = self.rule_detector.evaluate(features)
        score_flat, diag_flat = self.flatline_detector.evaluate(features)
        score_iforest, diag_if = self.iforest_detector.evaluate(vec)
        score_ae, attributions, diag_ae = self.autoencoder_detector.evaluate(vec)
        score_drift, diag_drift = self.drift_detector.evaluate(features)
        score_spatial, diag_spatial = self.spatial_detector.evaluate(features)

        # Update spatial network cache
        self.spatial_detector.update_network(features.get("station_id", "DEFAULT"), features.get("raw", {}))

        scores = {
            "rule_physical": round(score_rule, 3),
            "frozen_sensor": round(score_flat, 3),
            "statistical_iforest": round(score_iforest, 3),
            "multivariate_autoencoder": round(score_ae, 3),
            "drift_stl_cusum": round(score_drift, 3),
            "spatial_cross_check": round(score_spatial, 3)
        }

        # 2. Hybrid Decision Fusion Logic
        # If deterministic rules or flatline fire -> instant 100% anomaly
        if score_rule >= 1.0 or score_flat >= 0.90:
            final_severity = max(score_rule, score_flat)
            is_anomaly = True
            root_cause = diag_rule or diag_flat or "CRITICAL_RULE_VIOLATION"
        else:
            # Weighted ML Ensemble Score
            final_severity = round(
                0.35 * score_ae +
                0.25 * score_iforest +
                0.15 * score_drift +
                0.15 * score_spatial +
                0.10 * max(score_rule, score_flat), 3
            )
            # Flag anomaly if composite score >= 0.60 or any strong individual model fires >= 0.80
            has_strong_trigger = (score_ae >= 0.80) or (score_iforest >= 0.85) or (score_drift >= 0.80) or (score_spatial >= 0.80)
            is_anomaly = (final_severity >= 0.60) or has_strong_trigger
            root_cause = diag_ae or diag_if or diag_drift or diag_spatial or ("NORMAL" if not is_anomaly else "MULTIVARIATE_ANOMALY")

        confidence = round(float(np.mean([s for s in scores.values() if s > 0] or [0.0])), 2)
        if not is_anomaly:
            confidence = round(1.0 - final_severity, 2)

        return {
            "detector_scores": scores,
            "severity_score": final_severity,
            "confidence_score": max(0.5, confidence),
            "is_anomaly": is_anomaly,
            "root_cause": root_cause,
            "shap_attributions": attributions
        }

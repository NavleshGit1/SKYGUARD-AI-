import os
import joblib
import numpy as np
import torch
from typing import Dict, Any, Optional, Tuple
from backend.app.services.detectors import WeatherAutoencoder

class ValueImputer:
    """
    Sensor Value Imputation & Correction Engine
    Provides estimated physical values when raw sensor readings are corrupted or anomalous,
    leveraging the deep autoencoder's learned manifold with physical bounding and healthy state persistence.
    """

    def __init__(self, models_dir: str = "models"):
        ae_path = os.path.join(models_dir, "autoencoder.pt")
        scaler_path = os.path.join(models_dir, "scaler.pkl")

        self.model = None
        self.scaler = None
        self.last_healthy: Dict[str, Dict[str, float]] = {}

        if os.path.exists(ae_path) and os.path.exists(scaler_path):
            try:
                self.scaler = joblib.load(scaler_path)
                self.model = WeatherAutoencoder(input_dim=8, latent_dim=3)
                self.model.load_state_dict(torch.load(ae_path, map_location=torch.device('cpu')))
                self.model.eval()
            except Exception as e:
                print(f"[ValueImputer] ⚠️ Warning: Failed to load autoencoder model for imputation: {e}")

    def impute_corrected_values(
        self,
        features: Dict[str, Any],
        is_anomaly: bool,
        shap_attributions: Optional[Dict[str, float]] = None
    ) -> Dict[str, Any]:
        """
        Cross-checks and generates corrected physical values when sensor readings are flagged as anomalous.
        """
        st_id = features.get("station_id", "AWS-DEL-01")
        raw = features.get("raw", {})
        phys = features.get("physics_features", {})
        deriv = features.get("derivatives", {})

        t_raw = float(raw.get("temperature_c", 28.0))
        p_raw = float(raw.get("pressure_hpa", 1000.0))
        rh_raw = float(raw.get("humidity_pct", 75.0))

        # When reading is nominal: cache healthy state and return raw values as-is
        if not is_anomaly:
            self.last_healthy[st_id] = {
                "temperature_c": t_raw,
                "pressure_hpa": p_raw,
                "humidity_pct": rh_raw
            }
            return {
                "temperature_c": t_raw,
                "pressure_hpa": p_raw,
                "humidity_pct": rh_raw,
                "is_imputed": False
            }

        # Reading IS anomalous: retrieve pre-fault healthy baseline
        healthy = self.last_healthy.get(st_id, {
            "temperature_c": 28.5,
            "pressure_hpa": 1000.0,
            "humidity_pct": 75.0
        })

        t_clean = healthy["temperature_c"]
        p_clean = healthy["pressure_hpa"]
        rh_clean = healthy["humidity_pct"]

        # Identify which channels are faulted / spiked
        t_is_corrupted = abs(t_raw - t_clean) > 2.0 or abs(deriv.get("dT_dt", 0.0)) > 1.0 or (shap_attributions and shap_attributions.get("temperature_c", 0) > 0.15)
        p_is_corrupted = abs(p_raw - p_clean) > 3.0 or abs(deriv.get("dP_dt", 0.0)) > 1.5 or (shap_attributions and shap_attributions.get("pressure_hpa", 0) > 0.15)
        rh_is_corrupted = abs(rh_raw - rh_clean) > 6.0 or phys.get("is_dew_violation", False) or (shap_attributions and shap_attributions.get("humidity_pct", 0) > 0.15)

        # Baseline assignment: restore corrupted channels from clean manifold
        t_imputed = round(t_clean if t_is_corrupted else t_raw, 1)
        p_imputed = round(p_clean if p_is_corrupted else p_raw, 1)
        rh_imputed = round(rh_clean if rh_is_corrupted else rh_raw, 1)

        # Autoencoder neural manifold verification
        if self.model is not None and self.scaler is not None:
            vec = np.array([
                t_clean,
                p_clean,
                rh_clean,
                phys.get("dew_point_c", 18.0),
                phys.get("sea_level_pressure_hpa", 1013.25),
                0.0,
                0.5,
                0.0
            ], dtype=float)

            try:
                X_scaled = self.scaler.transform(vec.reshape(1, -1))
                tensor_in = torch.tensor(X_scaled, dtype=torch.float32)
                with torch.no_grad():
                    reconstructed_scaled = self.model(tensor_in).numpy()

                reconstructed = self.scaler.inverse_transform(reconstructed_scaled)[0]
                ae_t = round(float(reconstructed[0]), 1)
                ae_p = round(float(reconstructed[1]), 1)
                ae_rh = round(float(reconstructed[2]), 1)

                if t_is_corrupted and abs(ae_t - t_clean) <= 1.5:
                    t_imputed = ae_t
                if p_is_corrupted and abs(ae_p - p_clean) <= 4.0:
                    p_imputed = ae_p
                if rh_is_corrupted and abs(ae_rh - rh_clean) <= 8.0:
                    rh_imputed = ae_rh
            except Exception:
                pass

        # Strict physical thermodynamic bounding
        t_imputed = max(-50.0, min(60.0, t_imputed))
        p_imputed = max(850.0, min(1060.0, p_imputed))
        rh_imputed = max(0.0, min(100.0, rh_imputed))

        is_any_corrupted = (t_is_corrupted or p_is_corrupted or rh_is_corrupted)

        # Return imputed physical values ONLY for the channel(s) that were corrupted
        return {
            "temperature_c": t_imputed if t_is_corrupted else (t_imputed if not is_any_corrupted else None),
            "pressure_hpa": p_imputed if p_is_corrupted else None,
            "humidity_pct": rh_imputed if rh_is_corrupted else None,
            "is_imputed": is_any_corrupted,
            "corrupted_channels": {
                "temperature": t_is_corrupted,
                "pressure": p_is_corrupted,
                "humidity": rh_is_corrupted
            }
        }

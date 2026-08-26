import os
from typing import Dict, Any, List, Optional

class ExplainabilityEngine:
    """
    Explainable AI (XAI) & Root-Cause Classification Engine
    Translates complex multidimensional anomaly vectors and neural network reconstruction errors
    into clear, simple, plain-English explanations that anyone can easily understand.
    """

    FEATURE_NAMES = [
        "temperature_c", "pressure_hpa", "humidity_pct", "dew_point_c",
        "sea_level_pressure_hpa", "dT_dt", "t_std_1h", "t_delta_zscore"
    ]

    FRIENDLY_NAMES = {
        "temperature_c": "Temperature",
        "pressure_hpa": "Air Pressure",
        "humidity_pct": "Humidity",
        "dew_point_c": "Dew Point (Condensation Temp)",
        "sea_level_pressure_hpa": "Sea-Level Pressure",
        "dT_dt": "Temperature Jump Rate",
        "t_std_1h": "1-Hour Fluctuations",
        "t_delta_zscore": "Deviation from Normal Climate"
    }

    STATION_NAMES = {
        "AWS-DEL-01": "Delhi Safdarjung",
        "AWS-MUM-01": "Mumbai Santacruz",
        "AWS-CHE-01": "Chennai Meenambakkam",
        "AWS-KOL-01": "Kolkata Alipore",
        "AWS-JAI-01": "Jaipur Sanganer"
    }

    @classmethod
    def generate_explanation(
        cls,
        features: Dict[str, Any],
        detection_result: Dict[str, Any]
    ) -> str:
        """
        Generates a clear, plain-English explanation of the sensor anomaly.
        """
        if not detection_result.get("is_anomaly", False):
            return "All sensors are operating normally. Readings match expected weather conditions."

        root_cause = detection_result.get("root_cause", "UNKNOWN_ANOMALY")
        detector_scores = detection_result.get("detector_scores", {})
        attributions = detection_result.get("shap_attributions", {})
        raw = features.get("raw", {})
        phys = features.get("physics_features", {})

        st_id = features.get("station_id", "Unknown Station")
        st_name = cls.STATION_NAMES.get(st_id, st_id)
        t_val = raw.get("temperature_c", "N/A")
        p_val = raw.get("pressure_hpa", "N/A")
        rh_val = raw.get("humidity_pct", "N/A")
        dew_pt = phys.get("dew_point_c", "N/A")

        # 1. Thermodynamic Dew Point Invariant Violation
        if "THERMODYNAMIC_INVARIANT_VIOLATION" in root_cause or phys.get("is_dew_violation", False):
            return (
                f"💧 Humidity Sensor Error at {st_name}: The calculated dew point ({dew_pt}°C) is higher than the air temperature ({t_val}°C), "
                f"which is physically impossible in nature. This usually happens when water droplets, rain moisture, or dirt condense directly on the humidity sensor probe."
            )

        # 2. Frozen / Stuck Sensor
        elif "FLATLINE" in root_cause:
            return (
                f"🛑 Frozen/Stuck Sensor at {st_name}: The sensor is outputting the exact same value ({t_val}°C) without any natural micro-fluctuations. "
                f"The sensor probe is likely disconnected, stuck, or the data cable is locked up."
            )

        # 3. Physical Bound Exceeded
        elif "PHYSICAL_BOUND_VIOLATION" in root_cause:
            return (
                f"⚠️ Out-of-Range Sensor Reading at {st_name}: The reading ({t_val}°C, {p_val} hPa) exceeds real-world Earth weather limits. "
                f"This indicates a severe electrical fault or damaged sensor transducer."
            )

        # 4. Calibration Drift
        elif "CALIBRATION_DRIFT" in root_cause or detector_scores.get("drift_stl_cusum", 0) > 0.7:
            return (
                f"📉 Slow Calibration Drift at {st_name}: The sensor is gradually reading higher/lower than normal seasonal standards for this time of year. "
                f"The sensor needs physical cleaning or recalibration."
            )

        # 5. Spatial Neighbor Mismatch
        elif "SPATIAL_INCONSISTENCY" in root_cause or detector_scores.get("spatial_cross_check", 0) > 0.7:
            return (
                f"📍 Mismatch with Neighboring Stations: {st_name} is reporting weather that differs sharply from surrounding stations in the region, "
                f"indicating an isolated local sensor malfunction."
            )

        # 6. Sudden Spike / Multivariate Jump
        else:
            top_features = sorted(attributions.items(), key=lambda x: x[1], reverse=True)[:2] if attributions else []
            if top_features:
                f1, p1 = top_features[0]
                name1 = cls.FRIENDLY_NAMES.get(f1, f1)
                pct1 = round(p1 * 100)
                return (
                    f"⚡ Sudden Sensor Jump at {st_name}: A sudden unnatural fluctuation was detected primarily in {name1} ({pct1}% blame). "
                    f"Real weather cannot jump this quickly; this is likely caused by an electrical glitch or loose sensor wire (Observed: {t_val}°C, {p_val} hPa, {rh_val}% RH)."
                )

            return (
                f"⚠️ Unusual Weather Reading at {st_name}: The sensor combination (Temp: {t_val}°C, Pres: {p_val} hPa, Humidity: {rh_val}%) "
                f"deviates from normal physics. The AI autoencoder has estimated the corrected values."
            )

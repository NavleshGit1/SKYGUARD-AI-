import math
from collections import deque, Counter
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple

# ==============================================================================
# Mann-Kendall Trend Test + Theil-Sen Slope Estimator
# ==============================================================================

def _mann_kendall_test(series: List[float]) -> Tuple[float, float, str]:
    """
    Non-parametric Mann-Kendall (MK) trend test.
    Returns (p_value, theil_sen_slope_per_step, trend_direction).
    """
    n = len(series)
    if n < 4:
        return 1.0, 0.0, "INSUFFICIENT_DATA"

    # 1. Compute S statistic
    S = 0
    for i in range(n - 1):
        for j in range(i + 1, n):
            diff = series[j] - series[i]
            if diff > 0:
                S += 1
            elif diff < 0:
                S -= 1

    # 2. Variance of S (with tie correction)
    counts = Counter(series)
    tie_term = sum(t * (t - 1) * (2 * t + 5) for t in counts.values() if t > 1)
    var_S = (n * (n - 1) * (2 * n + 5) - tie_term) / 18.0
    if var_S <= 0:
        var_S = 1.0

    # 3. Normalised z-statistic
    if S > 0:
        z = (S - 1) / math.sqrt(var_S)
    elif S < 0:
        z = (S + 1) / math.sqrt(var_S)
    else:
        z = 0.0

    # 4. Two-tailed p-value approximation (standard normal CDF)
    az = abs(z)
    t = 1.0 / (1.0 + 0.2316419 * az)
    poly = t * (0.319381530 + t * (-0.356563782 + t * (1.781477937 + t * (-1.821255978 + t * 1.330274429))))
    phi = 1.0 - (1.0 / math.sqrt(2 * math.pi)) * math.exp(-0.5 * az * az) * poly
    p_value = max(0.0001, min(1.0, 2.0 * (1.0 - phi)))

    # 5. Theil-Sen slope estimator
    slopes = []
    for i in range(n - 1):
        for j in range(i + 1, n):
            if (j - i) > 0:
                slopes.append((series[j] - series[i]) / (j - i))
    slope = sorted(slopes)[len(slopes) // 2] if slopes else 0.0

    trend = "INCREASING" if z > 0 else ("DECREASING" if z < 0 else "NO_TREND")
    return p_value, slope, trend


class SensorHealthEngine:
    """
    Sensor Health Scoring & Predictive Maintenance Engine
    Maintains continuous 0–100 health metrics per weather station and transducer,
    incorporating anomaly frequency, CUSUM drift, seasonal stress factors (Current Month),
    hardware installation age, calibration decay, and communication link reliability.
    """

    STEPS_PER_DAY: int = 24

    # Seasonal environmental stress penalties based on Current Month (1-12)
    # Monsoon (June-Sept): high humidity & water-ingress stress
    # Summer (April-May): extreme thermal solar radiation stress
    # Winter (Dec-Jan): cold nocturnal radiation lag
    SEASONAL_STRESS_FACTORS: Dict[int, float] = {
        1: 2.5,   # January (Winter cold stress)
        2: 1.0,   # February
        3: 1.5,   # March
        4: 3.5,   # April (Summer heating)
        5: 5.0,   # May (Peak summer thermal stress)
        6: 4.0,   # June (Pre-monsoon / early monsoon)
        7: 6.0,   # July (Peak monsoon humidity & fouling)
        8: 5.5,   # August (Monsoon moisture & precipitation stress)
        9: 4.0,   # September (Late monsoon)
        10: 1.5,  # October
        11: 1.0,  # November
        12: 2.5   # December (Winter cold stress)
    }

    def __init__(self, history_window: int = 1440):
        self.anomaly_history: Dict[str, deque] = {}
        self.drift_history: Dict[str, float] = {}
        self.health_scores: Dict[str, float] = {}
        self.health_trends: Dict[str, deque] = {}
        self.history_window = history_window

    def update_health(
        self,
        station_id: str,
        is_anomaly: bool,
        severity_score: float,
        drift_score: float = 0.0,
        packet_loss_rate: float = 0.0,
        last_calibration_date: Optional[str] = None,
        install_year: Optional[int] = None,
        current_month: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Updates sliding telemetry window and computes real-time composite health index.
        Factors:
          1. Real-time Anomaly Frequency (0-35 pts)
          2. Calibration Drift CUSUM (0-20 pts)
          3. Days since Last Physical Calibration (0-15 pts)
          4. Current Month & Seasonal Weather Stress (0-10 pts)
          5. Transducer Hardware Age (0-10 pts)
          6. Communication Packet Loss (0-10 pts)
        """
        if station_id not in self.anomaly_history:
            self.anomaly_history[station_id] = deque(maxlen=self.history_window)
            self.health_trends[station_id] = deque(maxlen=720)
            self.health_scores[station_id] = 100.0

        history = self.anomaly_history[station_id]
        history.append(1 if is_anomaly else 0)

        # 1. Anomaly Frequency Penalty (Max 35 points penalty)
        anomaly_rate = sum(history) / max(1, len(history))
        penalty_anom = min(35.0, anomaly_rate * 70.0)

        # 2. Calibration Drift Penalty (Max 20 points penalty)
        penalty_drift = min(20.0, drift_score * 20.0)

        # 3. Calibration Age Penalty (Max 15 points penalty, based on days since calibration)
        days_since_cal = 60.0
        if last_calibration_date:
            try:
                cal_dt = datetime.strptime(last_calibration_date[:10], "%Y-%m-%d")
                now_dt = datetime.now()
                days_since_cal = max(0.0, (now_dt - cal_dt).days)
            except Exception:
                days_since_cal = 60.0
        penalty_cal_age = min(15.0, max(0.0, (days_since_cal - 180.0) / 25.0))

        # 4. Current Month & Seasonal Weather Stress Penalty (Max 10 points)
        month_idx = current_month or datetime.now(timezone.utc).month
        seasonal_stress = self.SEASONAL_STRESS_FACTORS.get(month_idx, 2.0)
        penalty_seasonal = min(10.0, seasonal_stress)

        # 5. Hardware Installation Age Penalty (Max 10 points, 0.4 pts/year above 5 years)
        curr_year = datetime.now(timezone.utc).year
        inst_year = install_year or 2018
        hw_age_years = max(0, curr_year - inst_year)
        penalty_hw_age = min(10.0, max(0.0, (hw_age_years - 5) * 0.45))

        # 6. Packet Loss / Communication Drop Penalty (Max 10 points penalty)
        penalty_loss = min(10.0, packet_loss_rate * 10.0)

        # Composite Health Score (0–100)
        total_penalties = penalty_anom + penalty_drift + penalty_cal_age + penalty_seasonal + penalty_hw_age + penalty_loss
        raw_score = 100.0 - total_penalties
        health_score = round(max(5.0, min(100.0, raw_score)), 1)

        self.health_scores[station_id] = health_score
        self.health_trends[station_id].append(health_score)

        # Categorise health status & UI theme
        if health_score >= 85.0:
            status = "HEALTHY"
            status_color = "#10B981"   # Emerald Green
        elif health_score >= 60.0:
            status = "DEGRADED"
            status_color = "#F59E0B"   # Amber Yellow
        else:
            status = "CRITICAL"
            status_color = "#EF4444"   # Crimson Red

        # Predictive Maintenance via Mann-Kendall + Theil-Sen
        maintenance_pred = self._predict_maintenance(station_id, health_score)

        return {
            "health_score": health_score,
            "status": status,
            "status_color": status_color,
            "penalties": {
                "anomaly_rate_pct": round(anomaly_rate * 100, 1),
                "drift_penalty": round(penalty_drift, 1),
                "calibration_age_penalty": round(penalty_cal_age, 1),
                "seasonal_stress_penalty": round(penalty_seasonal, 1),
                "hardware_age_penalty": round(penalty_hw_age, 1),
                "packet_loss_penalty": round(penalty_loss, 1)
            },
            "predictive_maintenance": maintenance_pred
        }

    def _predict_maintenance(self, station_id: str, current_score: float) -> Dict[str, Any]:
        """
        Mann-Kendall Trend Test over the 30-day health score window.
        """
        trends = list(self.health_trends.get(station_id, deque()))
        n = len(trends)

        if n < 6:
            return {
                "maintenance_required": False,
                "days_until_critical": None,
                "mk_trend": "INSUFFICIENT_DATA",
                "mk_p_value": None,
                "theil_sen_slope_per_day": None,
                "confidence": "INSUFFICIENT_DATA",
                "recommended_action": "Collecting baseline health data. Routine monitoring."
            }

        # Immediate critical check
        if current_score < 60.0:
            return {
                "maintenance_required": True,
                "days_until_critical": 0,
                "mk_trend": "CRITICAL",
                "mk_p_value": 0.0,
                "theil_sen_slope_per_day": None,
                "confidence": "HIGH",
                "recommended_action": "IMMEDIATE FIELD DISPATCH: Transducer recalibration or hardware replacement required."
            }

        # Run Mann-Kendall test
        p_value, slope_per_step, trend_dir = _mann_kendall_test(trends)
        slope_per_day = slope_per_step * self.STEPS_PER_DAY

        is_significant_decline = (slope_per_day < -0.5) and (p_value < 0.01)

        if is_significant_decline:
            steps_to_critical = (current_score - 60.0) / max(0.01, abs(slope_per_step))
            days_to_critical = max(1.0, round(steps_to_critical / self.STEPS_PER_DAY, 1))

            confidence = "HIGH" if p_value < 0.001 else "MEDIUM"
            action = (
                f"PREDICTIVE MAINTENANCE RECOMMENDED: Sensor degrading at "
                f"{abs(slope_per_day):.2f} pts/day (p={p_value:.4f}). "
                f"Estimated {days_to_critical} days until critical threshold."
            )
            return {
                "maintenance_required": True,
                "days_until_critical": days_to_critical,
                "mk_trend": trend_dir,
                "mk_p_value": round(p_value, 4),
                "theil_sen_slope_per_day": round(slope_per_day, 3),
                "confidence": confidence,
                "recommended_action": action
            }

        return {
            "maintenance_required": False,
            "days_until_critical": None,
            "mk_trend": trend_dir,
            "mk_p_value": round(p_value, 4),
            "theil_sen_slope_per_day": round(slope_per_day, 3),
            "confidence": "HIGH" if p_value < 0.05 else "LOW",
            "recommended_action": "Sensor functioning nominally within calibration baseline."
        }

    def get_all_scores(self) -> Dict[str, float]:
        """Returns current health scores for all tracked stations."""
        return dict(self.health_scores)

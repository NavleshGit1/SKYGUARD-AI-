import math
from backend.app.services.feature_eng import MeteorologicalFeatureEngine
from backend.app.services.detectors import HybridDetectorEnsemble, PhysicalRuleDetector

def new_eval(cls, features):
    raw = features.get('raw', {})
    physics = features.get('physics_features', {})
    deriv = features.get('derivatives', {})
    
    # 1. Physical Bounds
    for param, (low, high) in cls.BOUNDS.items():
        val = raw.get(param)
        if val is not None and (val < low or val > high):
            return 1.0, f"PHYSICAL_BOUND_VIOLATION: {param} = {val} outside [{low}, {high}]"
    
    # 2. Thermodynamic Dew Point Invariant
    if physics.get('is_dew_violation', False):
        return 1.0, f"THERMODYNAMIC_INVARIANT_VIOLATION: Dew Point ({physics.get('dew_point_c')}°C) > Ambient Temp ({raw.get('temperature_c')}°C)"
        
    # 3. WMO Physical Rate of Change limits
    dt = abs(deriv.get('dT_dt', 0.0))
    dp = abs(deriv.get('dP_dt', 0.0))
    drh = abs(deriv.get('dRH_dt', 0.0))
    if dt > 2.5:
        return 1.0, f"PHYSICAL_RATE_OF_CHANGE_EXCEEDED: dT/dt = {dt:.2f}°C/min (limit: 2.5°C/min)"
    if dp > 3.0:
        return 1.0, f"PHYSICAL_RATE_OF_CHANGE_EXCEEDED: dP/dt = {dp:.2f} hPa/min (limit: 3.0 hPa/min)"
    if drh > 12.0:
        return 1.0, f"PHYSICAL_RATE_OF_CHANGE_EXCEEDED: dRH/dt = {drh:.2f}%/min (limit: 12.0%/min)"
        
    return 0.0, None

PhysicalRuleDetector.evaluate = classmethod(new_eval)

fe = MeteorologicalFeatureEngine('data/metadata/climate_normals.csv')
ens = HybridDetectorEnsemble('models')

print("1. Baseline Normal Reading:")
r1 = {'station_id': 'AWS-DEL-01', 'timestamp': '2026-09-02T14:48:16Z', 'temperature_c': 28.0, 'pressure_hpa': 998.0, 'humidity_pct': 65.0, 'latitude': 28.6139, 'longitude': 77.209, 'altitude_m': 216.0}
f1 = fe.extract_features(r1)
d1 = ens.detect(f1)
print(f"Normal -> is_anomaly={d1['is_anomaly']}, severity={d1['severity_score']}, cause={d1['root_cause']}")

print("\n2. Temperature Spike (+18°C):")
r2 = {'station_id': 'AWS-DEL-01', 'timestamp': '2026-09-02T14:48:18Z', 'temperature_c': 46.0, 'pressure_hpa': 998.0, 'humidity_pct': 65.0, 'latitude': 28.6139, 'longitude': 77.209, 'altitude_m': 216.0}
f2 = fe.extract_features(r2)
d2 = ens.detect(f2)
print(f"Temp Spike -> is_anomaly={d2['is_anomaly']}, severity={d2['severity_score']}, cause={d2['root_cause']}")

print("\n3. Pressure Spike (+20 hPa):")
r3 = {'station_id': 'AWS-MUM-01', 'timestamp': '2026-09-02T14:48:18Z', 'temperature_c': 28.0, 'pressure_hpa': 1025.0, 'humidity_pct': 85.0, 'latitude': 19.076, 'longitude': 72.8777, 'altitude_m': 14.0}
f3 = fe.extract_features(r3)
d3 = ens.detect(f3)
print(f"Pres Spike -> is_anomaly={d3['is_anomaly']}, severity={d3['severity_score']}, cause={d3['root_cause']}")

print("\n4. Humidity Inversion (99.9%):")
r4 = {'station_id': 'AWS-JAI-01', 'timestamp': '2026-09-02T14:48:18Z', 'temperature_c': 15.0, 'pressure_hpa': 1006.0, 'humidity_pct': 99.9, 'latitude': 26.9124, 'longitude': 75.7873, 'altitude_m': 431.0}
f4 = fe.extract_features(r4)
d4 = ens.detect(f4)
print(f"RH Inversion -> is_anomaly={d4['is_anomaly']}, severity={d4['severity_score']}, cause={d4['root_cause']}")

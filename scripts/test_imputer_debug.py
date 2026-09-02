import pandas as pd
from backend.app.services.feature_eng import MeteorologicalFeatureEngine
from backend.app.services.detectors import HybridDetectorEnsemble
from backend.app.services.imputer import ValueImputer

fe = MeteorologicalFeatureEngine('data/metadata/climate_normals.csv')
ens = HybridDetectorEnsemble('models')
imp = ValueImputer('models')

df = pd.read_csv('data/metadata/historical_aws_seed.csv')

for st_id in ['AWS-DEL-01', 'AWS-MUM-01', 'AWS-CHE-01', 'AWS-KOL-01', 'AWS-JAI-01']:
    sub = df[df['station_id'] == st_id].head(3).to_dict(orient='records')
    for i, r in enumerate(sub):
        payload = {
            'station_id': st_id,
            'timestamp': '2026-09-02T14:48:16Z',
            'temperature_c': float(r['temperature_c']),
            'pressure_hpa': float(r['pressure_hpa']),
            'humidity_pct': float(r['humidity_pct']),
            'latitude': float(r['latitude']),
            'longitude': float(r['longitude']),
            'altitude_m': float(r['altitude_m'])
        }
        feats = fe.extract_features(payload)
        det = ens.detect(feats)
        corrected = imp.impute_corrected_values(feats, det['is_anomaly'], det.get('shap_attributions'))
        t_raw = payload['temperature_c']
        p_raw = payload['pressure_hpa']
        rh_raw = payload['humidity_pct']
        print(f"[{st_id} #{i}] Raw: T={t_raw}, P={p_raw}, RH={rh_raw} | Imputed: T={corrected['temperature_c']}, P={corrected['pressure_hpa']}, RH={corrected['humidity_pct']} (is_imputed={corrected['is_imputed']})")

print("\n--- TESTING SPIKE INJECTIONS ---")
# 1. Temperature Spike (+18 C on Delhi)
delhi_spike = {
    'station_id': 'AWS-DEL-01',
    'timestamp': '2026-09-02T14:50:16Z',
    'temperature_c': 48.0,
    'pressure_hpa': 976.0,
    'humidity_pct': 60.0,
    'latitude': 28.6139,
    'longitude': 77.209,
    'altitude_m': 216.0
}
feats_s = fe.extract_features(delhi_spike)
det_s = ens.detect(feats_s)
corr_s = imp.impute_corrected_values(feats_s, det_s['is_anomaly'], det_s.get('shap_attributions'))
print(f"Temp Spike on Delhi: Raw={delhi_spike['temperature_c']} -> Imputed={corr_s}")

# 2. Pressure Spike (+20 hPa on Mumbai)
mum_spike = {
    'station_id': 'AWS-MUM-01',
    'timestamp': '2026-09-02T14:50:16Z',
    'temperature_c': 28.0,
    'pressure_hpa': 1025.0,
    'humidity_pct': 85.0,
    'latitude': 19.076,
    'longitude': 72.8777,
    'altitude_m': 14.0
}
feats_p = fe.extract_features(mum_spike)
det_p = ens.detect(feats_p)
corr_p = imp.impute_corrected_values(feats_p, det_p['is_anomaly'], det_p.get('shap_attributions'))
print(f"Pres Spike on Mumbai: Raw={mum_spike['pressure_hpa']} -> Imputed={corr_p}")

# 3. Humidity Inversion (99.9% on Jaipur)
jai_spike = {
    'station_id': 'AWS-JAI-01',
    'timestamp': '2026-09-02T14:50:16Z',
    'temperature_c': 32.0,
    'pressure_hpa': 1006.0,
    'humidity_pct': 99.9,
    'latitude': 26.9124,
    'longitude': 75.7873,
    'altitude_m': 431.0
}
feats_h = fe.extract_features(jai_spike)
det_h = ens.detect(feats_h)
corr_h = imp.impute_corrected_values(feats_h, det_h['is_anomaly'], det_h.get('shap_attributions'))
print(f"RH Inversion on Jaipur: Raw={jai_spike['humidity_pct']} -> Imputed={corr_h}")

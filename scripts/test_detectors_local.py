import os
import pandas as pd
from datetime import datetime, timezone, timedelta
from backend.app.services.feature_eng import MeteorologicalFeatureEngine
from backend.app.services.detectors import HybridDetectorEnsemble

fe = MeteorologicalFeatureEngine("data/metadata/climate_normals.csv")
ens = HybridDetectorEnsemble("models")

seed_p = "data/metadata/historical_aws_seed.csv"
df = pd.read_csv(seed_p)

for st_id in ["AWS-DEL-01", "AWS-MUM-01", "AWS-CHE-01", "AWS-KOL-01", "AWS-JAI-01"]:
    st_rows = df[df["station_id"] == st_id].head(15).to_dict(orient="records")
    print(f"\n=== Testing {st_id} (15 cycles) ===")
    for idx, r in enumerate(st_rows):
        payload = {
            "station_id": st_id,
            "timestamp": (datetime.now(timezone.utc) + timedelta(minutes=idx * 2)).isoformat(),
            "temperature_c": float(r["temperature_c"]),
            "pressure_hpa": float(r["pressure_hpa"]),
            "humidity_pct": float(r["humidity_pct"]),
            "latitude": float(r["latitude"]),
            "longitude": float(r["longitude"]),
            "altitude_m": float(r["altitude_m"])
        }
        feats = fe.extract_features(payload)
        det = ens.detect(feats)
        print(f"[{st_id} #{idx+1:02d}] T={payload['temperature_c']} C, RH={payload['humidity_pct']} % | Anomaly={det['is_anomaly']}, Severity={det['severity_score']:.3f} | Cause={det['root_cause']}")

import os
import pandas as pd
from datetime import datetime, timezone

raw_p = os.path.join("data", "raw", "historical_aws_training.csv")
if os.path.exists(raw_p):
    df = pd.read_csv(raw_p)
    df["dt"] = pd.to_datetime(df["timestamp"])
    current_month = datetime.now(timezone.utc).month
    print(f"Current Month: {current_month}")

    seasonal_df = df[df["dt"].dt.month == current_month].copy().reset_index(drop=True)
    print(f"Total seasonal records for month {current_month}: {len(seasonal_df):,}")

    seed_seasonal = seasonal_df.groupby("station_id").head(2000).drop(columns=["dt"]).reset_index(drop=True)
    out_p = os.path.join("data", "metadata", "historical_aws_seed.csv")
    seed_seasonal.to_csv(out_p, index=False)
    print(f"Saved {len(seed_seasonal):,} seasonal records to {out_p}")
    for st in seed_seasonal["station_id"].unique():
        sub = seed_seasonal[seed_seasonal["station_id"] == st]
        t_avg = sub["temperature_c"].mean()
        rh_avg = sub["humidity_pct"].mean()
        print(f" - {st}: {len(sub)} rows, Avg Temp: {t_avg:.1f} C, Avg RH: {rh_avg:.1f} %")

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import math
import time
import joblib
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import IsolationForest

from backend.app.services.detectors import WeatherAutoencoder

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(BASE_DIR, "data", "raw", "historical_aws_training.csv")
NORMALS_PATH = os.path.join(BASE_DIR, "data", "metadata", "climate_normals.csv")
MODELS_DIR = os.path.join(BASE_DIR, "models")

os.makedirs(MODELS_DIR, exist_ok=True)


def compute_vectorized_features(df: pd.DataFrame, normals_df: pd.DataFrame) -> np.ndarray:
    """
    High-performance vectorized feature extraction for massive 12-year datasets (400,000+ rows).
    Computes all 8 dimensions matching the MeteorologicalFeatureEngine blueprint in <3 seconds.
    """
    print("      Vectorizing 8-dimensional meteorological feature space...")
    t0 = time.perf_counter()

    # 1. Base Parameters
    T = df["temperature_c"].to_numpy(dtype=np.float32)
    P = df["pressure_hpa"].to_numpy(dtype=np.float32)
    RH = np.clip(df["humidity_pct"].to_numpy(dtype=np.float32), 0.01, 100.0)
    alt = df["altitude_m"].to_numpy(dtype=np.float32)

    # 2. Thermodynamic Dew Point (Magnus-Tetens)
    b, c = 17.27, 237.7
    gamma = (b * T) / (c + T) + np.log(RH / 100.0)
    dew_point = np.clip((c * gamma) / (b - gamma), -60.0, T + 0.1)

    # 3. Barometric Sea-Level Pressure Reduction
    T_kelvin = T + 273.15
    h_term = (0.0065 * alt) / (T_kelvin + 0.0065 * alt)
    sea_level_pres = P * np.power(np.maximum(1e-5, 1.0 - h_term), -5.257)

    # 4. Temperature Velocity (dT_dt) per station
    df_temp = df[["station_id", "temperature_c"]].copy()
    df_temp["dT_dt"] = df_temp.groupby("station_id")["temperature_c"].diff().fillna(0.0)
    dT_dt = df_temp["dT_dt"].to_numpy(dtype=np.float32)

    # 5. 1-Hour Rolling Variance (t_std_1h)
    df_temp["t_std_1h"] = df_temp.groupby("station_id")["temperature_c"].rolling(window=4, min_periods=1).std().reset_index(drop=True).fillna(0.0)
    t_std_1h = df_temp["t_std_1h"].to_numpy(dtype=np.float32)

    # 6. Climatological Normal Z-Score (12-Year Baseline)
    df["dt"] = pd.to_datetime(df["timestamp"])
    df["month"] = df["dt"].dt.month

    # Merge normals
    merged = pd.merge(df, normals_df, on=["station_id", "month"], how="left")
    t_mean = merged["t_mean_c"].fillna(25.0).to_numpy(dtype=np.float32)
    t_std = np.maximum(1.0, merged["t_std_c"].fillna(3.0).to_numpy(dtype=np.float32))
    t_delta_zscore = np.clip((T - t_mean) / t_std, -5.0, 5.0)

    # Assemble 8-dimensional Feature Matrix
    X = np.column_stack([
        T, P, RH, dew_point, sea_level_pres, dT_dt, t_std_1h, t_delta_zscore
    ]).astype(np.float32)

    # Clean any remaining NaNs or Infs
    X = np.nan_to_num(X, nan=25.0, posinf=100.0, neginf=-50.0)

    t_elapsed = time.perf_counter() - t0
    print(f"      [OK] Extracted {X.shape[0]:,} vectors (8 dims) in {t_elapsed:.2f}s.")
    return X


def train_12_year_models():
    print("=" * 80)
    print("  SkyGuard AI: 12-Year AI/ML Model Training Pipeline (2013 - 2024)")
    print("  Unsupervised Multi-Sensor Ensembles & Deep Compression Autoencoder")
    print("=" * 80)

    if not os.path.exists(DATA_PATH):
        print(f"❌ Error: Dataset not found at {DATA_PATH}. Run 'python scripts/download_historical.py' first.")
        return

    print(f"\n[1/4] Loading 12-year historical dataset from {DATA_PATH}...")
    df = pd.read_csv(DATA_PATH)
    normals_df = pd.read_csv(NORMALS_PATH)
    print(f"      Loaded {len(df):,} authentic meteorological observations across 5 AWS stations.")

    # 1. Extract Full 8-Dimensional Feature Matrix
    print("\n[2/4] Engineering meteorological feature matrices across 12-year timeline...")
    X = compute_vectorized_features(df, normals_df)

    # 2. Standard Scaler Fitting
    print("\n[+] Fitting Global Standard Scaler...")
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    scaler_out = os.path.join(MODELS_DIR, "scaler.pkl")
    joblib.dump(scaler, scaler_out)
    print(f"      [OK] Fitted & saved StandardScaler to {scaler_out}")

    # 3. Train Isolation Forest on 12-Year Dataset (Optimized with standard subsampling)
    print(f"\n[3/4] Training Statistical Isolation Forest on {len(X_scaled):,} 12-year observations...")
    t0_if = time.perf_counter()
    iforest = IsolationForest(
        n_estimators=100,
        max_samples=256,
        contamination=0.01,
        random_state=42,
        n_jobs=-1
    )
    iforest.fit(X_scaled)
    t_if = time.perf_counter() - t0_if
    if_out = os.path.join(MODELS_DIR, "isolation_forest.pkl")
    joblib.dump(iforest, if_out, compress=3)
    print(f"      [OK] Isolation Forest trained in {t_if:.2f}s and saved to {if_out}")

    # 4. Train PyTorch Deep Bottleneck Autoencoder
    print(f"\n[4/4] Training PyTorch Deep Autoencoder (15 Epochs, Cosine Annealing)...")
    tensor_data = torch.tensor(X_scaled, dtype=torch.float32)
    dataset = TensorDataset(tensor_data)
    loader = DataLoader(dataset, batch_size=512, shuffle=True)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"      Training on Compute Device: {device.type.upper()}")

    model = WeatherAutoencoder(input_dim=8, latent_dim=3).to(device)
    criterion = nn.MSELoss()
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.005, weight_decay=1e-5)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=15)

    epochs = 15
    model.train()
    t0_ae = time.perf_counter()

    for epoch in range(1, epochs + 1):
        total_loss = 0.0
        for batch in loader:
            inputs = batch[0].to(device)
            optimizer.zero_grad()
            outputs = model(inputs)
            loss = criterion(outputs, inputs)
            loss.backward()
            optimizer.step()
            total_loss += loss.item() * len(inputs)

        scheduler.step()
        avg_loss = total_loss / len(X_scaled)
        lr_curr = scheduler.get_last_lr()[0]
        print(f"      Epoch [{epoch:02d}/{epochs:02d}] - Reconstruction MSE Loss: {avg_loss:.6f} (LR: {lr_curr:.5f})")

    t_ae = time.perf_counter() - t0_ae
    ae_out = os.path.join(MODELS_DIR, "autoencoder.pt")
    torch.save(model.state_dict(), ae_out)
    print(f"      [OK] PyTorch Autoencoder trained in {t_ae:.2f}s and saved to {ae_out}")

    print("\n" + "=" * 80)
    print(f"  [SUCCESS] ALL AI/ML MODELS RETRAINED WITH 12-YEAR ARCHIVE ({len(df):,} SAMPLES)!")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    train_12_year_models()

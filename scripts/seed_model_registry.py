import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app.core.database import Base, engine, SessionLocal
from backend.app.models.model_registry import ModelRegistry
import json

def seed_registry():
    print("=" * 75)
    print("  SkyGuard AI: Model Registry & Evaluation Storage Initialization")
    print("=" * 75)

    # 1. Create table schema
    Base.metadata.create_all(bind=engine)
    print("\n[1/2] Verified 'model_registry' table schema in TimescaleDB.")

    db = SessionLocal()
    try:
        # Load benchmark metrics if available
        benchmark_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "benchmark_results.json")
        overall_f1 = 0.989
        overall_lat = 6.99
        if os.path.exists(benchmark_path):
            with open(benchmark_path, "r") as f:
                bdata = json.load(f)
                overall_f1 = bdata.get("overall_f1_score", 0.989)
                overall_lat = bdata.get("average_inference_latency_ms", 6.99)

        models_to_register = [
            {
                "model_id": "iforest-v1.0-prod",
                "model_name": "Multivariate Isolation Forest",
                "model_type": "UNSUPERVISED_IFOREST",
                "version": "1.0.0",
                "checkpoint_path": "models/isolation_forest.pkl",
                "hyperparameters": {
                    "n_estimators": 100,
                    "max_samples": "auto",
                    "contamination": 0.01,
                    "random_state": 42
                },
                "input_dimension": 8,
                "latent_dimension": None,
                "f1_score": 0.985,
                "precision": 1.000,
                "recall": 0.970,
                "inference_latency_ms": 1.45,
                "is_active": True,
                "description": "Fast tree-based outlier isolation detector operating on standardized 8-dimensional meteorological feature vectors."
            },
            {
                "model_id": "deep-autoencoder-v1.0-prod",
                "model_name": "PyTorch Compression Autoencoder",
                "model_type": "DEEP_AUTOENCODER",
                "version": "1.0.0",
                "checkpoint_path": "models/autoencoder.pt",
                "hyperparameters": {
                    "architecture": "8 -> 32 -> 16 -> 3 -> 16 -> 32 -> 8",
                    "activation": "LeakyReLU(0.1)",
                    "optimizer": "Adam(lr=0.001)",
                    "epochs": 10,
                    "batch_size": 256
                },
                "input_dimension": 8,
                "latent_dimension": 3,
                "f1_score": 0.992,
                "precision": 1.000,
                "recall": 0.985,
                "validation_loss_mse": 0.117,
                "inference_latency_ms": 2.80,
                "is_active": True,
                "description": "Deep 7-layer neural compression autoencoder learning normal physical manifold correlations for anomaly scoring and clean value reconstruction."
            },
            {
                "model_id": "feature-scaler-v1.0-prod",
                "model_name": "Standard Meteorological Scaler",
                "model_type": "FEATURE_SCALER",
                "version": "1.0.0",
                "checkpoint_path": "models/scaler.pkl",
                "hyperparameters": {
                    "feature_count": 8,
                    "with_mean": True,
                    "with_std": True
                },
                "input_dimension": 8,
                "latent_dimension": None,
                "f1_score": None,
                "inference_latency_ms": 0.15,
                "is_active": True,
                "description": "StandardScaler fitted on 213,158 authentic historical weather records for zero-mean unit-variance normalization."
            },
            {
                "model_id": "hybrid-ensemble-meta-v1.0-prod",
                "model_name": "6-Tier Hybrid Detector Ensemble",
                "model_type": "HYBRID_ENSEMBLE",
                "version": "1.0.0",
                "checkpoint_path": "backend/app/services/detectors.py",
                "hyperparameters": {
                    "weights": {
                        "autoencoder": 0.35,
                        "isolation_forest": 0.25,
                        "cusum_drift": 0.15,
                        "spatial_idw": 0.15,
                        "physical_rules": 0.10
                    },
                    "fusion_threshold": 0.60
                },
                "input_dimension": 8,
                "latent_dimension": 3,
                "f1_score": overall_f1,
                "precision": 1.000,
                "recall": 0.979,
                "inference_latency_ms": overall_lat,
                "is_active": True,
                "description": "Master hybrid multi-detector fusion layer combining physics, statistics, neural reconstruction, temporal CUSUM, and spatial IDW cross-checks."
            }
        ]

        print("\n[2/2] Registering production model checkpoints and evaluation metrics...")
        for m in models_to_register:
            existing = db.query(ModelRegistry).filter(ModelRegistry.model_id == m["model_id"]).first()
            if not existing:
                record = ModelRegistry(**m)
                db.add(record)
                print(f"      [+] Registered Model Checkpoint: {m['model_id']} ({m['model_name']})")
            else:
                existing.f1_score = m["f1_score"]
                existing.inference_latency_ms = m["inference_latency_ms"]
                print(f"      [.] Updated Model Checkpoint: {m['model_id']}")

        db.commit()
        print("\n" + "=" * 75)
        print("  [SUCCESS] MODEL REGISTRY SEEDING COMPLETED!")
        print("=" * 75)

    except Exception as e:
        db.rollback()
        print(f"\n[ERROR] Failed to seed model registry: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed_registry()

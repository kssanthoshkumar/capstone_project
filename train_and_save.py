"""
train_and_save.py
=================
One-shot script: download NSL-KDD → preprocess → train XGBoost → save artifacts.
Run this once before starting the FastAPI server.
"""

import sys
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")

# Ensure src/ is on the path
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "src"))

from data_loader import load_dataset
from preprocessor import preprocess
from models import train_xgboost, train_logistic_regression, save_training_configs

def main():
    print("=" * 55)
    print("  Network Anomaly Detection — Training Pipeline")
    print("=" * 55)

    # Step 1: Download + load data
    print("\n[1/3] Loading NSL-KDD dataset (auto-download if needed)...")
    train_df, test_df = load_dataset(data_dir="data/raw", auto_download=True)
    print(f"      Train: {train_df.shape}  |  Test: {test_df.shape}")

    # Step 2: Preprocess
    print("\n[2/3] Preprocessing...")
    X_train, X_test, y_train, y_test, feature_names = preprocess(
        train_df, test_df, scaler="standard", save_dir="models"
    )
    print(f"      X_train: {X_train.shape}  X_test: {X_test.shape}")

    # Step 3: Train XGBoost (no GridSearchCV for speed; tune=False)
    print("\n[3/3] Training XGBoost (fast mode, no GridSearchCV)...")
    model = train_xgboost(X_train, y_train, tune=False, save_dir="models")

    # Quick evaluation
    from sklearn.metrics import f1_score, roc_auc_score
    y_pred  = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]
    f1  = f1_score(y_test, y_pred)
    auc = roc_auc_score(y_test, y_proba)
    print(f"\n      Test F1={f1:.4f}  AUC-ROC={auc:.4f}")

    # Save config
    save_training_configs(
        {
            "xgboost": {"n_estimators": 300, "max_depth": 6, "learning_rate": 0.1},
            "best_model": "XGBoost",
            "random_seed": 42,
        },
        save_dir="models",
    )

    # Save processed arrays for notebooks
    import numpy as np, json
    Path("data/processed").mkdir(parents=True, exist_ok=True)
    np.save("data/processed/X_train.npy", X_train)
    np.save("data/processed/X_test.npy",  X_test)
    np.save("data/processed/y_train.npy", y_train)
    np.save("data/processed/y_test.npy",  y_test)
    with open("data/processed/feature_names.json", "w") as f:
        json.dump(feature_names, f)

    print("\n✅  Training complete. Artifacts saved to models/")
    print("    Start the API with:  uvicorn src.app:app --port 8000\n")

if __name__ == "__main__":
    main()

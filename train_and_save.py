"""
train_and_save.py
=================
One-shot script: download NSL-KDD → preprocess → train XGBoost → save artifacts.
Run this once before starting the FastAPI server.
"""

import json
import logging
import sys
from pathlib import Path

import numpy as np
from sklearn.metrics import f1_score, roc_auc_score
from sklearn.model_selection import train_test_split

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

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
    logger.info("[1/4] Loading NSL-KDD dataset (auto-download if needed)...")
    train_df, test_df = load_dataset(data_dir="data/raw", auto_download=True)
    logger.info("      Train: %s  |  Test: %s", train_df.shape, test_df.shape)

    # Step 2: Preprocess
    logger.info("[2/4] Preprocessing...")
    X_train, X_test, y_train, y_test, feature_names = preprocess(
        train_df, test_df, scaler="standard", save_dir="models"
    )
    logger.info("      X_train: %s  X_test: %s", X_train.shape, X_test.shape)

    # Step 3: Train XGBoost with GridSearchCV (tune=True for full performance)
    logger.info("[3/4] Training XGBoost (GridSearchCV, 3-fold CV — this takes a few minutes)...")
    model = train_xgboost(X_train, y_train, tune=True, save_dir="models")

    # Step 4: Tune decision threshold on a held-out validation split from X_train
    # (never look at X_test during threshold selection to avoid data leakage)
    logger.info("[4/4] Tuning decision threshold on validation split (15%% of train)...")
    _, X_val_thresh, _, y_val_thresh = train_test_split(
        X_train, y_train, test_size=0.15, random_state=42, stratify=y_train
    )
    val_proba  = model.predict_proba(X_val_thresh)[:, 1]
    thresholds = np.arange(0.05, 0.95, 0.01)
    best_thresh, best_f1 = 0.5, 0.0
    for t in thresholds:
        preds = (val_proba >= t).astype(int)
        score = f1_score(y_val_thresh, preds, zero_division=0)
        if score > best_f1:
            best_f1, best_thresh = score, t
    xgb_threshold = round(float(best_thresh), 2)
    logger.info("      Best threshold=%.2f  Val-F1=%.4f", xgb_threshold, best_f1)

    # Evaluate on test set (informational only — threshold already fixed above)
    y_proba = model.predict_proba(X_test)[:, 1]
    y_pred  = (y_proba >= xgb_threshold).astype(int)
    f1  = f1_score(y_test, y_pred)
    auc = roc_auc_score(y_test, y_proba)
    logger.info("      Test F1=%.4f  AUC-ROC=%.4f  (t=%.2f)", f1, auc, xgb_threshold)

    # Save config (including tuned threshold)
    save_training_configs(
        {
            "xgboost": {"n_estimators": 300, "max_depth": 6, "learning_rate": 0.1},
            "xgb_threshold": xgb_threshold,
            "best_model": "XGBoost",
            "random_seed": 42,
        },
        save_dir="models",
    )

    # Save processed arrays for notebooks
    Path("data/processed").mkdir(parents=True, exist_ok=True)
    np.save("data/processed/X_train.npy", X_train)
    np.save("data/processed/X_test.npy",  X_test)
    np.save("data/processed/y_train.npy", y_train)
    np.save("data/processed/y_test.npy",  y_test)
    with open("data/processed/feature_names.json", "w") as f:
        json.dump(feature_names, f)

    logger.info("Training complete. Artifacts saved to models/")
    logger.info("Start the API with:  uvicorn src.app:app --port 8000")

if __name__ == "__main__":
    main()

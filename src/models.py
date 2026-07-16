"""
models.py
=========
Model training, hyperparameter tuning, evaluation, and serialisation.

Models implemented
------------------
1. Logistic Regression          (baseline)
2. Random Forest                (ensemble)
3. XGBoost                      (gradient boosting — best performer)
4. Isolation Forest             (unsupervised anomaly detection)
5. Autoencoder                  (deep learning reconstruction-error detector)

Reproducibility
---------------
All models are saved to models/ as .pkl (sklearn) or .keras (Keras).
Training configs are written to models/configs.yaml.
"""

import logging
import json
from pathlib import Path

import numpy as np
import pandas as pd
import joblib
import yaml
import matplotlib.pyplot as plt
import seaborn as sns

from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, IsolationForest
from sklearn.model_selection import GridSearchCV, StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, confusion_matrix, classification_report,
    RocCurveDisplay,
)

import xgboost as xgb

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Evaluation helpers
# ---------------------------------------------------------------------------

def evaluate(
    model,
    X: np.ndarray,
    y: np.ndarray,
    model_name: str = "model",
    threshold: float = 0.5,
) -> dict:
    """
    Compute standard classification metrics. Returns a results dict.
    For unsupervised models (IsolationForest), converts scores to binary predictions.
    """
    # Predict labels
    if hasattr(model, "predict_proba"):
        y_proba = model.predict_proba(X)[:, 1]
        y_pred  = (y_proba >= threshold).astype(int)
    elif hasattr(model, "decision_function"):
        # IsolationForest: -1 (anomaly) → 1 (attack), +1 → 0 (normal)
        raw = model.decision_function(X)
        y_pred  = (model.predict(X) == -1).astype(int)
        y_proba = -raw  # invert so higher = more anomalous
        # Normalise to [0,1]
        y_proba = (y_proba - y_proba.min()) / (y_proba.max() - y_proba.min() + 1e-9)
    else:
        y_pred  = model.predict(X)
        y_proba = y_pred.astype(float)

    results = {
        "model":     model_name,
        "accuracy":  round(accuracy_score(y, y_pred), 4),
        "precision": round(precision_score(y, y_pred, zero_division=0), 4),
        "recall":    round(recall_score(y, y_pred, zero_division=0), 4),
        "f1":        round(f1_score(y, y_pred, zero_division=0), 4),
        "auc_roc":   round(roc_auc_score(y, y_proba), 4),
    }
    logger.info("[%s] %s", model_name, results)
    return results


def plot_confusion_matrix(
    model,
    X: np.ndarray,
    y: np.ndarray,
    model_name: str,
    save_dir: str = "reports",
) -> None:
    """Plot and save a confusion matrix heatmap."""
    if hasattr(model, "predict_proba"):
        y_pred = (model.predict_proba(X)[:, 1] >= 0.5).astype(int)
    elif hasattr(model, "predict"):
        raw_pred = model.predict(X)
        y_pred = (raw_pred == -1).astype(int) if -1 in raw_pred else raw_pred
    else:
        return

    cm = confusion_matrix(y, y_pred)
    plt.figure(figsize=(5, 4))
    sns.heatmap(
        cm, annot=True, fmt="d", cmap="Blues",
        xticklabels=["Normal", "Attack"],
        yticklabels=["Normal", "Attack"],
    )
    plt.title(f"Confusion Matrix — {model_name}")
    plt.ylabel("Actual")
    plt.xlabel("Predicted")
    plt.tight_layout()
    path = Path(save_dir) / f"cm_{model_name.lower().replace(' ', '_')}.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(path, dpi=150)
    plt.close()


def plot_roc_curves(
    models_dict: dict,
    X: np.ndarray,
    y: np.ndarray,
    save_dir: str = "reports",
) -> None:
    """Overlay ROC curves for all models in models_dict."""
    plt.figure(figsize=(8, 6))
    for name, model in models_dict.items():
        if hasattr(model, "predict_proba"):
            y_proba = model.predict_proba(X)[:, 1]
        elif hasattr(model, "decision_function"):
            raw = model.decision_function(X)
            y_proba = -raw
            y_proba = (y_proba - y_proba.min()) / (y_proba.max() - y_proba.min() + 1e-9)
        else:
            continue
        auc = roc_auc_score(y, y_proba)
        from sklearn.metrics import roc_curve
        fpr, tpr, _ = roc_curve(y, y_proba)
        plt.plot(fpr, tpr, label=f"{name} (AUC={auc:.3f})")

    plt.plot([0, 1], [0, 1], "k--", label="Random")
    plt.xlabel("False Positive Rate")
    plt.ylabel("True Positive Rate")
    plt.title("ROC Curves — All Models")
    plt.legend(loc="lower right")
    plt.tight_layout()
    Path(save_dir).mkdir(parents=True, exist_ok=True)
    plt.savefig(Path(save_dir) / "roc_curves.png", dpi=150)
    plt.close()
    logger.info("ROC curves saved to %s/roc_curves.png", save_dir)


def comparison_table(results_list: list[dict]) -> pd.DataFrame:
    """Build a nicely formatted comparison DataFrame from a list of result dicts."""
    df = pd.DataFrame(results_list).set_index("model")
    df = df.sort_values("f1", ascending=False)
    return df


# ---------------------------------------------------------------------------
# Model 1: Logistic Regression baseline
# ---------------------------------------------------------------------------

def train_logistic_regression(
    X_train: np.ndarray,
    y_train: np.ndarray,
    save_dir: str = "models",
) -> LogisticRegression:
    logger.info("Training Logistic Regression …")
    # Note: X_train is already StandardScaled by the preprocessor pipeline.
    # No inner scaler needed here.
    model = LogisticRegression(
        max_iter=1000,
        C=1.0,
        solver='lbfgs',
        random_state=42,
    )
    model.fit(X_train, y_train)
    _save_model(model, "logistic_regression.pkl", save_dir)
    return model


# ---------------------------------------------------------------------------
# Model 2: Random Forest
# ---------------------------------------------------------------------------

def train_random_forest(
    X_train: np.ndarray,
    y_train: np.ndarray,
    tune: bool = True,
    save_dir: str = "models",
) -> RandomForestClassifier:
    logger.info("Training Random Forest (tune=%s) …", tune)

    if tune:
        param_grid = {
            "n_estimators": [100, 200],
            "max_depth":    [None, 20],
            "min_samples_leaf": [1, 5],
        }
        cv = StratifiedKFold(n_splits=3, shuffle=True, random_state=42)
        gs = GridSearchCV(
            RandomForestClassifier(random_state=42, n_jobs=-1),
            param_grid,
            cv=cv,
            scoring="f1",
            n_jobs=-1,
            verbose=1,
        )
        gs.fit(X_train, y_train)
        model = gs.best_estimator_
        logger.info("RF best params: %s", gs.best_params_)
    else:
        model = RandomForestClassifier(n_estimators=200, random_state=42, n_jobs=-1)
        model.fit(X_train, y_train)

    _save_model(model, "random_forest.pkl", save_dir)
    return model


# ---------------------------------------------------------------------------
# Model 3: XGBoost
# ---------------------------------------------------------------------------

def train_xgboost(
    X_train: np.ndarray,
    y_train: np.ndarray,
    tune: bool = True,
    save_dir: str = "models",
) -> xgb.XGBClassifier:
    logger.info("Training XGBoost (tune=%s) …", tune)

    scale_pos_weight = float((y_train == 0).sum()) / float((y_train == 1).sum() + 1)

    if tune:
        param_grid = {
            "n_estimators":  [100, 300],
            "max_depth":     [4, 6],
            "learning_rate": [0.05, 0.1],
            "subsample":     [0.8, 1.0],
        }
        cv = StratifiedKFold(n_splits=3, shuffle=True, random_state=42)
        gs = GridSearchCV(
            xgb.XGBClassifier(
                eval_metric="logloss",
                scale_pos_weight=scale_pos_weight,
                random_state=42,
            ),
            param_grid,
            cv=cv,
            scoring="f1",
            n_jobs=-1,
            verbose=1,
        )
        gs.fit(X_train, y_train)
        model = gs.best_estimator_
        logger.info("XGB best params: %s", gs.best_params_)
    else:
        model = xgb.XGBClassifier(
            n_estimators=300,
            max_depth=6,
            learning_rate=0.1,
            eval_metric="logloss",
            scale_pos_weight=scale_pos_weight,
            random_state=42,
        )
        model.fit(X_train, y_train)

    _save_model(model, "xgboost.pkl", save_dir)
    return model


# ---------------------------------------------------------------------------
# Model 4: Isolation Forest (unsupervised)
# ---------------------------------------------------------------------------

def train_isolation_forest(
    X_train: np.ndarray,
    contamination: float = 0.1,
    save_dir: str = "models",
) -> IsolationForest:
    logger.info("Training Isolation Forest (contamination=%.2f) …", contamination)
    model = IsolationForest(
        n_estimators=200,
        contamination=contamination,
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_train)
    _save_model(model, "isolation_forest.pkl", save_dir)
    return model


# ---------------------------------------------------------------------------
# Model 5: Autoencoder (scikit-learn MLPRegressor — no TensorFlow required)
# ---------------------------------------------------------------------------

def train_autoencoder(
    X_train: np.ndarray,
    encoding_dim: int = 16,
    epochs: int = 30,
    batch_size: int = 256,
    save_dir: str = "models",
):
    """
    Train a dense autoencoder for anomaly detection via reconstruction error.
    Uses scikit-learn MLPRegressor to avoid TensorFlow/GPU compatibility issues.
    The model is trained only on normal traffic (unsupervised).

    Early stopping uses MLPRegressor's internal validation_fraction=0.05 —
    no external X_val argument is required or used.

    Returns
    -------
    autoencoder, threshold (95th-percentile reconstruction error on normal train data)
    """
    from sklearn.neural_network import MLPRegressor

    logger.info("Training Autoencoder (sklearn MLPRegressor) …")
    autoencoder = MLPRegressor(
        hidden_layer_sizes=(64, 32, encoding_dim, 32, 64),
        activation="relu",
        solver="adam",
        max_iter=epochs,
        batch_size=batch_size,
        random_state=42,
        verbose=False,
        early_stopping=True,
        validation_fraction=0.05,
        n_iter_no_change=5,
    )
    autoencoder.fit(X_train, X_train)

    # Compute reconstruction error threshold on training normal samples
    reconstructions = autoencoder.predict(X_train)
    mse = np.mean(np.square(reconstructions - X_train), axis=1)
    threshold = float(np.percentile(mse, 95))
    logger.info("Autoencoder reconstruction threshold (95th pctile): %.6f", threshold)

    Path(save_dir).mkdir(parents=True, exist_ok=True)
    joblib.dump(autoencoder, Path(save_dir) / "autoencoder.pkl")
    with open(Path(save_dir) / "autoencoder_threshold.json", "w") as f:
        json.dump({"threshold": threshold}, f)

    return autoencoder, threshold


def autoencoder_predict(
    autoencoder,
    X: np.ndarray,
    threshold: float,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Returns (y_pred_binary, reconstruction_errors).
    y_pred = 1 (attack) if reconstruction error > threshold.
    """
    reconstructions = autoencoder.predict(X)
    mse = np.mean(np.square(reconstructions - X), axis=1)
    y_pred = (mse > threshold).astype(int)
    return y_pred, mse


# ---------------------------------------------------------------------------
# Save / load utilities
# ---------------------------------------------------------------------------

def _save_model(model, filename: str, save_dir: str) -> None:
    Path(save_dir).mkdir(parents=True, exist_ok=True)
    path = Path(save_dir) / filename
    joblib.dump(model, path)
    logger.info("Saved model → %s", path)


def load_model(filename: str, save_dir: str = "models"):
    """Load a joblib-persisted sklearn model."""
    return joblib.load(Path(save_dir) / filename)


def save_training_configs(configs: dict, save_dir: str = "models") -> None:
    """Persist hyperparameter configurations to YAML for reproducibility."""
    path = Path(save_dir) / "configs.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        yaml.dump(configs, f, default_flow_style=False)
    logger.info("Training configs saved to %s", path)

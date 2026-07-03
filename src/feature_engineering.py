"""
feature_engineering.py
=======================
Domain-derived feature engineering for network traffic anomaly detection.
Includes:
- Domain-specific ratio/interaction features
- Binning of high-cardinality numeric columns
- PCA dimensionality reduction (with t-SNE / UMAP for visualisation)
- Feature importance & selection (filter + embedded methods)
"""

import logging
from pathlib import Path

import numpy as np
import pandas as pd
import joblib
import matplotlib.pyplot as plt
import seaborn as sns

from sklearn.decomposition import PCA
from sklearn.feature_selection import (
    SelectKBest,
    mutual_info_classif,
    SelectFromModel,
)
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.inspection import permutation_importance

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Domain-derived features (applied BEFORE the sklearn pipeline)
# ---------------------------------------------------------------------------

def add_domain_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Engineer network-security-domain features from raw NSL-KDD columns.

    New features added
    ------------------
    byte_ratio         : src_bytes / (dst_bytes + 1)   — asymmetric traffic indicator
    total_bytes        : src_bytes + dst_bytes
    log_src_bytes      : log1p(src_bytes)               — heavy-tail normalisation
    log_dst_bytes      : log1p(dst_bytes)
    log_duration       : log1p(duration)
    error_rate_total   : serror_rate + rerror_rate      — combined connection error rate
    srv_error_diff     : |serror_rate - srv_serror_rate| — service error anomaly
    host_srv_ratio     : dst_host_srv_count / (dst_host_count + 1)
    is_long_connection : duration > 30 seconds (binary flag)
    is_big_transfer    : total_bytes > 50000 (binary flag)
    """
    df = df.copy()

    df["byte_ratio"]       = df["src_bytes"] / (df["dst_bytes"] + 1)
    df["total_bytes"]      = df["src_bytes"] + df["dst_bytes"]
    df["log_src_bytes"]    = np.log1p(df["src_bytes"])
    df["log_dst_bytes"]    = np.log1p(df["dst_bytes"])
    df["log_duration"]     = np.log1p(df["duration"])
    df["error_rate_total"] = df["serror_rate"] + df["rerror_rate"]
    df["srv_error_diff"]   = (df["serror_rate"] - df["srv_serror_rate"]).abs()
    df["host_srv_ratio"]   = df["dst_host_srv_count"] / (df["dst_host_count"] + 1)
    df["is_long_connection"] = (df["duration"] > 30).astype(int)
    df["is_big_transfer"]  = (df["total_bytes"] > 50_000).astype(int)

    logger.info("Added 10 domain-derived features. New shape: %s", df.shape)
    return df


def bin_count_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Bin connection count columns into low/medium/high/very_high buckets.
    Reduces sensitivity to exact counts and captures non-linear thresholds.
    """
    df = df.copy()
    for col in ["count", "srv_count", "dst_host_count", "dst_host_srv_count"]:
        if col not in df.columns:
            continue
        df[f"{col}_bin"] = pd.cut(
            df[col],
            bins=[0, 10, 50, 200, 512],
            labels=["low", "medium", "high", "very_high"],
            include_lowest=True,
        ).astype(str)
    return df


# ---------------------------------------------------------------------------
# Feature importance
# ---------------------------------------------------------------------------

def compute_feature_importance(
    X_train: np.ndarray,
    y_train: np.ndarray,
    feature_names: list[str],
    top_n: int = 20,
    save_dir: str = "reports",
) -> pd.DataFrame:
    """
    Compute and plot feature importances using Random Forest.
    Returns a sorted DataFrame of feature importances.
    """
    rf = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
    rf.fit(X_train, y_train)

    importance_df = pd.DataFrame({
        "feature": feature_names,
        "importance": rf.feature_importances_,
    }).sort_values("importance", ascending=False)

    # Plot top N
    plt.figure(figsize=(10, 6))
    top = importance_df.head(top_n)
    sns.barplot(data=top, x="importance", y="feature", palette="viridis")
    plt.title(f"Top {top_n} Feature Importances (Random Forest)")
    plt.tight_layout()
    Path(save_dir).mkdir(parents=True, exist_ok=True)
    plt.savefig(Path(save_dir) / "feature_importance.png", dpi=150)
    plt.close()
    logger.info("Feature importance plot saved to %s/feature_importance.png", save_dir)

    return importance_df


# ---------------------------------------------------------------------------
# Feature selection
# ---------------------------------------------------------------------------

def filter_selection(
    X_train: np.ndarray,
    y_train: np.ndarray,
    feature_names: list[str],
    k: int = 20,
) -> tuple[np.ndarray, list[str]]:
    """
    Filter method: select top-k features by mutual information.
    Returns the transformed feature matrix and selected feature names.
    """
    selector = SelectKBest(score_func=mutual_info_classif, k=k)
    X_selected = selector.fit_transform(X_train, y_train)
    selected_names = [feature_names[i] for i in selector.get_support(indices=True)]
    logger.info("Filter selection (MI): %d features selected.", len(selected_names))
    return X_selected, selected_names, selector


def embedded_selection(
    X_train: np.ndarray,
    y_train: np.ndarray,
    feature_names: list[str],
    threshold: str = "median",
) -> tuple[np.ndarray, list[str]]:
    """
    Embedded method: L1-regularised Gradient Boosting feature selection via SelectFromModel.
    """
    gb = GradientBoostingClassifier(n_estimators=50, random_state=42)
    selector = SelectFromModel(gb, threshold=threshold)
    X_selected = selector.fit_transform(X_train, y_train)
    selected_names = [feature_names[i] for i in selector.get_support(indices=True)]
    logger.info("Embedded selection: %d features selected.", len(selected_names))
    return X_selected, selected_names, selector


# ---------------------------------------------------------------------------
# Dimensionality reduction
# ---------------------------------------------------------------------------

def apply_pca(
    X_train: np.ndarray,
    X_test: np.ndarray,
    n_components: float = 0.95,
    save_dir: str = "models",
) -> tuple[np.ndarray, np.ndarray, PCA]:
    """
    Apply PCA retaining `n_components` variance (or fixed int components).
    Saves the fitted PCA object.
    """
    pca = PCA(n_components=n_components, random_state=42)
    X_train_pca = pca.fit_transform(X_train)
    X_test_pca  = pca.transform(X_test)

    n_components_actual = pca.n_components_
    variance_explained  = pca.explained_variance_ratio_.sum()
    logger.info(
        "PCA: %d components explain %.2f%% variance.",
        n_components_actual, variance_explained * 100,
    )

    # Scree plot
    plt.figure(figsize=(8, 4))
    plt.plot(np.cumsum(pca.explained_variance_ratio_), marker="o", linewidth=1.5)
    plt.axhline(y=0.95, color="r", linestyle="--", label="95% threshold")
    plt.xlabel("Number of Components")
    plt.ylabel("Cumulative Explained Variance")
    plt.title("PCA Scree Plot")
    plt.legend()
    plt.tight_layout()
    Path(save_dir).mkdir(parents=True, exist_ok=True)
    plt.savefig(Path(save_dir).parent / "reports" / "pca_scree.png", dpi=150)
    plt.close()

    joblib.dump(pca, Path(save_dir) / "pca.pkl")
    return X_train_pca, X_test_pca, pca


def plot_tsne(
    X: np.ndarray,
    y: np.ndarray,
    title: str = "t-SNE Visualisation",
    save_path: str = "reports/tsne_plot.png",
    sample_size: int = 5000,
) -> None:
    """
    2-D t-SNE visualisation of feature space coloured by binary label.
    Samples for speed.
    """
    from sklearn.manifold import TSNE

    if X.shape[0] > sample_size:
        idx = np.random.choice(X.shape[0], sample_size, replace=False)
        X, y = X[idx], y[idx]

    logger.info("Running t-SNE on %d samples …", X.shape[0])
    tsne = TSNE(n_components=2, random_state=42, perplexity=30, n_iter=500)
    X_2d = tsne.fit_transform(X)

    plt.figure(figsize=(8, 6))
    scatter = plt.scatter(X_2d[:, 0], X_2d[:, 1], c=y, cmap="coolwarm", alpha=0.5, s=5)
    plt.colorbar(scatter, label="0=Normal  1=Attack")
    plt.title(title)
    plt.tight_layout()
    Path(save_path).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(save_path, dpi=150)
    plt.close()
    logger.info("t-SNE plot saved to %s", save_path)

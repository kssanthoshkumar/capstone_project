"""
bias_audit.py
=============
Bias detection, fairness analysis, and mitigation strategies.

Since NSL-KDD has no sensitive demographic attributes, fairness is evaluated
across meaningful traffic subgroups:
    - protocol_type   (tcp / udp / icmp)
    - service         (http, ftp, smtp, …)
    - flag            (SF, S0, REJ, …)

Fairness metrics computed
-------------------------
- Group-level: Accuracy, Precision, Recall, F1 per subgroup
- Equalized Odds Difference (FPR and TPR parity across groups)
- Demographic Parity Difference
- False Positive Rate disparity (operational impact)
"""

import logging
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Subgroup metric computation
# ---------------------------------------------------------------------------

def subgroup_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    groups: pd.Series,
    group_name: str = "group",
) -> pd.DataFrame:
    """
    Compute per-subgroup classification metrics.

    Parameters
    ----------
    y_true   : ground-truth binary labels
    y_pred   : model predicted binary labels
    groups   : Series of categorical group membership (same length as y_true)
    group_name : column name for the grouping variable

    Returns
    -------
    DataFrame with columns: [group_name, n_samples, accuracy, precision, recall, f1,
                              fpr, tpr, positive_rate]
    """
    records = []
    for group_val in sorted(groups.unique()):
        mask = groups == group_val
        yt = y_true[mask]
        yp = y_pred[mask]

        if len(yt) == 0:
            continue

        tn = int(((yp == 0) & (yt == 0)).sum())
        fp = int(((yp == 1) & (yt == 0)).sum())
        fn = int(((yp == 0) & (yt == 1)).sum())
        tp = int(((yp == 1) & (yt == 1)).sum())

        fpr = fp / (fp + tn + 1e-9)
        tpr = tp / (tp + fn + 1e-9)

        records.append({
            group_name:       group_val,
            "n_samples":      int(mask.sum()),
            "positive_rate":  round(float(yt.mean()), 4),
            "accuracy":       round(accuracy_score(yt, yp), 4),
            "precision":      round(precision_score(yt, yp, zero_division=0), 4),
            "recall":         round(recall_score(yt, yp, zero_division=0), 4),
            "f1":             round(f1_score(yt, yp, zero_division=0), 4),
            "fpr":            round(fpr, 4),
            "tpr":            round(tpr, 4),
        })

    return pd.DataFrame(records)


# ---------------------------------------------------------------------------
# Fairness metrics
# ---------------------------------------------------------------------------

def demographic_parity_difference(metrics_df: pd.DataFrame, group_col: str) -> float:
    """
    Demographic Parity Difference = max(positive_rate) - min(positive_rate) across groups.
    Ideal value: 0.
    """
    return round(
        float(metrics_df["positive_rate"].max() - metrics_df["positive_rate"].min()), 4
    )


def equalized_odds_difference(metrics_df: pd.DataFrame) -> dict:
    """
    Equalized Odds Difference for FPR and TPR:
        EOD_fpr = max(fpr) - min(fpr)
        EOD_tpr = max(tpr) - min(tpr)
    Ideal: 0. Threshold for concern: > 0.1.
    """
    return {
        "eod_fpr": round(float(metrics_df["fpr"].max() - metrics_df["fpr"].min()), 4),
        "eod_tpr": round(float(metrics_df["tpr"].max() - metrics_df["tpr"].min()), 4),
    }


def fpr_disparity(metrics_df: pd.DataFrame) -> float:
    """
    FPR Disparity Ratio = max(fpr) / (min(fpr) + 1e-9).
    Ratio > 1.25 indicates potential bias (legitimate traffic flagged differently by group).
    """
    return round(float(metrics_df["fpr"].max() / (metrics_df["fpr"].min() + 1e-9)), 4)


# ---------------------------------------------------------------------------
# Full audit pipeline
# ---------------------------------------------------------------------------

def run_bias_audit(
    model,
    X_test: np.ndarray,
    y_test: np.ndarray,
    test_df_raw: pd.DataFrame,
    feature_names: list[str],
    grouping_cols: list[str] = None,
    save_dir: str = "reports",
) -> dict:
    """
    Run a full bias audit across protocol_type, service, and flag subgroups.

    Parameters
    ----------
    model         : fitted sklearn model
    X_test        : preprocessed test features
    y_test        : true binary labels
    test_df_raw   : original (pre-preprocessed) test DataFrame with raw categorical columns
    feature_names : feature names after preprocessing
    grouping_cols : which raw columns to audit (default: protocol_type, service, flag)
    save_dir      : directory to save audit plots and CSV

    Returns
    -------
    dict of {group_col: metrics_df, "fairness_summary": {...}}
    """
    if grouping_cols is None:
        grouping_cols = ["protocol_type", "service", "flag"]

    # Predictions
    if hasattr(model, "predict_proba"):
        y_pred = (model.predict_proba(X_test)[:, 1] >= 0.5).astype(int)
    else:
        raw = model.predict(X_test)
        y_pred = (raw == -1).astype(int)

    Path(save_dir).mkdir(parents=True, exist_ok=True)
    audit_results = {}
    fairness_summary = {}

    for col in grouping_cols:
        if col not in test_df_raw.columns:
            logger.warning("Column '%s' not in test_df_raw — skipping.", col)
            continue

        groups = test_df_raw[col].reset_index(drop=True)
        mdf = subgroup_metrics(y_test, y_pred, groups, group_name=col)

        dpd  = demographic_parity_difference(mdf, col)
        eod  = equalized_odds_difference(mdf)
        fprd = fpr_disparity(mdf)

        fairness_summary[col] = {
            "demographic_parity_difference": dpd,
            **eod,
            "fpr_disparity_ratio": fprd,
        }

        audit_results[col] = mdf
        logger.info(
            "[Bias Audit | %s] DPD=%.4f | EOD_FPR=%.4f | EOD_TPR=%.4f | FPR_Ratio=%.4f",
            col, dpd, eod["eod_fpr"], eod["eod_tpr"], fprd,
        )

        # Save CSV
        mdf.to_csv(Path(save_dir) / f"bias_audit_{col}.csv", index=False)

        # Plot F1 per subgroup
        _plot_subgroup_metric(mdf, col, metric="f1",
                               save_path=Path(save_dir) / f"bias_f1_{col}.png")
        _plot_subgroup_metric(mdf, col, metric="fpr",
                               save_path=Path(save_dir) / f"bias_fpr_{col}.png")

    audit_results["fairness_summary"] = fairness_summary
    _print_fairness_report(fairness_summary)
    return audit_results


def _plot_subgroup_metric(
    metrics_df: pd.DataFrame,
    group_col: str,
    metric: str = "f1",
    save_path: str = "reports/bias_plot.png",
) -> None:
    plt.figure(figsize=(max(8, len(metrics_df) * 0.6), 5))
    order = metrics_df.sort_values(metric, ascending=False)[group_col].tolist()
    sns.barplot(data=metrics_df, x=group_col, y=metric, order=order, palette="coolwarm")
    plt.xticks(rotation=45, ha="right")
    plt.title(f"{metric.upper()} per {group_col} Subgroup")
    plt.axhline(y=metrics_df[metric].mean(), linestyle="--", color="gray", label="Mean")
    plt.legend()
    plt.tight_layout()
    plt.savefig(save_path, dpi=150)
    plt.close()


def _print_fairness_report(fairness_summary: dict) -> None:
    """Log a human-readable fairness summary."""
    logger.info("=" * 60)
    logger.info("FAIRNESS AUDIT SUMMARY")
    logger.info("=" * 60)
    for col, metrics in fairness_summary.items():
        logger.info("  Group: %s", col)
        for k, v in metrics.items():
            concern = " ⚠️  CONCERN" if (
                (k == "demographic_parity_difference" and abs(v) > 0.05)
                or (k in ("eod_fpr", "eod_tpr") and abs(v) > 0.1)
                or (k == "fpr_disparity_ratio" and v > 1.25)
            ) else ""
            logger.info("    %-40s: %.4f%s", k, v, concern)
    logger.info("=" * 60)


# ---------------------------------------------------------------------------
# Mitigation strategies (documented, not automated)
# ---------------------------------------------------------------------------

MITIGATION_STRATEGIES = {
    "class_imbalance": (
        "Use SMOTE / class_weight='balanced' to oversample minority attack types "
        "(U2R, R2L represent <1% of traffic). Prevents model bias toward majority class."
    ),
    "data_leakage": (
        "NSL-KDD 'difficulty_level' column is removed before training. "
        "Preprocessor is fit only on training data, then applied to test data."
    ),
    "overfitting": (
        "Cross-validation (StratifiedKFold) used during GridSearchCV. "
        "Tree depth limits and early stopping applied for XGB and Autoencoder."
    ),
    "fpr_disparity": (
        "If FPR disparity ratio > 1.25 for a subgroup, investigate feature "
        "distributions for that group. Consider group-specific thresholds "
        "or adversarial debiasing as a post-processing step."
    ),
    "distribution_shift": (
        "NSL-KDD is from 1999; modern traffic patterns differ significantly. "
        "Model should be periodically retrained on recent CICIDS/UNSW datasets. "
        "Feature drift monitoring (e.g., Evidently AI) should be deployed in production."
    ),
}

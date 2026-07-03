"""
explainability.py
=================
Model explainability using SHAP, LIME, PDP, and ICE plots.
"""

import logging
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# SHAP
# ---------------------------------------------------------------------------

def shap_global_importance(
    model,
    X: np.ndarray,
    feature_names: list[str],
    max_display: int = 20,
    save_dir: str = "reports",
    sample_size: int = 2000,
) -> None:
    """
    Compute and plot global SHAP feature importances (beeswarm + bar).
    Samples X for speed.
    """
    import shap

    if X.shape[0] > sample_size:
        idx = np.random.choice(X.shape[0], sample_size, replace=False)
        X_sample = X[idx]
    else:
        X_sample = X

    logger.info("Computing SHAP values on %d samples …", X_sample.shape[0])

    # Tree explainer for RF/XGB; fallback to KernelExplainer
    try:
        explainer = shap.TreeExplainer(model)
        shap_values = explainer.shap_values(X_sample)
        # For multi-output (RF returns list), take attack class (index 1)
        if isinstance(shap_values, list):
            shap_values = shap_values[1]
    except Exception:
        logger.warning("TreeExplainer failed, falling back to KernelExplainer (slower).")
        explainer = shap.KernelExplainer(model.predict_proba, shap.sample(X_sample, 100))
        shap_values = explainer.shap_values(X_sample)[:, :, 1]

    Path(save_dir).mkdir(parents=True, exist_ok=True)

    # Summary beeswarm plot
    plt.figure(figsize=(10, 7))
    shap.summary_plot(
        shap_values,
        X_sample,
        feature_names=feature_names,
        max_display=max_display,
        show=False,
    )
    plt.tight_layout()
    plt.savefig(Path(save_dir) / "shap_beeswarm.png", dpi=150, bbox_inches="tight")
    plt.close()

    # Bar plot (mean |SHAP|)
    plt.figure(figsize=(8, 6))
    shap.summary_plot(
        shap_values,
        X_sample,
        feature_names=feature_names,
        plot_type="bar",
        max_display=max_display,
        show=False,
    )
    plt.tight_layout()
    plt.savefig(Path(save_dir) / "shap_bar.png", dpi=150, bbox_inches="tight")
    plt.close()
    logger.info("SHAP plots saved to %s/", save_dir)

    return shap_values, explainer


def shap_local_explanation(
    explainer,
    X: np.ndarray,
    instance_idx: int,
    feature_names: list[str],
    save_dir: str = "reports",
) -> None:
    """Plot a waterfall (force) plot for a single instance."""
    import shap

    shap_values = explainer.shap_values(X[instance_idx : instance_idx + 1])
    if isinstance(shap_values, list):
        shap_values = shap_values[1]

    plt.figure(figsize=(14, 4))
    shap.waterfall_plot(
        shap.Explanation(
            values=shap_values[0],
            base_values=explainer.expected_value[1]
            if isinstance(explainer.expected_value, list)
            else explainer.expected_value,
            data=X[instance_idx],
            feature_names=feature_names,
        ),
        show=False,
    )
    plt.tight_layout()
    plt.savefig(Path(save_dir) / f"shap_local_instance_{instance_idx}.png", dpi=150, bbox_inches="tight")
    plt.close()


# ---------------------------------------------------------------------------
# LIME
# ---------------------------------------------------------------------------

def lime_local_explanation(
    model,
    X_train: np.ndarray,
    X_instance: np.ndarray,
    feature_names: list[str],
    class_names: list[str] = None,
    save_dir: str = "reports",
    instance_idx: int = 0,
) -> None:
    """
    Generate a LIME explanation for a single instance.
    """
    import lime
    import lime.lime_tabular

    if class_names is None:
        class_names = ["Normal", "Attack"]

    explainer = lime.lime_tabular.LimeTabularExplainer(
        X_train,
        feature_names=feature_names,
        class_names=class_names,
        discretize_continuous=True,
        random_state=42,
    )

    explanation = explainer.explain_instance(
        X_instance,
        model.predict_proba,
        num_features=15,
        top_labels=1,
    )

    Path(save_dir).mkdir(parents=True, exist_ok=True)
    fig = explanation.as_pyplot_figure()
    fig.tight_layout()
    fig.savefig(Path(save_dir) / f"lime_instance_{instance_idx}.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("LIME explanation saved for instance %d.", instance_idx)


# ---------------------------------------------------------------------------
# PDP (Partial Dependence Plots)
# ---------------------------------------------------------------------------

def plot_partial_dependence(
    model,
    X: np.ndarray,
    feature_names: list[str],
    features_to_plot: list[str],
    save_dir: str = "reports",
) -> None:
    """
    Plot 1-D partial dependence plots for specified features.
    """
    from sklearn.inspection import PartialDependenceDisplay

    feature_indices = [feature_names.index(f) for f in features_to_plot if f in feature_names]
    if not feature_indices:
        logger.warning("None of the requested PDP features found in feature_names.")
        return

    fig, ax = plt.subplots(1, len(feature_indices), figsize=(5 * len(feature_indices), 4))
    if len(feature_indices) == 1:
        ax = [ax]

    PartialDependenceDisplay.from_estimator(
        model,
        X,
        features=feature_indices,
        feature_names=feature_names,
        ax=ax,
        grid_resolution=50,
    )
    plt.suptitle("Partial Dependence Plots")
    plt.tight_layout()
    Path(save_dir).mkdir(parents=True, exist_ok=True)
    plt.savefig(Path(save_dir) / "pdp_plots.png", dpi=150, bbox_inches="tight")
    plt.close()
    logger.info("PDP plots saved to %s/pdp_plots.png", save_dir)

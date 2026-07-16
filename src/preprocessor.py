"""
preprocessor.py
===============
Data cleaning, encoding, scaling, and preprocessing pipeline for NSL-KDD.
"""

import logging
from pathlib import Path

import numpy as np
import pandas as pd
import joblib
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import (
    StandardScaler,
    LabelEncoder,
    OneHotEncoder,
    MinMaxScaler,
)
from sklearn.impute import SimpleImputer
from sklearn.base import BaseEstimator, TransformerMixin

from feature_engineering import add_domain_features, bin_count_features

logger = logging.getLogger(__name__)

# NSL-KDD categorical feature columns
CATEGORICAL_COLS = ["protocol_type", "service", "flag"]

# Numeric feature columns (all except categorical, label, difficulty)
NUMERIC_COLS = [
    "duration", "src_bytes", "dst_bytes", "land", "wrong_fragment", "urgent",
    "hot", "num_failed_logins", "logged_in", "num_compromised", "root_shell",
    "su_attempted", "num_root", "num_file_creations", "num_shells",
    "num_access_files", "num_outbound_cmds", "is_host_login", "is_guest_login",
    "count", "srv_count", "serror_rate", "srv_serror_rate", "rerror_rate",
    "srv_rerror_rate", "same_srv_rate", "diff_srv_rate", "srv_diff_host_rate",
    "dst_host_count", "dst_host_srv_count", "dst_host_same_srv_rate",
    "dst_host_diff_srv_rate", "dst_host_same_src_port_rate",
    "dst_host_srv_diff_host_rate", "dst_host_serror_rate",
    "dst_host_srv_serror_rate", "dst_host_rerror_rate",
    "dst_host_srv_rerror_rate",
]

DROP_COLS = ["label", "difficulty_level", "attack_category"]

# Numeric features produced by add_domain_features()
ENGINEERED_NUMERIC_COLS = [
    "byte_ratio", "total_bytes", "log_src_bytes", "log_dst_bytes",
    "log_duration", "error_rate_total", "srv_error_diff", "host_srv_ratio",
    "is_long_connection", "is_big_transfer",
]

# Categorical (binned) features produced by bin_count_features()
ENGINEERED_CATEGORICAL_COLS = [
    "count_bin", "srv_count_bin", "dst_host_count_bin", "dst_host_srv_count_bin",
]

ALL_NUMERIC_COLS     = NUMERIC_COLS + ENGINEERED_NUMERIC_COLS
ALL_CATEGORICAL_COLS = CATEGORICAL_COLS + ENGINEERED_CATEGORICAL_COLS


def remove_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    """Drop exact duplicate rows."""
    before = len(df)
    df = df.drop_duplicates()
    after = len(df)
    logger.info("Removed %d duplicate rows (%d → %d)", before - after, before, after)
    return df.reset_index(drop=True)


def cap_outliers_iqr(df: pd.DataFrame, cols: list[str], factor: float = 3.0) -> pd.DataFrame:
    """
    Winsorize outliers in numeric columns using IQR capping.
    Values beyond [Q1 - factor*IQR, Q3 + factor*IQR] are clipped.
    """
    df = df.copy()
    for col in cols:
        if col not in df.columns:
            continue
        q1, q3 = df[col].quantile(0.25), df[col].quantile(0.75)
        iqr = q3 - q1
        lower, upper = q1 - factor * iqr, q3 + factor * iqr
        clipped = ((df[col] < lower) | (df[col] > upper)).sum()
        if clipped > 0:
            df[col] = df[col].clip(lower=lower, upper=upper)
            logger.debug("Capped %d outliers in '%s'", clipped, col)
    return df


class FeatureEngineer(BaseEstimator, TransformerMixin):
    """Applies domain feature engineering as a sklearn-compatible transform.
    Returns a DataFrame so the downstream ColumnTransformer can select columns
    by name.  No parameters to fit — transform is stateless."""

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        X = add_domain_features(X)
        X = bin_count_features(X)
        return X


class OutlierClipper(BaseEstimator, TransformerMixin):
    """Learns IQR clip bounds from training data and applies the same bounds
    at transform time — fixes the train/test preprocessing inconsistency where
    test data was previously not clipped."""

    def __init__(self, cols=None, factor: float = 3.0):
        self.cols = cols
        self.factor = factor

    def fit(self, X, y=None):
        df = X if isinstance(X, pd.DataFrame) else pd.DataFrame(X)
        cols = self.cols if self.cols is not None else []
        self.bounds_ = {}
        for col in cols:
            if col in df.columns:
                q1, q3 = df[col].quantile(0.25), df[col].quantile(0.75)
                iqr = q3 - q1
                self.bounds_[col] = (q1 - self.factor * iqr, q3 + self.factor * iqr)
        return self

    def transform(self, X):
        df = X.copy() if isinstance(X, pd.DataFrame) else pd.DataFrame(X).copy()
        for col, (lower, upper) in self.bounds_.items():
            if col in df.columns:
                df[col] = df[col].clip(lower=lower, upper=upper)
        return df


def build_preprocessing_pipeline(scaler: str = "standard") -> ColumnTransformer:
    """
    Build a sklearn ColumnTransformer that:
    - Imputes + scales numeric columns
    - Imputes + one-hot encodes categorical columns

    Parameters
    ----------
    scaler : 'standard' | 'minmax'
    """
    scaler_obj = StandardScaler() if scaler == "standard" else MinMaxScaler()

    numeric_transformer = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler",  scaler_obj),
    ])

    categorical_transformer = Pipeline([
        ("imputer", SimpleImputer(strategy="most_frequent")),
        ("ohe",     OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
    ])

    preprocessor = ColumnTransformer(
        transformers=[
            ("num", numeric_transformer,  NUMERIC_COLS),
            ("cat", categorical_transformer, CATEGORICAL_COLS),
        ],
        remainder="drop",
        verbose_feature_names_out=False,
    )
    return preprocessor


def build_full_pipeline(scaler: str = "standard") -> Pipeline:
    """Return the complete end-to-end Pipeline used for training and inference:

      1. FeatureEngineer   — add 14 domain features to the DataFrame
      2. OutlierClipper    — fit IQR bounds on train; apply same bounds to test
      3. ColumnTransformer — impute + scale numerics; impute + OHE categoricals

    This is the only pipeline that should be fit and saved to disk.
    """
    scaler_obj = StandardScaler() if scaler == "standard" else MinMaxScaler()

    column_transformer = ColumnTransformer(
        transformers=[
            ("num", Pipeline([
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler",  scaler_obj),
            ]), ALL_NUMERIC_COLS),
            ("cat", Pipeline([
                ("imputer", SimpleImputer(strategy="most_frequent")),
                ("ohe",     OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
            ]), ALL_CATEGORICAL_COLS),
        ],
        remainder="drop",
        verbose_feature_names_out=False,
    )
    return Pipeline([
        ("feature_engineering", FeatureEngineer()),
        ("outlier_clipper",     OutlierClipper(cols=ALL_NUMERIC_COLS)),
        ("column_transformer", column_transformer),
    ])


def get_feature_names(pipeline) -> list[str]:
    """Extract feature names from a fitted Pipeline or ColumnTransformer."""
    ct = pipeline[-1] if isinstance(pipeline, Pipeline) else pipeline
    return list(ct.get_feature_names_out())


def preprocess(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    scaler: str = "standard",
    save_dir: str = "models",
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, list[str]]:
    """
    Full preprocessing: clean → outlier cap → fit/transform pipeline.

    Returns
    -------
    X_train, X_test, y_train, y_test, feature_names
    """
    train_df = remove_duplicates(train_df)

    # Feature engineering and outlier clipping are now handled inside
    # build_full_pipeline so they apply consistently to train AND test.
    y_train = train_df["binary_label"].values
    y_test  = test_df["binary_label"].values

    pipeline = build_full_pipeline(scaler=scaler)
    X_train = pipeline.fit_transform(train_df)
    X_test  = pipeline.transform(test_df)

    feature_names = get_feature_names(pipeline)
    logger.info(
        "Preprocessing complete. X_train=%s  X_test=%s",
        X_train.shape, X_test.shape,
    )

    # Persist the fitted pipeline
    Path(save_dir).mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, Path(save_dir) / "preprocessor.pkl")
    logger.info("Saved preprocessor to %s/preprocessor.pkl", save_dir)

    return X_train, X_test, y_train, y_test, feature_names


def load_preprocessor(save_dir: str = "models") -> ColumnTransformer:
    """Load a persisted preprocessing pipeline."""
    path = Path(save_dir) / "preprocessor.pkl"
    if not path.exists():
        raise FileNotFoundError(f"Preprocessor not found at {path}. Run preprocess() first.")
    return joblib.load(path)

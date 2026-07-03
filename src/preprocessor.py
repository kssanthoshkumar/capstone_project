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


def get_feature_names(preprocessor: ColumnTransformer) -> list[str]:
    """Extract feature names after fitting a ColumnTransformer."""
    return list(preprocessor.get_feature_names_out())


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

    # Outlier capping on training set only (to avoid data leakage)
    train_df = cap_outliers_iqr(train_df, NUMERIC_COLS)

    y_train = train_df["binary_label"].values
    y_test  = test_df["binary_label"].values

    pipeline = build_preprocessing_pipeline(scaler=scaler)
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

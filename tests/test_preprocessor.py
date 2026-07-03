"""
test_preprocessor.py
====================
Unit tests for src/preprocessor.py — cleaning and pipeline functions.
"""

import numpy as np
import pandas as pd
import pytest

from src.preprocessor import (
    remove_duplicates,
    cap_outliers_iqr,
    build_preprocessing_pipeline,
    NUMERIC_COLS,
    CATEGORICAL_COLS,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_df(n=10, seed=42) -> pd.DataFrame:
    """Create a minimal valid NSL-KDD-like DataFrame for pipeline testing."""
    rng = np.random.default_rng(seed)
    data = {col: rng.uniform(0, 100, n) for col in NUMERIC_COLS}
    data["protocol_type"] = rng.choice(["tcp", "udp", "icmp"], n)
    data["service"]       = rng.choice(["http", "ftp", "ssh"], n)
    data["flag"]          = rng.choice(["SF", "REJ", "S0"], n)
    return pd.DataFrame(data)


# ---------------------------------------------------------------------------
# remove_duplicates
# ---------------------------------------------------------------------------

class TestRemoveDuplicates:
    def test_removes_exact_duplicates(self):
        df = pd.DataFrame({"a": [1, 2, 2, 3], "b": [4, 5, 5, 6]})
        result = remove_duplicates(df)
        assert len(result) == 3

    def test_no_duplicates_unchanged(self):
        df = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
        result = remove_duplicates(df)
        assert len(result) == 3

    def test_all_duplicates(self):
        df = pd.DataFrame({"a": [1, 1, 1], "b": [2, 2, 2]})
        result = remove_duplicates(df)
        assert len(result) == 1

    def test_index_reset_after_dedup(self):
        df = pd.DataFrame({"a": [1, 2, 2]})
        result = remove_duplicates(df)
        assert list(result.index) == [0, 1]

    def test_empty_dataframe(self):
        df = pd.DataFrame({"a": []})
        result = remove_duplicates(df)
        assert len(result) == 0


# ---------------------------------------------------------------------------
# cap_outliers_iqr
# ---------------------------------------------------------------------------

class TestCapOutliersIQR:
    def test_extreme_values_clipped(self):
        df = pd.DataFrame({"x": [1.0, 2.0, 3.0, 4.0, 1000.0]})
        result = cap_outliers_iqr(df, ["x"], factor=1.5)
        assert result["x"].max() < 1000.0

    def test_normal_values_unchanged(self):
        df = pd.DataFrame({"x": [10.0, 11.0, 12.0, 11.5, 10.5]})
        original_max = df["x"].max()
        result = cap_outliers_iqr(df, ["x"], factor=3.0)
        assert result["x"].max() == original_max

    def test_does_not_modify_original(self):
        df = pd.DataFrame({"x": [1.0, 2.0, 3.0, 4.0, 9999.0]})
        _ = cap_outliers_iqr(df, ["x"])
        assert df["x"].max() == 9999.0  # original untouched

    def test_missing_column_skipped(self):
        df = pd.DataFrame({"x": [1.0, 2.0, 3.0]})
        result = cap_outliers_iqr(df, ["x", "nonexistent"])
        assert "nonexistent" not in result.columns

    def test_no_values_outside_bounds_at_factor3(self):
        df = pd.DataFrame({"x": list(range(100))})
        result = cap_outliers_iqr(df, ["x"], factor=3.0)
        q1, q3 = df["x"].quantile(0.25), df["x"].quantile(0.75)
        iqr = q3 - q1
        assert result["x"].min() >= q1 - 3.0 * iqr
        assert result["x"].max() <= q3 + 3.0 * iqr


# ---------------------------------------------------------------------------
# build_preprocessing_pipeline
# ---------------------------------------------------------------------------

class TestBuildPreprocessingPipeline:
    def test_returns_column_transformer(self):
        from sklearn.compose import ColumnTransformer
        pipeline = build_preprocessing_pipeline()
        assert isinstance(pipeline, ColumnTransformer)

    def test_fit_transform_produces_array(self):
        df = _make_df()
        pipeline = build_preprocessing_pipeline()
        result = pipeline.fit_transform(df)
        assert isinstance(result, np.ndarray)

    def test_output_rows_match_input(self):
        df = _make_df(n=20)
        pipeline = build_preprocessing_pipeline()
        result = pipeline.fit_transform(df)
        assert result.shape[0] == 20

    def test_output_has_no_nans(self):
        df = _make_df()
        # Inject NaN
        df.loc[0, NUMERIC_COLS[0]] = np.nan
        pipeline = build_preprocessing_pipeline()
        result = pipeline.fit_transform(df)
        assert not np.isnan(result).any()

    def test_transform_unseen_category(self):
        """handle_unknown='ignore' should not raise on unseen categories."""
        df_train = _make_df(n=20)
        df_test  = df_train.copy()
        df_test.loc[0, "service"] = "totally_unknown_service"
        pipeline = build_preprocessing_pipeline()
        pipeline.fit(df_train)
        result = pipeline.transform(df_test)
        assert not np.isnan(result).any()

    def test_minmax_scaler_variant(self):
        df = _make_df()
        pipeline = build_preprocessing_pipeline(scaler="minmax")
        result = pipeline.fit_transform(df)
        assert isinstance(result, np.ndarray)

    def test_standard_and_minmax_same_shape(self):
        df = _make_df()
        std = build_preprocessing_pipeline(scaler="standard").fit_transform(df)
        mmx = build_preprocessing_pipeline(scaler="minmax").fit_transform(df)
        assert std.shape == mmx.shape

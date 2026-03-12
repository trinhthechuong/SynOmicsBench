"""
Smoke tests for SynOmics.processing module.

Tests DataProcessor, MetaData, and postprocessing functions using
a 100-column subset of the real test data to keep execution fast.
"""

import os
import json
import tempfile

import numpy as np
import pandas as pd
import pytest

from SynOmics.processing.preprocessing import DataProcessor
from SynOmics.processing.metadata import MetaData
from SynOmics.processing import postprocessing

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

TEST_DATA_DIR = os.path.join(os.path.dirname(__file__), "test_data")
N_COLS = 100  # keep tests fast


@pytest.fixture(scope="module")
def original_data() -> pd.DataFrame:
    """Load original data with first N_COLS columns."""
    path = os.path.join(TEST_DATA_DIR, "original_data.csv")
    full = pd.read_csv(path)
    return full.iloc[:, :N_COLS].copy()


@pytest.fixture(scope="module")
def synthetic_data() -> pd.DataFrame:
    """Load synthetic data with first N_COLS columns."""
    path = os.path.join(TEST_DATA_DIR, "synthetic_data.csv")
    full = pd.read_csv(path)
    return full.iloc[:, :N_COLS].copy()


@pytest.fixture(scope="module")
def metadata_dict(original_data: pd.DataFrame) -> dict:
    """Build metadata from the original data (excluding 'Patient' id column)."""
    return MetaData.get_metadata(
        data=original_data,
        threshold_unique_values=10,
        id_columns=["Patient"],
    )


@pytest.fixture
def tmp_dir(tmp_path):
    """Provide a temporary directory for file-output tests."""
    return str(tmp_path)


# ===========================================================================
# DataProcessor tests
# ===========================================================================


class TestDataProcessor:
    """Smoke tests for DataProcessor static methods."""

    def test_remove_duplications_rows(self, original_data: pd.DataFrame):
        result = DataProcessor.remove_duplications(original_data, axis=0)
        assert isinstance(result, pd.DataFrame)
        assert len(result) <= len(original_data)

    def test_remove_duplications_cols(self, original_data: pd.DataFrame):
        result = DataProcessor.remove_duplications(original_data, axis=1)
        assert isinstance(result, pd.DataFrame)
        assert result.shape[1] <= original_data.shape[1]

    def test_remove_duplications_invalid_axis(self, original_data: pd.DataFrame):
        with pytest.raises(ValueError):
            DataProcessor.remove_duplications(original_data, axis=2)

    def test_remove_duplications_invalid_type(self):
        with pytest.raises(TypeError):
            DataProcessor.remove_duplications("not a dataframe", axis=0)

    def test_remove_unknown_entities(self, original_data: pd.DataFrame):
        result = DataProcessor.remove_unknown_entities(
            original_data, id_column="Patient"
        )
        assert isinstance(result, pd.DataFrame)
        # No NaN in Patient column
        assert result["Patient"].isna().sum() == 0

    def test_remove_unknown_entities_bad_column(self, original_data: pd.DataFrame):
        with pytest.raises(KeyError):
            DataProcessor.remove_unknown_entities(
                original_data, id_column="NONEXISTENT"
            )

    def test_remove_overmissing_entities(self, original_data: pd.DataFrame):
        result = DataProcessor.remove_overmissing_entities(
            original_data, threshold=50.0
        )
        assert isinstance(result, pd.DataFrame)
        assert len(result) <= len(original_data)

    def test_remove_overmissing_entities_invalid_threshold(
        self, original_data: pd.DataFrame
    ):
        with pytest.raises(ValueError):
            DataProcessor.remove_overmissing_entities(original_data, threshold=150)

    def test_find_missing_percent(self, original_data: pd.DataFrame):
        result = DataProcessor.find_missing_percent(original_data)
        assert isinstance(result, pd.DataFrame)
        assert "PercentMissing" in result.columns
        assert "ColumnName" in result.columns
        assert len(result) == original_data.shape[1]

    def test_remove_overmissing_features(self, original_data: pd.DataFrame):
        result = DataProcessor.remove_overmissing_features(
            original_data, threshold=80.0
        )
        assert isinstance(result, pd.DataFrame)
        assert result.shape[1] <= original_data.shape[1]

    def test_remove_low_expression_genes(self, original_data: pd.DataFrame):
        # Use only numeric gene columns (skip clinical/string columns)
        numeric_cols = original_data.select_dtypes(include=[np.number]).columns.tolist()
        gene_data = original_data[numeric_cols].copy()
        result = DataProcessor.remove_low_expression_genes(
            gene_data, variance_threshold=0.0005
        )
        assert isinstance(result, pd.DataFrame)
        assert result.shape[1] <= gene_data.shape[1]

    def test_encode_dummy_features(self, original_data: pd.DataFrame):
        # Pick only object/categorical columns
        cat_cols = original_data.select_dtypes(
            include=["object", "category"]
        ).columns.tolist()
        if not cat_cols:
            pytest.skip("No categorical columns in the test subset")
        cat_data = original_data[cat_cols].copy()
        result = DataProcessor.encode_dummy_features(cat_data)
        assert isinstance(result, pd.DataFrame)
        assert result.shape[0] == cat_data.shape[0]

    def test_encode_ordinal_features(self, original_data: pd.DataFrame):
        # Use a small categorical subset; fill NaN to avoid encoder issues
        cat_cols = original_data.select_dtypes(
            include=["object", "category"]
        ).columns.tolist()
        if not cat_cols:
            pytest.skip("No categorical columns in the test subset")
        cat_data = original_data[cat_cols].fillna("MISSING").copy()
        result_df, encoder = DataProcessor.encode_ordinal_features(cat_data)
        assert isinstance(result_df, pd.DataFrame)
        assert result_df.shape == cat_data.shape
        assert encoder is not None

    def test_standardization_standard(self, original_data: pd.DataFrame):
        numeric_cols = original_data.select_dtypes(include=[np.number]).columns.tolist()
        num_data = original_data[numeric_cols].dropna(axis=1).copy()
        if num_data.empty:
            pytest.skip("No complete numeric columns")
        result_df, scaler = DataProcessor.standardization(num_data, scaler="standard")
        assert isinstance(result_df, pd.DataFrame)
        assert result_df.shape == num_data.shape

    def test_standardization_minmax(self, original_data: pd.DataFrame):
        numeric_cols = original_data.select_dtypes(include=[np.number]).columns.tolist()
        num_data = original_data[numeric_cols].dropna(axis=1).copy()
        if num_data.empty:
            pytest.skip("No complete numeric columns")
        result_df, scaler = DataProcessor.standardization(num_data, scaler="minmax")
        assert isinstance(result_df, pd.DataFrame)

    def test_standardization_robust(self, original_data: pd.DataFrame):
        numeric_cols = original_data.select_dtypes(include=[np.number]).columns.tolist()
        num_data = original_data[numeric_cols].dropna(axis=1).copy()
        if num_data.empty:
            pytest.skip("No complete numeric columns")
        result_df, scaler = DataProcessor.standardization(num_data, scaler="robust")
        assert isinstance(result_df, pd.DataFrame)

    def test_standardization_invalid_scaler(self, original_data: pd.DataFrame):
        with pytest.raises(ValueError):
            DataProcessor.standardization(original_data, scaler="invalid")

    def test_knn_imputer(self, original_data: pd.DataFrame):
        """Test KNN imputer on numeric data with some NaN."""
        numeric_cols = original_data.select_dtypes(include=[np.number]).columns.tolist()
        num_data = original_data[numeric_cols].copy()
        if num_data.isna().sum().sum() == 0:
            # Inject some NaNs for testing
            rng = np.random.default_rng(42)
            mask = rng.random(num_data.shape) < 0.05
            num_data = num_data.mask(mask)
        result = DataProcessor.knn_imputer(
            num_data,
            dummy_cat_columns=[],
            ordinal_cat_columns=[],
            n_neighbors=3,
            add_indicators=False,
        )
        assert isinstance(result, pd.DataFrame)
        # All NaN should be filled
        assert result[numeric_cols].isna().sum().sum() == 0


# ===========================================================================
# MetaData tests
# ===========================================================================


class TestMetaData:
    """Smoke tests for MetaData static methods."""

    def test_classify_features_types(self, original_data: pd.DataFrame):
        data_no_id = original_data.drop(columns=["Patient"], errors="ignore")
        dummy_cols, num_cols = MetaData.classify_features_types(
            data_no_id, threshold_unique_values=10
        )
        assert isinstance(dummy_cols, list)
        assert isinstance(num_cols, list)
        # Together they should cover most columns
        assert len(dummy_cols) + len(num_cols) > 0

    def test_get_metadata(self, original_data: pd.DataFrame):
        metadata = MetaData.get_metadata(
            data=original_data,
            threshold_unique_values=10,
            id_columns=["Patient"],
        )
        assert isinstance(metadata, dict)
        # Should not contain 'Patient'
        assert "Patient" not in metadata
        # Every remaining column should be classified
        expected_cols = set(original_data.columns) - {"Patient"}
        assert set(metadata.keys()) == expected_cols

    def test_grouping_features_astype(
        self, original_data: pd.DataFrame, metadata_dict: dict
    ):
        data_no_id = original_data.drop(columns=["Patient"], errors="ignore")
        groups = MetaData.grouping_features_astype(data_no_id, metadata_dict)
        assert isinstance(groups, dict)
        for key in [
            "numerical",
            "ordinal_categorical",
            "dummy_categorical",
            "missing_categorical",
        ]:
            assert key in groups
            assert isinstance(groups[key], list)

    def test_metadata_as_SDV(self, original_data: pd.DataFrame, metadata_dict: dict):
        data_no_id = original_data.drop(columns=["Patient"], errors="ignore")
        sdv_meta = MetaData.metadata_as_SDV(data_no_id, metadata_dict)
        assert isinstance(sdv_meta, dict)
        assert "columns" in sdv_meta
        # Every column should have an sdtype
        for col_info in sdv_meta["columns"].values():
            assert "sdtype" in col_info

    def test_get_column_indices(self, original_data: pd.DataFrame):
        cols = original_data.columns[:5].tolist()
        indices = MetaData.get_column_indices(original_data, cols)
        assert isinstance(indices, np.ndarray)
        assert len(indices) == 5
        np.testing.assert_array_equal(indices, np.arange(5))

    def test_get_column_indices_missing_column(self, original_data: pd.DataFrame):
        with pytest.raises(ValueError):
            MetaData.get_column_indices(original_data, ["NONEXISTENT_COL"])

    def test_save_and_load(self, metadata_dict: dict, tmp_dir: str):
        MetaData.save(metadata_dict, output_dir=tmp_dir, filename="test_meta")
        json_path = os.path.join(tmp_dir, "test_meta.json")
        assert os.path.exists(json_path)

        loaded = MetaData.load(json_path)
        assert loaded == metadata_dict


# ===========================================================================
# Postprocessing tests
# ===========================================================================


class TestPostprocessing:
    """Smoke tests for postprocessing functions."""

    def test_detect_discrete_columns(
        self, original_data: pd.DataFrame, metadata_dict: dict
    ):
        data_no_id = original_data.drop(columns=["Patient"], errors="ignore")
        discrete = postprocessing._detect_discrete_columns(data_no_id, metadata_dict)
        assert isinstance(discrete, list)

    def test_detect_numerical_columns(
        self, original_data: pd.DataFrame, metadata_dict: dict
    ):
        data_no_id = original_data.drop(columns=["Patient"], errors="ignore")
        numerical = postprocessing._detect_numerical_columns(data_no_id, metadata_dict)
        assert isinstance(numerical, list)
        assert len(numerical) > 0

    def test_detect_min_max_values(
        self, original_data: pd.DataFrame, metadata_dict: dict
    ):
        data_no_id = original_data.drop(columns=["Patient"], errors="ignore")
        numerical = postprocessing._detect_numerical_columns(data_no_id, metadata_dict)
        min_vals, max_vals = postprocessing._detect_min_max_values(
            data_no_id, numerical
        )
        assert isinstance(min_vals, dict)
        assert isinstance(max_vals, dict)
        for col in numerical:
            assert col in min_vals
            assert col in max_vals
            assert min_vals[col] <= max_vals[col]

    def test_detect_rounding_digits(
        self, original_data: pd.DataFrame, metadata_dict: dict
    ):
        data_no_id = original_data.drop(columns=["Patient"], errors="ignore")
        numerical = postprocessing._detect_numerical_columns(data_no_id, metadata_dict)
        rounding = postprocessing._detect_rounding_digits(data_no_id, numerical)
        assert isinstance(rounding, dict)
        for col in numerical:
            assert col in rounding
            assert rounding[col] >= 0

    def test_apply_min_max(self, synthetic_data: pd.DataFrame, metadata_dict: dict):
        data_no_id = synthetic_data.drop(columns=["Patient"], errors="ignore")
        numerical = postprocessing._detect_numerical_columns(data_no_id, metadata_dict)
        # Use arbitrary bounds
        min_vals = {col: -100.0 for col in numerical}
        max_vals = {col: 100.0 for col in numerical}
        result = postprocessing.apply_min_max(
            data_no_id.copy(), numerical, min_vals, max_vals
        )
        assert isinstance(result, pd.DataFrame)
        for col in numerical:
            assert result[col].min() >= -100.0
            assert result[col].max() <= 100.0

    def test_apply_rounding(self, synthetic_data: pd.DataFrame, metadata_dict: dict):
        data_no_id = synthetic_data.drop(columns=["Patient"], errors="ignore")
        numerical = postprocessing._detect_numerical_columns(data_no_id, metadata_dict)
        rounding = {col: 2 for col in numerical}
        result = postprocessing.apply_rounding(data_no_id.copy(), numerical, rounding)
        assert isinstance(result, pd.DataFrame)

    def test_anonymize_ids(self, synthetic_data: pd.DataFrame, tmp_dir: str):
        ids = [f"patient_{i}" for i in range(len(synthetic_data))]
        # Drop both Patient and Patient_ID to avoid insert conflict
        syn_copy = synthetic_data.drop(columns=["Patient", "Patient_ID"], errors="ignore").copy()
        result = postprocessing.anonymize_ids(ids, syn_copy, tmp_dir)
        assert isinstance(result, pd.DataFrame)
        assert "Patient_ID" in result.columns
        # Mapping file should be created
        assert os.path.exists(os.path.join(tmp_dir, "anonymized_ids.json"))

    def test_post_masking(self, original_data: pd.DataFrame):
        result = postprocessing.post_masking(original_data)
        assert isinstance(result, pd.DataFrame)
        # If no missingindicator columns, result should be identical
        if not any(c.startswith("missingindicator_") for c in original_data.columns):
            assert result.shape == original_data.shape

    def test_load_metadata(self, metadata_dict: dict, tmp_dir: str):
        # Save then load via postprocessing.load_metadata
        path = os.path.join(tmp_dir, "meta_load_test.json")
        with open(path, "w") as f:
            json.dump(metadata_dict, f)
        loaded = postprocessing.load_metadata(path)
        assert loaded == metadata_dict

    def test_load_metadata_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            postprocessing.load_metadata("/nonexistent/path/meta.json")

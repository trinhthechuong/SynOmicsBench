"""
Tests for synomicsbench processing pipeline module.

Note: Some tests require optional dependencies (mygene). Those tests will be skipped
if the dependency is not available.
"""

import os
import json

import numpy as np
import pandas as pd
import pytest

# Check for optional dependencies
try:
    from synomicsbench.processing.pipeline import DataIntegrationPipeline

    PIPELINE_AVAILABLE = True
except ImportError:
    PIPELINE_AVAILABLE = False


TEST_DATA_DIR = os.path.join(os.path.dirname(__file__), "test_data")


@pytest.fixture
def clinical_df():
    path = os.path.join(TEST_DATA_DIR, "clinical_sample.csv")
    if os.path.exists(path):
        return pd.read_csv(path)
    # Create minimal test data
    np.random.seed(42)
    n = 50
    return pd.DataFrame(
        {
            "Patient_ID": [f"P{i:03d}" for i in range(n)],
            "age": np.random.randint(40, 80, n),
            "sex": np.random.choice(["M", "F"], n),
            "stage": np.random.choice(["I", "II", "III", "IV"], n),
        }
    )


@pytest.fixture
def transcriptomics_df():
    np.random.seed(42)
    n = 50
    genes = [f"Gene_{i}" for i in range(100)]
    return pd.DataFrame(
        {
            "Sample": [f"P{i:03d}" for i in range(n)],
            **{gene: np.random.randn(n) for gene in genes},
        }
    )


@pytest.fixture
def tmp_output_dir(tmp_path):
    return str(tmp_path)


@pytest.mark.skipif(
    not PIPELINE_AVAILABLE, reason="Pipeline requires mygene dependency"
)
class TestDataIntegrationPipeline:
    """Tests for DataIntegrationPipeline class."""

    def test_init_creates_output_directory(self, tmp_output_dir):
        pipeline = DataIntegrationPipeline(output_dir=tmp_output_dir, logger="test")
        assert os.path.exists(tmp_output_dir)
        assert pipeline.output_dir == tmp_output_dir

    def test_process_transcriptomics_basic(self, transcriptomics_df, tmp_output_dir):
        pipeline = DataIntegrationPipeline(
            output_dir=tmp_output_dir, logger="test_trans"
        )

        result = pipeline.process_transcriptomics_data(
            transcriptomics_data=transcriptomics_df,
            transcriptomics_id_column="Sample",
            steps_config={
                "remove_undefined": True,
                "remove_duplicates": True,
                "remove_overmissing_samples": True,
                "remove_low_expression_genes": False,
                "check_duplicate_genes": False,
                "mapping_genes": False,
                "feature_engineering": True,
            },
            verbose=False,
        )

        assert isinstance(result, pd.DataFrame)
        assert "Sample" in result.columns

    def test_process_transcriptomics_invalid_input(self, tmp_output_dir):
        pipeline = DataIntegrationPipeline(output_dir=tmp_output_dir, logger="test")

        with pytest.raises(TypeError):
            pipeline.process_transcriptomics_data(
                transcriptomics_data="not a dataframe",
                transcriptomics_id_column="Sample",
                steps_config={},
            )

    def test_process_clinical_basic(self, clinical_df, tmp_output_dir):
        pipeline = DataIntegrationPipeline(
            output_dir=tmp_output_dir, logger="test_clinical"
        )

        result = pipeline.process_clinical_data(
            clinical_data=clinical_df,
            clinical_id_column="Patient_ID",
            steps_config={
                "remove_undefined": True,
                "remove_duplicates": True,
                "remove_overmissing_samples": True,
                "feature_engineering": True,
            },
            verbose=False,
        )

        assert isinstance(result, pd.DataFrame)
        assert "Patient_ID" in result.columns

    def test_run_pipeline_full(self, clinical_df, transcriptomics_df, tmp_output_dir):
        pipeline = DataIntegrationPipeline(
            output_dir=tmp_output_dir, logger="full_test"
        )

        results = pipeline.run_pipeline(
            clinical_data=clinical_df,
            transcriptomics_data=transcriptomics_df,
            clinical_id_column="Patient_ID",
            transcriptomics_id_column="Sample",
            integration_id_column="Patient_ID",
            steps_config={
                "remove_undefined": True,
                "remove_duplicates": True,
                "remove_overmissing_samples": True,
                "remove_low_expression_genes": False,
                "check_duplicate_genes": False,
                "mapping_genes": False,
                "feature_engineering": True,
                "integrate_data": True,
            },
            verbose=False,
        )

        assert isinstance(results, dict)
        assert "processed_clinical" in results
        assert "processed_transcriptomics" in results
        assert "integrated_data" in results

    def test_run_pipeline_metadata_saved(
        self, clinical_df, transcriptomics_df, tmp_output_dir
    ):
        pipeline = DataIntegrationPipeline(
            output_dir=tmp_output_dir, logger="metadata_test"
        )

        pipeline.run_pipeline(
            clinical_data=clinical_df,
            transcriptomics_data=transcriptomics_df,
            clinical_id_column="Patient_ID",
            transcriptomics_id_column="Sample",
            integration_id_column="Patient_ID",
            steps_config={
                "remove_undefined": True,
                "remove_duplicates": True,
                "remove_overmissing_samples": True,
                "remove_low_expression_genes": False,
                "check_duplicate_genes": False,
                "mapping_genes": False,
                "feature_engineering": True,
                "integrate_data": True,
            },
            verbose=False,
        )

        metadata_path = os.path.join(tmp_output_dir, "feature_metadata.json")
        assert os.path.exists(metadata_path)

        with open(metadata_path) as f:
            metadata = json.load(f)
        assert isinstance(metadata, dict)

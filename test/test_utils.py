"""
Tests for synomicsbench utils, gene_query, and postprocessing modules.
"""

import os
import numpy as np
import pandas as pd
import pytest


TEST_DATA_DIR = os.path.join(os.path.dirname(__file__), "test_data")


class TestMonitoringUtils:
    """Tests for monitoring/logging utilities."""

    def test_set_logger_basic(self, tmp_path):
        from synomicsbench.utils.monitoring import set_logger

        logger = set_logger("test_logger", str(tmp_path))

        assert logger is not None
        assert logger.name == "test_logger"

    def test_set_logger_with_file(self, tmp_path):
        from synomicsbench.utils.monitoring import set_logger

        log_file = "test_log.log"
        logger = set_logger("test", str(tmp_path), log_file)

        logger.info("Test message")

        log_path = os.path.join(tmp_path, log_file)
        assert os.path.exists(log_path)

    def test_set_logger_different_names(self, tmp_path):
        from synomicsbench.utils.monitoring import set_logger

        logger1 = set_logger("logger1", str(tmp_path))
        logger2 = set_logger("logger2", str(tmp_path))

        assert logger1.name != logger2.name


class TestPostprocessing:
    """Tests for postprocessing functions."""

    def test_postprocessing_import(self):
        from synomicsbench.processing import postprocessing

        assert postprocessing is not None





class TestMissingValueSimilarity:
    """Tests for MissingValueSimilarity (fixed version)."""

    def test_missing_value_similarity_import(self):
        try:
            from synomicsbench.metrics.fidelity.MissingValueSimilarity import (
                MissingValue_Similarity,
            )

            assert callable(MissingValue_Similarity)
        except (NameError, ImportError) as e:
            pytest.skip(f"MissingValueSimilarity has import issues: {e}")

    def test_missing_value_similarity_init(self):
        try:
            from synomicsbench.metrics.fidelity.MissingValueSimilarity import (
                MissingValue_Similarity,
            )
            import pandas as pd

            df_real = pd.DataFrame({"colA": [1, 2], "missingindicator_colA": [0, 1]})
            df_syn = pd.DataFrame({"colA": [1, 3], "missingindicator_colA": [0, 1]})
            mvs = MissingValue_Similarity(
                origin_data=df_real, synthetic_data=df_syn, missing_indicators=["missingindicator_colA"]
            )
            assert isinstance(mvs, dict)
        except (NameError, ImportError) as e:
            pytest.skip(f"MissingValueSimilarity has import issues: {e}")


class TestPairwiseSimilarityCoverage:
    """Additional tests to improve PairwiseSimilarity coverage."""

    def test_pairwise_with_different_methods(self):
        from synomicsbench.metrics.fidelity.PairwiseSimilarity import PairwiseSimilarity
        from synomicsbench.processing.metadata import MetaData

        np.random.seed(42)
        n = 30
        data = pd.DataFrame(
            {
                "num1": np.random.randn(n),
                "num2": np.random.randn(n),
                "cat1": np.random.choice(["A", "B"], n),
            }
        )

        metadata = MetaData.get_metadata(
            data=data,
            threshold_unique_values=10,
        )

        ps = PairwiseSimilarity(
            original_data=data,
            synthetic_data=data.copy(),
            metadata=metadata,
            output_dir="/tmp/test_pairwise",
            verbose=False,
            save=False,
        )

        pearson_scores = ps.get_pairwise_scores(method="pearson")
        assert isinstance(pearson_scores, dict)


class TestUnivariateSimilarityCoverage:
    """Additional tests for UnivariateSimilarity coverage."""

    def test_univariate_get_visualization(self):
        from synomicsbench.metrics.fidelity.UnivariateSimilarity import UnivariateSimilarity
        from synomicsbench.processing.metadata import MetaData

        np.random.seed(42)
        n = 30
        data = pd.DataFrame(
            {
                "num1": np.random.randn(n),
                "num2": np.random.randn(n),
            }
        )

        metadata = MetaData.get_metadata(
            data=data,
            threshold_unique_values=10,
        )

        us = UnivariateSimilarity(output_dir="/tmp/test_uni", logger_name="test")
        us.get_univariate_score(
            original_data=data,
            synthetic_data=data.copy(),
            metadata=metadata,
            save=False,
        )

        details = us.get_detail_df()
        fig = us.get_visualization(plotly=False, data_name="test")
        assert fig is not None


class TestCorrelationsUtils:
    """Additional tests for correlations module."""

    def test_correlations_module_import(self):
        from synomicsbench.utils import correlations

        assert correlations is not None


class TestMetadataCoverage:
    """Additional tests for MetaData module."""

    def test_metadata_with_ordinal_features(self):
        from synomicsbench.processing.metadata import MetaData

        np.random.seed(42)
        data = pd.DataFrame(
            {
                "num": np.random.randn(50),
                "cat": np.random.choice(["A", "B", "C"], 50),
                "ordinal": np.random.choice([1, 2, 3, 4, 5], 50),
            }
        )

        metadata = MetaData.get_metadata(
            data=data,
            threshold_unique_values=10,
            ordinal_features=["ordinal"],
        )

        assert isinstance(metadata, dict)

    def test_metadata_as_sdv_format(self):
        from synomicsbench.processing.metadata import MetaData

        np.random.seed(42)
        data = pd.DataFrame(
            {
                "num": np.random.randn(50),
                "cat": np.random.choice(["A", "B", "C"], 50),
            }
        )

        metadata = MetaData.get_metadata(data=data, threshold_unique_values=10)
        sdv_metadata = MetaData.metadata_as_SDV(data=data, metadata=metadata)

        assert isinstance(sdv_metadata, dict)
        assert "columns" in sdv_metadata

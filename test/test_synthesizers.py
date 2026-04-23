"""
Tests for synomicsbench synthesizer modules.

Note: Some tests require optional dependencies and will be skipped if not available.
"""

import os
import numpy as np
import pandas as pd
import pytest


TEST_DATA_DIR = os.path.join(os.path.dirname(__file__), "test_data")


@pytest.fixture
def sample_data():
    np.random.seed(42)
    n = 50
    return pd.DataFrame({
        "id": [f"P{i:03d}" for i in range(n)],
        "age": np.random.randint(40, 80, n),
        "score": np.random.randn(n),
        "category": np.random.choice(["A", "B", "C"], n),
    })


@pytest.fixture
def sample_metadata():
    return {
        "columns": {
            "id": {"sdtype": "id"},
            "age": {"sdtype": "numerical"},
            "score": {"sdtype": "numerical"},
            "category": {"sdtype": "categorical"},
        }
    }


class TestBaseSynthesizer:
    """Tests for BaseSynthesizer class."""

    def test_import_base_synthesizer(self):
        from synomicsbench.synthesizer.BaseSynthesizer import BaseSynthesizer
        assert BaseSynthesizer is not None


class TestGaussianCopulaSynthesizer:
    """Tests for GaussianCopulasynthesizer class."""

    def test_import_gc(self):
        from synomicsbench.synthesizer.GaussianCopulasynthesizer import GaussianCopulasynthesizer
        assert GaussianCopulasynthesizer is not None


class TestCTGANSynthesizer:
    """Tests for CTGANSynthesizer class."""

    def test_import_ctgan(self):
        from synomicsbench.synthesizer.CTGANsynthesizer import CTGANsynthesizer
        assert CTGANsynthesizer is not None


class TestTVAESynthesizer:
    """Tests for TVAESynthesizer class."""

    def test_import_tvae(self):
        from synomicsbench.synthesizer.TVAEsynthesizer import TVAEsynthesizer
        assert TVAEsynthesizer is not None


class TestSynthpopSynthesizer:
    """Tests for SynthpopSynthesizer class."""

    def test_import_synthpop(self):
        try:
            from synomicsbench.synthesizer.Synthpopsynthesizer import SynthpopSynthesizer
            assert SynthpopSynthesizer is not None
        except (ImportError, RuntimeError, FileNotFoundError) as e:
            pytest.skip(f"SynthpopSynthesizer tests skipped because R or rpy2 is not properly configured: {e}")

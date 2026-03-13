"""
Tests for SynOmics GSEA and narrow utility modules.
"""

import numpy as np
import pandas as pd
import pytest


class TestGSEAAnalyzer:
    """Tests for GSEA PCSAnalyzer class."""

    @pytest.fixture
    def sample_gsea_data(self):
        rng = np.random.default_rng(42)
        n_pathways = 50
        pathways = [f"Pathway_{i}" for i in range(n_pathways)]
        
        ori = pd.DataFrame({
            "Term": pathways,
            "NES": rng.normal(0, 2, n_pathways),
            "FDR q-val": rng.uniform(0.001, 0.5, n_pathways),
        })
        
        syn = pd.DataFrame({
            "Term": pathways,
            "NES": rng.normal(0, 2, n_pathways),
            "FDR q-val": rng.uniform(0.001, 0.5, n_pathways),
        })
        
        return ori, syn

    def test_pcs_analyzer_init(self):
        from SynOmics.metrics.narrow_utility.GSEA import PCSAnalyzer
        
        analyzer = PCSAnalyzer(
            term_col="Term",
            nes_col="NES",
            q_col="FDR q-val",
            q_thr=0.05,
            w=0.5
        )
        
        assert analyzer.q_thr == 0.05
        assert analyzer.w == 0.5

    def test_pcs_analyzer_default_init(self):
        from SynOmics.metrics.narrow_utility.GSEA import PCSAnalyzer
        
        analyzer = PCSAnalyzer()
        
        assert analyzer.q_thr == 0.05
        assert analyzer.w == 0.5


class TestPredictiveModelComparator:
    """Tests for PredictiveModelComparator class."""

    def test_import(self):
        from SynOmics.metrics.narrow_utility import predictive_model_comp
        assert predictive_model_comp is not None


class TestNarrowUtilityBayesianComparison:
    """Tests for narrow utility BayesianComparison module."""

    def test_import(self):
        try:
            from SynOmics.metrics.narrow_utility.BayesianComparison import BayesianComparison
            assert BayesianComparison is not None
        except ImportError:
            pytest.skip("Module not available")


class TestVisualization:
    """Tests for visualization utilities."""

    def test_import_visualization_module(self):
        from SynOmics.metrics.fidelity import visualization
        assert visualization is not None

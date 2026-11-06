"""
Tests for synomicsbench GSEA and narrow utility modules.
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
        from synomicsbench.metrics.narrow_utility.GSEA import PCSAnalyzer
        
        analyzer = PCSAnalyzer(
            term_col="Term",
            nes_col="NES",
            sig_col="NOM p-val",
            sig_thr=0.01,
        )
        
        assert analyzer.sig_col == "NOM p-val"
        assert analyzer.sig_thr == 0.01

    def test_pcs_analyzer_default_init(self):
        from synomicsbench.metrics.narrow_utility.GSEA import PCSAnalyzer
        
        analyzer = PCSAnalyzer()
        
        assert analyzer.sig_col == "FDR q-val"
        assert analyzer.sig_thr == 0.05

    def test_compute_metrics(self, sample_gsea_data):
        from synomicsbench.metrics.narrow_utility.GSEA import PCSAnalyzer

        ori, syn = sample_gsea_data
        analyzer = PCSAnalyzer()
        scores = analyzer.compute_metrics(ori, syn)
        _, _, result = analyzer.process_single_gsea_result(ori, syn)
        assert scores["F1"] == result.f1
        assert analyzer.compute_metrics(ori, ori.copy(), metrics="F1") == pytest.approx(1.0)

    def test_no_significant_synthetic_pathway(self, sample_gsea_data):
        from synomicsbench.metrics.narrow_utility.GSEA import PCSAnalyzer

        ori, _ = sample_gsea_data
        scores = PCSAnalyzer().compute_metrics(ori, ori.assign(**{"FDR q-val": 0.9}),
                                               metrics=["Precision", "F1"])
        assert np.isnan(scores["Precision"])
        assert scores["F1"] == 0.0


class TestPredictiveModelComparator:
    """Tests for PredictiveModelComparator class."""

    def test_import(self):
        from synomicsbench.metrics.narrow_utility import predictive_model_comp
        assert predictive_model_comp is not None


class TestNarrowUtilityBayesianComparison:
    """Tests for narrow utility BayesianComparison module."""

    def test_import(self):
        try:
            from synomicsbench.metrics.narrow_utility.BayesianComparison import BayesianComparison
            assert BayesianComparison is not None
        except ImportError:
            pytest.skip("Module not available")


class TestVisualization:
    """Tests for visualization utilities."""

    def test_import_visualization_module(self):
        from synomicsbench.metrics.fidelity import visualization
        assert visualization is not None

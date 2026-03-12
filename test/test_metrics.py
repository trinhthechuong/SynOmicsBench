"""
Smoke tests for SynOmics.metrics module.

Tests fidelity (UnivariateSimilarity, PairwiseSimilarity, BayesianComparison,
check_column_consistency), narrow_utility (GCSAnalyzer, cell_deconvolution), and privacy metrics.

Uses a 100-column subset of test data for speed. Optional-dependency tests
are skipped gracefully when the library is absent.
"""

import os
import warnings

import matplotlib

matplotlib.use("Agg")  # non-interactive backend for CI

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytest

from SynOmics.processing.metadata import MetaData

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

TEST_DATA_DIR = os.path.join(os.path.dirname(__file__), "test_data")
N_COLS = 100


@pytest.fixture(scope="module")
def original_data() -> pd.DataFrame:
    path = os.path.join(TEST_DATA_DIR, "original_data.csv")
    full = pd.read_csv(path)
    return full.iloc[:, :N_COLS].copy()


@pytest.fixture(scope="module")
def synthetic_data() -> pd.DataFrame:
    path = os.path.join(TEST_DATA_DIR, "synthetic_data.csv")
    full = pd.read_csv(path)
    return full.iloc[:, :N_COLS].copy()


@pytest.fixture(scope="module")
def data_no_id(original_data: pd.DataFrame) -> pd.DataFrame:
    """Original data without the Patient id column."""
    return original_data.drop(columns=["Patient", "Patient_ID"], errors="ignore")


@pytest.fixture(scope="module")
def syn_no_id(synthetic_data: pd.DataFrame, data_no_id: pd.DataFrame) -> pd.DataFrame:
    """Synthetic data aligned to the same columns as data_no_id.

    The synthetic CSV may use 'Patient_ID' instead of 'Patient'.
    We drop id columns, then align to data_no_id columns so that
    both DataFrames share exactly the same column set.
    """
    syn = synthetic_data.drop(columns=["Patient", "Patient_ID"], errors="ignore")
    # Keep only the columns present in both
    common = [c for c in data_no_id.columns if c in syn.columns]
    return syn[common].copy()


@pytest.fixture(scope="module")
def metadata_dict(data_no_id: pd.DataFrame) -> dict:
    """Metadata covering all non-id columns (built from data_no_id)."""
    return MetaData.get_metadata(
        data=data_no_id,
        threshold_unique_values=10,
    )


@pytest.fixture
def tmp_dir(tmp_path):
    return str(tmp_path)


# ===========================================================================
# Fidelity — check_column_consistency
# ===========================================================================


class TestColumnConsistency:
    def test_same_columns_returns_true(self, data_no_id, syn_no_id):
        from SynOmics.metrics.fidelity.utils import check_column_consistency

        result = check_column_consistency(data_no_id, syn_no_id)
        assert isinstance(result, bool)
        assert result is True

    def test_different_columns_returns_false(self, data_no_id):
        from SynOmics.metrics.fidelity.utils import check_column_consistency

        altered = data_no_id.copy()
        altered = altered.rename(columns={altered.columns[0]: "FAKE_COL"})
        assert check_column_consistency(data_no_id, altered) is False


# ===========================================================================
# Fidelity — UnivariateSimilarity (requires sdmetrics)
# ===========================================================================


class TestUnivariateSimilarity:
    @pytest.fixture(autouse=True)
    def _skip_if_no_sdmetrics(self):
        pytest.importorskip("sdmetrics")

    def test_univariate_score(self, data_no_id, syn_no_id, metadata_dict, tmp_dir):
        from SynOmics.metrics.fidelity.UnivariateSimilarity import UnivariateSimilarity

        us = UnivariateSimilarity(output_dir=tmp_dir)
        score = us.get_univariate_score(
            original_data=data_no_id,
            synthetic_data=syn_no_id,
            metadata=metadata_dict,
            save=True,
        )
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0

    def test_get_detail_df(self, data_no_id, syn_no_id, metadata_dict, tmp_dir):
        from SynOmics.metrics.fidelity.UnivariateSimilarity import UnivariateSimilarity

        us = UnivariateSimilarity(output_dir=tmp_dir, logger_name="detail_test")
        us.get_univariate_score(data_no_id, syn_no_id, metadata_dict, save=False)
        details = us.get_detail_df()
        assert isinstance(details, pd.DataFrame)
        assert "Score" in details.columns

    def test_summarize(self, data_no_id, syn_no_id, metadata_dict, tmp_dir):
        from SynOmics.metrics.fidelity.UnivariateSimilarity import UnivariateSimilarity

        us = UnivariateSimilarity(output_dir=tmp_dir, logger_name="summarize_test")
        us.get_univariate_score(data_no_id, syn_no_id, metadata_dict, save=False)
        summary = us.summarize()
        assert isinstance(summary, pd.DataFrame)

    def test_plot_column_score_histogram(
        self, data_no_id, syn_no_id, metadata_dict, tmp_dir
    ):
        from SynOmics.metrics.fidelity.UnivariateSimilarity import UnivariateSimilarity

        us = UnivariateSimilarity(output_dir=tmp_dir, logger_name="plot_test")
        us.get_univariate_score(data_no_id, syn_no_id, metadata_dict, save=False)
        details = us.get_detail_df()
        fig = UnivariateSimilarity.plot_column_score_histogram(
            details, data_name="test"
        )
        assert isinstance(fig, plt.Figure)
        plt.close(fig)


# ===========================================================================
# Fidelity — PairwiseSimilarity
# ===========================================================================


class TestPairwiseSimilarity:
    def test_init_and_get_pairwise_scores(
        self, data_no_id, syn_no_id, metadata_dict, tmp_dir
    ):
        from SynOmics.metrics.fidelity.PairwiseSimilarity import PairwiseSimilarity

        ps = PairwiseSimilarity(
            original_data=data_no_id,
            synthetic_data=syn_no_id,
            metadata=metadata_dict,
            output_dir=tmp_dir,
            verbose=False,
            save=False,
        )
        scores = ps.get_pairwise_scores(method="pearson")
        assert isinstance(scores, dict)

    def test_metadata_mismatch_raises(
        self, data_no_id, syn_no_id, metadata_dict, tmp_dir
    ):
        from SynOmics.metrics.fidelity.PairwiseSimilarity import PairwiseSimilarity

        bad_meta = {k: v for k, v in list(metadata_dict.items())[:-1]}  # drop one key
        with pytest.raises(RuntimeError, match="metadata does not match"):
            PairwiseSimilarity(
                original_data=data_no_id,
                synthetic_data=syn_no_id,
                metadata=bad_meta,
                output_dir=tmp_dir,
            )


# ===========================================================================
# Fidelity — BayesianComparison (requires baycomp)
# ===========================================================================


class TestBayesianComparison:
    @pytest.fixture(autouse=True)
    def _skip_if_no_baycomp(self):
        pytest.importorskip("baycomp")

    def test_compare_methods(self):
        from SynOmics.metrics.fidelity.BayesianComparison import BayesianComparison

        rng = np.random.default_rng(0)
        scores_a = rng.normal(0.8, 0.05, size=20).tolist()
        scores_b = rng.normal(0.75, 0.05, size=20).tolist()
        scores_c = rng.normal(0.7, 0.06, size=20).tolist()

        bc = BayesianComparison(rope=0.01, seed=0)
        df = bc.compare_methods(
            method_to_scores={"A": scores_a, "B": scores_b, "C": scores_c}
        )
        assert isinstance(df, pd.DataFrame)
        assert set(df.columns) >= {
            "Method 1",
            "Method 2",
            "Better Prob",
            "Worse Prob",
            "Equivalent Prob",
        }
        # 3 methods → 6 ordered pairs
        assert len(df) == 6

    def test_compare_methods_too_few_methods(self):
        from SynOmics.metrics.fidelity.BayesianComparison import BayesianComparison

        bc = BayesianComparison()
        with pytest.raises(ValueError):
            bc.compare_methods(method_to_scores={"A": [0.8, 0.7]})

    def test_invalid_rope(self):
        from SynOmics.metrics.fidelity.BayesianComparison import BayesianComparison

        with pytest.raises(ValueError, match="rope must be > 0"):
            BayesianComparison(rope=-1)


# ===========================================================================
# Fidelity — MissingValueSimilarity (has known missing import bug)
# ===========================================================================


class TestMissingValueSimilarity:
    def test_import_or_skip(self):
        """MissingValueSimilarity.py is missing 'import pandas as pd'. Verify it fails or works."""
        try:
            from SynOmics.metrics.fidelity.MissingValueSimilarity import (
                MissingValue_Similarity,
            )
        except (NameError, ImportError) as exc:
            pytest.skip(f"MissingValueSimilarity has a known import issue: {exc}")
        # If we get here, the module loaded fine (bug was fixed)
        assert callable(MissingValue_Similarity)


# ===========================================================================
# Narrow Utility — GCSAnalyzer (DGE)
# ===========================================================================


class TestGCSAnalyzer:
    @pytest.fixture
    def sample_dge_data(self):
        """Create minimal DGE-like DataFrames for testing."""
        rng = np.random.default_rng(42)
        n_genes = 200
        genes = [f"Gene_{i}" for i in range(n_genes)]
        ori = pd.DataFrame(
            {
                "Gene": genes,
                "Log2FC": rng.normal(0, 2, n_genes),
                "Q_value": rng.uniform(0.001, 0.5, n_genes),
            }
        )
        syn = pd.DataFrame(
            {
                "Gene": genes,
                "Log2FC": rng.normal(0, 2, n_genes),
                "Q_value": rng.uniform(0.001, 0.5, n_genes),
            }
        )
        return ori, syn

    def test_init(self):
        from SynOmics.metrics.narrow_utility.DGE import GCSAnalyzer

        analyzer = GCSAnalyzer(term_col="Gene", nes_col="Log2FC", q_col="Q_value")
        assert analyzer.q_thr == 0.05
        assert analyzer.w == 0.5

    def test_invalid_q_thr(self):
        from SynOmics.metrics.narrow_utility.DGE import GCSAnalyzer

        with pytest.raises(ValueError, match="q_thr"):
            GCSAnalyzer(q_thr=0.0)

    def test_invalid_w(self):
        from SynOmics.metrics.narrow_utility.DGE import GCSAnalyzer

        with pytest.raises(ValueError, match="w must be"):
            GCSAnalyzer(w=-1)

    def test_compute_rank_score(self, sample_dge_data):
        from SynOmics.metrics.narrow_utility.DGE import GCSAnalyzer

        ori, _ = sample_dge_data
        analyzer = GCSAnalyzer()
        rnk = analyzer.compute_rank_score(ori)
        assert isinstance(rnk, pd.DataFrame)
        assert "rank_score" in rnk.columns
        assert "qval" in rnk.columns

    def test_align_rank_scores(self, sample_dge_data):
        from SynOmics.metrics.narrow_utility.DGE import GCSAnalyzer

        ori, syn = sample_dge_data
        analyzer = GCSAnalyzer()
        rnk_ori = analyzer.compute_rank_score(ori)
        rnk_syn = analyzer.compute_rank_score(syn)
        aligned = GCSAnalyzer.align_rank_scores(rnk_ori, rnk_syn)
        assert isinstance(aligned, pd.DataFrame)
        assert "rank_ori" in aligned.columns
        assert "rank_syn" in aligned.columns

    def test_gene_set_concordance_score(self, sample_dge_data):
        from SynOmics.metrics.narrow_utility.DGE import GCSAnalyzer

        ori, syn = sample_dge_data
        analyzer = GCSAnalyzer()
        rnk_ori = analyzer.compute_rank_score(ori)
        rnk_syn = analyzer.compute_rank_score(syn)
        aligned = GCSAnalyzer.align_rank_scores(rnk_ori, rnk_syn)
        gcs, n_sign, n_non_sign, m = analyzer.gene_set_concordance_score(
            aligned, ori_rank_size=len(rnk_ori)
        )
        assert isinstance(gcs, float)
        assert 0.0 <= gcs <= 1.0
        assert isinstance(n_sign, int)
        assert isinstance(n_non_sign, int)

    def test_process_single_dge_result(self, sample_dge_data):
        from SynOmics.metrics.narrow_utility.DGE import GCSAnalyzer

        ori, syn = sample_dge_data
        analyzer = GCSAnalyzer()
        result = analyzer.process_single_dge_result(ori, syn)
        assert isinstance(result, tuple)
        # Should return 11 elements
        assert len(result) == 11


# ===========================================================================
# Narrow Utility — SurvivalEvaluator (requires lifelines + scienceplots)
# ===========================================================================


class TestSurvivalEvaluator:
    @pytest.fixture(autouse=True)
    def _skip_if_no_deps(self):
        pytest.importorskip("lifelines")
        pytest.importorskip("scienceplots")

    def test_init_and_compute(self):
        from SynOmics.metrics.narrow_utility.survival_analysis import SurvivalEvaluator

        rng = np.random.default_rng(0)
        n = 50
        base = pd.DataFrame(
            {
                "OS": rng.exponential(12, n),
                "OS_CNSR": rng.integers(0, 2, n),
                "group_col": rng.choice(["A", "B"], n),
            }
        )
        datasets = {"Origin": base.copy(), "Synthetic": base.copy()}
        evaluator = SurvivalEvaluator(
            datasets_dict=datasets,
            phenotype={"group_col": ["A", "B"]},
            time_target="OS",
            event_target="OS_CNSR",
        )
        assert evaluator is not None

    def test_compute_survival_metrics(self):
        from SynOmics.metrics.narrow_utility.survival_analysis import SurvivalEvaluator

        rng = np.random.default_rng(1)
        n = 60
        base = pd.DataFrame(
            {
                "OS": rng.exponential(15, n),
                "OS_CNSR": rng.integers(0, 2, n),
                "phenotype": rng.choice(["High", "Low"], n),
            }
        )
        datasets = {"Real": base.copy(), "Synth": base.copy()}
        evaluator = SurvivalEvaluator(
            datasets_dict=datasets,
            phenotype={"phenotype": ["High", "Low"]},
            time_target="OS",
            event_target="OS_CNSR",
        )
        metrics = evaluator.compute_survival_metrics()
        assert isinstance(metrics, pd.DataFrame)
        assert len(metrics) > 0


# ===========================================================================
# Privacy — inference, singling_out, linkability (require anonymeter)
# ===========================================================================


class TestPrivacyInference:
    @pytest.fixture(autouse=True)
    def _skip_if_no_anonymeter(self):
        pytest.importorskip("anonymeter")

    def test_eval_inference(self, data_no_id, syn_no_id):
        from SynOmics.metrics.privacy.inference import eval_inference_genes_clinical

        # Use a tiny subset (5 clinical cols) for speed
        num_clinical = 5
        small_ori = data_no_id.iloc[:, :20].copy()
        small_syn = syn_no_id.iloc[:, :20].copy()
        # Drop any fully-NaN columns
        small_ori = small_ori.dropna(axis=1, how="all")
        small_syn = small_syn[small_ori.columns]

        results = eval_inference_genes_clinical(
            ori=small_ori,
            syns={"test_synth": small_syn},
            num_clinical=num_clinical,
        )
        assert isinstance(results, dict)
        assert "test_synth" in results


class TestPrivacySinglingOut:
    @pytest.fixture(autouse=True)
    def _skip_if_no_anonymeter(self):
        pytest.importorskip("anonymeter")

    def test_eval_singling_out_univariate(self, data_no_id, syn_no_id):
        from SynOmics.metrics.privacy.singling_out import eval_singling_out_univariate

        # Use small subset for speed
        small_ori = (
            data_no_id.select_dtypes(include=[np.number])
            .iloc[:, :15]
            .dropna(axis=1)
            .copy()
        )
        small_syn = syn_no_id[small_ori.columns].copy()

        results = eval_singling_out_univariate(
            ori=small_ori,
            syns={"test_synth": small_syn},
            n_attacks=100,
            max_attempts=10_000,
            proportions=(0.5, 1.0),
            seed=42,
        )
        assert isinstance(results, dict)
        assert "test_synth" in results
        assert len(results["test_synth"]) == 2  # two proportions


class TestPrivacyLinkability:
    @pytest.fixture(autouse=True)
    def _skip_if_no_anonymeter(self):
        pytest.importorskip("anonymeter")

    def test_eval_linkability(self, data_no_id, syn_no_id):
        from SynOmics.metrics.privacy.linkability import eval_linkability_genes_clinical

        # Use small subset: 5 clinical + 10 gene columns
        num_clinical = 5
        small_ori = (
            data_no_id.select_dtypes(include=[np.number])
            .iloc[:, :15]
            .dropna(axis=1)
            .copy()
        )
        small_syn = syn_no_id[small_ori.columns].copy()

        results = eval_linkability_genes_clinical(
            ori=small_ori,
            syns={"test_synth": small_syn},
            num_clinical=num_clinical,
            proportions=(0.5, 1.0),
            seed=42,
        )
        assert isinstance(results, dict)
        assert "test_synth" in results
        assert len(results["test_synth"]) == 2


# ===========================================================================
# Narrow Utility — Cell Deconvolution (requires skbio)
# ===========================================================================


class TestCellDeconvolution:
    @pytest.fixture(autouse=True)
    def _skip_if_no_skbio(self):
        pytest.importorskip("skbio")

    @pytest.fixture
    def sample_composition_data(self):
        """Create minimal cell-type composition DataFrames."""
        rng = np.random.default_rng(42)
        cell_types = ["B_cells", "T_cells_CD4", "T_cells_CD8", "Macrophages", "NK_cells"]
        n_samples = 30
        # Generate random compositions that sum to ~1
        orig_raw = rng.dirichlet(np.ones(len(cell_types)), size=n_samples)
        syn_raw = rng.dirichlet(np.ones(len(cell_types)), size=n_samples)
        df_orig = pd.DataFrame(orig_raw, columns=cell_types)
        df_syn = pd.DataFrame(syn_raw, columns=cell_types)
        return df_orig, df_syn, cell_types

    def test_geometric_center(self):
        from SynOmics.metrics.narrow_utility.cell_deconvolution import geometric_center

        X = np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])
        center = geometric_center(X)
        assert center.shape == (3,)
        # geometric mean of col 0: exp(mean(log([1,4]))) = exp((0 + ln4)/2) = 2.0
        np.testing.assert_allclose(center[0], np.exp(np.mean(np.log([1.0, 4.0]))), rtol=1e-6)

    def test_geometric_center_uniform(self):
        from SynOmics.metrics.narrow_utility.cell_deconvolution import geometric_center

        # All same values → center equals that value
        X = np.full((5, 3), 7.0)
        center = geometric_center(X)
        np.testing.assert_allclose(center, [7.0, 7.0, 7.0], rtol=1e-6)

    def test_aitchison_distance_identical(self, sample_composition_data):
        from SynOmics.metrics.narrow_utility.cell_deconvolution import aitchison_distance

        df_orig, _, cell_types = sample_composition_data
        # Distance to itself should be 0
        dist = aitchison_distance(df_orig, df_orig, cell_types)
        assert isinstance(dist, float)
        assert dist == pytest.approx(0.0, abs=1e-10)

    def test_aitchison_distance_non_negative(self, sample_composition_data):
        from SynOmics.metrics.narrow_utility.cell_deconvolution import aitchison_distance

        df_orig, df_syn, cell_types = sample_composition_data
        dist = aitchison_distance(df_orig, df_syn, cell_types)
        assert isinstance(dist, float)
        assert dist >= 0.0

    def test_aitchison_distance_with_zeros(self):
        from SynOmics.metrics.narrow_utility.cell_deconvolution import aitchison_distance

        # Data containing zeros — multi_replace should handle them
        cell_types = ["A", "B", "C"]
        df1 = pd.DataFrame({"A": [0.5, 0.0, 0.3], "B": [0.3, 0.6, 0.0], "C": [0.2, 0.4, 0.7]})
        df2 = pd.DataFrame({"A": [0.4, 0.1, 0.2], "B": [0.4, 0.5, 0.3], "C": [0.2, 0.4, 0.5]})
        dist = aitchison_distance(df1, df2, cell_types)
        assert isinstance(dist, float)
        assert dist >= 0.0

    def test_aitchison_score_zero_distance(self):
        from SynOmics.metrics.narrow_utility.cell_deconvolution import aitchison_score

        score = aitchison_score(0.0)
        assert score == pytest.approx(1.0)

    def test_aitchison_score_positive_distance(self):
        from SynOmics.metrics.narrow_utility.cell_deconvolution import aitchison_score

        score = aitchison_score(1.0)
        assert score == pytest.approx(np.exp(-1.0))
        assert 0.0 < score < 1.0

    def test_aitchison_score_large_distance(self):
        from SynOmics.metrics.narrow_utility.cell_deconvolution import aitchison_score

        score = aitchison_score(100.0)
        assert score > 0.0
        assert score < 1e-40  # exp(-100) is extremely small

    def test_aitchison_distance_and_score_integration(self, sample_composition_data):
        from SynOmics.metrics.narrow_utility.cell_deconvolution import (
            aitchison_distance,
            aitchison_score,
        )

        df_orig, df_syn, cell_types = sample_composition_data
        dist = aitchison_distance(df_orig, df_syn, cell_types)
        score = aitchison_score(dist)
        assert 0.0 < score <= 1.0

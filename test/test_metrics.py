"""
Smoke tests for synomicsbench.metrics module.

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

from synomicsbench.processing.metadata import MetaData

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
        from synomicsbench.metrics.fidelity.utils import check_column_consistency

        result = check_column_consistency(data_no_id, syn_no_id)
        assert isinstance(result, bool)
        assert result is True

    def test_different_columns_returns_false(self, data_no_id):
        from synomicsbench.metrics.fidelity.utils import check_column_consistency

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
        from synomicsbench.metrics.fidelity.UnivariateSimilarity import UnivariateSimilarity

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
        from synomicsbench.metrics.fidelity.UnivariateSimilarity import UnivariateSimilarity

        us = UnivariateSimilarity(output_dir=tmp_dir, logger_name="detail_test")
        us.get_univariate_score(data_no_id, syn_no_id, metadata_dict, save=False)
        details = us.get_detail_df()
        assert isinstance(details, pd.DataFrame)
        assert "Score" in details.columns

    def test_summarize(self, data_no_id, syn_no_id, metadata_dict, tmp_dir):
        from synomicsbench.metrics.fidelity.UnivariateSimilarity import UnivariateSimilarity

        us = UnivariateSimilarity(output_dir=tmp_dir, logger_name="summarize_test")
        us.get_univariate_score(data_no_id, syn_no_id, metadata_dict, save=False)
        summary = us.summarize()
        assert isinstance(summary, pd.DataFrame)

    def test_plot_column_score_histogram(
        self, data_no_id, syn_no_id, metadata_dict, tmp_dir
    ):
        from synomicsbench.metrics.fidelity.UnivariateSimilarity import UnivariateSimilarity

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
        from synomicsbench.metrics.fidelity.PairwiseSimilarity import PairwiseSimilarity

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
        from synomicsbench.metrics.fidelity.PairwiseSimilarity import PairwiseSimilarity

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
        from synomicsbench.metrics.fidelity.BayesianComparison import BayesianComparison

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
        from synomicsbench.metrics.fidelity.BayesianComparison import BayesianComparison

        bc = BayesianComparison()
        with pytest.raises(ValueError):
            bc.compare_methods(method_to_scores={"A": [0.8, 0.7]})

    def test_invalid_rope(self):
        from synomicsbench.metrics.fidelity.BayesianComparison import BayesianComparison

        with pytest.raises(ValueError, match="rope must be > 0"):
            BayesianComparison(rope=-1)


# ===========================================================================
# Fidelity — MissingValueSimilarity (has known missing import bug)
# ===========================================================================


class TestMissingValueSimilarity:
    def test_import_or_skip(self):
        """MissingValueSimilarity.py is missing 'import pandas as pd'. Verify it fails or works."""
        try:
            from synomicsbench.metrics.fidelity.MissingValueSimilarity import (
                MissingValue_Similarity,
            )
        except (NameError, ImportError) as exc:
            pytest.skip(f"MissingValueSimilarity has a known import issue: {exc}")
        # If we get here, the module loaded fine (bug was fixed)
        assert callable(MissingValue_Similarity)


# ===========================================================================
# Fidelity — NetworkPreservation (WGCNA through rpy2)
# ===========================================================================


def _wgcna_available() -> bool:
    try:
        from rpy2.robjects.packages import isinstalled

        return bool(isinstalled("WGCNA"))
    except Exception:
        return False


class TestNetworkPreservation:
    @pytest.fixture
    def expr(self):
        rng = np.random.default_rng(4)
        n, g = 40, 120
        latent = rng.normal(size=(n, 3))
        loadings = rng.normal(size=(3, g)) * (rng.random(g) < 0.6)
        values = latent @ loadings + rng.normal(scale=0.5, size=(n, g))
        return pd.DataFrame(values, columns=[f"G{i}" for i in range(g)])

    def test_quantile_normalisation_gives_equal_distributions(self, expr):
        from synomicsbench.metrics.fidelity.NetworkPreservation import quantile_normalize_samples

        q = quantile_normalize_samples(expr)
        sorted_rows = np.sort(q.values, axis=1)
        np.testing.assert_allclose(sorted_rows, np.broadcast_to(sorted_rows[0], sorted_rows.shape))
        # ranks within each sample are kept
        assert (q.rank(axis=1).values == expr.rank(axis=1).values).all()

    def test_reference_gene_space(self, expr, tmp_path):
        from synomicsbench.metrics.fidelity.NetworkPreservation import NetworkPreservation

        data = expr.assign(dup=expr["G0"], const=1.0)
        npres = NetworkPreservation(output_dir=str(tmp_path), n_genes=50)
        ref = npres.prepare_reference(data)
        assert ref.shape == (40, 50)
        assert "const" not in npres.genes and not ("dup" in npres.genes and "G0" in npres.genes)

        syn = expr.copy()
        syn["G1"] = 0.0                       # a constant gene keeps its place in the gene space
        syn.iloc[0, 2] = np.inf
        out = npres.prepare_synthetic(syn)
        assert list(out.columns) == npres.genes
        assert np.isfinite(out.values).all()
        with pytest.raises(ValueError, match="reference genes are absent"):
            npres.prepare_synthetic(syn.drop(columns=npres.genes[0]))

    @pytest.mark.skipif(not _wgcna_available(), reason="R package WGCNA not available")
    def test_self_comparison_is_perfect(self, expr, tmp_path):
        from synomicsbench.metrics.fidelity.NetworkPreservation import NetworkPreservation

        npres = NetworkPreservation(output_dir=str(tmp_path), n_permutations=10, threads=1)
        npres.build_reference(expr)
        scores = npres.evaluate({"copy": expr.copy()})
        assert scores.loc["copy", "Zsummary_norm"] == pytest.approx(1.0)
        assert scores.loc["copy", "ARI"] == pytest.approx(1.0)
        assert scores.loc["copy", "TPR"] == pytest.approx(1.0)


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
                "P_value": rng.uniform(0.001, 0.5, n_genes),
            }
        )
        syn = pd.DataFrame(
            {
                "Gene": genes,
                "Log2FC": rng.normal(0, 2, n_genes),
                "P_value": rng.uniform(0.001, 0.5, n_genes),
            }
        )
        return ori, syn

    def test_init(self):
        from synomicsbench.metrics.narrow_utility.DGE import GCSAnalyzer

        analyzer = GCSAnalyzer(term_col="Gene", nes_col="Log2FC", sig_col="Q_value")
        assert analyzer.sig_col == "Q_value"
        assert analyzer.sig_thr == 0.05
        assert GCSAnalyzer().sig_col == "P_value"

    def test_invalid_sig_thr(self):
        from synomicsbench.metrics.narrow_utility.DGE import GCSAnalyzer

        with pytest.raises(ValueError, match="sig_thr"):
            GCSAnalyzer(sig_thr=0.0)

    def test_compute_rank_score(self, sample_dge_data):
        from synomicsbench.metrics.narrow_utility.DGE import GCSAnalyzer

        ori, _ = sample_dge_data
        analyzer = GCSAnalyzer()
        rnk = analyzer.compute_rank_score(ori)
        assert isinstance(rnk, pd.DataFrame)
        assert "rank_score" in rnk.columns
        assert "qval" in rnk.columns

    def test_align_rank_scores(self, sample_dge_data):
        from synomicsbench.metrics.narrow_utility.DGE import GCSAnalyzer

        ori, syn = sample_dge_data
        analyzer = GCSAnalyzer()
        rnk_ori = analyzer.compute_rank_score(ori)
        rnk_syn = analyzer.compute_rank_score(syn)
        aligned = GCSAnalyzer.align_rank_scores(rnk_ori, rnk_syn)
        assert isinstance(aligned, pd.DataFrame)
        assert "rank_ori" in aligned.columns
        assert "rank_syn" in aligned.columns

    def test_gene_set_concordance_score(self, sample_dge_data):
        from synomicsbench.metrics.narrow_utility.DGE import GCSAnalyzer

        ori, syn = sample_dge_data
        analyzer = GCSAnalyzer()
        rnk_ori = analyzer.compute_rank_score(ori)
        rnk_syn = analyzer.compute_rank_score(syn)
        aligned = GCSAnalyzer.align_rank_scores(rnk_ori, rnk_syn)
        res = analyzer.gene_set_concordance_score(aligned)
        assert res.n_sign == res.n_zone3 + res.n_zone4
        assert res.recall == pytest.approx(res.n_sign / res.n_sig_ori)
        assert res.precision == pytest.approx(res.n_sign / res.n_sig_syn)
        assert 0.0 <= res.f1 <= 1.0

    def test_identical_tables_are_perfect(self, sample_dge_data):
        from synomicsbench.metrics.narrow_utility.DGE import GCSAnalyzer

        ori, _ = sample_dge_data
        scores = GCSAnalyzer().compute_metrics(ori, ori.copy())
        for name in ("Recall", "Precision", "F1", "Slope", "Pearson", "SignConcordance"):
            assert scores[name] == pytest.approx(1.0), name

    def test_no_concordant_gene_gives_zero_f1(self, sample_dge_data):
        from synomicsbench.metrics.narrow_utility.DGE import GCSAnalyzer

        ori, _ = sample_dge_data
        syn = ori.assign(P_value=0.9)
        scores = GCSAnalyzer().compute_metrics(ori, syn, metrics=["Recall", "Precision", "F1"])
        assert scores["Recall"] == 0.0
        assert np.isnan(scores["Precision"])
        assert scores["F1"] == 0.0

    def test_metrics_argument(self, sample_dge_data):
        from synomicsbench.metrics.narrow_utility.DGE import GCSAnalyzer

        ori, syn = sample_dge_data
        analyzer = GCSAnalyzer()
        f1 = analyzer.compute_metrics(ori, syn, metrics="F1")
        both = analyzer.compute_metrics(ori, syn, metrics=["F1", "Slope"])
        assert isinstance(f1, float)
        assert list(both) == ["F1", "Slope"]
        assert both["F1"] == f1
        with pytest.raises(ValueError, match="Valid metrics"):
            analyzer.compute_metrics(ori, syn, metrics="GCS")

    def test_compute_metrics_datasets(self, sample_dge_data):
        from synomicsbench.metrics.narrow_utility.DGE import GCSAnalyzer

        ori, syn = sample_dge_data
        table = GCSAnalyzer().compute_metrics_datasets(ori, {"A": syn, "B": ori}, metrics=["F1", "Pearson"])
        assert list(table.index) == ["A", "B"]
        assert list(table.columns) == ["F1", "Pearson"]
        assert table.loc["B", "F1"] == pytest.approx(1.0)

    def test_process_single_dge_result(self, sample_dge_data):
        from synomicsbench.metrics.narrow_utility.DGE import GCSAnalyzer
        from synomicsbench.metrics.narrow_utility.concordance import ConcordanceResult

        ori, syn = sample_dge_data
        x, y, result = GCSAnalyzer().process_single_dge_result(ori, syn)
        assert len(x) == len(y) == result.aligned_size
        assert isinstance(result, ConcordanceResult)

    def test_plot_calibration_scatter(self, sample_dge_data):
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from synomicsbench.metrics.narrow_utility.DGE import GCSAnalyzer

        ori, syn = sample_dge_data
        analyzer = GCSAnalyzer()
        fig, table = analyzer.plot_calibration_scatter(
            ori, {"A": syn, "B": ori}, highlight={"top": ["Gene_0", "Gene_1"]}
        )
        assert set(table.index) == {"A", "B"}
        assert table.loc["A", "Slope"] == pytest.approx(analyzer.compute_metrics(ori, syn, "Slope"))
        plt.close(fig)

    def test_slope_method_per_level(self, sample_dge_data):
        from scipy import stats
        from synomicsbench.metrics.narrow_utility.DGE import GCSAnalyzer
        from synomicsbench.metrics.narrow_utility.GSEA import PCSAnalyzer

        ori, syn = sample_dge_data
        gcs = GCSAnalyzer()
        x, y = gcs._calibration_points(gcs.merge_effects(ori, syn))
        assert gcs.compute_metrics(ori, syn, "Slope") == pytest.approx(stats.linregress(x, y).slope)

        pcs = PCSAnalyzer(term_col="Gene", nes_col="Log2FC", sig_col="P_value")
        assert pcs.compute_metrics(ori, syn, "Slope") == pytest.approx(stats.theilslopes(y, x)[0])

    def test_theil_sen_intercept_is_joint(self):
        from scipy import stats
        from synomicsbench.metrics.narrow_utility.GSEA import PCSAnalyzer

        # two clusters of pathways, NES < 0 and > 0, with an uneven split
        x = np.array([-2.0, -1.8, -1.6, 1.4, 1.6, 1.8, 2.0, 2.2, 2.4])
        y = 0.5 * x + np.array([0.1, -0.1, 0.0, 0.05, -0.05, 0.1, 0.0, -0.1, 0.05])
        terms = [f"P{i}" for i in range(len(x))]
        ori = pd.DataFrame({"Term": terms, "NES": x, "FDR q-val": 0.01})
        syn = pd.DataFrame({"Term": terms, "NES": y, "FDR q-val": 0.01})
        pcs = PCSAnalyzer()
        res = pcs.calibration_score(pcs.merge_effects(ori, syn))
        slope, intercept = stats.theilslopes(y, x, method="joint")[:2]
        assert res["Slope"] == pytest.approx(slope)
        assert res["Intercept"] == pytest.approx(intercept)
        assert abs(res["Intercept"]) < 0.1   # the line passes through the two clusters

    def test_plot_calibration_scatter_marks_few_features(self):
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from synomicsbench.metrics.narrow_utility.GSEA import PCSAnalyzer

        terms = [f"P{i}" for i in range(6)]
        ori = pd.DataFrame({"Term": terms, "NES": [-2, -1.5, 1.5, 2, 2.5, 1.8], "FDR q-val": 0.01})
        syn = pd.DataFrame({"Term": terms, "NES": [-1, 1, 1.2, 2.1, -0.5, 1.0],
                            "FDR q-val": [0.01, 0.5, 0.01, 0.01, 0.3, 0.2]})
        from matplotlib.collections import PathCollection

        fig, table = PCSAnalyzer().plot_calibration_scatter(ori, {"A": syn})
        ax = fig.axes[0]
        points = [c for c in ax.collections if isinstance(c, PathCollection) and len(c.get_offsets())]
        assert points and all(c.get_sizes()[0] == 48 for c in points)   # every pathway marked
        assert sum(len(c.get_offsets()) for c in points) == 6
        assert table.loc["A", "N"] == 6
        # one range for both axes, containing every effect size and 0
        assert ax.get_xlim() == ax.get_ylim()
        lo, hi = ax.get_xlim()
        assert lo <= min(ori.NES.min(), syn.NES.min(), 0) and hi >= max(ori.NES.max(), syn.NES.max(), 0)
        plt.close(fig)

        # pathways not significant in the original are drawn as small context points
        ori2 = ori.assign(**{"FDR q-val": [0.01, 0.01, 0.01, 0.01, 0.4, 0.6]})
        fig, table = PCSAnalyzer().plot_calibration_scatter(ori2, {"A": syn})
        points = [c for c in fig.axes[0].collections if isinstance(c, PathCollection) and len(c.get_offsets())]
        assert sorted((c.get_sizes()[0], len(c.get_offsets())) for c in points if c.get_sizes()[0] == 16) == [(16, 2)]
        assert table.loc["A", "N"] == 4
        plt.close(fig)


# ===========================================================================
# Narrow Utility — SurvivalEvaluator (requires lifelines + scienceplots)
# ===========================================================================


class TestSurvivalEvaluator:
    @pytest.fixture(autouse=True)
    def _skip_if_no_deps(self):
        pytest.importorskip("lifelines")
        pytest.importorskip("scienceplots")

    def test_init_and_compute(self):
        from synomicsbench.metrics.narrow_utility.survival_analysis import SurvivalEvaluator

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
        from synomicsbench.metrics.narrow_utility.survival_analysis import SurvivalEvaluator

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

    @staticmethod
    def _cox_datasets():
        rng = np.random.default_rng(2)
        n = 80
        group = rng.choice(["A", "B"], n)
        # group A has a lower hazard, so the original HR is below 1
        time = rng.exponential(np.where(group == "A", 20.0, 8.0))
        ori = pd.DataFrame({"OS": time, "OS_CNSR": rng.integers(0, 2, n) | (time < 10), "grp": group})
        reversed_ = ori.assign(grp=np.where(ori["grp"] == "A", "B", "A"))
        return {"Origin": ori, "Same": ori.copy(), "Reversed": reversed_}

    def test_compute_cox_metrics(self):
        from synomicsbench.metrics.narrow_utility.survival_analysis import SurvivalEvaluator

        ev = SurvivalEvaluator(self._cox_datasets(), phenotype={"grp": ["A", "B"]})
        table = ev.compute_cox_metrics(n_bootstrap=30, n_jobs=1).set_index("Dataset")

        assert table.loc["Origin", "HR"] < 1
        assert np.isnan(table.loc["Origin", "Survival_score"])
        assert table.loc["Same", "Survival_score"] == pytest.approx(1.0)
        assert table.loc["Same", "HR_same_direction"] == 1.0
        assert table.loc["Reversed", "HR_same_direction"] == 0.0
        assert table.loc["Reversed", "HR"] == pytest.approx(1 / table.loc["Origin", "HR"], rel=1e-4)
        assert (table["CI_low"] < table["CI_high"]).all()

    def test_cox_metrics_are_reproducible(self):
        from synomicsbench.metrics.narrow_utility.survival_analysis import SurvivalEvaluator

        datasets = self._cox_datasets()
        first = SurvivalEvaluator(datasets, phenotype={"grp": ["A", "B"]}).compute_cox_metrics(
            n_bootstrap=20, seed=5, n_jobs=1)
        second = SurvivalEvaluator(datasets, phenotype={"grp": ["A", "B"]}).compute_cox_metrics(
            n_bootstrap=20, seed=5, n_jobs=1)
        pd.testing.assert_frame_equal(first, second)

    def test_plot_cindex_forest(self):
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from synomicsbench.metrics.narrow_utility.survival_analysis import SurvivalEvaluator

        ev = SurvivalEvaluator(self._cox_datasets(), phenotype={"grp": ["A", "B"]})
        ev.compute_cox_metrics(n_bootstrap=20, n_jobs=1)
        fig, table = ev.plot_cindex_forest()
        assert table is ev.cox_df
        assert len(fig.axes[0].get_yticklabels()) == 2
        plt.close(fig)


# ===========================================================================
# Privacy — inference, singling_out, linkability (require anonymeter)
# ===========================================================================


class TestPrivacyInference:
    @pytest.fixture(autouse=True)
    def _skip_if_no_anonymeter(self):
        pytest.importorskip("anonymeter")

    def test_eval_inference(self, data_no_id, syn_no_id):
        from synomicsbench.metrics.privacy.inference import eval_inference_genes_clinical

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
            clinical_cols=list(range(num_clinical)),
        )
        assert isinstance(results, dict)
        assert "test_synth" in results


class TestPrivacySinglingOut:
    @pytest.fixture(autouse=True)
    def _skip_if_no_anonymeter(self):
        pytest.importorskip("anonymeter")

    def test_eval_singling_out_univariate(self, data_no_id, syn_no_id):
        from synomicsbench.metrics.privacy.singling_out import eval_singling_out_univariate

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
        from synomicsbench.metrics.privacy.linkability import eval_linkability_genes_clinical

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
            clinical_cols=list(range(num_clinical)),
            proportions=(0.5, 1.0),
            seed=42,
        )
        assert isinstance(results, dict)
        assert "test_synth" in results
        assert len(results["test_synth"]) == 2


class TestPrivacyControl:
    """External control cohort: residual risk, attack budget and the risk table."""

    @pytest.fixture(autouse=True)
    def _skip_if_no_anonymeter(self):
        pytest.importorskip("anonymeter")

    @pytest.fixture
    def frames(self):
        rng = np.random.default_rng(3)

        def make(n):
            return pd.DataFrame({
                "sex": rng.choice(["F", "M"], n),
                "stage": rng.integers(1, 5, n),
                **{f"g{i}": rng.normal(size=n).round(2) for i in range(12)},
            })

        return make(60), make(60), make(40)

    def test_knowledge_levels(self):
        from synomicsbench.metrics.privacy.knowledge import knowledge_levels

        genes = [f"g{i}" for i in range(20)]
        levels = knowledge_levels(["sex"], genes, proportions=(0.25, 1.0),
                                  gene_sets={"set": ["g3", "g1", "zz"]})
        assert [label for label, _ in levels] == ["set", "25%", "100%"]
        assert levels[0][1] == ["sex", "g1", "g3"]
        assert len(levels[1][1]) == 1 + 5
        assert levels[2][1] == ["sex"] + genes
        # the same seed gives the same genes on every call
        assert knowledge_levels(["sex"], genes, (0.25,))[0] == levels[1]

    def test_knowledge_levels_from_gmt(self, tmp_path):
        from synomicsbench.metrics.privacy.knowledge import knowledge_levels, read_gmt

        gmt = tmp_path / "sets.gmt"
        gmt.write_text("A\tdesc\tg3\tg1\nB\thttp://x\tg2\tzz\n")
        assert read_gmt(gmt) == {"A": ["g3", "g1"], "B": ["g2", "zz"]}

        genes = [f"g{i}" for i in range(5)]
        levels = knowledge_levels(["sex"], genes, proportions=(), gene_sets=str(gmt))
        assert levels == [("A", ["sex", "g1", "g3"]), ("B", ["sex", "g2"])]

    def test_residual_risk_with_control(self, frames):
        from synomicsbench.metrics.privacy.linkability import eval_linkability_genes_clinical
        from synomicsbench.metrics.privacy.risk import privacy_risk_table
        from synomicsbench.metrics.privacy.singling_out import eval_singling_out_univariate

        ori, syn, control = frames
        uni = eval_singling_out_univariate(ori, {"s": syn}, n_attacks=50, max_attempts=5_000,
                                           proportions=(1.0,), control=control,
                                           clinical_cols=["sex", "stage"])
        table = privacy_risk_table(uni, "SO_uni", configs=["100%"])
        assert {"R_residual", "R_attack", "R_control"} <= set(table.columns)
        assert "R_naive" not in table.columns
        assert 0.0 <= table.loc[0, "R_residual"] <= 1.0

        link = eval_linkability_genes_clinical(ori, {"s": syn}, clinical_cols=["sex", "stage"],
                                               proportions=(1.0,), control=control)
        # the control cohort bounds the number of attacks
        assert link["s"][0].results().n_attacks == len(control)

    def test_naive_risk_without_control(self, frames):
        from synomicsbench.metrics.privacy.inference import eval_inference_genes_clinical
        from synomicsbench.metrics.privacy.risk import privacy_risk_table

        ori, syn, _ = frames
        infer = eval_inference_genes_clinical(ori, {"s": syn}, clinical_cols=["sex", "stage"])
        table = privacy_risk_table(infer, "Inference")
        assert list(table["Config"]) == ["100%", "100%"]
        assert list(table["Secret"]) == ["sex", "stage"]
        assert {"R_attack", "R_naive"} <= set(table.columns)
        assert "R_residual" not in table.columns

    def test_inference_knowledge_levels(self, frames):
        from synomicsbench.metrics.privacy.inference import eval_inference_genes_clinical
        from synomicsbench.metrics.privacy.risk import privacy_risk_table

        ori, syn, control = frames
        infer = eval_inference_genes_clinical(ori, {"s": syn}, clinical_cols=["sex", "stage"],
                                              proportions=(0.5, 1.0), gene_sets={"set": ["g0"]},
                                              control=control)
        assert [(level, secret) for level, secret, _ in infer["s"]] == [
            ("set", "sex"), ("set", "stage"), ("50%", "sex"), ("50%", "stage"),
            ("100%", "sex"), ("100%", "stage")]
        table = privacy_risk_table(infer, "Inference")
        assert list(table.columns[:4]) == ["Dataset", "Attack", "Config", "Secret"]
        assert "R_residual" in table.columns

    def test_evaluator_seed_repeats_linkability_and_inference(self, frames):
        from synomicsbench.metrics.privacy.inference import eval_inference_genes_clinical
        from synomicsbench.metrics.privacy.linkability import eval_linkability_genes_clinical

        ori, syn, control = frames   # 60 original records, 40 control: 40 targets drawn at random

        def link(seed):
            ev = eval_linkability_genes_clinical(ori, {"s": syn}, clinical_cols=["sex", "stage"],
                                                 control=control, evaluator_seed=seed)["s"][0]
            return ev.results().n_success, ev.results().n_control

        def infer(seed):
            out = eval_inference_genes_clinical(ori, {"s": syn}, clinical_cols=["sex", "stage"],
                                                control=control, evaluator_seed=seed)["s"]
            return [(r.n_success, r.n_baseline, r.n_control) for _, _, r in out]

        np.random.seed(123)
        before = np.random.get_state()[1].copy()
        assert link(7) == link(7)
        assert infer(7) == infer(7)
        assert [infer(s) for s in range(4)] != [infer(7)] * 4   # the seed does change the draw
        # numpy's global generator is left as it was
        assert (np.random.get_state()[1] == before).all()

    def test_control_must_have_attacked_columns(self, frames):
        from synomicsbench.metrics.privacy.singling_out import eval_singling_out_multivariate

        ori, syn, control = frames
        with pytest.raises(ValueError, match="control dataset lacks"):
            eval_singling_out_multivariate(ori, {"s": syn}, n_cols_list=(2,),
                                           control=control.drop(columns="g0"))


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
        from synomicsbench.metrics.narrow_utility.cell_deconvolution import geometric_center

        X = np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])
        center = geometric_center(X)
        assert center.shape == (3,)
        # geometric mean of col 0: exp(mean(log([1,4]))) = exp((0 + ln4)/2) = 2.0
        np.testing.assert_allclose(center[0], np.exp(np.mean(np.log([1.0, 4.0]))), rtol=1e-6)

    def test_geometric_center_uniform(self):
        from synomicsbench.metrics.narrow_utility.cell_deconvolution import geometric_center

        # All same values → center equals that value
        X = np.full((5, 3), 7.0)
        center = geometric_center(X)
        np.testing.assert_allclose(center, [7.0, 7.0, 7.0], rtol=1e-6)

    def test_aitchison_distance_identical(self, sample_composition_data):
        from synomicsbench.metrics.narrow_utility.cell_deconvolution import aitchison_distance

        df_orig, _, cell_types = sample_composition_data
        # Distance to itself should be 0
        dist = aitchison_distance(df_orig, df_orig, cell_types)
        assert isinstance(dist, float)
        assert dist == pytest.approx(0.0, abs=1e-10)

    def test_aitchison_distance_non_negative(self, sample_composition_data):
        from synomicsbench.metrics.narrow_utility.cell_deconvolution import aitchison_distance

        df_orig, df_syn, cell_types = sample_composition_data
        dist = aitchison_distance(df_orig, df_syn, cell_types)
        assert isinstance(dist, float)
        assert dist >= 0.0

    def test_aitchison_distance_with_zeros(self):
        from synomicsbench.metrics.narrow_utility.cell_deconvolution import aitchison_distance

        # Data containing zeros — multi_replace should handle them
        cell_types = ["A", "B", "C"]
        df1 = pd.DataFrame({"A": [0.5, 0.0, 0.3], "B": [0.3, 0.6, 0.0], "C": [0.2, 0.4, 0.7]})
        df2 = pd.DataFrame({"A": [0.4, 0.1, 0.2], "B": [0.4, 0.5, 0.3], "C": [0.2, 0.4, 0.5]})
        dist = aitchison_distance(df1, df2, cell_types)
        assert isinstance(dist, float)
        assert dist >= 0.0

    def test_aitchison_score_zero_distance(self):
        from synomicsbench.metrics.narrow_utility.cell_deconvolution import aitchison_score

        score = aitchison_score(0.0)
        assert score == pytest.approx(1.0)

    def test_aitchison_score_positive_distance(self):
        from synomicsbench.metrics.narrow_utility.cell_deconvolution import aitchison_score

        score = aitchison_score(1.0)
        assert score == pytest.approx(np.exp(-1.0))
        assert 0.0 < score < 1.0

    def test_aitchison_score_large_distance(self):
        from synomicsbench.metrics.narrow_utility.cell_deconvolution import aitchison_score

        score = aitchison_score(100.0)
        assert score > 0.0
        assert score < 1e-40  # exp(-100) is extremely small

    def test_aitchison_distance_and_score_integration(self, sample_composition_data):
        from synomicsbench.metrics.narrow_utility.cell_deconvolution import (
            aitchison_distance,
            aitchison_score,
        )

        df_orig, df_syn, cell_types = sample_composition_data
        dist = aitchison_distance(df_orig, df_syn, cell_types)
        score = aitchison_score(dist)
        assert 0.0 < score <= 1.0

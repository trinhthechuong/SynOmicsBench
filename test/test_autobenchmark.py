"""
Tests for the automatic benchmark sub-package (synomicsbench.metrics.autobenchmark).

The unit tests use small synthetic inputs and only depend on numpy/pandas/matplotlib
(+ sdmetrics for the fidelity path). The full-cohort reproduction is exercised in
scripts under the manuscript workspace, not here.
"""

import numpy as np
import pandas as pd
import pytest

from synomicsbench.metrics.autobenchmark import (
    BenchmarkConfig,
    build_metascore,
    composite_scores,
    plot_weighted_composite_scores,
    ALL_DIMS,
    NAME_MAP,
)
from synomicsbench.metrics.autobenchmark.config import NARROW_DIMS
from synomicsbench.metrics.autobenchmark import compute as C


METHODS = list(NAME_MAP.keys())


def _dummy_per_dim(seed=0):
    rng = np.random.default_rng(seed)
    return {d: pd.DataFrame({"Model": METHODS, "Seed": [42] * len(METHODS),
                             "Value": rng.random(len(METHODS))}) for d in ALL_DIMS}


def test_config_resolve_columns_splits_at_gene_start():
    cfg = BenchmarkConfig(metadata={}, gene_start_column="A1BG")
    clin, omic = cfg.resolve_columns(["Patient", "age", "sex", "A1BG", "TP53"])
    assert clin == ["age", "sex"]
    assert omic == ["A1BG", "TP53"]


def test_build_metascore_ranks_are_means():
    per = _dummy_per_dim()
    ms = build_metascore(per)
    assert set(ms.keys()) == set(ALL_DIMS)
    for dim, ranks in ms.items():
        # 6 distinct random values -> ranks are a permutation of 1..6
        assert sorted(ranks.values()) == [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]


def test_composite_lower_is_better_and_has_all_pillars():
    per = _dummy_per_dim(seed=1)
    ms = build_metascore(per)
    fig, comp = plot_weighted_composite_scores(ms)
    import matplotlib.pyplot as plt
    plt.close(fig)
    pillars = ["Statistical fidelity", "Biological utility", "Privacy"]
    assert list(comp.columns) == pillars + ["Total"]
    assert len(comp) == len(METHODS)
    # Total equals the sum of the three pillars.
    np.testing.assert_allclose(comp["Total"].values, comp[pillars].sum(axis=1).values)
    # each pillar is the weighted mean rank of its dimensions
    from synomicsbench.metrics.autobenchmark import PILLARS
    ranks = pd.DataFrame(ms)
    for pillar, dims in PILLARS.items():
        np.testing.assert_allclose(comp[pillar].values,
                                   ranks.loc[comp.index, list(dims)].mean(axis=1).values / 3)


def test_metascore_ranks_privacy_risks_lowest_first():
    risk = pd.DataFrame({"Model": ["A", "B", "C"], "Seed": [0, 0, 0], "Value": [0.02, 0.01, np.nan]})
    ms = build_metascore({"Linkability": risk, "Univariate": risk})
    assert ms["Linkability"] == {"A": 2.0, "B": 1.0, "C": 3.0}   # missing risk ranks last
    assert ms["Univariate"] == {"A": 1.0, "B": 2.0, "C": 3.0}


def test_metascore_ties_at_twelve_decimals():
    per = {"Univariate": pd.DataFrame({"Model": ["A", "B", "C"], "Seed": [0, 0, 0],
                                       "Value": [0.5, 0.5 + 1e-15, 0.4]})}
    ms = build_metascore(per)
    assert ms["Univariate"] == {"A": 1.0, "B": 1.0, "C": 3.0}


def test_category_risk_uses_residual_with_control():
    from synomicsbench.metrics.autobenchmark import privacy as P

    class _Rate:
        value = 0.2

    class _ControlResults:
        control_rate = _Rate()
        def risk(self, baseline=False): return _Risk(0.05 if not baseline else 0.9)

    class _ControlEvaluator:
        def results(self): return _ControlResults()

    risks = P.category_risks_from_attacks({"A": [_ControlEvaluator()]}, {"A": [_Evaluator(0.2, 0.4)]}, {}, {})
    assert risks["Singling-out (uni)"]["A"] == pytest.approx(0.05)    # residual, no naive floor
    assert risks["Singling-out (multi)"]["A"] == pytest.approx(0.4)   # floored at the naive risk


def test_derive_labels_is_object_dtype_and_maps_groups():
    df = pd.DataFrame({"BR": ["CR", "PR", "PD", "SD", "MR"]})
    out = C.derive_labels(df, "BR", ("CR", "PR"), ("PD",), "Labels", ("Responder", "Progressor"))
    assert out["Labels"].tolist()[:3] == ["Responder", "Responder", "Progressor"]
    # values outside either group stay missing
    assert out["Labels"].isna().sum() == 2


def test_build_gene_matrix_has_gene_column():
    df = pd.DataFrame({"g1": [1.0, 2.0], "g2": [3.0, 4.0]}, index=["s1", "s2"])
    gm = C.build_gene_matrix(df, ["g1", "g2"])
    assert gm.columns[0] == "Gene"
    assert set(gm["Gene"]) == {"g1", "g2"}
    assert "s1" in gm.columns and "s2" in gm.columns


def _dummy_result(seed=2):
    """Build a BenchmarkResult from dummy per-dimension values."""
    from synomicsbench.metrics.autobenchmark.runner import BenchmarkRunner, BenchmarkResult
    per = _dummy_per_dim(seed)
    ms = build_metascore(per)
    value_table = BenchmarkRunner._wide(per, "Value")
    rank_table = pd.DataFrame(ms)
    composite = composite_scores(ms)
    return BenchmarkResult(per_dim_values=per, metascore=ms, value_table=value_table,
                           rank_table=rank_table, composite=composite,
                           dims_run=list(ALL_DIMS), dims_missing=[])


def test_candidate_seed_parsing_detects_multi_seed():
    """A dict keyed by '{method}_{seed}' is parsed into (method, seed) → multi-seed."""
    from synomicsbench.metrics.autobenchmark import BenchmarkRunner
    runner = BenchmarkRunner(BenchmarkConfig(metadata={}))
    runner._default_seed = 42
    dummy = pd.DataFrame({"x": [1]})
    datasets = {f"{stem}_{seed}": dummy
                for stem in ("gaussiancopula", "ctgan") for seed in (0, 1, 2)}
    cands = runner._candidates(datasets)
    seeds = sorted({c.seed for c in cands})
    methods = sorted({c.method for c in cands})
    assert seeds == [0, 1, 2]                       # multi-seed detected from names
    assert methods == ["CTGAN", "Gaussian Copula"]  # stems mapped to display names


def test_candidate_name_without_seed_is_single_seed():
    from synomicsbench.metrics.autobenchmark import BenchmarkRunner
    runner = BenchmarkRunner(BenchmarkConfig(metadata={}))
    runner._default_seed = 7
    cands = runner._candidates({"my_method": pd.DataFrame({"x": [1]})})
    # "my_method" ends in a non-numeric token → no seed parsed → falls back to default seed
    assert cands[0].seed == 7


def test_explicit_labels_still_supported():
    from synomicsbench.metrics.autobenchmark import BenchmarkRunner, Candidate
    runner = BenchmarkRunner(BenchmarkConfig(metadata={}))
    runner._default_seed = 42
    df = pd.DataFrame({"x": [1]})
    cands = runner._candidates([{"method": "CTGAN", "seed": 3, "data": df},
                                Candidate("TVAE", 5, df)])
    assert {(c.method, c.seed) for c in cands} == {("CTGAN", 3), ("TVAE", 5)}


class _Risk:
    def __init__(self, v): self.value = v


class _Evaluator:
    """Fake SO/linkability evaluator: exposes risk(baseline=...)."""
    def __init__(self, attack, naive): self._a, self._n = attack, naive
    def risk(self, baseline=False): return _Risk(self._n if baseline else self._a)


class _Results:
    """Fake inference EvaluationResults: risk() has no baseline kwarg."""
    def __init__(self, v): self._v = v
    def risk(self): return _Risk(self._v)


def test_write_html_report_is_self_contained(tmp_path):
    from synomicsbench.metrics.autobenchmark import write_html_report
    result = _dummy_result()
    config = BenchmarkConfig(metadata={}, output_dir=str(tmp_path))
    path = write_html_report(result, config)
    assert path.endswith("report.html")
    doc = open(path, encoding="utf-8").read()
    # self-contained: full document, inline script, no external/CDN references
    assert "<html" in doc.lower()
    assert "<script>" in doc and 'id="tri-canvas"' in doc and 'id="scen-table"' in doc
    assert "http://" not in doc and "https://" not in doc
    # narrative + transparency: winner named, every dimension present
    winner = result.composite["Total"].idxmin()
    assert winner in doc
    from synomicsbench.metrics.autobenchmark.html_report import METRIC_LABELS
    for dim in ALL_DIMS:
        assert METRIC_LABELS[dim] in doc
    # the three pillars and the scenarios are labelled
    for pillar in ("Statistical fidelity", "Biological utility", "Privacy"):
        assert pillar in doc
    from synomicsbench.metrics.autobenchmark import SCENARIO_DESCRIPTIONS
    for name, text in SCENARIO_DESCRIPTIONS.items():
        assert name in doc and text in doc


def test_write_report_writes_markdown_tables(tmp_path):
    from synomicsbench.metrics.autobenchmark import write_report
    result = _dummy_result()
    config = BenchmarkConfig(metadata={}, output_dir=str(tmp_path))
    paths = write_report(result, config)
    report = open(tmp_path / "REPORT.md", encoding="utf-8").read()
    assert "report_html" in paths
    for dim in ALL_DIMS:
        assert dim in report
    assert "| Statistical fidelity | Biological utility | Privacy | Total |" in report


def test_resolve_metrics_names_groups_and_errors():
    from synomicsbench.metrics.autobenchmark import resolve_metrics, PRIVACY_DIMS
    assert resolve_metrics(None) == list(ALL_DIMS)
    assert resolve_metrics("privacy") == list(PRIVACY_DIMS)
    assert resolve_metrics(["survival", "f1_gcs"]) == ["DGE", "Survival Analysis"]
    assert resolve_metrics(["DGE", "fidelity"]) == ["Univariate", "Bivariate", "Network Preservation", "DGE"]
    with pytest.raises(ValueError, match="Valid names"):
        resolve_metrics(["f1-gcs"])


def test_composite_over_a_subset_of_pillars_rescales_the_weights():
    per = _dummy_per_dim(seed=3)
    ms = build_metascore({d: per[d] for d in ("DGE", "Survival Analysis", "Linkability")})
    comp = composite_scores(ms, weights=(0.5, 0.3, 0.2))
    assert list(comp.columns) == ["Biological utility", "Privacy", "Total"]
    ranks = pd.DataFrame(ms)
    want = (ranks[["DGE", "Survival Analysis"]].mean(axis=1) * 0.6 + ranks["Linkability"] * 0.4)
    np.testing.assert_allclose(comp["Total"].values, want.loc[comp.index].values)
    assert comp["Total"].is_monotonic_increasing


def test_composite_with_every_pillar_matches_the_plot():
    ms = build_metascore(_dummy_per_dim(seed=4))
    fig, plotted = plot_weighted_composite_scores(ms, 0.3, 0.5, 0.2)
    import matplotlib.pyplot as plt
    plt.close(fig)
    comp = composite_scores(ms, (0.3, 0.5, 0.2))
    pd.testing.assert_frame_equal(comp.loc[plotted.index], plotted)


def test_scenario_table_and_weight_sweep():
    from synomicsbench.metrics.autobenchmark import SCENARIOS, pillar_scores, scenario_table, weight_sweep
    ms = build_metascore(_dummy_per_dim(seed=5))
    table = scenario_table(ms, SCENARIOS)
    for name, w in SCENARIOS.items():
        total = composite_scores(ms, w)["Total"]
        np.testing.assert_allclose(table[(name, "Score")].loc[total.index].values, total.values)
        assert sorted(table[(name, "Rank")]) == list(range(1, len(METHODS) + 1))
    sweep, summary = weight_sweep(ms, step=0.1)
    assert len(sweep) == 66                                  # (n + 1)(n + 2) / 2 points, n = 10
    np.testing.assert_allclose(sweep[["w_stat", "w_bio", "w_priv"]].sum(axis=1), 1.0)
    assert summary["First place (%)"].sum() == pytest.approx(100.0)
    corner = sweep[(sweep.w_stat == 1.0)].iloc[0]           # all weight on statistical fidelity
    assert corner["First"] == pillar_scores(ms)["Statistical fidelity"].idxmin()


def test_weight_sweep_needs_the_three_pillars():
    from synomicsbench.metrics.autobenchmark import weight_sweep
    ms = build_metascore({"DGE": _dummy_per_dim()["DGE"]})
    with pytest.raises(ValueError, match="three pillars"):
        weight_sweep(ms)


def _toy_cohort(n=40, seed=0):
    """Small cohort with clinical, survival and gene columns."""
    rng = np.random.default_rng(seed)
    br = rng.choice(["CR", "PR", "PD"], size=n)
    df = pd.DataFrame({
        "Patient": [f"p{i}" for i in range(n)],
        "age": rng.integers(30, 80, n).astype(float),
        "BR": br,
        "OS": rng.exponential(20, n) + np.where(br == "PD", 0, 15),
        "dead": rng.integers(0, 2, n),
        "PFS": rng.exponential(10, n),
        "progressed": rng.integers(0, 2, n),
    })
    for g in range(6):
        df[f"G{g}"] = rng.normal(5, 1, n)
    return df


def test_run_benchmark_on_a_subset_of_metrics(tmp_path):
    from synomicsbench.metrics.autobenchmark import run_benchmark
    ori = _toy_cohort(seed=0)
    syn = {"ctgan_0": _toy_cohort(seed=1), "ctgan_1": _toy_cohort(seed=2), "tvae_0": _toy_cohort(seed=3)}
    res = run_benchmark(ori, syn, metrics=["survival"], gene_start_column="G0",
                        output_dir=str(tmp_path / "out"))
    assert res.dims_run == ["Survival Analysis"] and not res.errors
    assert set(res.ranking.index) == {"CTGAN", "TVAE"}
    assert list(res.composite.columns) == ["Biological utility", "Total"]
    assert res.report_html.endswith("report.html")
    assert (tmp_path / "out" / "result.pkl").exists()


def test_run_benchmark_checks_columns_before_computing(tmp_path):
    from synomicsbench.metrics.autobenchmark import run_benchmark
    ori = _toy_cohort()
    with pytest.raises(ValueError, match="phenotype_source_col 'Response'"):
        run_benchmark(ori, {"a_0": ori}, metrics="f1_gcs", gene_start_column="G0",
                      phenotype_source_col="Response", output_dir=str(tmp_path))
    with pytest.raises(ValueError, match="Survival columns"):
        run_benchmark(ori, {"a_0": ori}, metrics="survival", gene_start_column="G0",
                      survival_endpoints=[("OS", "death")], output_dir=str(tmp_path))
    with pytest.raises(ValueError, match="CIBERSORTx"):
        run_benchmark(ori, {"a_0": ori}, metrics="cell_deconvolution", gene_start_column="G0",
                      output_dir=str(tmp_path))


def test_run_benchmark_records_or_raises_errors(tmp_path):
    from synomicsbench.metrics.autobenchmark import run_benchmark
    ori = _toy_cohort()
    bad = {"original": "missing.csv", "a_0": "missing.csv"}
    res = run_benchmark(ori, {"a_0": ori}, metrics=["survival", "cell_deconvolution"], gene_start_column="G0",
                        cibersortx=bad, output_dir=str(tmp_path))
    assert res.dims_run == ["Survival Analysis"]
    assert "Cell Deconvolution" in res.errors and "missing.csv" in res.errors["Cell Deconvolution"]
    with pytest.raises(FileNotFoundError):
        run_benchmark(ori, {"a_0": ori}, metrics="cell_deconvolution", gene_start_column="G0",
                      cibersortx=bad, on_error="raise", output_dir=str(tmp_path))


def test_cell_deconvolution_reads_a_cibersortx_directory(tmp_path):
    from synomicsbench.metrics.autobenchmark import runners as R
    rng = np.random.default_rng(0)

    def fractions():
        x = rng.dirichlet(np.ones(4), size=10)
        df = pd.DataFrame(x, columns=["B", "T", "NK", "Mono"])
        df["P-value"], df["Correlation"], df["RMSE"] = 0.0, 0.9, 0.5
        return df

    fractions().to_csv(tmp_path / "CIBERSORTx_Origin_Results.csv")
    fractions().to_csv(tmp_path / "CIBERSORTx_tvae_0_Results.csv")
    fractions().to_csv(tmp_path / "ctgan_0.csv")
    cfg = BenchmarkConfig(cibersortx=str(tmp_path), top_k_cell_types=3)
    cands = [R.Candidate("TVAE", 0, None, "tvae_0"), R.Candidate("CTGAN", 0, None, "ctgan_0")]
    out = R.run_cell_deconvolution(None, cands, cfg)
    assert out["Value"].between(0, 1).all() and out["Value"].notna().all()
    with pytest.raises(ValueError, match="No CIBERSORTx result"):
        R.run_cell_deconvolution(None, [R.Candidate("TabDiff", 0, None, "tabdiff_0")], cfg)


def test_privacy_knowledge_levels_are_averaged(tmp_path, monkeypatch):
    pytest.importorskip("anonymeter")
    import synomicsbench.metrics.privacy.inference as inference
    import synomicsbench.metrics.privacy.linkability as linkability
    from synomicsbench.metrics.autobenchmark import run_benchmark

    calls = {}

    def spy(module, name):
        original = getattr(module, name)

        def wrapped(*args, **kwargs):
            out = original(*args, **kwargs)
            calls.setdefault(name, {}).update({k: len(v) for k, v in out.items()})
            return out
        monkeypatch.setattr(module, name, wrapped)

    spy(linkability, "eval_linkability_genes_clinical")
    spy(inference, "eval_inference_genes_clinical")
    ori = _toy_cohort(seed=0)
    syn = {"ctgan_0": _toy_cohort(seed=1), "tvae_0": _toy_cohort(seed=2)}
    res = run_benchmark(ori, syn, metrics=["linkability", "inference"], gene_start_column="G0",
                        privacy_proportions=(0.5, 1.0), privacy_gene_sets={"set": ["G0", "G1"]},
                        privacy_control=_toy_cohort(seed=9), on_error="raise",
                        output_dir=str(tmp_path / "out"))
    # three levels (the gene set, 50% and 100% of the genes); inference: x 6 clinical secrets
    assert sorted(calls["eval_linkability_genes_clinical"].values()) == [3, 3]
    assert sorted(calls["eval_inference_genes_clinical"].values()) == [18, 18]
    for dim in ("Linkability", "Inference"):
        assert res.per_dim_values[dim]["Value"].between(0, 1).all()
    with pytest.raises(ValueError, match="privacy_proportions"):
        run_benchmark(ori, syn, metrics=["linkability"], gene_start_column="G0",
                      privacy_proportions=(0.0,), output_dir=str(tmp_path / "err"))


def test_resume_reads_saved_metrics_back(tmp_path, monkeypatch):
    from synomicsbench.metrics.autobenchmark import run_benchmark
    from synomicsbench.metrics.autobenchmark import runner as runner_module

    ori = _toy_cohort(seed=0)
    syn = {"ctgan_0": _toy_cohort(seed=1), "tvae_0": _toy_cohort(seed=2)}
    common = dict(metrics=["survival"], gene_start_column="G0", on_error="raise",
                  output_dir=str(tmp_path / "out"))
    first = run_benchmark(ori, syn, resume=True, **common)
    assert (tmp_path / "out" / "_work" / "values" / "Survival_Analysis.csv").exists()

    calls = []
    real = runner_module.DIMENSION_RUNNERS["Survival Analysis"]

    def counting(*args, **kwargs):
        calls.append(1)
        return real(*args, **kwargs)
    monkeypatch.setitem(runner_module.DIMENSION_RUNNERS, "Survival Analysis", counting)

    # same inputs and settings: read back, not computed
    again = run_benchmark(ori, syn, resume=True, **common)
    assert calls == []
    pd.testing.assert_frame_equal(
        again.per_dim_values["Survival Analysis"].reset_index(drop=True),
        first.per_dim_values["Survival Analysis"][["Model", "Seed", "Value"]].reset_index(drop=True),
        check_dtype=False)
    # another setting: computed again
    run_benchmark(ori, syn, resume=True, survival_endpoints=[("OS", "dead")], **common)
    assert calls == [1]
    # without resume: computed again
    run_benchmark(ori, syn, **common)
    assert calls == [1, 1]


def test_singling_out_uses_the_vendored_evaluator_and_the_dataset_seed(tmp_path, monkeypatch):
    pytest.importorskip("polars")
    import synomicsbench.metrics.privacy.singling_out as so
    from synomicsbench.metrics.autobenchmark import run_benchmark

    seen = {}
    real = so.eval_singling_out_multivariate

    def spy(ori, syns, **kwargs):
        out = real(ori, syns, **kwargs)
        for key, evs in out.items():
            seen[key] = (kwargs.get("evaluator_seed"), type(evs[0]).__module__)
        return out
    monkeypatch.setattr(so, "eval_singling_out_multivariate", spy)
    syn = {"ctgan_3": _toy_cohort(seed=1), "tvae_7": _toy_cohort(seed=2)}
    run_benchmark(_toy_cohort(seed=0), syn, metrics=["singling_out_multi"], gene_start_column="G0",
                  privacy_n_attacks=50, privacy_max_attempts=5_000, privacy_so_multi_n_cols=(2,),
                  on_error="raise", output_dir=str(tmp_path / "out"))
    assert {k: v[0] for k, v in seen.items()} == {"CTGAN_3": 3, "TVAE_7": 7}
    assert all(mod.startswith("synomicsbench.third_party.anonymeter_polars") for _, mod in seen.values())


def test_dge_log2fc_on_log_and_linear_scales():
    genes = pd.DataFrame({"Gene": ["g1", "g2"],
                          "a1": [2.0, 0.0], "a2": [4.0, 0.0], "b1": [1.0, 3.0], "b2": [1.0, 5.0]})
    meta = pd.DataFrame({"id": ["a1", "a2", "b1", "b2"], "grp": ["A", "A", "B", "B"]})
    log = C.dge_analysis(genes, meta, {"grp": ["A", "B"]}, id_col="id", n_jobs=1, log_transformed=True)
    # log2 scale: the difference of the group means, also when a group mean is 0
    assert log["Log2FC"].tolist() == pytest.approx([3.0 - 1.0, 0.0 - 4.0])
    assert log["Status"].tolist() == ["ok", "ok"]
    lin = C.dge_analysis(genes, meta, {"grp": ["A", "B"]}, id_col="id", n_jobs=1)
    # linear scale: log2 of the ratio of the group means, undefined when a mean is 0
    assert lin.loc[0, "Log2FC"] == pytest.approx(np.log2(3.0 / 1.0))
    assert np.isnan(lin.loc[1, "Log2FC"]) and "Mean_nonpositive" in lin.loc[1, "Status"]
    assert log["P_value"].tolist() == pytest.approx(lin["P_value"].tolist())


def test_ssgsea_scores_every_gene_column(monkeypatch):
    from synomicsbench.metrics.autobenchmark import BenchmarkConfig
    from synomicsbench.metrics.autobenchmark import runners as R

    seen = []

    def capture(gene_matrix, gene_set, **kwargs):
        seen.append(list(gene_matrix["Gene"]))
        raise RuntimeError("stop")
    monkeypatch.setattr(R._compute, "ssgsea_scores", capture)
    ori = _toy_cohort(seed=0).set_index("Patient")
    cand = R.Candidate("ctgan", 0, _toy_cohort(seed=1).set_index("Patient"))
    with pytest.raises(RuntimeError, match="stop"):
        R.run_ssgsea(ori, [cand], BenchmarkConfig(gene_start_column="G0"))
    # all the genes, the last column included
    assert seen[0] == [f"G{g}" for g in range(6)]


def test_fges_gmt_is_one_knowledge_level():
    from synomicsbench.metrics.autobenchmark import FGES_GMT
    from synomicsbench.metrics.privacy.knowledge import knowledge_levels, read_gmt
    union = {g for genes in read_gmt(FGES_GMT).values() for g in genes}
    genes = sorted(union)[:5] + ["NOT_A_GENE"]
    levels = knowledge_levels(["age"], genes, proportions=(), gene_sets={"FGES": FGES_GMT})
    assert levels == [("FGES", ["age"] + sorted(union)[:5])]


def test_default_gene_set_is_bundled():
    from synomicsbench.metrics.autobenchmark import HALLMARK_GMT
    from synomicsbench.metrics.privacy.knowledge import read_gmt
    sets = read_gmt(HALLMARK_GMT)
    assert len(sets) == 50 and "HALLMARK_INTERFERON_GAMMA_RESPONSE" in sets


def test_run_benchmark_rejects_empty_phenotype_groups_and_zero_weights(tmp_path):
    from synomicsbench.metrics.autobenchmark import run_benchmark
    ori = _toy_cohort()
    with pytest.raises(ValueError, match="Group 'Responder'"):
        run_benchmark(ori, {"a_0": ori}, metrics="survival", gene_start_column="G0",
                      responder_values=("Responder",), output_dir=str(tmp_path))
    with pytest.raises(ValueError, match="sum to zero"):
        run_benchmark(ori, {"a_0": ori}, metrics="survival", gene_start_column="G0",
                      weights=(1, 0, 0), output_dir=str(tmp_path))
    with pytest.raises(ValueError, match="non-negative"):
        BenchmarkConfig(scenarios={"bad": (0, 0, 0)})


def test_duplicate_dataset_names_are_rejected():
    from synomicsbench.metrics.autobenchmark import BenchmarkRunner
    runner = BenchmarkRunner(BenchmarkConfig())
    df = pd.DataFrame({"x": [1]})
    with pytest.raises(ValueError, match="CTGAN_0"):
        runner._candidates({"ctgan_0": df, "ctgan": df})


def test_metric_group_in_a_list_skips_cell_deconvolution_without_results(tmp_path, monkeypatch):
    from synomicsbench.metrics.autobenchmark import runner as RN
    seen = {}

    def fake_run(self, original, datasets, metrics=None, seed=0):
        seen["dims"] = list(metrics)
        return _dummy_result()

    monkeypatch.setattr(RN.BenchmarkRunner, "run", fake_run)
    res = RN.run_benchmark(None, None, metrics=["utility", "privacy"], output_dir=str(tmp_path))
    assert "Cell Deconvolution" not in seen["dims"] and "DGE" in seen["dims"] and "Inference" in seen["dims"]
    assert "Cell Deconvolution" in res.errors
    RN.run_benchmark(None, None, metrics=["utility", "cell_deconvolution"], output_dir=str(tmp_path))
    assert "Cell Deconvolution" in seen["dims"]


def test_single_pillar_report_has_no_weight_analysis(tmp_path):
    from synomicsbench.metrics.autobenchmark import run_benchmark
    ori = _toy_cohort()
    res = run_benchmark(ori, {"a_0": _toy_cohort(seed=1), "b_0": _toy_cohort(seed=2)}, metrics="survival",
                        gene_start_column="G0", output_dir=str(tmp_path))
    doc = open(res.report_html, encoding="utf-8").read()
    assert "do not change" in doc and 'id="tri-canvas"' not in doc
    assert not (tmp_path / "metascore_scenarios.csv").exists()

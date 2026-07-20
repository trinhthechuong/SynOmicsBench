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


def test_config_mode_validation():
    cfg = BenchmarkConfig(metadata={}, modes={"DGE": "bogus"})
    assert cfg.mode_for("Univariate") == "compute"
    with pytest.raises(ValueError):
        cfg.mode_for("DGE")


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
    assert list(comp.columns) == ["Broad Utility", "Narrow Utility", "Privacy", "Total"]
    assert len(comp) == len(METHODS)
    # Total equals the sum of the three pillars.
    np.testing.assert_allclose(comp["Total"].values,
                               comp[["Broad Utility", "Narrow Utility", "Privacy"]].sum(axis=1).values)


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
    _, composite = plot_weighted_composite_scores(ms)
    import matplotlib.pyplot as plt
    plt.close("all")
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


def test_overall_privacy_from_attacks_matches_1_minus_mean():
    from synomicsbench.metrics.autobenchmark import privacy as P
    tools = ["A", "B"]
    uni = {"A": [_Evaluator(0.2, 0.1), _Evaluator(0.3, 0.1)], "B": [_Evaluator(0.5, 0.4), _Evaluator(0.5, 0.6)]}
    multi = {"A": [_Evaluator(0.1, 0.05)], "B": [_Evaluator(0.2, 0.2)]}
    link = {"A": [_Evaluator(0.2, 0.1)], "B": [_Evaluator(0.4, 0.1)]}
    # inference: an error entry must be skipped; EvaluationResults has no baseline
    infer = {"A": [("s1", _Results(0.4)), ("s2", {"error": "boom"})], "B": [("s1", _Results(0.2))]}
    scores = P.overall_privacy_from_attacks(uni, multi, link, infer, tools)
    # A: uni=mean(0.2,0.3)=0.25 (naive<attack); multi=0.1; link=0.2; infer=0.4 → 1-mean=1-0.2375=0.7625
    assert abs(scores["A"] - 0.7625) < 1e-9
    # B: uni=mean(0.5,0.6)=0.55 (2nd floored to naive 0.6); multi=0.2; link=0.4; infer=0.2 → 1-0.3375=0.6625
    assert abs(scores["B"] - 0.6625) < 1e-9


def test_write_html_report_is_self_contained(tmp_path):
    from synomicsbench.metrics.autobenchmark import write_html_report
    result = _dummy_result()
    config = BenchmarkConfig(metadata={}, output_dir=str(tmp_path))
    path = write_html_report(result, config)
    assert path.endswith("report.html")
    doc = open(path, encoding="utf-8").read()
    # self-contained: full document, embedded images, no external/CDN references
    assert "<html" in doc.lower()
    assert "data:image/png;base64," in doc
    assert "http://" not in doc and "https://" not in doc
    # narrative + transparency: winner named, all 8 dimensions present
    winner = result.composite["Total"].idxmin()
    assert winner in doc
    for dim in ALL_DIMS:
        assert dim in doc
    # the three pillars are labelled
    for pillar in ("Broad Utility", "Narrow Utility", "Privacy"):
        assert pillar in doc

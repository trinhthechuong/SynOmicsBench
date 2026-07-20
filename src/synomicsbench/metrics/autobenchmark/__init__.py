"""
Automatic benchmark for synthetic data generation (SDG).

Given the original data and a list of synthetic datasets, run all metric
dimensions in one pass (statistical fidelity, biological/narrow utility and
privacy), aggregate a rank-derived meta-score, and emit a comprehensive report
plus the weighted composite figure — replacing the manual, per-metric-then-
aggregate workflow while staying numerically consistent with it.

Example
-------
>>> from synomicsbench.metrics.autobenchmark import BenchmarkConfig, BenchmarkRunner, write_report
>>> config = BenchmarkConfig(metadata="metadata.json", gene_set="h.all.gmt",
...                          output_dir="results", cibersortx_dir="cibersort",
...                          privacy_pickle_dir="Privacy")
>>> runner = BenchmarkRunner(config)
>>> result = runner.run("original_data.csv",
...                     [{"method": "Gaussian Copula", "seed": 42, "data": "gaussiancopula_42.csv"}])
>>> write_report(result, config)
"""

from .config import BenchmarkConfig, NAME_MAP, ALL_DIMS, BROAD_DIMS, NARROW_DIMS, PRIVACY_DIMS
from .runner import BenchmarkRunner, BenchmarkResult
from .runners import Candidate
from .report import write_report
from .html_report import write_html_report
from .metascore import build_metascore, plot_weighted_composite_scores, COMPONENT_COLORS

__all__ = [
    "BenchmarkConfig",
    "BenchmarkRunner",
    "BenchmarkResult",
    "Candidate",
    "write_report",
    "write_html_report",
    "build_metascore",
    "plot_weighted_composite_scores",
    "COMPONENT_COLORS",
    "NAME_MAP",
    "ALL_DIMS",
    "BROAD_DIMS",
    "NARROW_DIMS",
    "PRIVACY_DIMS",
]

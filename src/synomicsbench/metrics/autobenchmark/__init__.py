"""
Automatic benchmark for synthetic data generation (SDG).

Given the original data and synthetic datasets, compute the selected metrics of the three
pillars (statistical fidelity, biological utility, privacy), rank the datasets into the
rank-derived meta-score, test its sensitivity to the pillar weights, and write a
self-contained report.

Example
-------
>>> from synomicsbench.metrics.autobenchmark import run_benchmark
>>> res = run_benchmark("original.csv", "synthetic/", metrics="all",
...                     cibersortx="cibersortx/", output_dir="benchmark")
>>> res.ranking          # meta-score per method, best first
>>> res.report_html      # path of the HTML report
"""

from .config import (BenchmarkConfig, NAME_MAP, ALL_DIMS, BROAD_DIMS, NARROW_DIMS, PRIVACY_DIMS, PILLARS,
                     LOWER_IS_BETTER, METRICS, METRIC_GROUPS, SCENARIOS, SCENARIO_DESCRIPTIONS, HALLMARK_GMT,
                     resolve_metrics)
from synomicsbench.metrics.privacy.knowledge import FGES_GMT
from .runner import BenchmarkRunner, BenchmarkResult, run_benchmark
from .runners import Candidate
from .report import write_report
from .html_report import write_html_report
from .metascore import (build_metascore, composite_scores, pillar_scores, scenario_table, weight_sweep,
                        plot_weighted_composite_scores, COMPONENT_COLORS)

__all__ = [
    "run_benchmark",
    "BenchmarkConfig",
    "BenchmarkRunner",
    "BenchmarkResult",
    "Candidate",
    "write_report",
    "write_html_report",
    "build_metascore",
    "composite_scores",
    "pillar_scores",
    "scenario_table",
    "weight_sweep",
    "plot_weighted_composite_scores",
    "resolve_metrics",
    "COMPONENT_COLORS",
    "NAME_MAP",
    "METRICS",
    "METRIC_GROUPS",
    "SCENARIOS",
    "HALLMARK_GMT",
    "FGES_GMT",
    "SCENARIO_DESCRIPTIONS",
    "ALL_DIMS",
    "BROAD_DIMS",
    "NARROW_DIMS",
    "PRIVACY_DIMS",
    "PILLARS",
    "LOWER_IS_BETTER",
]

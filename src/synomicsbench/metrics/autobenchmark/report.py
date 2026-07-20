"""
Comprehensive report writer for the automatic benchmark.

Persists, into ``config.output_dir`` (a fresh directory — never an existing
results folder):

- ``per_metric_values.csv`` / ``per_metric_ranks.csv`` : method x dimension tables
- ``per_dimension_long.csv``                            : every (method, seed, dimension, value)
- ``metascore.json`` / ``metascore_composite.csv``      : rank-derived scores + composite pillars
- ``metascore_composite.pdf`` / ``.png``                : the stacked-bar composite figure
- ``per_metric_scores.png``                             : per-dimension value bars (dataset colors)
- ``REPORT.md``                                         : a human-readable summary
"""

from __future__ import annotations

import json
import os
from typing import List

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from .config import BenchmarkConfig, ALL_DIMS
from .metascore import plot_weighted_composite_scores
from synomicsbench.metrics.fidelity.visualization import DATASET_COLORS


def write_report(result, config: BenchmarkConfig) -> dict:
    """Write all report artifacts and return a dict of output paths."""
    out = config.output_dir
    os.makedirs(out, exist_ok=True)
    paths = {}

    # 1. Long per-(method, seed, dimension, value) table.
    long_rows = []
    for dim, df in result.per_dim_values.items():
        tmp = df.copy()
        tmp["Dimension"] = dim
        long_rows.append(tmp)
    if long_rows:
        long_df = pd.concat(long_rows, ignore_index=True)[["Dimension", "Model", "Seed", "Value"]]
        p = os.path.join(out, "per_dimension_long.csv")
        long_df.to_csv(p, index=False)
        paths["per_dimension_long"] = p

    # 2. Wide value / rank tables.
    p = os.path.join(out, "per_metric_values.csv")
    result.value_table.to_csv(p)
    paths["per_metric_values"] = p
    p = os.path.join(out, "per_metric_ranks.csv")
    result.rank_table.to_csv(p)
    paths["per_metric_ranks"] = p

    # 3. Meta-score JSON.
    p = os.path.join(out, "metascore.json")
    with open(p, "w") as fh:
        json.dump(result.metascore, fh, indent=4)
    paths["metascore_json"] = p

    # 4. Composite (only when all eight dimensions are present).
    if all(d in result.metascore for d in ALL_DIMS):
        fig, composite = plot_weighted_composite_scores(
            result.metascore,
            broad_weight=config.weights[0],
            narrow_weight=config.weights[1],
            privacy_weight=config.weights[2],
            save_path=os.path.join(out, "metascore_composite.pdf"),
        )
        fig.savefig(os.path.join(out, "metascore_composite.png"), dpi=300, bbox_inches="tight")
        plt.close(fig)
        composite.to_csv(os.path.join(out, "metascore_composite.csv"))
        paths["composite_csv"] = os.path.join(out, "metascore_composite.csv")
        paths["composite_pdf"] = os.path.join(out, "metascore_composite.pdf")
        paths["composite_png"] = os.path.join(out, "metascore_composite.png")

    # 5. Per-dimension value bars (dataset colors).
    fig_path = os.path.join(out, "per_metric_scores.png")
    _plot_per_metric_values(result.value_table, fig_path)
    paths["per_metric_scores"] = fig_path

    # 6. Human-readable summary.
    p = os.path.join(out, "REPORT.md")
    with open(p, "w") as fh:
        fh.write(_render_markdown(result, config))
    paths["report_md"] = p

    # 7. Self-contained, eye-catching HTML report.
    from .html_report import write_html_report
    paths["report_html"] = write_html_report(result, config)

    return paths


def _plot_per_metric_values(value_table: pd.DataFrame, path: str) -> None:
    """Grouped bar chart of per-dimension values, one color per SDG method."""
    if value_table.empty:
        return
    methods = list(value_table.index)
    dims = list(value_table.columns)
    x = np.arange(len(dims))
    n = len(methods)
    width = 0.8 / max(n, 1)
    fig, ax = plt.subplots(figsize=(max(8, 1.4 * len(dims)), 5))
    for i, method in enumerate(methods):
        ax.bar(x + i * width, value_table.loc[method, dims].values, width,
               label=method, color=DATASET_COLORS.get(method, "#999999"),
               edgecolor="white", linewidth=0.8)
    ax.set_xticks(x + width * (n - 1) / 2)
    ax.set_xticklabels(dims, rotation=30, ha="right")
    ax.set_ylabel("Score (higher = better)")
    ax.set_title("Per-metric scores by SDG method")
    ax.legend(fontsize=8, ncol=min(n, 3))
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    ax.set_axisbelow(True)
    plt.tight_layout()
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close(fig)


def _render_markdown(result, config: BenchmarkConfig) -> str:
    lines: List[str] = ["# Automatic Benchmark Report", ""]
    lines.append(f"- Dimensions evaluated: {', '.join(result.dims_run) or 'none'}")
    if result.dims_missing:
        lines.append(f"- Dimensions missing/skipped/failed: {', '.join(result.dims_missing)}")
    lines.append("")
    lines.append("## Per-metric scores (mean over seeds, higher = better)")
    lines.append("")
    lines.append(result.value_table.round(4).to_markdown())
    lines.append("")
    lines.append("## Rank-derived meta-score per dimension (lower = better)")
    lines.append("")
    lines.append(result.rank_table.round(3).to_markdown())
    lines.append("")
    if result.composite is not None:
        lines.append("## Composite (lower Total = more balanced)")
        lines.append("")
        lines.append(result.composite.round(3).to_markdown())
        lines.append("")
        best = result.composite["Total"].idxmin()
        lines.append(f"**Most balanced method: {best}** (Total = {result.composite['Total'].min():.3f}).")
    else:
        lines.append("_Composite not built: not all eight dimensions were available._")
    lines.append("")
    return "\n".join(lines)

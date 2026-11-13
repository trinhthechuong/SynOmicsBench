"""
Comprehensive report writer for the automatic benchmark.

Writes into ``config.output_dir``:

- ``report.html``                                       : the self-contained report
- ``REPORT.md``                                         : the same tables in Markdown
- ``per_metric_values.csv`` / ``per_metric_ranks.csv`` : method x dimension tables
- ``per_dimension_long.csv``                            : every (dimension, method, seed, value)
- ``metascore.json`` / ``metascore_composite.csv``      : rank-derived scores and meta-score
- ``metascore_scenarios.csv``                           : meta-score and rank under each weighting scenario
- ``weight_sweep_summary.csv``                          : rank of each method over all pillar weights
- ``metascore_composite.pdf`` / ``.png``                : the stacked-bar composite figure
- ``per_metric_scores.png``                             : per-dimension values by method
- ``result.pkl``                                        : the ``BenchmarkResult``, to rewrite the report
"""

from __future__ import annotations

import json
import os
import pickle
from typing import List

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from .config import BenchmarkConfig, LOWER_IS_BETTER, PILLARS
from .metascore import composite_scores, pillar_scores, plot_weighted_composite_scores, scenario_table, weight_sweep
from synomicsbench.metrics.fidelity.visualization import DATASET_COLORS


def write_report(result, config: BenchmarkConfig) -> dict:
    """Write all report artifacts and return a dict of output paths."""
    out = config.output_dir
    os.makedirs(out, exist_ok=True)
    paths = {}

    # The result itself first, to rewrite the report without recomputing.
    p = os.path.join(out, "result.pkl")
    with open(p, "wb") as fh:
        pickle.dump(result, fh)
    paths["result_pkl"] = p

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

    # 4. Meta-score, weighting scenarios and weight sweep.
    if result.metascore:
        fig, _ = plot_weighted_composite_scores(
            result.metascore,
            broad_weight=config.weights[0],
            narrow_weight=config.weights[1],
            privacy_weight=config.weights[2],
            save_path=os.path.join(out, "metascore_composite.pdf"),
        )
        fig.savefig(os.path.join(out, "metascore_composite.png"), dpi=300, bbox_inches="tight")
        plt.close(fig)
        composite_scores(result.metascore, config.weights).to_csv(os.path.join(out, "metascore_composite.csv"))
        paths["composite_csv"] = os.path.join(out, "metascore_composite.csv")
        paths["composite_pdf"] = os.path.join(out, "metascore_composite.pdf")
        paths["composite_png"] = os.path.join(out, "metascore_composite.png")
        if (config.scenarios and len(pillar_scores(result.metascore).columns) > 1
                and not scenario_table(result.metascore, config.scenarios).empty):
            p = os.path.join(out, "metascore_scenarios.csv")
            scenario_table(result.metascore, config.scenarios).to_csv(p)
            paths["scenarios_csv"] = p
        if all(any(d in result.metascore for d in dims) for dims in PILLARS.values()):
            p = os.path.join(out, "weight_sweep_summary.csv")
            weight_sweep(result.metascore)[1].to_csv(p)
            paths["weight_sweep_csv"] = p

    # 5. Per-dimension value bars (dataset colors).
    fig_path = os.path.join(out, "per_metric_scores.png")
    _plot_per_metric_values(result.value_table, fig_path)
    paths["per_metric_scores"] = fig_path

    # 6. Human-readable summary.
    p = os.path.join(out, "REPORT.md")
    with open(p, "w") as fh:
        fh.write(_render_markdown(result, config))
    paths["report_md"] = p

    # 7. Self-contained HTML report.
    from .html_report import write_html_report
    paths["report_html"] = write_html_report(result, config)

    return paths


def _plot_per_metric_values(value_table: pd.DataFrame, path: str) -> None:
    """Grouped bar charts of per-dimension values, one color per SDG method.

    Scores (higher = better) and risks (lower = better) are drawn in separate panels.
    """
    if value_table.empty:
        return
    methods = list(value_table.index)
    panels = [(dims, label) for dims, label in (
        ([d for d in value_table.columns if d not in LOWER_IS_BETTER], "Score (higher = better)"),
        ([d for d in value_table.columns if d in LOWER_IS_BETTER], "Risk (lower = better)"),
    ) if dims]
    n = len(methods)
    width = 0.8 / max(n, 1)
    fig, axes = plt.subplots(1, len(panels), squeeze=False,
                             figsize=(max(8, 1.4 * value_table.shape[1]), 5),
                             gridspec_kw={"width_ratios": [len(d) for d, _ in panels]})
    for ax, (dims, ylabel) in zip(axes[0], panels):
        x = np.arange(len(dims))
        for i, method in enumerate(methods):
            ax.bar(x + i * width, value_table.loc[method, dims].values, width,
                   label=method, color=DATASET_COLORS.get(method, "#999999"),
                   edgecolor="white", linewidth=0.8)
        ax.set_xticks(x + width * (n - 1) / 2)
        ax.set_xticklabels(dims, rotation=30, ha="right")
        ax.set_ylabel(ylabel)
        ax.grid(axis="y", linestyle="--", alpha=0.4)
        ax.set_axisbelow(True)
    axes[0][0].legend(fontsize=8, ncol=min(n, 3))
    fig.suptitle("Per-metric values by SDG method")
    plt.tight_layout()
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close(fig)


def _markdown_table(df: pd.DataFrame, decimals: int) -> str:
    """Pipe table of ``df`` (index as first column), numbers rounded to ``decimals``."""
    def cell(v) -> str:
        if isinstance(v, (float, np.floating)):
            return "" if np.isnan(v) else f"{v:.{decimals}f}"
        return str(v)

    header = [str(df.index.name or "")] + [str(c) for c in df.columns]
    rows = [[str(idx)] + [cell(v) for v in row] for idx, row in zip(df.index, df.to_numpy())]
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    lines += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(lines)


def _render_markdown(result, config: BenchmarkConfig) -> str:
    lines: List[str] = ["# Automatic Benchmark Report", ""]
    lines.append(f"- Metrics evaluated: {', '.join(result.dims_run) or 'none'}")
    for dim in result.dims_missing:
        lines.append(f"- Not evaluated: {dim} ({getattr(result, 'errors', {}).get(dim, 'not computed')})")
    lines.append("")
    lines.append("## Per-metric values (mean over seeds; scores higher = better, privacy risks lower = better)")
    lines.append("")
    lines.append(_markdown_table(result.value_table, 4))
    lines.append("")
    lines.append("## Rank-derived score per metric (lower = better)")
    lines.append("")
    lines.append(_markdown_table(result.rank_table, 3))
    lines.append("")
    if result.composite is None:
        lines.append("_No metric was evaluated: no meta-score._")
        lines.append("")
        return "\n".join(lines)
    lines.append("## Meta-score (weighted pillar scores; lower Total = better)")
    lines.append("")
    lines.append(_markdown_table(result.composite, 3))
    lines.append("")
    best = result.composite["Total"].idxmin()
    lines.append(f"**Best overall: {best}** (meta-score {result.composite['Total'].min():.3f}).")
    lines.append("")
    table = scenario_table(result.metascore, config.scenarios) if config.scenarios else pd.DataFrame()
    if len(result.composite.columns) > 2 and not table.empty:
        table.columns = [f"{name} {kind.lower()}" for name, kind in table.columns]
        lines.append("## Weighting scenarios")
        lines.append("")
        lines.append("Pillar weights (statistical fidelity, biological utility, privacy): " + "; ".join(
            f"{name} ({', '.join(f'{w:.2f}' for w in ws)})" for name, ws in config.scenarios.items()) + ".")
        lines.append("")
        lines.append(_markdown_table(table, 2))
        lines.append("")
    if all(any(d in result.metascore for d in dims) for dims in PILLARS.values()):
        lines.append("## Rank over all pillar weights (weight grid, step 0.01)")
        lines.append("")
        lines.append(_markdown_table(weight_sweep(result.metascore)[1], 2))
        lines.append("")
    return "\n".join(lines)

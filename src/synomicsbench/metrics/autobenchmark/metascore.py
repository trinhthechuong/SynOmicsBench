"""
Rank-derived meta-score aggregation and the weighted composite plot.

For each dimension, all candidates (method x seed) are ranked jointly (rank 1 = the highest
score, or the lowest value for the dimensions in ``LOWER_IS_BETTER`` such as privacy risks;
ties share the minimum rank); each method's dimension score is the
mean rank of its replicates. The score of a pillar (statistical fidelity, biological
utility, privacy) is the mean of its dimensions' scores, and the meta-score is the
weighted sum of the pillar scores: a lower total = a more balanced method.
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from synomicsbench.metrics.fidelity.visualization import DATASET_COLORS

from .config import LOWER_IS_BETTER, PILLARS

# Component (pillar) colors.
COMPONENT_COLORS = {
    "Statistical fidelity": "#3498db",  # blue
    "Biological utility": "#9b59b6",    # purple
    "Privacy": "#e74c3c",               # red
}


def build_metascore(per_dim_values: Dict[str, pd.DataFrame],
                    collapse_dims: tuple = (),
                    lower_is_better: tuple = LOWER_IS_BETTER) -> Dict[str, Dict[str, float]]:
    """Convert per-dimension candidate values into per-method mean ranks.

    Values are rounded to 12 decimals before ranking, so that scores differing only in
    the last floating-point bit tie. Missing values rank last.

    Args:
        per_dim_values: dimension name -> DataFrame with columns ['Model', 'Seed', 'Value'].
            'Value' is the value of that (method, seed) candidate: a score (higher = better),
            or a risk for the dimensions in ``lower_is_better``.
        collapse_dims: dimensions whose per-(method, seed) values are replaced by the
            per-method mean before ranking. Default: none (every dimension ranked per seed).
        lower_is_better: dimensions ranked in increasing order (default: the privacy risks).

    Returns:
        dict: ``MetaScore[dimension][model]`` = mean rank (lower = better).
    """
    metascore: Dict[str, Dict[str, float]] = {}
    for dim, df in per_dim_values.items():
        if df is None or df.empty:
            continue
        d = df.copy()
        ascending = dim in lower_is_better
        d["Value"] = pd.to_numeric(d["Value"], errors="coerce").fillna(np.inf if ascending else 0.0)
        if dim in collapse_dims:
            d["Value"] = d.groupby("Model")["Value"].transform("mean")
        d["Rank"] = d["Value"].round(12).rank(ascending=ascending, method="min").astype(int)
        rank_by_model = {m: float(d.loc[d["Model"] == m, "Rank"].mean())
                         for m in d["Model"].unique()}
        metascore[dim] = rank_by_model
    return metascore


def pillar_scores(MetaScore: dict) -> pd.DataFrame:
    """Unweighted pillar scores: the mean rank-derived score of each pillar's dimensions.

    Pillars without any dimension in ``MetaScore`` are left out.

    Returns:
        DataFrame indexed by method, one column per present pillar (lower = better).
    """
    df = pd.DataFrame(MetaScore)
    out = pd.DataFrame(index=df.index)
    for pillar, dims in PILLARS.items():
        present = [d for d in dims if d in df.columns]
        if present:
            out[pillar] = df[present].mean(axis=1)
    return out


def _normalised_weights(pillars, weights) -> Dict[str, float]:
    """Weights of the present pillars, rescaled to sum to 1."""
    w = {p: float(v) for p, v in zip(PILLARS, weights) if p in pillars}
    total = sum(w.values())
    if total <= 0:
        raise ValueError("The weights of the evaluated pillars sum to zero.")
    return {p: v / total for p, v in w.items()}


def composite_scores(MetaScore: dict, weights: Tuple[float, float, float] = (1 / 3, 1 / 3, 1 / 3)) -> pd.DataFrame:
    """Weighted pillar scores and their sum (``Total``, the meta-score; lower = better).

    ``weights`` are the (statistical fidelity, biological utility, privacy) weights. When a
    pillar has no evaluated dimension it is left out and the other weights are rescaled to
    sum to 1.

    Returns:
        DataFrame indexed by method, sorted by increasing ``Total``.
    """
    pillars = pillar_scores(MetaScore)
    if pillars.empty or not len(pillars.columns):
        raise ValueError("No evaluated dimension: the meta-score cannot be computed.")
    w = _normalised_weights(pillars.columns, weights)
    out = pd.DataFrame({p: pillars[p] * w[p] for p in pillars.columns})
    out["Total"] = out.sum(axis=1)
    return out.sort_values("Total", kind="stable")


def scenario_table(MetaScore: dict, scenarios: Dict[str, Tuple[float, float, float]]) -> pd.DataFrame:
    """Meta-score and rank of every method under each weighting scenario.

    Returns:
        DataFrame indexed by method, with columns ``(scenario, "Score")`` and
        ``(scenario, "Rank")`` (rank 1 = lowest meta-score; ties share the lowest rank),
        sorted by the rank under the first scenario. A scenario that puts no weight on the
        evaluated pillars is left out.
    """
    evaluated = list(pillar_scores(MetaScore).columns)
    cols = {}
    for name, weights in scenarios.items():
        if sum(w for p, w in zip(PILLARS, weights) if p in evaluated) <= 0:
            continue          # the scenario puts no weight on the evaluated pillars
        total = composite_scores(MetaScore, weights)["Total"]
        cols[(name, "Score")] = total
        cols[(name, "Rank")] = total.rank(method="min").astype(int)
    table = pd.DataFrame(cols)
    if table.empty:
        return table
    table.columns = pd.MultiIndex.from_tuples(table.columns)
    first = table.columns[0][0]
    return table.sort_values((first, "Rank"), kind="stable")


def simplex_grid(step: float = 0.01):
    """Every (statistical fidelity, biological utility, privacy) weight triple summing to 1."""
    n = round(1 / step)
    return [(i / n, j / n, (n - i - j) / n) for i in range(n + 1) for j in range(n + 1 - i)]


def weight_sweep(MetaScore: dict, step: float = 0.01) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Rank of every method over all pillar weights, on a grid of the weight simplex.

    Each grid point is a weight triple summing to 1 (step ``step``); the meta-score is the
    weighted sum of the unweighted pillar scores (:func:`pillar_scores`). Needs the three
    pillars.

    Returns:
        (sweep, summary): ``sweep`` has one row per grid point with the weights
        (``w_stat``, ``w_bio``, ``w_priv``), the first-ranked method (``First``) and the rank
        of every method; ``summary`` gives, per method, the share of the grid where it ranks
        first (in %) and its mean, best and worst rank, sorted by mean rank.
    """
    pillars = pillar_scores(MetaScore)
    missing = [p for p in PILLARS if p not in pillars.columns]
    if missing:
        raise ValueError(f"The weight sweep needs the three pillars; missing: {missing}.")
    methods = list(pillars.index)
    values = pillars[list(PILLARS)].to_numpy()
    rows = []
    for w in simplex_grid(step):
        total = pd.Series(values @ np.asarray(w), index=methods)
        rank = total.rank(method="min")
        rows.append({"w_stat": w[0], "w_bio": w[1], "w_priv": w[2], "First": total.idxmin(),
                     **{m: rank[m] for m in methods}})
    sweep = pd.DataFrame(rows)
    ranks = sweep[methods]
    summary = pd.DataFrame({
        "First place (%)": (sweep["First"].value_counts(normalize=True) * 100).reindex(methods).fillna(0.0),
        "Mean rank": ranks.mean(),
        "Best rank": ranks.min().astype(int),
        "Worst rank": ranks.max().astype(int),
    }).sort_values("Mean rank", kind="stable")
    return sweep, summary


def plot_weighted_composite_scores(
    MetaScore: dict,
    broad_weight: float = 1 / 3,
    narrow_weight: float = 1 / 3,
    privacy_weight: float = 1 / 3,
    figsize: tuple = (6, 4),
    save_path: Optional[str] = None,
    orientation: str = "horizontal",
) -> Tuple[plt.Figure, pd.DataFrame]:
    """Plot weighted composite (stacked-bar) scores.

    Each pillar is the mean rank-derived score of its dimensions present in ``MetaScore``,
    multiplied by its weight (``broad_weight`` = statistical fidelity, ``narrow_weight`` =
    biological utility, ``privacy_weight`` = privacy). Lower total = a more balanced method.

    Returns:
        (figure, composite DataFrame with one column per pillar and ``Total``, sorted by
        decreasing total).

    Pillars without any dimension in ``MetaScore`` are left out and the other weights
    rescaled to sum to 1 (see :func:`composite_scores`).
    """
    try:
        import scienceplots  # noqa: F401  (registers the "science" matplotlib styles)

        plt.style.use(["science", "nature", "notebook"])
    except Exception:
        pass

    plt.rcParams.update({
        "text.usetex": False,
        "axes.edgecolor": "#333333",
        "xtick.minor.visible": False,
        "ytick.minor.visible": False,
        "xtick.top": False,
        "ytick.right": False,
    })

    composite = composite_scores(MetaScore, (broad_weight, narrow_weight, privacy_weight))
    components = [p for p in PILLARS if p in composite.columns]
    df_final = composite.sort_values("Total", ascending=(orientation == "vertical"))[components].copy()

    fig, ax = plt.subplots(figsize=figsize)
    datasets = df_final.index.tolist()
    n_datasets = len(datasets)

    if orientation == "horizontal":
        y = np.arange(n_datasets)
        height = 0.6
        left = np.zeros(n_datasets)
        for component in components:
            values = df_final[component].values
            color = COMPONENT_COLORS[component]
            bars = ax.barh(y, values, height, left=left, label=component,
                           color=color, edgecolor="white", linewidth=1.5, alpha=0.9)
            for i, (bar, val) in enumerate(zip(bars, values)):
                if val > 0.5:
                    ax.text(left[i] + val / 2, bar.get_y() + bar.get_height() / 2,
                            f"{val:.2f}", ha="center", va="center",
                            color="white", fontsize=8, fontweight="bold")
            left += values
        for i, total in enumerate(left):
            ax.text(total + 0.3, i, f"{total:.2f}", ha="left", va="center",
                    color="black", fontsize=10, fontweight="bold")
        ax.set_xlabel("Rank-derived score", fontsize=12, fontweight="bold")
        ax.set_ylabel("SDG methods", fontsize=12, fontweight="bold")
        ax.set_yticks(y)
        ax.set_yticklabels([f"$\\mathbf{{{ds}}}$" for ds in datasets], fontsize=10)
        for tick_label, dataset in zip(ax.get_yticklabels(), datasets):
            tick_label.set_color(DATASET_COLORS.get(dataset, "#333333"))
        ax.grid(axis="x", linestyle="--", linewidth=0.6, alpha=0.5)
        ax.set_axisbelow(True)
        ax.set_xlim(0, left.max() * 1.15)
    else:
        x = np.arange(n_datasets)
        width = 0.6
        bottom = np.zeros(n_datasets)
        for component in components:
            values = df_final[component].values
            color = COMPONENT_COLORS[component]
            bars = ax.bar(x, values, width, bottom=bottom, label=component,
                          color=color, edgecolor="white", linewidth=1.5, alpha=0.9)
            for i, (bar, val) in enumerate(zip(bars, values)):
                if val > 0.5:
                    ax.text(bar.get_x() + bar.get_width() / 2, bottom[i] + val / 2,
                            f"{val:.2f}", ha="center", va="center",
                            color="white", fontsize=9, fontweight="bold")
            bottom += values
        for i, total in enumerate(bottom):
            ax.text(i, total + 0.3, f"{total:.2f}", ha="center", va="bottom",
                    color="black", fontsize=10, fontweight="bold")
        ax.set_ylabel("Rank-derived score", fontsize=12, fontweight="bold")
        ax.set_xlabel("SDG methods", fontsize=12, fontweight="bold")
        ax.set_xticks(x)
        ax.set_xticklabels([f"$\\mathbf{{{ds}}}$" for ds in datasets],
                           rotation=45, ha="right", fontsize=10)
        for tick_label, dataset in zip(ax.get_xticklabels(), datasets):
            tick_label.set_color(DATASET_COLORS.get(dataset, "#333333"))
        ax.grid(axis="y", linestyle="--", linewidth=0.6, alpha=0.5)
        ax.set_axisbelow(True)
        ax.set_ylim(0, bottom.max() * 1.1)

    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches="tight")

    df_final["Total"] = df_final.sum(axis=1)
    return fig, df_final.sort_values("Total", ascending=False)

"""
Rank-derived meta-score aggregation and the weighted composite plot.

Reproduces the logic of ``Manuscript/MetaScore/MetaScore_Melanoma.ipynb``:
for each of the eight dimensions, all candidates (method x seed) are ranked
(higher score = better = lower rank); each method's dimension score is the mean
rank of its replicates. The three pillars (broad = univariate+bivariate,
narrow = DGE+GSEA+ssGSEA+cell+survival, privacy) are combined with equal weights,
and a lower total = a more balanced method.
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from synomicsbench.metrics.fidelity.visualization import DATASET_COLORS

# Component (pillar) colors — identical to MetaScore_Melanoma.ipynb.
COMPONENT_COLORS = {
    "Broad Utility": "#3498db",   # blue
    "Narrow Utility": "#9b59b6",  # purple
    "Privacy": "#e74c3c",         # red
}

NARROW_METRICS = ["DGE", "GSEA", "ssGSEA", "Cell Deconvolution", "Survival Analysis"]


def build_metascore(per_dim_values: Dict[str, pd.DataFrame],
                    collapse_dims: tuple = ()) -> Dict[str, Dict[str, float]]:
    """Convert per-dimension candidate values into per-method mean ranks.

    Args:
        per_dim_values: dimension name -> DataFrame with columns ['Model', 'Seed', 'Value'].
            'Value' is the higher-is-better score for that (method, seed) candidate.
        collapse_dims: dimensions whose per-(method, seed) values are replaced by the
            per-method mean before ranking. This reproduces the manuscript MetaScore,
            where DGE/GSEA/Privacy were collapsed to one value per method. Default: none
            (every dimension ranked per-seed).

    Returns:
        dict: MetaScore[dimension][model] = mean rank (lower = better).
    """
    metascore: Dict[str, Dict[str, float]] = {}
    for dim, df in per_dim_values.items():
        if df is None or df.empty:
            continue
        d = df.copy()
        d["Value"] = pd.to_numeric(d["Value"], errors="coerce").fillna(0.0)
        if dim in collapse_dims:
            d["Value"] = d.groupby("Model")["Value"].transform("mean")
        d["Rank"] = d["Value"].rank(ascending=False, method="min").astype(int)
        rank_by_model = {m: float(d.loc[d["Model"] == m, "Rank"].mean())
                         for m in d["Model"].unique()}
        metascore[dim] = rank_by_model
    return metascore


def plot_weighted_composite_scores(
    MetaScore: dict,
    broad_weight: float = 1 / 3,
    narrow_weight: float = 1 / 3,
    privacy_weight: float = 1 / 3,
    figsize: tuple = (6, 4),
    save_path: Optional[str] = None,
    orientation: str = "horizontal",
) -> Tuple[plt.Figure, pd.DataFrame]:
    """Plot weighted composite (stacked-bar) scores. Ported from the MetaScore notebook.

    Lower total = a more balanced method. Returns (figure, sorted composite DataFrame).
    """
    try:
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

    df = pd.DataFrame(MetaScore)
    df_final = pd.DataFrame()

    broad_weighted = broad_weight * (1 / 2)
    df_final["Broad Utility"] = (
        df["Univariate"] * broad_weighted + df["Bivariate"] * broad_weighted
    )
    narrow_weighted = narrow_weight * (1 / 5)
    df_final["Narrow Utility"] = df[NARROW_METRICS].sum(axis=1) * narrow_weighted
    df_final["Privacy"] = df["Privacy"] * privacy_weight

    df_final["Total"] = df_final.sum(axis=1)
    df_final = df_final.sort_values("Total", ascending=(orientation == "vertical")).drop(columns="Total")

    fig, ax = plt.subplots(figsize=figsize)
    datasets = df_final.index.tolist()
    n_datasets = len(datasets)

    if orientation == "horizontal":
        y = np.arange(n_datasets)
        height = 0.6
        left = np.zeros(n_datasets)
        for component in ["Broad Utility", "Narrow Utility", "Privacy"]:
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
        for component in ["Broad Utility", "Narrow Utility", "Privacy"]:
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

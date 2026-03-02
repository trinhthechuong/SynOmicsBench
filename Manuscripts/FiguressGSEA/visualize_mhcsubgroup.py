from typing import Dict, List, Optional, Tuple
import warnings
import logging

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.patches import Rectangle
from scipy.stats import mannwhitneyu

# Consistent palette used across SynOmics visualizations
DATA_COLORS = {"real": "#4c72b0", "synthetic": "#dd8452"}

DEFAULT_DATASET_COLORS = {
    "Origin": "#4d4d4d",
    "Avatars K5": "#66c2a5",
    "Avatars K10": "#fc8d62",
    "CTGAN": "#8da0cb",
    "Gaussian Copula": "#e78ac3",
    "Synthpop": "#a6d854",
    "TVAE": "#ffd92f",
}

DEFAULT_GROUP_COLORS = {
    "Responder": DATA_COLORS["real"],
    "Progressor": DATA_COLORS["synthetic"],
}

logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)
warnings.filterwarnings("ignore")


def _pvalue_label(p: float) -> str:
    """
    Format p-value with significance stars.

    Args:
        p (float): P-value.

    Returns:
        str: Formatted label (NS/*/**/***) with p-value.
    """
    if p is None or not np.isfinite(p):
        return "NA"
    if p < 0.01:
        return f"*** (p={p:.3g})"
    if p < 0.05:
        return f"** (p={p:.3g})"
    if p < 0.1:
        return f"* (p={p:.3g})"
    return f"NS (p={p:.3g})"


def _mannwhitney_pvalue(x: List[float], y: List[float]) -> float:
    """
    Compute Wilcoxon rank-sum test (Mann–Whitney U) p-value.

    Args:
        x (List[float]): Values from group 1.
        y (List[float]): Values from group 2.

    Returns:
        float: Two-sided p-value.

    Raises:
        ValueError: If one group has no valid values.
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    x = x[np.isfinite(x)]
    y = y[np.isfinite(y)]
    if x.size == 0 or y.size == 0:
        raise ValueError("Both groups must contain at least one finite value.")
    res = mannwhitneyu(x, y, alternative="two-sided")
    return float(res.pvalue)


def _draw_pvalue_in_axes(
    ax: plt.Axes,
    label: str,
    x1: float = 0.18,
    x2: float = 0.82,
    y: float = 0.98,
    h: float = 0.04,
    lw: float = 1.0,
    fontsize: float = 9.0,
) -> None:
    """
    Draw a p-value bracket and label in axes coordinates (stable placement).

    Args:
        ax (plt.Axes): Target axis.
        label (str): Label to show above bracket.
        x1 (float): Left x position in axes coords (0..1).
        x2 (float): Right x position in axes coords (0..1).
        y (float): Baseline y position in axes coords (0..1).
        h (float): Bracket height in axes coords.
        lw (float): Line width.
        fontsize (float): Text fontsize.
    """
    trans = ax.transAxes
    ax.plot([x1, x1, x2, x2], [y, y + h, y + h, y], transform=trans, color="black", lw=lw, clip_on=False)
    ax.text((x1 + x2) / 2, y + h, label, transform=trans, ha="center", va="bottom", fontsize=fontsize, clip_on=False)


def plot_mhc_responders_vs_progressors(
    mhc_dict: Dict[str, Dict[str, Dict[str, List[float]]]],
    subgroups: Optional[List[str]] = None,
    datasets_order: Optional[List[str]] = None,
    dataset_colors: Optional[Dict[str, str]] = None,
    group_order: Tuple[str, str] = ("Responder", "Progressor"),
    group_palette: Optional[Dict[str, str]] = None,
    figsize: Tuple[float, float] = (15, 8),
    ylim: Optional[Tuple[float, float]] = None,
    show_points: bool = True,
    points_style: Optional[str] = "swarm",
    points_size: float = 2.6,
    points_alpha: float = 0.55,
    points_color: str = "black",
    strip_height: float = 0.015,
    strip_y: float = 1.015,
    show: bool = True,
    savepath: Optional[str] = None,
    show_legend: bool = True,  # Thay đổi: Thêm tham số show_legend để bật/tắt legend
) -> plt.Figure:
    """
    Plot boxplots comparing Responders vs Progressors across datasets and subgroups.

    Args:
        mhc_dict (Dict[str, Dict[str, Dict[str, List[float]]]]): Nested dictionary:
            mhc_dict[dataset][subgroup]["Responder"/"Progressor"] -> list of values.
        subgroups (Optional[List[str]]): Subgroups to plot.
        datasets_order (Optional[List[str]]): Dataset/method order (columns).
        dataset_colors (Optional[Dict[str, str]]): Mapping dataset -> color for titles.
        group_order (Tuple[str, str]): Group order on x-axis.
        group_palette (Optional[Dict[str, str]]): Mapping group -> box color.
        figsize (Tuple[float, float]): Figure size.
        ylim (Optional[Tuple[float, float]]): Fixed y-limits if provided.
        show_points (bool): If True, overlay points on top of boxplots.
        points_style (Optional[str]): "swarm", "strip", or None (disable points).
        points_size (float): Point size.
        points_alpha (float): Point alpha.
        points_color (str): Point color.
        strip_height (float): Colored strip height in axes coords.
        strip_y (float): Colored strip y position in axes coords.
        show (bool): If True, call plt.show().
        savepath (Optional[str]): If provided, save the figure.
        show_legend (bool): If True, add legend for groups.  # Thay đổi: Thêm mô tả cho show_legend

    Returns:
        plt.Figure: Matplotlib Figure.

    Raises:
        ValueError: If mhc_dict is empty.
        ValueError: If required groups are missing in input.
    """
    if not mhc_dict:
        raise ValueError("mhc_dict must not be empty.")

    if subgroups is None:
        subgroups = ["Overall", "IpiTreated", "IpiNaive"]

    if dataset_colors is None:
        dataset_colors = DEFAULT_DATASET_COLORS

    if group_palette is None:
        group_palette = DEFAULT_GROUP_COLORS

    if datasets_order is None:
        common_order = ["Origin", "Avatars K5", "Avatars K10", "CTGAN", "Gaussian Copula", "Synthpop", "TVAE"]
        present = [d for d in common_order if d in mhc_dict]
        datasets_order = present if present else list(mhc_dict.keys())

    # build long-form dataframe
    records = []
    for dataset in datasets_order:
        if dataset not in mhc_dict:
            continue
        for subgroup in subgroups:
            subgroup_data = mhc_dict[dataset].get(subgroup, {})
            for grp in group_order:
                if grp not in subgroup_data:
                    raise ValueError(f"Missing group '{grp}' in mhc_dict[{dataset}][{subgroup}].")
                for v in subgroup_data.get(grp, []):
                    records.append({"Dataset": dataset, "Subgroup": subgroup, "Group": grp, "Value": v})

    df = pd.DataFrame(records)
    if df.empty:
        raise ValueError("No data available after assembling mhc_dict into a dataframe.")

    nrows = len(subgroups)
    ncols = len(datasets_order)
    fig, axes = plt.subplots(
        nrows,
        ncols,
        figsize=figsize,
        gridspec_kw={"wspace": 0.15, "hspace": 0.25},
        sharey=True,
    )
    if nrows == 1:
        axes = axes.reshape(1, -1)
    if ncols == 1:
        axes = axes.reshape(-1, 1)

    for row_idx, subgroup in enumerate(subgroups):
        for col_idx, dataset in enumerate(datasets_order):
            ax = axes[row_idx, col_idx]
            plot_data = df[(df["Subgroup"] == subgroup) & (df["Dataset"] == dataset)].copy()

            if plot_data.empty:
                ax.text(0.5, 0.5, "No data", ha="center", va="center", fontsize=10, color="grey", transform=ax.transAxes)
                ax.set_xticks([])
                ax.set_xlabel("")
                if col_idx == 0:
                    ax.set_ylabel(subgroup, fontsize=11, labelpad=5)
                else:
                    ax.set_ylabel("")
                    ax.tick_params(axis="y", labelleft=False)
                continue

            sns.boxplot(
                ax=ax,
                data=plot_data,
                x="Group",
                y="Value",
                order=list(group_order),
                palette=group_palette,
                width=0.6,
                fliersize=2,
                linewidth=1.0,
            )

            # optional points overlay
            if show_points and points_style is not None:
                style = str(points_style).lower()
                if style == "swarm":
                    sns.swarmplot(
                        ax=ax,
                        data=plot_data,
                        x="Group",
                        y="Value",
                        order=list(group_order),
                        color=points_color,
                        size=points_size,
                        alpha=points_alpha,
                    )
                elif style == "strip":
                    sns.stripplot(
                        ax=ax,
                        data=plot_data,
                        x="Group",
                        y="Value",
                        order=list(group_order),
                        color=points_color,
                        size=points_size,
                        alpha=points_alpha,
                        jitter=0.18,
                    )
                else:
                    raise ValueError("points_style must be one of {'swarm', 'strip', None}.")

            if row_idx == 0:
                dataset_color = dataset_colors.get(dataset, "#cccccc")
                ax.set_title(dataset, fontsize=11, fontweight="bold", pad=20, color=dataset_color)

            ax.set_xlabel("")
            ax.set_xticklabels([])

            if col_idx == 0:
                ax.set_ylabel(subgroup, fontsize=11, labelpad=5)
            else:
                ax.set_ylabel("")
                ax.tick_params(axis="y", labelleft=False)

            responder_vals = plot_data[plot_data["Group"] == group_order[0]]["Value"].tolist()
            progressor_vals = plot_data[plot_data["Group"] == group_order[1]]["Value"].tolist()
            try:
                p = _mannwhitney_pvalue(responder_vals, progressor_vals)
                p_txt = _pvalue_label(p)
            except ValueError:
                p_txt = "NA"

            _draw_pvalue_in_axes(ax=ax, label=p_txt, x1=0.22, x2=0.78, y=1, h=0.04, lw=1.0, fontsize=10.0)

            if ylim is not None:
                ax.set_ylim(*ylim)

            ax.grid(axis="y", linestyle="--", alpha=0.25)

    # Thay đổi: Thêm legend nếu show_legend=True
    if show_legend:
        handles = [Rectangle((0, 0), 1, 1, facecolor=color, edgecolor='none') for color in group_palette.values()]
        fig.legend(handles, list(group_order), loc='upper center', bbox_to_anchor=(0.5, 1.08), ncol=2, fontsize=10, frameon=False)

    fig.suptitle("", fontsize=16, fontweight="bold", y=0.99)
    plt.tight_layout()

    if savepath:
        fig.savefig(savepath, dpi=300, bbox_inches="tight", facecolor="white")
    if show:
        plt.show()

    return fig
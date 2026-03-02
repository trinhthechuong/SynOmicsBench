import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from scipy import stats
from typing import Dict, List, Optional, Sequence, Tuple
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm
import json
import math 
from scipy.stats import ranksums

STABILITY_PLOT_COLORS = {
    "grid": "#e6e6e6",
    "median": "#000000",
}

NATURE_FONT = {
    "family": "sans-serif",
    "sans-serif": ["Helvetica", "Arial", "DejaVu Sans"],
}

DATASET_COLORS = {
    "Original Data": "#4d4d4d",
    "Avatars K5": "#66c2a5",
    "Avatars K10": "#fc8d62",
    "CTGAN": "#8da0cb",
    "Gaussian Copula": "#e78ac3",
    "Synthpop": "#a6d854",
    "TVAE": "#ffd92f",
}


def _set_nature_rcparams(fontsize: int = 11) -> None:
    """
    Apply Nature-like matplotlib rcParams (Helvetica/Arial and clean fonts).

    Args:
        fontsize (int): Base font size.

    Raises:
        ValueError: If fontsize is not positive.
    """
    if fontsize <= 0:
        raise ValueError("fontsize must be a positive integer.")

    plt.rcParams.update(
        {
            "font.size": fontsize,
            "font.family": NATURE_FONT["family"],
            "font.sans-serif": NATURE_FONT["sans-serif"],
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "axes.titlesize": fontsize + 1,
            "axes.labelsize": fontsize,
            "xtick.labelsize": fontsize - 1,
            "ytick.labelsize": fontsize - 1,
            "legend.fontsize": fontsize - 1,
        }
    )


def _format_pvalue_nature(p: float) -> str:
    """
    Format p-values for Nature-style annotation.

    Args:
        p (float): P-value.

    Returns:
        str: Formatted p-value label.

    Raises:
        ValueError: If p is not finite or not in [0, 1].
    """
    if not np.isfinite(p) or p < 0 or p > 1:
        raise ValueError("p must be a finite value in [0, 1].")

    if p < 0.01:
        star = "**"
    elif 0.01 <= p <= 0.05:
        star = "*"
    else:
        star = "NS"

    return f"{star}\n(p={p:.3g})"


def plot_pbrm1_box_strip_by_dataset(
    dataset_to_groups: Dict[str, Dict[str, List[float]]],
    dataset_order: Optional[Sequence[str]] = None,
    group_order: Sequence[str] = ("PBRM1_mut", "PBRM1_wt"),
    value_label: str = "Score",
    title: Optional[str] = None,
    figsize: Tuple[int, int] = (18, 6),
    fontsize: int = 11,
    strip_size: float = 3.2,
    strip_alpha: float = 0.9,
    box_width: float = 0.75,
    box_edge_lw: float = 1.6,
    median_lw: float = 2.0,
    box_face_alpha: float = 0.20,
    showfliers: bool = False,
    pvalue_line_height_frac: float = 0.06,
    group_label_y_offset_frac: float = 0.10,
    algorithm_label_y_offset_frac: float = 0.22,
    # legend_outside: bool = True,
) -> Tuple[plt.Figure, plt.Axes, pd.DataFrame]:
    if not dataset_to_groups:
        raise ValueError("dataset_to_groups must be a non-empty dictionary.")

    if len(group_order) != 2:
        raise ValueError("group_order must contain exactly 2 groups.")

    if dataset_order is None:
        dataset_order = list(dataset_to_groups.keys())
    else:
        dataset_order = list(dataset_order)

    if len(dataset_order) == 0:
        raise ValueError("dataset_order must contain at least one dataset.")

    _set_nature_rcparams(fontsize=fontsize)
    sns.set_style("whitegrid", rc={"grid.color": STABILITY_PLOT_COLORS["grid"]})

    # ---- Build long dataframe ----
    rows = []
    for ds in dataset_order:
        gdict = dataset_to_groups.get(ds, {})
        if not isinstance(gdict, dict):
            raise ValueError(f"Dataset '{ds}' must map to a dict of groups -> list of values.")
        for g in group_order:
            vals = gdict.get(g, None)
            if vals is None:
                continue
            for v in vals:
                rows.append({"Dataset": ds, "Group": g, "Value": v})

    df = pd.DataFrame(rows)
    if df.empty:
        raise ValueError("No data found after conversion. Check dataset_to_groups content.")

    df["Value"] = pd.to_numeric(df["Value"], errors="coerce")
    df = df.dropna(subset=["Value"])
    if df.empty:
        raise ValueError("No valid numeric values available after coercion and NaN removal.")

    # Ensure consistent categorical ordering (optional but good for reproducibility)
    df["Dataset"] = pd.Categorical(df["Dataset"], categories=dataset_order, ordered=True)
    df["Group"] = pd.Categorical(df["Group"], categories=list(group_order), ordered=True)

    fig, ax = plt.subplots(figsize=figsize)

    # Manual plotting per dataset (so BOTH groups share the dataset color)
    total_width = float(box_width)
    step = total_width / 2
    offsets = np.linspace(-total_width / 2 + step / 2, total_width / 2 - step / 2, 2)
    g_to_off = {group_order[i]: float(offsets[i]) for i in range(2)}
    jitter = 0.08

    # Precompute y-range for annotations
    y_all = df["Value"].to_numpy(dtype=float)
    y_all = y_all[np.isfinite(y_all)]
    y_min = float(np.nanmin(y_all))
    y_max = float(np.nanmax(y_all))
    y_span = (y_max - y_min) if y_max > y_min else 1.0
    h = float(pvalue_line_height_frac) * y_span

    stats_rows = []

    for i, ds in enumerate(dataset_order):
        col = DATASET_COLORS.get(ds, "#333333")
        sub_ds = df[df["Dataset"].astype(str) == str(ds)]

        # Boxplots (2 groups) + strip points
        data_for_box = []
        positions = []

        for g in group_order:
            v = sub_ds[sub_ds["Group"].astype(str) == str(g)]["Value"].to_numpy(dtype=float)
            v = v[np.isfinite(v)]
            data_for_box.append(v)
            positions.append(i + g_to_off[g])

            if v.size > 0:
                x = (i + g_to_off[g]) + np.random.uniform(-jitter, jitter, size=v.size)
                ax.scatter(
                    x,
                    v,
                    s=float(strip_size) ** 2 / 2.5,
                    c=col,
                    alpha=strip_alpha,
                    edgecolors="white",
                    linewidths=0.3,
                    zorder=3,
                )

        bp = ax.boxplot(
            data_for_box,
            positions=positions,
            widths=total_width * 0.42,
            patch_artist=True,
            showfliers=showfliers,
            medianprops={"color": STABILITY_PLOT_COLORS["median"], "linewidth": median_lw},
            boxprops={"edgecolor": col, "linewidth": box_edge_lw},
            whiskerprops={"color": col, "linewidth": box_edge_lw},
            capprops={"color": col, "linewidth": box_edge_lw},
        )
        for patch in bp["boxes"]:
            patch.set_facecolor(col)
            patch.set_alpha(box_face_alpha)

        # Rank-sum p-value per dataset (PBRM1_mut vs PBRM1_wt)
        v1 = sub_ds[sub_ds["Group"].astype(str) == str(group_order[0])]["Value"].to_numpy(dtype=float)
        v2 = sub_ds[sub_ds["Group"].astype(str) == str(group_order[1])]["Value"].to_numpy(dtype=float)
        v1 = v1[np.isfinite(v1)]
        v2 = v2[np.isfinite(v2)]

        p = np.nan if (v1.size == 0 or v2.size == 0) else float(stats.ranksums(v1, v2).pvalue)
        stats_rows.append(
            {"Dataset": ds, f"n_{group_order[0]}": int(v1.size), f"n_{group_order[1]}": int(v2.size), "p_value": p}
        )

        if np.isfinite(p):
            y_top = float(np.nanmax(sub_ds["Value"].to_numpy(dtype=float)))
            y = y_top + h
            x1 = i + g_to_off[group_order[0]]
            x2 = i + g_to_off[group_order[1]]
            ax.plot([x1, x1, x2, x2], [y, y + 0.4 * h, y + 0.4 * h, y], color="black", lw=1.2, zorder=4)
            ax.text(
                (x1 + x2) / 2,
                y + 0.55 * h,
                _format_pvalue_nature(p),
                ha="center",
                va="bottom",
                fontsize=fontsize - 1,
                color="black",
                zorder=5,
            )

    # Hide default x tick labels (we add custom text)
    ax.set_xticks(range(len(dataset_order)))
    ax.set_xticklabels(["" for _ in dataset_order])

    # Custom x annotations:
    # - Group labels higher (closer to axis), rotated 45°
    # - Algorithm labels lower, bold, horizontal
    y_group = y_min - float(group_label_y_offset_frac) * y_span
    y_alg = y_min - float(algorithm_label_y_offset_frac) * y_span

    for i, ds in enumerate(dataset_order):
        # group labels at dodged positions
        ax.text(
            i + g_to_off[group_order[0]],
            y_group,
            str(group_order[0]),
            ha="center",
            va="top",
            rotation=0,
            fontsize=fontsize - 2,
            color="black",
            clip_on=False,
        )
        ax.text(
            i + g_to_off[group_order[1]],
            y_group,
            str(group_order[1]),
            ha="center",
            va="top",
            rotation=0,
            fontsize=fontsize - 2,
            color="black",
            clip_on=False,
        )

        # algorithm label at dataset center (below group labels)
        ax.text(
            i,
            y_alg,
            str(ds),
            ha="center",
            va="top",
            rotation=0,
            fontsize=fontsize,
            fontweight="bold",
            color="black",
            clip_on=False,
        )

    ax.set_xlabel("")
    ax.set_ylabel(value_label, fontsize=fontsize)
    if title is not None:
        ax.set_title(title, fontsize=fontsize + 1, fontweight="bold", pad=14)

    # Legend: dataset colors with filled background
    legend_handles = [
        mpatches.Patch(
            facecolor=DATASET_COLORS.get(ds, "#333333"),
            edgecolor=DATASET_COLORS.get(ds, "#333333"),
            alpha=box_face_alpha,
            label=str(ds),
            linewidth=2.0,
        )
        for ds in dataset_order
    ]
    # if legend_outside:
    #     ax.legend(
    #         handles=legend_handles,
    #         title="Dataset",
    #         frameon=False,
    #         loc="upper left",
    #         bbox_to_anchor=(1.01, 1.0),
    #         fontsize=fontsize - 1,
    #         title_fontsize=fontsize,
    #     )
    #     plt.tight_layout(rect=[0, 0.12, 0.86, 1])
    # else:
    #     ax.legend(
    #         handles=legend_handles,
    #         title="Dataset",
    #         frameon=False,
    #         loc="upper right",
    #         fontsize=fontsize - 1,
    #         title_fontsize=fontsize,
    #     )
    #     plt.tight_layout(rect=[0, 0.12, 1, 1])

    stats_df = pd.DataFrame(stats_rows)
    return fig, ax, stats_df
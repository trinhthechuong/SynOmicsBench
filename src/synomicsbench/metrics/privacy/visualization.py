"""
Privacy risk heatmap visualizations.

Refactored from ``Manuscripts/FigurePrivacy/*.ipynb``.
Provides functions to plot singling-out, linkability, and inference risk
heatmaps across multiple cancer cohorts.  Each risk plot pairs a seaborn
heatmap with a matched horizontal boxplot summarising cross-seed variability.
"""

from __future__ import annotations

from typing import Dict, List, Mapping, Optional, Sequence, Tuple, Union

import matplotlib.colors as mcolors
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns


# ---------- colour defaults ---------- #

RISK_CMAP = "viridis"
OVERALL_CMAP = "BuGn"


# ------------------------------------------------------------------ #
#  Shared helpers                                                     #
# ------------------------------------------------------------------ #

def aggregate_seeds(
    dfs: List[pd.DataFrame],
    method: str = "mean",
) -> pd.DataFrame:
    """Average a list of identically-shaped risk DataFrames across seeds.

    Args:
        dfs: List of DataFrames (one per seed), all with the same
            index (SDG methods) and columns (risk configurations).
        method: Aggregation method, either ``'mean'`` or ``'median'``.

    Returns:
        pd.DataFrame: Aggregated DataFrame with the same shape.

    Example:
        >>> seed_dfs = [load_linkability_results(f"seed_{s}.pkl") for s in range(5)]
        >>> mean_risk = aggregate_seeds(seed_dfs, method="mean")
    """
    stacked = np.stack([df.values for df in dfs], axis=0)

    if method == "mean":
        agg = np.nanmean(stacked, axis=0)
    elif method == "median":
        agg = np.nanmedian(stacked, axis=0)
    else:
        raise ValueError("method must be 'mean' or 'median'")

    return pd.DataFrame(agg, index=dfs[0].index, columns=dfs[0].columns)


def collect_boxplot_data(
    dfs: List[pd.DataFrame],
) -> Dict[str, np.ndarray]:
    """Collect all risk values across seeds and configurations for each SDG method.

    This flattens the per-seed, per-configuration risk values into a single
    array per method, suitable for boxplot visualisation.

    Args:
        dfs: List of DataFrames (one per seed).

    Returns:
        dict: Mapping from method name to an array of non-NaN risk values.

    Example:
        >>> box_data = collect_boxplot_data(seed_dfs)
        >>> box_data["Gaussian Copula"]
        array([0.01, 0.02, 0.01, ...])
    """
    box_data = {}
    tools = dfs[0].index

    for tool in tools:
        values = []
        for df in dfs:
            vals = df.loc[tool].values
            vals = vals[~np.isnan(vals)]
            values.extend(vals)
        box_data[tool] = np.array(values)

    return box_data


def _overlay_hatched_missing_cells(
    ax: plt.Axes,
    mat: pd.DataFrame,
    hatch: str = "///",
    edgecolor: str = "#BDBDBD",
    facecolor: str = "#FFFFFF",
    linewidth: float = 0.6,
) -> None:
    """Draw hatched rectangles over NaN cells in a heatmap.

    This provides a clear visual indicator that a cell has no data rather
    than just showing white space.

    Args:
        ax: Matplotlib Axes containing the heatmap.
        mat: DataFrame whose NaN positions will be hatched.
        hatch: Hatch pattern string.
        edgecolor: Edge colour of the hatched rectangles.
        facecolor: Face colour of the hatched rectangles.
        linewidth: Line width for the rectangle border.
    """
    nan_mask = mat.isna().to_numpy()
    nrows, ncols = mat.shape

    for i in range(nrows):
        for j in range(ncols):
            if not nan_mask[i, j]:
                continue
            rect = mpatches.Rectangle(
                (j, i), 1.0, 1.0,
                facecolor=facecolor,
                edgecolor=edgecolor,
                hatch=hatch,
                linewidth=linewidth,
                fill=True,
                zorder=10,
            )
            ax.add_patch(rect)


# ------------------------------------------------------------------ #
#  Singling-out / Linkability risk heatmap (horizontal layout)        #
# ------------------------------------------------------------------ #

def plot_risk_heatmap_grid(
    risk_data: Mapping[str, Union[pd.DataFrame, List[pd.DataFrame]]],
    *,
    risk_label: str = "Risk",
    cmap: str = RISK_CMAP,
    vmin: float = 0.0,
    vmax: float = 1.0,
    figsize: Optional[Tuple[float, float]] = None,
) -> plt.Figure:
    """Plot side-by-side heatmaps with boxplots for each cancer cohort.

    Each cohort panel contains a seaborn heatmap (SDG methods × attack
    configurations) and a horizontal boxplot summarising the distribution
    of risk values across seeds.  NaN cells are overlaid with hatched
    rectangles to clearly indicate failed attacks.

    Args:
        risk_data: Mapping from cohort name to **either**:
            - a single ``pd.DataFrame`` (pre-aggregated mean risk), or
            - a ``list[pd.DataFrame]`` (per-seed results; mean is computed
              automatically and boxplots show cross-seed variability).
            Index = SDG methods, columns = configuration labels.
        risk_label: Colour-bar label (e.g. ``'Linkability Risk'``).
        cmap: Matplotlib colourmap name.
        vmin: Minimum value for colour scale.
        vmax: Maximum value for colour scale.
        figsize: Optional figure size; auto-calculated if *None*.

    Returns:
        matplotlib.figure.Figure: The generated figure.

    Example:
        >>> fig = plot_risk_heatmap_grid(
        ...     {"ccRCC": seed_dfs_ccrcc, "Melanoma": seed_dfs_mel},
        ...     risk_label="Linkability Risk",
        ... )
        >>> fig.savefig("linkability_risk.png", dpi=300, bbox_inches="tight")
    """
    cohorts = list(risk_data.keys())
    n_cohorts = len(cohorts)

    # Normalise input: ensure we have both aggregated + per-seed data
    agg_data: Dict[str, pd.DataFrame] = {}
    seed_data: Dict[str, Optional[List[pd.DataFrame]]] = {}

    for cohort, val in risk_data.items():
        if isinstance(val, list):
            seed_data[cohort] = val
            agg_data[cohort] = aggregate_seeds(val)
        else:
            agg_data[cohort] = val
            seed_data[cohort] = None

    if figsize is None:
        figsize = (4 * n_cohorts, 3)

    norm = mcolors.Normalize(vmin=vmin, vmax=vmax)
    colormap = plt.get_cmap(cmap)

    # Grid layout: for each cohort [heatmap, boxplot, spacer]
    width_ratios = []
    for i in range(n_cohorts):
        width_ratios.extend([1, 0.55, 0.25])

    fig, axes = plt.subplots(
        1, 3 * n_cohorts,
        figsize=figsize,
        gridspec_kw={"width_ratios": width_ratios, "wspace": 0.02},
    )
    if n_cohorts == 1:
        axes = np.array(axes)

    line_params = {"linewidths": 0.5, "linecolor": "gray"}

    for idx in range(n_cohorts):
        step = idx * 3
        cohort = cohorts[idx]
        ax_heat = axes[step]
        ax_box = axes[step + 1]
        axes[step + 2].axis("off")  # spacer

        data_mean = agg_data[cohort]
        yticklabels = idx == 0

        # ---- HEATMAP ----
        sns.heatmap(
            data_mean,
            ax=ax_heat,
            cmap=cmap,
            norm=norm,
            cbar=False,
            xticklabels=True,
            yticklabels=yticklabels,
            **line_params,
        )

        _overlay_hatched_missing_cells(ax=ax_heat, mat=data_mean)

        ax_heat.set_title(cohort, fontsize=14, fontweight="bold")
        ax_heat.tick_params(left=False, right=False)

        for label in ax_heat.get_xticklabels():
            label.set_rotation(45)
            label.set_ha("right")
            label.set_fontsize(10)

        # ---- BOXPLOT (HORIZONTAL) ----
        if seed_data[cohort] is not None:
            boxplot_data = collect_boxplot_data(seed_data[cohort])
        else:
            # Fake single-seed boxplot from aggregated data
            boxplot_data = {
                t: data_mean.loc[t].dropna().values
                for t in data_mean.index
            }

        tools = data_mean.index.tolist()
        y_pos = np.arange(len(tools)) + 0.5
        box_values = [boxplot_data[t] for t in tools]

        bp = ax_box.boxplot(
            box_values,
            vert=False,
            positions=y_pos,
            widths=0.6,
            patch_artist=True,
            showfliers=False,
            medianprops=dict(color="black", linewidth=1.2),
            boxprops=dict(linewidth=0.8),
            whiskerprops=dict(linewidth=0.8),
            capprops=dict(linewidth=0.8),
        )

        # Colour boxes by mean risk
        means = data_mean.mean(axis=1).values
        for patch, m in zip(bp["boxes"], means):
            if np.isnan(m):
                patch.set_facecolor("#EEEEEE")
            else:
                patch.set_facecolor(colormap(norm(m)))
            patch.set_alpha(0.85)

        # Annotate mean values
        for i, tool in enumerate(tools):
            vals = boxplot_data[tool]
            y = y_pos[i]
            if len(vals) == 0:
                ax_box.text(
                    0.01, y, "NA", va="center", ha="left",
                    fontsize=9, color="black", zorder=10,
                )
            else:
                mean_val = np.mean(vals)
                ax_box.text(
                    mean_val + 0.06, y, f"{mean_val:.2f}",
                    va="center", ha="left",
                    fontsize=9, color="black", zorder=10,
                )

        # Align and clean axis
        ax_box.set_ylim(ax_heat.get_ylim())
        ax_box.set_xlim(vmin, vmax)
        ax_box.set_yticks([])
        ax_box.spines["left"].set_visible(False)
        ax_box.spines["top"].set_visible(False)
        ax_box.spines["right"].set_visible(False)
        ax_box.tick_params(axis="x", labelsize=10)
        ax_box.tick_params(which="both", left=False)

    # Remove top ticks for all axes
    for ax in axes:
        ax.tick_params(top=False, labeltop=False)

    # Shared colorbar
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])

    valid_axes = [axes[i * 3 + j] for i in range(n_cohorts) for j in range(2)]
    cbar = fig.colorbar(sm, ax=valid_axes, fraction=0.015, pad=0.04)
    cbar.set_label(risk_label, fontsize=11)
    cbar.ax.tick_params(labelsize=10)

    return fig


# ------------------------------------------------------------------ #
#  Inference risk heatmap (vertical layout)                           #
# ------------------------------------------------------------------ #

def plot_inference_heatmap(
    inference_data: Mapping[str, Union[pd.DataFrame, List[pd.DataFrame]]],
    *,
    cmap: str = RISK_CMAP,
    vmin: float = 0.0,
    vmax: float = 1.0,
    figsize: Optional[Tuple[float, float]] = None,
    numerical_clinical: Optional[Mapping[str, List[str]]] = None,
) -> plt.Figure:
    """Plot inference risk heatmaps with boxplots (one row per cohort).

    Each row contains a seaborn heatmap (SDG methods × clinical attributes)
    and a horizontal boxplot.  Numerical clinical feature labels can be
    highlighted in a distinct colour.

    Args:
        inference_data: Mapping from cohort name to **either**:
            - a single ``pd.DataFrame``, or
            - a ``list[pd.DataFrame]`` (per-seed results).
            Index = SDG methods, columns = clinical attribute names.
        cmap: Matplotlib colourmap name.
        vmin: Minimum value for colour scale.
        vmax: Maximum value for colour scale.
        figsize: Optional figure size.
        numerical_clinical: Optional mapping from cohort name to a list of
            numerical clinical feature names.  These will be highlighted
            in red on the x-axis.

    Returns:
        matplotlib.figure.Figure: The generated figure.

    Example:
        >>> fig = plot_inference_heatmap(
        ...     {"ccRCC": seed_dfs_ccrcc, "Melanoma": seed_dfs_mel},
        ...     numerical_clinical={"ccRCC": ["Age", "BMI"]},
        ... )
    """
    cohorts = list(inference_data.keys())
    n_cohorts = len(cohorts)

    if numerical_clinical is None:
        numerical_clinical = {}

    # Normalise input
    agg_data: Dict[str, pd.DataFrame] = {}
    seed_data: Dict[str, Optional[List[pd.DataFrame]]] = {}

    for cohort, val in inference_data.items():
        if isinstance(val, list):
            seed_data[cohort] = val
            agg_data[cohort] = aggregate_seeds(val)
        else:
            agg_data[cohort] = val
            seed_data[cohort] = None

    norm = mcolors.Normalize(vmin=vmin, vmax=vmax)
    colormap = plt.get_cmap(cmap)

    if figsize is None:
        n_attrs_max = max(len(df.columns) for df in agg_data.values())
        figsize = (max(12, n_attrs_max * 0.35), 5 * n_cohorts)

    line_params = {"linewidths": 0.4, "linecolor": "white"}

    fig, axes = plt.subplots(
        n_cohorts, 2,
        figsize=figsize,
        gridspec_kw={"width_ratios": [1, 0.28], "wspace": 0.03, "hspace": 0.8},
        squeeze=False,
    )

    for ci, cohort in enumerate(cohorts):
        ax_heat = axes[ci, 0]
        ax_box = axes[ci, 1]

        data_mean = agg_data[cohort]

        # ---- HEATMAP ----
        sns.heatmap(
            data_mean,
            ax=ax_heat,
            cmap=cmap,
            norm=norm,
            cbar=False,
            xticklabels=True,
            **line_params,
        )

        _overlay_hatched_missing_cells(ax=ax_heat, mat=data_mean)

        ax_heat.set_title(cohort, fontsize=14, fontweight="bold")
        ax_heat.tick_params(
            which="major", top=False, bottom=False, left=False, right=False,
        )

        # Highlight numerical clinical features in red
        num_features = numerical_clinical.get(cohort, [])
        for label in ax_heat.get_xticklabels():
            if label.get_text() in num_features:
                label.set_color("red")
            label.set_rotation(45)
            label.set_fontsize(9)
            label.set_ha("right")

        # ---- BOXPLOT (HORIZONTAL) ----
        if seed_data[cohort] is not None:
            boxplot_data = collect_boxplot_data(seed_data[cohort])
        else:
            boxplot_data = {
                t: data_mean.loc[t].dropna().values
                for t in data_mean.index
            }

        tools = data_mean.index.tolist()
        y_pos = np.arange(len(tools)) + 0.5
        box_values = [boxplot_data[t] for t in tools]

        bp = ax_box.boxplot(
            box_values,
            vert=False,
            positions=y_pos,
            widths=0.6,
            patch_artist=True,
            showfliers=False,
            medianprops=dict(color="black", linewidth=1.2),
            boxprops=dict(linewidth=0.8),
            whiskerprops=dict(linewidth=0.8),
            capprops=dict(linewidth=0.8),
        )

        # Colour by mean
        means = data_mean.mean(axis=1).values
        for patch, m in zip(bp["boxes"], means):
            if np.isnan(m):
                patch.set_facecolor("#EEEEEE")
            else:
                patch.set_facecolor(colormap(norm(m)))
            patch.set_alpha(0.85)

        # Annotate mean
        for i_t, tool in enumerate(tools):
            vals = boxplot_data[tool]
            y = y_pos[i_t]
            if len(vals) == 0:
                ax_box.text(0.01, y, "NA", va="center", fontsize=9)
            else:
                mean_val = np.mean(vals)
                ax_box.text(
                    mean_val + 0.04, y, f"{mean_val:.2f}",
                    va="center", fontsize=9,
                )

        # Clean axis
        ax_box.set_ylim(ax_heat.get_ylim())
        ax_box.set_xlim(vmin, vmax)
        ax_box.set_yticks([])
        ax_box.set_ylabel("")
        ax_box.spines["left"].set_visible(False)
        ax_box.spines["top"].set_visible(False)
        ax_box.spines["right"].set_visible(False)
        ax_box.tick_params(axis="x", labelsize=10)
        ax_box.tick_params(which="both", left=False)
        ax_box.tick_params(top=False, labeltop=False)

    # Shared colorbar
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=axes.ravel().tolist(), fraction=0.015, pad=0.04)
    cbar.set_label("Inference Risk", fontsize=11)
    cbar.ax.tick_params(labelsize=10)

    return fig


# ------------------------------------------------------------------ #
#  Overall privacy score heatmap (Bayesian comparison style)          #
# ------------------------------------------------------------------ #

def plot_overall_privacy_heatmap(
    score_data: Mapping[str, pd.DataFrame],
    *,
    cmap: str = OVERALL_CMAP,
    vmin: float = 0.0,
    vmax: float = 1.0,
    figsize: Optional[Tuple[float, float]] = None,
) -> plt.Figure:
    """Plot overall privacy score Bayesian comparison heatmaps.

    Each cohort panel shows a method × method matrix of pairwise
    Bayesian probabilities that Method 1 has a better privacy score
    than Method 2.

    Args:
        score_data: Mapping from cohort name to a square DataFrame whose
            index and columns are SDG method names, with values being
            pairwise 'better' probabilities.
        cmap: Colourmap name.
        vmin: Minimum value for colour scale.
        vmax: Maximum value for colour scale.
        figsize: Optional figure size.

    Returns:
        matplotlib.figure.Figure: The generated figure.
    """
    cohorts = list(score_data.keys())
    n_cohorts = len(cohorts)

    if figsize is None:
        figsize = (6 * n_cohorts, 5)

    fig, axes = plt.subplots(
        1, n_cohorts + 1, figsize=figsize,
        gridspec_kw={"width_ratios": [1.0] * n_cohorts + [0.05]},
    )
    if n_cohorts == 1:
        axes = [axes[0], axes[1]]

    norm = mcolors.Normalize(vmin=vmin, vmax=vmax)

    for ci, cohort in enumerate(cohorts):
        df = score_data[cohort]
        ax = axes[ci]
        im = ax.imshow(df.values, aspect="auto", cmap=cmap, norm=norm)

        # Annotate cells
        for i in range(df.shape[0]):
            for j in range(df.shape[1]):
                val = df.values[i, j]
                color = "white" if val > 0.6 else "black"
                ax.text(
                    j, i, f"{val:.2f}",
                    ha="center", va="center", fontsize=9, color=color,
                )

        ax.set_xticks(range(len(df.columns)))
        ax.set_xticklabels(df.columns, rotation=45, ha="right", fontsize=9)
        ax.set_yticks(range(len(df.index)))
        ax.set_yticklabels(
            df.index, fontsize=10,
            fontweight="bold" if ci == 0 else "normal",
        )
        ax.set_title(cohort, fontsize=13, fontweight="bold")
        ax.set_xlabel("Method 2")
        if ci == 0:
            ax.set_ylabel("Method 1")

    fig.colorbar(im, cax=axes[-1], label="Better Prob")
    fig.tight_layout()
    return fig


# ------------------------------------------------------------------ #
#  Helpers: compute overall privacy risk from individual risks        #
# ------------------------------------------------------------------ #

def compute_overall_privacy_score(
    singling_uni_risk: float,
    singling_multi_risk: float,
    linkability_risk: float,
    inference_risk: float,
) -> float:
    """Compute overall privacy score from individual risk categories.

    $$R_{overall} = \\frac{1}{4}(R_{uni} + R_{multi} + R_{link} + R_{inf})$$
    $$\\text{Privacy Score} = 1 - R_{overall}$$

    Args:
        singling_uni_risk: Mean univariate singling-out risk.
        singling_multi_risk: Mean multivariate singling-out risk.
        linkability_risk: Mean linkability risk.
        inference_risk: Mean inference risk.

    Returns:
        float: Privacy score in [0, 1] (higher = better privacy).
    """
    r_overall = (
        singling_uni_risk + singling_multi_risk + linkability_risk + inference_risk
    ) / 4.0
    return 1.0 - r_overall

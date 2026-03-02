from typing import Dict, Iterable, Any, Tuple, List, Optional
import warnings
import traceback
import os
import concurrent.futures

import numpy as np
import pandas as pd
from scipy.stats import ranksums
from statsmodels.stats.multitest import multipletests
import matplotlib.pyplot as plt

# Consistent color definitions used across SynOmics visualizations
DATA_COLORS = {"real": "#4c72b0", "synthetic": "#dd8452"}
PVAL_BIN_COLORS_DEFAULT = ["#d62728", "#ff7f0e", "#1f77b4", "#cccccc"]  # red, orange, blue, gray


def plot_pathway(
    ssGSEA_comparison: Dict[str, pd.DataFrame],
    ref_pathway_list: List[str],
    highlight_pathways: List[str] = None,
    origin_name: str = "Origin",
    term_col: str = "Term",
    pval_col: str = "adj_pvalues",
    diff_col: str = "Diff_NES",
    pval_bin_colors: List[str] = PVAL_BIN_COLORS_DEFAULT,
    fig_width_min: float = 14.0,
    bubble_size: float = 170,
    show: bool = True,
    save_path: Optional[str] = None,
    return_dataframe: bool = True,
) -> Tuple[plt.Figure, pd.DataFrame]:
    """
    Produce a pathway scatter figure for a fixed list of pathways, preserving input order.

    Args:
        ssGSEA_comparison (Dict[str, pd.DataFrame]): Mapping dataset_name -> ssGSEA comparison DataFrame.
        ref_pathway_list (List[str]): Ordered list of pathways/terms to show. Y-axis order will match this list.
        highlight_pathways (List[str]): Pathways to highlight on the y-axis.
        origin_name (str): Name of the reference dataset (unused for ordering; preserved for API compatibility).
        term_col (str): Column name in the input frames that holds pathway/term names.
        pval_col (str): Column name in the input frames that holds adjusted p-values / q-values.
        diff_col (str): Column name in the input frames that holds the NES difference (groupA - groupB).
        pval_bin_colors (List[str]): Four colors for p-value bins [p<0.01, 0.01≤p<0.05, 0.05≤p<0.25, p≥0.25].
        fig_width_min (float): Minimum figure width in inches.
        bubble_size (float): Fixed bubble size (area) for scatter markers.
        show (bool): If True, call plt.show() before returning the figure.
        save_path (Optional[str]): If provided, save the figure to this path (dpi=300).
        return_dataframe (bool): If True return the concatenated dataframe used for plotting along with the Figure.

    Returns:
        Tuple[matplotlib.figure.Figure, pandas.DataFrame]: The created matplotlib Figure and the DataFrame used for plotting.

    Raises:
        ValueError: If ssGSEA_comparison or ref_pathway_list are empty.
        ValueError: If none of the datasets contain the provided term/p-value/diff columns.
    """
    if not ssGSEA_comparison:
        raise ValueError("ssGSEA_comparison must not be empty.")
    if not ref_pathway_list:
        raise ValueError("ref_pathway_list must not be empty.")
    if highlight_pathways is None:
        highlight_pathways = []

    datasets = list(ssGSEA_comparison.keys())
    all_data_to_plot: List[pd.DataFrame] = []
    global_nes_values: List[float] = []
    found_any = False

    for ds_name in datasets:
        df_ds = ssGSEA_comparison.get(ds_name)
        if df_ds is None or not isinstance(df_ds, pd.DataFrame):
            warnings.warn(f"Skipping {ds_name}: not a pandas DataFrame.")
            continue

        # check required columns exist
        if term_col not in df_ds.columns or pval_col not in df_ds.columns or diff_col not in df_ds.columns:
            warnings.warn(
                f"Skipping {ds_name}: missing one of required columns "
                f"({term_col}, {pval_col}, {diff_col})."
            )
            continue

        sub_df = df_ds[df_ds[term_col].isin(ref_pathway_list)].copy()
        if sub_df.empty:
            continue

        found_any = True
        # normalize column names for plotting output
        sub_df = sub_df.rename(columns={term_col: "Term", pval_col: "adj_pvalues", diff_col: "Diff_NES"})
        sub_df["Dataset"] = ds_name

        # sanitize numeric columns
        sub_df["adj_pvalues"] = pd.to_numeric(sub_df["adj_pvalues"], errors="coerce")
        sub_df["Diff_NES"] = pd.to_numeric(sub_df["Diff_NES"], errors="coerce").fillna(0.0)

        # safe -log10 q-value
        sub_df["-log10(qvalue)"] = -np.log10(sub_df["adj_pvalues"].clip(lower=np.nextafter(0, 1)))

        global_nes_values.extend(sub_df["Diff_NES"].tolist())
        all_data_to_plot.append(sub_df[["Dataset", "Term", "adj_pvalues", "Diff_NES", "-log10(qvalue)"]])

    if not found_any:
        raise ValueError("No dataset contained the requested term/p-value/diff columns for the provided reference pathways.")

    df_plot = pd.concat(all_data_to_plot, ignore_index=True)

    # unified NES scale
    max_abs_nes = np.nanmax(np.abs(global_nes_values))
    if not np.isfinite(max_abs_nes) or max_abs_nes == 0:
        max_abs_nes = 1.0

    # p-value bins and colors
    bins = [0, 0.01, 0.05, 0.25, 1.01]
    bin_labels = ["p<0.01", "0.01≤p<0.05", "0.05≤p<0.25", "p≥0.25"]
    color_map = dict(zip(bin_labels, pval_bin_colors))
    df_plot["pvalue_bin"] = pd.cut(df_plot["adj_pvalues"], bins=bins, labels=bin_labels, include_lowest=True, right=False)

    # Respect ref_pathway_list order directly (filter to pathways actually present)
    present_pathways_set = set(df_plot["Term"].unique())
    sorted_pathways = [p for p in ref_pathway_list if p in present_pathways_set]

    # Fallback: if none of the ref_pathway_list are present, use whatever is available
    if not sorted_pathways:
        sorted_pathways = sorted(list(present_pathways_set))

    # Build mapping: index follows ref_pathway_list order (0 is first element in ref_pathway_list)
    mapping = {p: idx for idx, p in enumerate(sorted_pathways)}
    y_labels = sorted_pathways
    y_pos = np.arange(len(y_labels))

    N_COLS = len(datasets)
    FIG_WIDTH = max(3.5 * N_COLS + 2, fig_width_min)
    FIG_HEIGHT = max(0.6 * len(y_labels) + 3, 7)

    fig, axes = plt.subplots(nrows=1, ncols=N_COLS, figsize=(FIG_WIDTH, FIG_HEIGHT), sharey=True, sharex=True)
    axes_list = [axes] if N_COLS == 1 else list(axes.flat)
    plt.subplots_adjust(left=0.28, right=0.88, top=0.88, bottom=0.08, wspace=0.18)

    for i, ds in enumerate(datasets):
        ax = axes_list[i]
        sub = df_plot[df_plot["Dataset"] == ds].copy()
        sub["y"] = sub["Term"].map(mapping)

        if sub.empty or sub["y"].isna().all():
            ax.text(0.5, 0.5, "No data", ha="center", va="center", fontsize=10, color="grey", transform=ax.transAxes)
            ax.set_xlim(-max_abs_nes * 1.05, max_abs_nes * 1.05)
            ax.set_xticks([])
            ax.set_title(ds, fontsize=10, fontweight="bold", pad=10)
            ax.tick_params(left=False, labelleft=False)
            ax.grid(axis="y", linestyle="--", alpha=0.4)
            continue

        bubble_colors = sub["pvalue_bin"].map(color_map).fillna("#cccccc")

        ax.scatter(
            x=sub["Diff_NES"],
            y=sub["y"],
            s=bubble_size,
            c=bubble_colors,
            edgecolor="k",
            linewidths=0.4,
            alpha=0.95,
            zorder=2,
        )

        ax.axvline(x=0, color="gray", linestyle="--", linewidth=1.2, zorder=1)
        ax.set_xlim(-max_abs_nes * 1.05, max_abs_nes * 1.05)
        ax.set_xlabel(diff_col, fontsize=9, labelpad=6)

        ax.set_yticks(y_pos)
        ax.set_ylim(-0.5, len(y_labels) - 0.5)
        # Place the first entry of ref_pathway_list at the top of the figure.
        ax.invert_yaxis()
        ax.set_title(ds, fontsize=10, fontweight="bold", pad=10)
        ax.grid(axis="y", linestyle="--", alpha=0.4)

        if i == 0:
            # Use the preserved ref_pathway_list order for labels
            ax.set_yticklabels(y_labels, fontsize=9)
            ax.tick_params(axis="y", which="major", pad=6)
            for label in ax.get_yticklabels():
                pathway_name = label.get_text()
                if pathway_name in (highlight_pathways or []):
                    label.set_color(DATA_COLORS["real"])
                    label.set_fontweight("bold")
                else:
                    label.set_color("black")
        else:
            ax.tick_params(left=False, labelleft=False)

    # remove extra axes if present
    if len(axes_list) > N_COLS:
        for j in range(N_COLS, len(axes_list)):
            fig.delaxes(axes_list[j])

    # legend for p-value bins
    import matplotlib.patches as mpatches
    legend_patches = [mpatches.Patch(color=color_map[l], label=l) for l in bin_labels]
    axes_list[-1].legend(handles=legend_patches, title="Adjusted p-value", bbox_to_anchor=(1.05, 1), loc="upper left", fontsize=8, title_fontsize=9, frameon=False)

    plt.tight_layout(rect=[0, 0.03, 0.88, 0.98])

    if save_path:
        fig.savefig(save_path, dpi=300, bbox_inches="tight")
    if show:
        plt.show()

    df_plot["y"] = df_plot["Term"].map(mapping)
    # keep consistent output column order
    df_plot = df_plot[["Dataset", "Term", "adj_pvalues", "Diff_NES", "-log10(qvalue)", "y", "pvalue_bin"]]

    return (fig, df_plot) if return_dataframe else (fig, None)
import pandas as pd
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from scipy import stats

DATASET_COLORS = {
    "Original Data": "#4d4d4d",
    "Avatars K5":  "#66c2a5",  # greenish
    "Avatars K10": "#fc8d62",  # orange
    "CTGAN":  "#8da0cb",  # blue
    "Gaussian Copula":   "#e78ac3",  # pink
    "Synthpop":  "#a6d854",  # lime
    "TVAE":  "#ffd92f",  # yellow
}

STABILITY_PLOT_COLORS = {
    "grid": "#e6e6e6",
    "median": "#000000",
}

NATURE_FONT = {
    "family": "sans-serif",
    "sans-serif": ["Helvetica", "Arial", "DejaVu Sans"],
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


def plot_grouped_box_strip_by_dataset(
    dataset_to_signals: dict,
    dataset_order: list,
    signal_order: list,
    comparisons=(("Interferon Gamma", "ImmunoProteasome"), ("Proteasome subunits", "ImmunoProteasome")),
    value_label: str = r"signed $\mathregular{log_{10}(p-value)}$",
    title: str = None,
    figsize=(24, 6),
    fontsize: int = 11,
    strip_size: float = 3.0,
    strip_alpha: float = 0.75,
    box_width: float = 0.62,
    box_edge_lw: float = 1.6,
    median_lw: float = 2.0,
    dataset_label_y_offset: float = 0.14,
    # legend_outside: bool = True,
    show: bool = True,
):
    """
    Plot grouped boxplot + stripplot where each dataset forms a group of 3 signals.
    Boxes have white facecolor and dataset-colored edges. P-values are computed within each dataset.

    Args:
        dataset_to_signals (dict): Mapping dataset -> {signal -> list of values}.
        dataset_order (list): Dataset order on the x-axis (groups).
        signal_order (list): Signal order within each dataset group (3 boxes per dataset).
        comparisons (tuple): Pairs of signals to compare within each dataset using rank-sum test.
        value_label (str): Y-axis label.
        title (str | None): Plot title.
        figsize (tuple): Figure size.
        fontsize (int): Base font size.
        strip_size (float): Strip point size.
        strip_alpha (float): Strip alpha.
        box_width (float): Width of each box.
        box_edge_lw (float): Line width for dataset-colored box edges.
        median_lw (float): Line width for median.
        dataset_label_y_offset (float): How far to push dataset labels downward (fraction of y-span).
        legend_outside (bool): Put legend outside (right) if True.
        show (bool): If True, calls plt.show().

    Returns:
        tuple: (fig, ax, stats_df)

    Raises:
        ValueError: If dataset_to_signals is empty.
        ValueError: If required signals are missing.
    """
    if not dataset_to_signals:
        raise ValueError("dataset_to_signals must be a non-empty dictionary.")

    _set_nature_rcparams(fontsize=fontsize)
    sns.set_style("whitegrid", rc={"grid.color": STABILITY_PLOT_COLORS["grid"]})

    # ---- Build long dataframe ----
    rows = []
    for ds in dataset_order:
        sig_dict = dataset_to_signals.get(ds, {})
        for sig in signal_order:
            vals = sig_dict.get(sig, None)
            if vals is None:
                continue
            for v in vals:
                rows.append({"Dataset": ds, "Signal": sig, "Value": v})

    df = pd.DataFrame(rows)
    if df.empty:
        raise ValueError("No data found after conversion. Check dataset_to_signals content.")

    df["Value"] = pd.to_numeric(df["Value"], errors="coerce")
    df = df.dropna(subset=["Value"])
    if df.empty:
        raise ValueError("No valid numeric values to plot after NaN removal.")

    # Validate required signals exist somewhere
    present = set(df["Signal"].astype(str))
    missing_sig = [s for s in signal_order if s not in present]
    if missing_sig:
        raise ValueError(f"Missing required signals in the input data: {missing_sig}")

    n_ds = len(dataset_order)
    n_sig = len(signal_order)
    ds_to_i = {ds: i for i, ds in enumerate(dataset_order)}
    sig_to_j = {sig: j for j, sig in enumerate(signal_order)}

    df["_xpos"] = [
        ds_to_i[str(ds)] * n_sig + sig_to_j[str(sig)] for ds, sig in zip(df["Dataset"].astype(str), df["Signal"].astype(str))
    ]

    # For plotting
    fig, ax = plt.subplots(figsize=figsize)

    # Determine y span for dataset label placement and pvalue brackets
    y_all = df["Value"].to_numpy(dtype=float)
    y_all = y_all[np.isfinite(y_all)]
    y_min = float(np.nanmin(y_all))
    y_max = float(np.nanmax(y_all))
    y_span = (y_max - y_min) if y_max > y_min else 1.0

    # ---- Strip + Box per dataset ----
    stats_rows = []
    jitter = 0.18  # horizontal jitter for strip points
    p_h = 0.06 * y_span
    p_gap = 0.05 * y_span

    for ds in dataset_order:
        col = DATASET_COLORS.get(ds, "#333333")
        sub_ds = df[df["Dataset"].astype(str) == str(ds)]

        # Strip points
        for sig in signal_order:
            sub_sig = sub_ds[sub_ds["Signal"].astype(str) == str(sig)]
            if sub_sig.empty:
                continue
            xpos = ds_to_i[ds] * n_sig + sig_to_j[sig]
            xj = xpos + np.random.uniform(-jitter, jitter, size=len(sub_sig))

            ax.scatter(
                xj,
                sub_sig["Value"].to_numpy(dtype=float),
                s=strip_size**2 / 2.5,
                c=col,
                alpha=strip_alpha,
                edgecolors="white",
                linewidths=0.35,
                zorder=2,
            )

        # Boxplot with white face + colored edges
        data_for_box = []
        positions = []
        for sig in signal_order:
            vals = sub_ds[sub_ds["Signal"].astype(str) == str(sig)]["Value"].to_numpy(dtype=float)
            vals = vals[np.isfinite(vals)]
            data_for_box.append(vals)
            positions.append(ds_to_i[ds] * n_sig + sig_to_j[sig])

        bp = ax.boxplot(
            data_for_box,
            positions=positions,
            widths=box_width,
            patch_artist=True,
            showfliers=False,
            medianprops={"color": STABILITY_PLOT_COLORS["median"], "linewidth": median_lw},
            boxprops={"edgecolor": col, "linewidth": box_edge_lw},
            whiskerprops={"color": col, "linewidth": box_edge_lw},
            capprops={"color": col, "linewidth": box_edge_lw},
        )
        for patch in bp["boxes"]:
            patch.set_facecolor(col)
            patch.set_alpha(0.18)  

        # P-values within dataset (rank-sum test)
        y_top_ds = float(np.nanmax(sub_ds["Value"].to_numpy(dtype=float)))
        base_y = y_top_ds + p_h

        for j, (s1, s2) in enumerate(comparisons):
            v1 = sub_ds[sub_ds["Signal"].astype(str) == str(s1)]["Value"].to_numpy(dtype=float)
            v2 = sub_ds[sub_ds["Signal"].astype(str) == str(s2)]["Value"].to_numpy(dtype=float)
            v1 = v1[np.isfinite(v1)]
            v2 = v2[np.isfinite(v2)]

            p = np.nan if (v1.size == 0 or v2.size == 0) else float(stats.ranksums(v1, v2).pvalue)
            stats_rows.append({"Dataset": ds, "Signal_1": s1, "Signal_2": s2, "p_value": p, f"n_{s1}": int(v1.size), f"n_{s2}": int(v2.size)})

            if not np.isfinite(p):
                continue

            x1 = ds_to_i[ds] * n_sig + sig_to_j[s1]
            x2 = ds_to_i[ds] * n_sig + sig_to_j[s2]
            y = base_y + j * (p_h + p_gap)

            ax.plot([x1, x1, x2, x2], [y, y + 0.4 * p_h, y + 0.4 * p_h, y], color="black", lw=1.1, zorder=3)
            ax.text(
                (x1 + x2) / 2,
                y + 0.55 * p_h,
                _format_pvalue_nature(p),
                ha="center",
                va="bottom",
                fontsize=fontsize - 1,
                color="black",
                zorder=4,
            )

    # ---- X ticks: show signal labels (repeated) ----
    x_positions = list(range(n_ds * n_sig))
    pretty_signal = {
        "Interferon Gamma": "IFNγ",
        "Proteasome subunits": "Proteasome",
        "ImmunoProteasome": "iPSM",
    }
    x_ticklabels = [pretty_signal.get(signal_order[j], signal_order[j]) for _ds in dataset_order for j in range(n_sig)]

    ax.set_xticks(x_positions)
    ax.set_xticklabels(x_ticklabels, fontsize=fontsize - 1, rotation=0, ha="center")

    ax.set_xlabel("")
    ax.set_ylabel(value_label, fontsize=fontsize)

    if title is not None:
        ax.set_title(title, fontsize=fontsize + 1, fontweight="bold", pad=14)

    # ---- Dataset labels: move them DOWN so they don't overlap signal labels ----
    # Place dataset name under the group center, lower than the signal tick labels.
    y_text = y_min - dataset_label_y_offset * y_span
    for ds in dataset_order:
        x_center = ds_to_i[ds] * n_sig + (n_sig - 1) / 2
        ax.text(
            x_center,
            y_text,
            ds,
            ha="center",
            va="top",
            fontsize=fontsize,
            fontweight="bold",
            clip_on=False,  # important: allow drawing outside axes
        )

    # Expand bottom margin so dataset labels are visible
    ax.set_ylim(y_min, y_max + 0.25 * y_span)

    # # # Legend: dataset colors only
    # legend_handles = [
    #     mpatches.Patch(facecolor=col, edgecolor=DATASET_COLORS.get(ds, "#333333"), label=ds, linewidth=2.0)
    #     for ds in dataset_order
    # ]
    # BOX_FACE_COLOR = "#F2F2F2"
    # legend_handles = []
    # for ds in dataset_order:
    #     col = DATASET_COLORS.get(ds, "#333333")
    #     legend_handles.append(
    #         mpatches.Patch(
    #             facecolor=col,  # <-- tô nền legend
    #             edgecolor=None,
    #             linewidth=2.0,
    #             label=ds,
    #         )
    #     )
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
    #     plt.tight_layout(rect=[0, 0.12, 0.86, 1])  # extra bottom space + right space
    # else:
    #     ax.legend(
    #         handles=legend_handles,
    #         title="Dataset",
    #         frameon=False,
    #         loc="upper right",
    #         fontsize=fontsize - 1,
    #         title_fontsize=fontsize,
    #     )
    #     plt.tight_layout(rect=[0, 0.20, 1, 1])

    stats_df = pd.DataFrame(stats_rows)

    if show:
        plt.show()

    return fig, ax, stats_df
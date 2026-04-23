from typing import Dict, Optional, Tuple, Union, List, Sequence
import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap


METHOD_COLOR_SCHEME = {
    "palette_name": "Set2",
    "palette": [
        "#66c2a5",  # greenish
        "#fc8d62",  # orange
        "#8da0cb",  # blue
        "#e78ac3",  # pink
        "#a6d854",  # lime
        "#ffd92f",  # yellow
        "#e5c494",  # tan
        "#b3b3b3",  # grey
    ],
}

# Cancer-type colors (fixed identity across the manuscript)
CANCER_COLORS = {
    "ccRCC": "#4C72B0",     # blue
    "Melanoma": "#DD8452",  # orange
    "NSCLC": "#55A868",     # green
}


_FONT = {
    "family": "sans-serif",
    "sans-serif": ["Helvetica", "Arial", "DejaVu Sans"],
}


STABILITY_PLOT_COLORS = {
    "median": "#000000",
    "swarm": "#000000",
    "mean_edge": "#b2182b",   # dark red
    "mean_face": "#ffffff",   # white
    "grid": "#e6e6e6",
    "heatmap_bg": "#f7f7f7",
}


DATASET_COLORS = {
    "Avatars K5": "#66c2a5",         # greenish
    "Avatars K10": "#fc8d62",        # orange
    "CTGAN": "#8da0cb",              # blue
    "Gaussian Copula": "#e78ac3",    # pink
    "Synthpop": "#a6d854",           # lime
    "TVAE": "#ffd92f",               # yellow
}


PBETTER_FOCUS_CMAP = LinearSegmentedColormap.from_list(
    "pbetter_focus",
    [
        (0.0, "#ffffff"),
        (0.5, "#ffffff"),
        (1.0, "#1a9850"),
    ],
)


def _build_method_palette(methods: Sequence[str], palette: Union[str, list]) -> Dict[str, str]:
    """
    Build a stable categorical palette mapping method -> color.

    Args:
        methods (Sequence[str]): Method names in the desired order.
        palette (Union[str, list]): Seaborn palette name or a list of colors.

    Returns:
        Dict[str, str]: Mapping from method name to hex/RGB color.

    Raises:
        ValueError: If methods is empty.
    """
    if not methods:
        raise ValueError("methods must be a non-empty sequence.")

    n = len(methods)

    if isinstance(palette, (list, tuple)) and len(palette) >= n:
        pal = list(palette)
    elif isinstance(palette, str):
        try:
            pal = list(sns.color_palette(palette, n_colors=n))
        except Exception:
            pal = METHOD_COLOR_SCHEME["palette"][:n]
    else:
        pal = METHOD_COLOR_SCHEME["palette"][:n]

    return {methods[i]: pal[i % len(pal)] for i in range(n)}


def _set_nature_rcparams(fontsize: int = 11) -> None:
    """
    Apply Nature-like matplotlib rcParams (Helvetica/Arial and clean axes).

    Args:
        fontsize (int): Base font size for the figure.
    """
    plt.rcParams.update(
        {
            "font.size": fontsize,
            "font.family": _FONT["family"],
            "font.sans-serif": _FONT["sans-serif"],
            "pdf.fonttype": 42,  # embed TrueType fonts (Illustrator-friendly)
            "ps.fonttype": 42,
            "axes.titlesize": fontsize + 1,
            "axes.labelsize": fontsize,
            "xtick.labelsize": fontsize - 1,
            "ytick.labelsize": fontsize - 1,
            "legend.fontsize": fontsize - 1,
        }
    )


def plot_violin_grid_by_cancer(
    cancer_to_method_scores: Dict[str, Dict[str, List[float]]],
    value_name: str = "Score",
    methods_order: Optional[Sequence[str]] = None,
    palette: Optional[Dict[str, str]] = DATASET_COLORS,
    figsize: Tuple[int, int] = (18, 5),
    fontsize: int = 11,
    annotate_mean: bool = True,
    mean_fmt: str = "{:.3f}",
    mean_marker: str = "D",
    mean_marker_size: float = 70.0,
    mean_text_offset_frac: float = 0.03,
    sharey: bool = True,
    show: bool = True,
) -> Tuple[plt.Figure, np.ndarray, Dict[str, pd.Series]]:
    """
    Plot a 1xN grid of violin plots, one per cancer type, using a shared method color palette.
    The mean of each method is shown as a white diamond and optionally annotated as text.

    Args:
        cancer_to_method_scores (Dict[str, Dict[str, List[float]]]): Mapping cancer -> {method -> list of scores}.
        value_name (str): Y-axis label for the score metric.
        methods_order (Optional[Sequence[str]]): Global ordering of methods across all panels.
            If None, uses the union of methods in insertion order.
        palette (Optional[Dict[str, str]]): Mapping method -> color. If None, uses DATASET_COLORS.
        figsize (Tuple[int, int]): Figure size.
        fontsize (int): Base font size.
        annotate_mean (bool): If True, write the mean value above each violin.
        mean_fmt (str): Format string for the mean annotation (e.g., "{:.3f}").
        mean_marker (str): Marker for mean point.
        mean_marker_size (float): Marker size for mean point.
        mean_text_offset_frac (float): Vertical offset for mean text as a fraction of y-span.
        sharey (bool): If True, share y-axis across panels.
        show (bool): If True, calls plt.show().

    Returns:
        Tuple[plt.Figure, np.ndarray, Dict[str, pd.Series]]: (figure, axes, mean_by_cancer).

    Raises:
        ValueError: If cancer_to_method_scores is empty.
        ValueError: If any cancer has no methods or no numeric scores after cleaning.
        ValueError: If methods_order contains methods missing from all cancers.
    """
    if not cancer_to_method_scores:
        raise ValueError("cancer_to_method_scores must be a non-empty dictionary.")

    cancers = list(cancer_to_method_scores.keys())

    # Determine global method order
    if methods_order is None:
        union_methods: List[str] = []
        for cancer in cancers:
            for m in list(cancer_to_method_scores.get(cancer, {}).keys()):
                if m not in union_methods:
                    union_methods.append(m)
        methods_order = union_methods
    else:
        methods_order = list(methods_order)

    if len(methods_order) == 0:
        raise ValueError("methods_order resolved to an empty list.")

    # Palette: default to DATASET_COLORS (requested) and ensure all needed methods exist
    if palette is None:
        palette = dict(DATASET_COLORS)

    pal_map = {m: palette.get(m, "#333333") for m in methods_order}

    _set_nature_rcparams(fontsize=fontsize)
    sns.set_style("whitegrid", rc={"grid.color": STABILITY_PLOT_COLORS["grid"]})

    n = len(cancers)
    fig, axes = plt.subplots(1, n, figsize=figsize, sharey=sharey)
    if n == 1:
        axes = np.array([axes])

    mean_by_cancer: Dict[str, pd.Series] = {}

    for ax, cancer in zip(axes, cancers):
        method_scores = cancer_to_method_scores.get(cancer, {})
        if method_scores is None or len(method_scores) == 0:
            raise ValueError(f"Cancer '{cancer}' has no method scores.")

        # Build long df
        rows = []
        for m in methods_order:
            vals = method_scores.get(m, None)
            if vals is None:
                continue
            arr = pd.to_numeric(pd.Series(vals), errors="coerce").dropna().to_numpy(dtype=float)
            for v in arr:
                rows.append({"Method": m, value_name: float(v)})

        df_long = pd.DataFrame(rows)
        if df_long.empty:
            raise ValueError(f"Cancer '{cancer}' has no valid numeric scores after cleaning.")

        df_long["Method"] = pd.Categorical(df_long["Method"], categories=list(methods_order), ordered=True)

        sns.violinplot(
            data=df_long,
            x="Method",
            y=value_name,
            order=list(methods_order),
            palette=pal_map,
            cut=0,
            inner="quartile",
            linewidth=1.2,
            ax=ax,
        )

        # Means
        mean_by_method = df_long.groupby("Method")[value_name].mean().reindex(list(methods_order))
        mean_by_cancer[cancer] = mean_by_method

        y_min, y_max = ax.get_ylim()
        y_span = (y_max - y_min) if (y_max > y_min) else 1.0

        for i, m in enumerate(list(methods_order)):
            mu = mean_by_method.loc[m]
            if pd.isna(mu):
                continue

            ax.scatter(
                i,
                float(mu),
                marker=mean_marker,
                s=mean_marker_size,
                facecolor=STABILITY_PLOT_COLORS["mean_face"],
                edgecolor=STABILITY_PLOT_COLORS["mean_edge"],
                linewidth=1.3,
                zorder=10,
            )

            if annotate_mean:
                ax.text(
                    i,
                    float(mu) + float(mean_text_offset_frac) * y_span,
                    mean_fmt.format(float(mu)),
                    ha="center",
                    va="bottom",
                    fontsize=fontsize - 2,
                    color="black",
                )

        ax.set_xlabel("")
        if ax is axes[0]:
            ax.set_ylabel(value_name, fontsize=fontsize)
        else:
            ax.set_ylabel("")

        ax.tick_params(axis="x", rotation=45)
        # ax.tick_params(axis="x", rotation=0)

        for lbl in ax.get_xticklabels():
            lbl.set_fontweight("bold")   # hoặc 700

        
        cancer_color = CANCER_COLORS.get(cancer, "#333333")
        ax.set_title(cancer, fontsize=fontsize + 1, fontweight="bold", color="black", pad=10)
        ax.plot([0.02, 0.98], [1.02, 1.02], transform=ax.transAxes, color=cancer_color, lw=4, clip_on=False)

    plt.tight_layout()
    if show:
        plt.show()

    return fig, axes, mean_by_cancer
from typing import Dict, Optional, Tuple, Union, List, Sequence
import itertools
import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from scipy import stats
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm

# Consistent color definitions for manuscript-quality figures
# Reuse these variables across plotting functions to ensure consistent visual identity.
METHOD_COLOR_SCHEME = {
    "palette_name": "Set2",
    # A default Set2-like palette defined explicitly as hex colors so it's stable across environments.
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

# Colors for stability/benchmark plots (aligned with METHOD_COLOR_SCHEME)
STABILITY_PLOT_COLORS = {
    "median": "#000000",
    "swarm": "#000000",
    "mean_edge": "#b2182b",   # dark red
    "mean_face": "#ffffff",   # white
    "grid": "#e6e6e6",
    "heatmap_bg": "#f7f7f7",
}

# Heatmap: emphasize only whether P(Better) exceeds 0.5
# - Below 0.5 -> near-white
# - Above 0.5 -> progressively greener
# This makes "better than chance" immediately visible.
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


def wide_to_long(
    df_wide: pd.DataFrame,
    method_col: str = "Method",
    value_col: str = "Score",
    dropna: bool = True,
) -> pd.DataFrame:
    """
    Convert a wide-format DataFrame (columns=methods, rows=replicates) into long format.

    Args:
        df_wide (pd.DataFrame): Wide DataFrame where columns are method names and rows are seeds/replicates.
        method_col (str): Output column name for method labels.
        value_col (str): Output column name for score values.
        dropna (bool): If True, drop rows with missing score after conversion.

    Returns:
        pd.DataFrame: Long-format DataFrame with columns [method_col, value_col].

    Raises:
        ValueError: If df_wide is None or empty.
    """
    if df_wide is None or df_wide.empty:
        raise ValueError("df_wide must be a non-empty DataFrame.")

    df_long = df_wide.reset_index(drop=True).melt(var_name=method_col, value_name=value_col)
    df_long[value_col] = pd.to_numeric(df_long[value_col], errors="coerce")
    if dropna:
        df_long = df_long.dropna(subset=[value_col])
    return df_long


def plot_box_swarm_with_mean(
    df_long: pd.DataFrame,
    method_col: str = "Method",
    value_col: str = "Score",
    title: Optional[str] = None,
    figsize: Tuple[int, int] = (14, 6),
    order: Optional[List[str]] = None,
    palette: Union[str, list] = METHOD_COLOR_SCHEME["palette_name"],
    annotate_mean: bool = False,
    fontsize: int = 11,
    mean_style: str = "diamond",
) -> Tuple[plt.Figure, plt.Axes, pd.Series]:
    """
    Plot boxplot + swarmplot and overlay per-method mean markers, using a consistent method palette.

    Args:
        df_long (pd.DataFrame): Long-format table with method and score columns.
        method_col (str): Column name containing method names.
        value_col (str): Column name containing scores.
        title (Optional[str]): Plot title. If None, uses a default.
        figsize (Tuple[int, int]): Figure size.
        order (Optional[List[str]]): Explicit x-axis order. If None, uses appearance order.
        palette (Union[str, list]): Seaborn palette name or list of colors.
        annotate_mean (bool): If True, show numeric mean value near the marker.
        fontsize (int): Base font size for labels and annotations.
        mean_style (str): "diamond" (white diamond) or "line" (red tick).

    Returns:
        Tuple[plt.Figure, plt.Axes, pd.Series]: (figure, axis, mean_by_method).

    Raises:
        ValueError: If df_long is empty or missing required columns.
        ValueError: If mean_style is invalid.
    """
    if df_long is None or df_long.empty:
        raise ValueError("df_long must be a non-empty DataFrame.")

    if method_col not in df_long.columns or value_col not in df_long.columns:
        raise ValueError(f"df_long must contain columns '{method_col}' and '{value_col}'.")

    if mean_style not in {"diamond", "line"}:
        raise ValueError("mean_style must be one of {'diamond', 'line'}.")

    df_long = df_long.copy()
    df_long[value_col] = pd.to_numeric(df_long[value_col], errors="coerce")
    df_long = df_long.dropna(subset=[value_col])

    if order is None:
        order = list(pd.unique(df_long[method_col]))

    pal_map = _build_method_palette(order, palette)

    sns.set(style="whitegrid", rc={"axes.facecolor": (0.98, 0.98, 0.99), "grid.color": STABILITY_PLOT_COLORS["grid"]})
    fig, ax = plt.subplots(figsize=figsize)

    sns.boxplot(
        data=df_long,
        x=method_col,
        y=value_col,
        order=order,
        palette=pal_map,
        ax=ax,
        showfliers=False,
        width=0.6,
        medianprops={"color": STABILITY_PLOT_COLORS["median"], "linewidth": 2.0},
        whiskerprops={"color": "black"},
        capprops={"color": "black"},
        boxprops={"edgecolor": "black"},
    )

    sns.swarmplot(
        data=df_long,
        x=method_col,
        y=value_col,
        order=order,
        ax=ax,
        color=STABILITY_PLOT_COLORS["swarm"],
        size=5,
        alpha=0.75,
    )

    mean_by_method = df_long.groupby(method_col)[value_col].mean().reindex(order)
    y_min, y_max = ax.get_ylim()
    y_span = (y_max - y_min) if (y_max > y_min) else 1.0

    for i, m in enumerate(order):
        mu = mean_by_method.loc[m]
        if pd.isna(mu):
            continue

        if mean_style == "diamond":
            ax.scatter(
                i,
                float(mu),
                marker="D",
                s=80,
                facecolor=STABILITY_PLOT_COLORS["mean_face"],
                edgecolor=STABILITY_PLOT_COLORS["mean_edge"],
                linewidth=1.4,
                zorder=10,
            )
        else:
            ax.scatter(
                i,
                float(mu),
                marker="_",
                s=700,
                color=STABILITY_PLOT_COLORS["mean_edge"],
                linewidths=3,
                zorder=10,
            )

        if annotate_mean:
            ax.text(
                i,
                float(mu) + 0.03 * y_span,
                f"{float(mu):.3f}",
                ha="center",
                va="bottom",
                fontsize=fontsize - 1,
                color="black",
            )

    ax.set_xlabel("")
    ax.set_ylabel(value_col, fontsize=fontsize)
    ax.tick_params(axis="x", labelsize=fontsize - 1, rotation=90)
    ax.tick_params(axis="y", labelsize=fontsize - 1)

    if title:
        ax.set_title(title, fontsize=fontsize + 1, fontweight="bold")
    else:
        ax.set_title(
            "",
            fontsize=fontsize + 1,
            fontweight="bold",
        )

    plt.tight_layout()
    return fig, ax, mean_by_method


def bayesian_estimation(
    df_wide: pd.DataFrame,
    rope: float = 0.01,
    n_samples: int = 10_000,
    seed: int = 0,
    methods: Optional[Sequence[str]] = None,
) -> pd.DataFrame:
    """
    Compute Benavoli-style Bayesian pairwise probabilities using Student-t posterior sampling.

    Args:
        df_wide (pd.DataFrame): Wide DataFrame with columns as methods and rows as seeds/replicates.
        rope (float): ROPE threshold for practical equivalence on mean differences.
        n_samples (int): Monte Carlo samples per method for posterior mean sampling.
        seed (int): Random seed for reproducibility.
        methods (Optional[Sequence[str]]): Optional subset/order of methods.

    Returns:
        pd.DataFrame: Long table with columns:
            ["Method_A", "Method_B", "P(Better)", "P(Worse)", "P(Equivalent)", "ROPE"].

    Raises:
        ValueError: If df_wide is empty.
        ValueError: If fewer than 2 methods are available.
        ValueError: If n_samples < 1000.
    """
    if df_wide is None or df_wide.empty:
        raise ValueError("df_wide must be a non-empty DataFrame.")

    if n_samples < 1000:
        raise ValueError("n_samples must be >= 1000 (recommend >= 10000).")

    if methods is None:
        methods = list(df_wide.columns)
    else:
        methods = list(methods)

    if len(methods) < 2:
        raise ValueError("Need at least 2 methods for pairwise comparison.")

    rng = np.random.default_rng(seed)

    def _posterior_mean_samples(x: np.ndarray) -> np.ndarray:
        x = np.asarray(x, dtype=float)
        x = x[np.isfinite(x)]
        if x.size < 2:
            raise ValueError("Need at least 2 finite observations per method for Student-t posterior.")
        n = x.size
        mu_hat = float(np.mean(x))
        s = float(np.std(x, ddof=1))
        df = n - 1
        scale = s / np.sqrt(n) if s > 0 else 0.0
        return mu_hat + scale * rng.standard_t(df=df, size=int(n_samples))

    post = {m: _posterior_mean_samples(pd.to_numeric(df_wide[m], errors="coerce").to_numpy()) for m in methods}

    rows = []
    for a, b in itertools.permutations(methods, 2):
        diff = post[a] - post[b]
        rows.append(
            {
                "Method_A": a,
                "Method_B": b,
                "P(Better)": float(np.mean(diff > rope)),
                "P(Worse)": float(np.mean(diff < -rope)),
                "P(Equivalent)": float(np.mean(np.abs(diff) <= rope)),
                "ROPE": float(rope),
            }
        )

    return pd.DataFrame(rows)


def pairwise_to_matrix(
    pairwise_df: pd.DataFrame,
    value_col: str = "P(Better)",
    methods: Optional[Sequence[str]] = None,
    diag_value: float = 0.5,
) -> pd.DataFrame:
    """
    Convert pairwise probability table into a square matrix for heatmap plotting.

    Args:
        pairwise_df (pd.DataFrame): Output from benavoli_pairwise_probabilities().
        value_col (str): Probability column to pivot into the matrix (e.g., "P(Better)").
        methods (Optional[Sequence[str]]): Optional ordering of methods.
        diag_value (float): Value to set on diagonal.

    Returns:
        pd.DataFrame: Square matrix of probabilities.

    Raises:
        ValueError: If required columns are missing.
    """
    required = {"Method_A", "Method_B", value_col}
    missing = required - set(pairwise_df.columns)
    if missing:
        raise ValueError(f"pairwise_df missing required columns: {sorted(missing)}")

    mat = pairwise_df.pivot(index="Method_A", columns="Method_B", values=value_col)

    if methods is not None:
        methods = list(methods)
        mat = mat.reindex(index=methods, columns=methods)

    for m in mat.index:
        if m in mat.columns:
            mat.loc[m, m] = float(diag_value)

    return mat


def plot_pbetter_heatmap(
    pbetter_mat: pd.DataFrame,
    title: str = "P(Better) heatmap (focus on > 0.50)",
    figsize: Tuple[int, int] = (10, 8),
    annot: bool = True,
    fmt: str = ".2f",
    show: bool = True,
) -> Tuple[plt.Figure, plt.Axes]:
    """
    Plot a P(Better) heatmap emphasizing only cells above 0.50.

    Args:
        pbetter_mat (pd.DataFrame): Square matrix of probabilities in [0, 1].
        title (str): Plot title.
        figsize (Tuple[int, int]): Figure size.
        annot (bool): If True, annotate each cell with its value.
        fmt (str): Annotation format.
        show (bool): If True, calls plt.show().

    Returns:
        Tuple[plt.Figure, plt.Axes]: Figure and Axes.

    Raises:
        ValueError: If pbetter_mat is empty.
    """
    if pbetter_mat is None or pbetter_mat.empty:
        raise ValueError("pbetter_mat must be a non-empty DataFrame.")

    # Normalize around 0.5 so anything below is visually "not better than chance"
    norm = TwoSlopeNorm(vmin=0.0, vcenter=0.5, vmax=1.0)

    sns.set(style="white", rc={"axes.facecolor": STABILITY_PLOT_COLORS["heatmap_bg"]})
    fig, ax = plt.subplots(figsize=figsize)

    sns.heatmap(
        pbetter_mat,
        ax=ax,
        cmap=PBETTER_FOCUS_CMAP,
        norm=norm,
        annot=annot,
        fmt=fmt,
        linewidths=0.5,
        linecolor="lightgray",
        cbar_kws={"label": "P(Better)"},
    )

    ax.set_title(title, fontsize=12, fontweight="bold")
    ax.set_xlabel("Method B", fontsize=11, fontweight="bold")
    ax.set_ylabel("Method A", fontsize=11, fontweight="bold")
    plt.tight_layout()

    if show:
        plt.show()

    return fig, ax
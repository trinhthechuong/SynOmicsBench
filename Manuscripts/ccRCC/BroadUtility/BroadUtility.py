from typing import Dict, Optional, Tuple, Union
import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

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


def plot_violin(
    scores_dict: Dict[str, np.ndarray],
    title: Optional[str] = None,
    figsize: Tuple[int, int] = (14, 6),
    order: Optional[list] = None,
    palette: Union[str, list] = METHOD_COLOR_SCHEME["palette_name"],
    annotate: bool = True,
    fontsize: int = 11,
) -> Tuple[plt.Figure, plt.Axes]:
    """
    Plot violin plots of score distributions for multiple methods.

    Args:
        scores_dict (Dict[str, np.ndarray]): Mapping from method name to array-like scores.
        title (Optional[str]): Figure title. If None, a sensible default title is used.
        figsize (Tuple[int, int]): Size of the matplotlib figure (width, height).
        order (Optional[list]): Explicit order of methods to display. If None, uses keys order.
        palette (Union[str, list]): Either a seaborn palette name (str) or a list of colors.
        annotate (bool): If True, annotate each method's mean above the violin.
        fontsize (int): Base font size for labels and annotations.

    Returns:
        Tuple[plt.Figure, plt.Axes]: Matplotlib Figure and the Axes containing the violin plot.

    Raises:
        ValueError: If scores_dict contains fewer than one group or after removing NaNs no data remains.
    """
    # Basic validation
    if not scores_dict or len(scores_dict) < 1:
        raise ValueError("scores_dict must contain at least one group to plot.")

    methods = list(scores_dict.keys()) if order is None else order
    missing = [m for m in methods if m not in scores_dict]
    if missing:
        raise ValueError(f"The following methods specified in order are missing from scores_dict: {missing}")

    # Build DataFrame for plotting (drop NaNs)
    records = []
    for m in methods:
        arr = np.asarray(scores_dict[m])
        arr = arr[~np.isnan(arr)]
        for v in arr:
            records.append((m, float(v)))
    df = pd.DataFrame(records, columns=["method", "score"])
    if df.empty:
        raise ValueError("After removing NaNs, no data remains to plot.")

    # Ensure consistent palette: accept list or palette name
    n = len(methods)
    if isinstance(palette, (list, tuple)) and len(palette) >= n:
        pal = palette
    elif isinstance(palette, str):
        # if user provided a known name use seaborn to generate required number
        try:
            pal = sns.color_palette(palette, n_colors=n)
        except Exception:
            # fallback to our default explicit palette
            pal = METHOD_COLOR_SCHEME["palette"][:n]
    else:
        # fallback to explicit default palette
        pal = METHOD_COLOR_SCHEME["palette"][:n]

    # --- Fix for FutureWarning:
    # Recent seaborn versions warn when passing a palette (list) without a hue.
    # To avoid the FutureWarning and ensure stable behavior across seaborn versions,
    # convert a list/sequence palette into a mapping {category: color} and pass that dict.
    # seaborn treats a palette dict as a categorical color mapping and will not emit the warning.
    if isinstance(pal, (list, tuple)):
        pal = {methods[i]: pal[i % len(pal)] for i in range(n)}

    # Plot styling
    sns.set(style="whitegrid", rc={"axes.facecolor": (0.98, 0.98, 0.99)})
    fig, ax_violin = plt.subplots(figsize=figsize)

    # Violin plot
    sns.violinplot(
        x="method",
        y="score",
        data=df,
        order=methods,
        palette=pal,
        cut=0,
        inner="quartile",
        linewidth=1.2,
        ax=ax_violin,
    )

    # Compute and plot means
    means = df.groupby("method")["score"].mean().reindex(methods)
    ylim = ax_violin.get_ylim()
    yspan = ylim[1] - ylim[0] if (ylim[1] - ylim[0]) != 0 else 1.0
    for i, m in enumerate(methods):
        mean_val = means.loc[m]
        # white diamond with black edge
        ax_violin.scatter(
            i,
            mean_val,
            color="white",
            edgecolor="black",
            s=80,
            zorder=10,
            linewidth=1.1,
            marker="D",
        )
        if annotate:
            ax_violin.text(
                i,
                mean_val + yspan * 0.03,
                f"{mean_val:.3f}",
                ha="center",
                va="bottom",
                fontsize=fontsize - 1,
                color="black",
            )

    ax_violin.set_xlabel("")
    ax_violin.set_ylabel("Score", fontsize=fontsize)
    ax_violin.tick_params(axis="x", labelsize=fontsize - 1, rotation=90)
    ax_violin.tick_params(axis="y", labelsize=fontsize - 1)
    if title:
        ax_violin.set_title(title, fontsize=fontsize + 1, fontweight="bold")
    else:
        ax_violin.set_title(
            "Distribution of scores by method\n(mean shown as white diamond)",
            fontsize=fontsize + 1,
            fontweight="bold",
        )

    plt.tight_layout()
    return fig, ax_violin
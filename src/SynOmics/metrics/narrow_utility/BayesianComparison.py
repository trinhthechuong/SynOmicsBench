from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm

try:
    import baycomp
except ImportError as e:
    raise ImportError("baycomp is required. Install with: pip install baycomp") from e


# =========================
# Color & style definitions
# =========================

METHOD_COLOR_SCHEME = {
    "palette_name": "Set2",
    "palette": [
        "#66c2a5",
        "#fc8d62",
        "#8da0cb",
        "#e78ac3",
        "#a6d854",
        "#ffd92f",
        "#e5c494",
        "#b3b3b3",
    ],
}

CANCER_COLORS = {
    "ccRCC": "#4C72B0",
    "Melanoma": "#DD8452",
    "NSCLC": "#55A868",
}

NATURE_FONT = {
    "family": "sans-serif",
    "sans-serif": ["Helvetica", "Arial", "DejaVu Sans"],
}

STABILITY_PLOT_COLORS = {
    "grid": "#e6e6e6",
    "heatmap_bg": "#f7f7f7",
    "missing_edge": "#BDBDBD",
    "missing_face": "#FFFFFF",
}

PBETTER_FOCUS_CMAP = LinearSegmentedColormap.from_list(
    "pbetter_focus",
    [
        (0.0, "#ffffff"),
        (0.5, "#ffffff"),
        (1.0, "#1a9850"),
    ],
)


def _set_nature_rcparams(fontsize: int = 11) -> None:
    """
    Apply Nature-like matplotlib rcParams (Helvetica/Arial and clean axes).

    Args:
        fontsize (int): Base font size for the figure.

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


def _overlay_hatched_missing_cells(
    ax: plt.Axes,
    mat: pd.DataFrame,
    hatch: str,
    edgecolor: str,
    facecolor: str,
    linewidth: float,
) -> None:
    """
    Overlay hatched rectangles on NaN cells in a seaborn heatmap.

    Args:
        ax (plt.Axes): Axis containing the heatmap.
        mat (pd.DataFrame): Heatmap matrix (NaNs indicate missing cells).
        hatch (str): Matplotlib hatch pattern.
        edgecolor (str): Rectangle edge color.
        facecolor (str): Rectangle face color.
        linewidth (float): Rectangle edge line width.
    """
    nrows, ncols = mat.shape
    nan_mask = mat.isna().to_numpy()

    for i in range(nrows):
        for j in range(ncols):
            if not nan_mask[i, j]:
                continue
            rect = mpatches.Rectangle(
                (j, i),
                1.0,
                1.0,
                facecolor=facecolor,
                edgecolor=edgecolor,
                hatch=hatch,
                linewidth=linewidth,
                fill=True,
                zorder=10,
            )
            ax.add_patch(rect)


def build_baycomp_comparison_df(
    method_to_scores: Mapping[str, Sequence[float]],
    methods_order: Optional[Sequence[str]] = None,
    rope: float = 0.01,
) -> pd.DataFrame:
    """
    Compute pairwise Bayesian comparison probabilities (better/worse/equivalent)
    using baycomp.two_on_single for all ordered pairs of methods.

    Args:
        method_to_scores (Mapping[str, Sequence[float]]): Mapping tool/method -> list/array of scores.
        methods_order (Optional[Sequence[str]]): Optional method ordering. If None, uses dict keys.
        rope (float): ROPE threshold for practical equivalence.

    Returns:
        pd.DataFrame: Comparison table with columns:
            ["Method 1", "Method 2", "Better Prob", "Worse Prob", "Equivalent Prob"].

    Raises:
        ValueError: If rope is not positive.
        ValueError: If fewer than 2 methods are provided.
        ValueError: If any method has fewer than 2 finite scores.
    """
    if rope <= 0:
        raise ValueError("rope must be > 0.")

    if not method_to_scores or len(method_to_scores) < 2:
        raise ValueError("method_to_scores must contain at least 2 methods.")

    methods = list(method_to_scores.keys()) if methods_order is None else list(methods_order)

    scores_np: Dict[str, np.ndarray] = {}
    for m in methods:
        if m not in method_to_scores:
            continue
        x = np.asarray(method_to_scores[m], dtype=float)
        x = x[np.isfinite(x)]
        if x.size < 2:
            raise ValueError(f"Method '{m}' must have at least 2 finite scores for baycomp.")
        scores_np[m] = x

    present_methods = [m for m in methods if m in scores_np]
    if len(present_methods) < 2:
        raise ValueError("Fewer than 2 methods remain after filtering invalid scores / missing methods.")

    rows: List[dict] = []
    for m1 in present_methods:
        for m2 in present_methods:
            if m1 == m2:
                continue

            p_left, p_rope, p_right = baycomp.two_on_single(
                scores_np[m1],
                scores_np[m2],
                rope=rope,
                plot=False,
            )

            rows.append(
                {
                    "Method 1": m1,
                    "Method 2": m2,
                    "Better Prob": float(p_left),
                    "Worse Prob": float(p_right),
                    "Equivalent Prob": float(p_rope),
                }
            )

    return pd.DataFrame(rows)


@dataclass(frozen=True)
class BaycompStyle:
    """
    Store manuscript-style visualization settings for baycomp heatmaps.

    Args:
        fontsize (int): Base font size used in matplotlib rcParams.
        nature_font (Dict[str, Sequence[str]]): Font family configuration.
        plot_colors (Dict[str, str]): Common background/grid colors.
        pbetter_cmap (LinearSegmentedColormap): Colormap for P(Better) heatmaps.
        cancer_colors (Dict[str, str]): Color strip mapping for each cancer panel.

    Raises:
        ValueError: If fontsize is not positive.
    """
    fontsize: int = 11
    nature_font: Dict[str, Sequence[str]] = None  # type: ignore[assignment]
    plot_colors: Dict[str, str] = None  # type: ignore[assignment]
    # pbetter_cmap: LinearSegmentedColormap = PBETTER_FOCUS_CMAP
    pbetter_cmap: LinearSegmentedColormap = field(
        default_factory=lambda: PBETTER_FOCUS_CMAP
    ) 
    cancer_colors: Dict[str, str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.fontsize <= 0:
            raise ValueError("fontsize must be a positive integer.")
        object.__setattr__(self, "nature_font", dict(NATURE_FONT))
        object.__setattr__(self, "plot_colors", dict(STABILITY_PLOT_COLORS))
        object.__setattr__(self, "cancer_colors", dict(CANCER_COLORS))


@dataclass
class BayesianComparison:
    """
    Compute Bayesian pairwise comparisons using the external baycomp package and plot heatmaps.

    Args:
        rope (float): ROPE threshold for practical equivalence.
        seed (int): Random seed for reproducibility in baycomp.
        style (BaycompStyle): Plot styling settings for consistent manuscript figures.

    Raises:
        ValueError: If rope is not positive.
    """
    rope: float = 0.01
    seed: int = 0
    style: BaycompStyle = BaycompStyle()

    def __post_init__(self) -> None:
        if self.rope <= 0:
            raise ValueError("rope must be > 0.")

    @staticmethod
    def _validate_scores(scores: Sequence[float], method: str) -> np.ndarray:
        """
        Validate and coerce a score sequence to a finite numpy array.

        Args:
            scores (Sequence[float]): Metric values across repeated runs (seeds/folds).
            method (str): Method name for error messages.

        Returns:
            np.ndarray: Finite float numpy array of scores.

        Raises:
            ValueError: If fewer than 2 finite scores are present.
        """
        x = np.asarray(scores, dtype=float)
        x = x[np.isfinite(x)]
        if x.size < 2:
            raise ValueError(f"Method '{method}' must have at least 2 finite scores for baycomp.")
        return x

    @staticmethod
    def _resolve_methods_order(
        method_to_scores: Mapping[str, Sequence[float]],
        methods_order: Optional[Sequence[str]],
    ) -> List[str]:
        """
        Resolve and validate the method ordering.

        Args:
            method_to_scores (Mapping[str, Sequence[float]]): Mapping method -> scores.
            methods_order (Optional[Sequence[str]]): Optional explicit ordering.

        Returns:
            List[str]: Ordered list of methods.

        Raises:
            ValueError: If fewer than 2 methods are provided.
            ValueError: If methods_order contains methods not present in method_to_scores.
        """
        if not method_to_scores or len(method_to_scores) < 2:
            raise ValueError("method_to_scores must contain at least 2 methods.")

        if methods_order is None:
            return list(method_to_scores.keys())

        resolved = list(methods_order)
        missing = [m for m in resolved if m not in method_to_scores]
        if missing:
            raise ValueError(f"methods_order contains methods missing in method_to_scores: {missing}")
        return resolved

    def compare_methods(
        self,
        method_to_scores: Mapping[str, Sequence[float]],
        methods_order: Optional[Sequence[str]] = None,
    ) -> pd.DataFrame:
        """
        Compute ordered-pair Bayesian comparison probabilities for a set of methods.

        Args:
            method_to_scores (Mapping[str, Sequence[float]]): Mapping method -> scores across seeds/folds.
            methods_order (Optional[Sequence[str]]): Optional ordering for methods.

        Returns:
            pd.DataFrame: Table with columns:
                ["Method 1", "Method 2", "Better Prob", "Worse Prob", "Equivalent Prob"].

        Raises:
            ValueError: If fewer than 2 methods are provided.
            ValueError: If any method has fewer than 2 finite scores.
        """
        methods = self._resolve_methods_order(method_to_scores, methods_order)
        scores_np = {m: self._validate_scores(method_to_scores[m], method=m) for m in methods}

        rows: List[dict] = []
        for i, m1 in enumerate(methods):
            for j, m2 in enumerate(methods):
                if i == j:
                    continue

                p_left, p_rope, p_right = baycomp.two_on_single(
                    scores_np[m1],
                    scores_np[m2],
                    rope=self.rope,
                    plot=False,
                )

                rows.append(
                    {
                        "Method 1": m1,
                        "Method 2": m2,
                        "Better Prob": float(p_left),
                        "Worse Prob": float(p_right),
                        "Equivalent Prob": float(p_rope),
                    }
                )

        return pd.DataFrame(rows)

    @staticmethod
    def comparison_to_matrix(
        comparison_df: pd.DataFrame,
        methods_order: Sequence[str],
        value_col: str = "Better Prob",
        nan_diagonal: bool = True,
    ) -> pd.DataFrame:
        """
        Convert a comparison table into a square matrix suitable for heatmap plotting.

        Args:
            comparison_df (pd.DataFrame): Output of compare_methods.
            methods_order (Sequence[str]): Method ordering for rows and columns.
            value_col (str): Which column to visualize.
            nan_diagonal (bool): If True, set diagonal values to NaN.

        Returns:
            pd.DataFrame: Square matrix with index=Method 1 and columns=Method 2.

        Raises:
            ValueError: If value_col is not present in comparison_df.
        """
        if value_col not in comparison_df.columns:
            raise ValueError(f"value_col must be a column in comparison_df, got '{value_col}'.")

        mat = comparison_df.pivot(index="Method 1", columns="Method 2", values=value_col)
        mat = mat.reindex(index=list(methods_order), columns=list(methods_order))

        if nan_diagonal:
            for m in methods_order:
                if m in mat.index and m in mat.columns:
                    mat.loc[m, m] = np.nan

        return mat

    def plot_pbetter_heatmap_grid(
        self,
        cancer_to_method_scores: Mapping[str, Mapping[str, Sequence[float]]],
        cancers_order: Sequence[str] = ("ccRCC", "Melanoma", "NSCLC"),
        methods_order: Optional[Sequence[str]] = None,
        value_col: str = "Better Prob",
        figsize: Tuple[float, float] = (18, 5),
        annot: bool = True,
        fmt: str = ".2f",
        missing_hatch: str = "///",
        show: bool = True,
    ) -> Tuple[plt.Figure, np.ndarray, Dict[str, pd.DataFrame], Dict[str, pd.DataFrame]]:
        """
        Plot a 1xN grid of baycomp probability heatmaps (one per cancer).

        Args:
            cancer_to_method_scores (Mapping[str, Mapping[str, Sequence[float]]]): Cancer -> method/tool -> score list.
            cancers_order (Sequence[str]): Order of cancers in the grid.
            methods_order (Optional[Sequence[str]]): Global method ordering. If None, uses union across cancers.
            value_col (str): Which probability to visualize:
                "Better Prob", "Worse Prob", or "Equivalent Prob".
            figsize (Tuple[float, float]): Figure size.
            annot (bool): If True, annotate cells (NaN cells are blank).
            fmt (str): Annotation format.
            missing_hatch (str): Hatch pattern for missing (NaN) cells.
            show (bool): If True, calls plt.show().

        Returns:
            Tuple[plt.Figure, np.ndarray, Dict[str, pd.DataFrame], Dict[str, pd.DataFrame]]: Tuple containing:
                - fig: Matplotlib Figure object.
                - axes: Array of Axes objects.
                - matrices_by_cancer: Probability matrices for each cancer.
                - comparison_dfs_by_cancer: Comparison DataFrames for each cancer.

        Raises:
            ValueError: If value_col is invalid.
            ValueError: If any requested cancer is missing from cancer_to_method_scores.
            ValueError: If resolved methods_order is empty.
        """
        allowed = {"Better Prob", "Worse Prob", "Equivalent Prob"}
        if value_col not in allowed:
            raise ValueError(f"value_col must be one of {sorted(allowed)}.")

        cancers = list(cancers_order)
        for c in cancers:
            if c not in cancer_to_method_scores:
                raise ValueError(f"Cancer '{c}' missing from cancer_to_method_scores.")

        if methods_order is None:
            union_methods: List[str] = []
            for c in cancers:
                for m in cancer_to_method_scores[c].keys():
                    if m not in union_methods:
                        union_methods.append(m)
            methods_order_resolved = union_methods
        else:
            methods_order_resolved = list(methods_order)

        if len(methods_order_resolved) == 0:
            raise ValueError("methods_order resolved to an empty list.")

        _set_nature_rcparams(fontsize=self.style.fontsize)
        sns.set(style="white", rc={"axes.facecolor": self.style.plot_colors["heatmap_bg"]})

        fig, axes = plt.subplots(1, len(cancers), figsize=figsize)
        if len(cancers) == 1:
            axes = np.array([axes])

        norm = TwoSlopeNorm(vmin=0.0, vcenter=0.5, vmax=1.0)
        cmap = self.style.pbetter_cmap if value_col == "Better Prob" else plt.get_cmap("viridis")

        matrices_by_cancer: Dict[str, pd.DataFrame] = {}
        comparison_by_cancer: Dict[str, pd.DataFrame] = {}

        for ax, cancer in zip(axes, cancers):
            present_methods = set(cancer_to_method_scores[cancer].keys())

            comp_df = build_baycomp_comparison_df(
                method_to_scores=cancer_to_method_scores[cancer],
                methods_order=methods_order_resolved,
                rope=self.rope,
            )
            comparison_by_cancer[cancer] = comp_df

            mat = pd.DataFrame(index=methods_order_resolved, columns=methods_order_resolved, dtype=float)
            if not comp_df.empty:
                mat_present = comp_df.pivot(index="Method 1", columns="Method 2", values=value_col)
                mat.loc[mat_present.index, mat_present.columns] = mat_present

            for m in methods_order_resolved:
                if m in present_methods:
                    mat.loc[m, m] = 0.5

            matrices_by_cancer[cancer] = mat

            mask = mat.isna()
            sns.heatmap(
                mat,
                ax=ax,
                cmap=cmap,
                norm=norm if value_col == "Better Prob" else None,
                mask=mask,
                annot=annot,
                fmt=fmt,
                linewidths=0.5,
                linecolor="lightgray",
                cbar=(ax is axes[-1]),
                cbar_kws={"label": value_col} if (ax is axes[-1]) else None,
                square=True,
            )

            _overlay_hatched_missing_cells(
                ax=ax,
                mat=mat,
                hatch=missing_hatch,
                edgecolor=self.style.plot_colors.get("missing_edge", STABILITY_PLOT_COLORS["missing_edge"]),
                facecolor=self.style.plot_colors.get("missing_face", STABILITY_PLOT_COLORS["missing_face"]),
                linewidth=0.6,
            )

            for i, m in enumerate(methods_order_resolved):
                if m in present_methods:
                    rect = mpatches.Rectangle(
                        (i, i),
                        1.0,
                        1.0,
                        facecolor="#D3D3D3",
                        edgecolor="lightgray",
                        linewidth=0.5,
                        zorder=11,
                    )
                    ax.add_patch(rect)

            ax.set_title(cancer, fontsize=self.style.fontsize + 1, fontweight="bold", pad=10)

            cancer_color = self.style.cancer_colors.get(cancer, "#333333")
            ax.plot(
                [0.02, 0.98],
                [1.02, 1.02],
                transform=ax.transAxes,
                color=cancer_color,
                lw=4,
                clip_on=False,
            )

            ax.set_xlabel("Method 2", fontsize=self.style.fontsize)
            ax.set_ylabel("Method 1", fontsize=self.style.fontsize)
            plt.setp(ax.get_xticklabels(), rotation=45, ha="right", rotation_mode="anchor")
            ax.tick_params(axis="y", rotation=0)

        plt.tight_layout()
        if show:
            plt.show()

        return fig, axes, matrices_by_cancer, comparison_by_cancer
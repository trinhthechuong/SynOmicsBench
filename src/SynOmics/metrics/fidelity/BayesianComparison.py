from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

try:
    import baycomp
except ImportError as e:
    raise ImportError("baycomp is required. Install with: pip install baycomp") from e

from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm


# -----------------------------
# Nature-style + consistent colormap
# -----------------------------

_FONT = {
    "family": "sans-serif",
    "sans-serif": ["Helvetica", "Arial", "DejaVu Sans"],
}

STABILITY_PLOT_COLORS = {
    "grid": "#e6e6e6",
    "heatmap_bg": "#f7f7f7",
}

PBETTER_FOCUS_CMAP = LinearSegmentedColormap.from_list(
    "pbetter_focus",
    [
        (0.0, "#ffffff"),
        (0.5, "#ffffff"),
        (1.0, "#1a9850"),
    ],
)

CANCER_COLORS = {
    "ccRCC": "#4C72B0",
    "Melanoma": "#DD8452",
    "NSCLC": "#55A868",
}


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
            "font.family": _FONT["family"],
            "font.sans-serif": _FONT["sans-serif"],
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "axes.titlesize": fontsize + 1,
            "axes.labelsize": fontsize,
            "xtick.labelsize": fontsize - 1,
            "ytick.labelsize": fontsize - 1,
            "legend.fontsize": fontsize - 1,
        }
    )


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
    nature_font: Dict[str, Sequence[str]] = field(default_factory=lambda: dict(_FONT))
    plot_colors: Dict[str, str] = field(default_factory=lambda: dict(STABILITY_PLOT_COLORS))
    pbetter_cmap: LinearSegmentedColormap = PBETTER_FOCUS_CMAP
    cancer_colors: Dict[str, str] = field(default_factory=lambda: dict(CANCER_COLORS))

    def __post_init__(self) -> None:
        if self.fontsize <= 0:
            raise ValueError("fontsize must be a positive integer.")


@dataclass
class BayesianComparison:
    """
    Compute Bayesian pairwise comparisons using the external baycomp package.

    Args:
        rope (float): ROPE threshold for practical equivalence.
        seed (int): Random seed for reproducibility in baycomp.
        style (BaycompStyle): Plot styling settings for consistent manuscript figures.

    Raises:
        ValueError: If rope is not positive.
    """
    rope: float = 0.01
    seed: int = 0
    style: BaycompStyle = field(default_factory=BaycompStyle)

    def __post_init__(self) -> None:
        if self.rope <= 0:
            raise ValueError("rope must be > 0.")

    @staticmethod
    def _validate_scores(scores: Sequence[float], method: str) -> np.ndarray:
        """
        Validate and coerce a score sequence to a finite numpy array.
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

                probs = baycomp.two_on_single(scores_np[m1], scores_np[m2], rope=self.rope)
                p_better = float(probs[0])
                p_equiv = float(probs[1])
                p_worse = float(probs[2])

                rows.append(
                    {
                        "Method 1": m1,
                        "Method 2": m2,
                        "Better Prob": p_better,
                        "Worse Prob": p_worse,
                        "Equivalent Prob": p_equiv,
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
        cancer_to_method_scores: Dict[str, Dict[str, Sequence[float]]],
        cancers_order: Sequence[str] = ("ccRCC", "Melanoma", "NSCLC"),
        methods_order: Optional[Sequence[str]] = None,
        value_col: str = "Better Prob",
        figsize: Tuple[int, int] = (18, 5.5),
        annot: bool = True,
        fmt: str = ".2f",
        show: bool = True,
    ) -> Tuple[plt.Figure, np.ndarray, Dict[str, pd.DataFrame], Dict[str, pd.DataFrame]]:
        """
        Plot a 1xN grid of Bayesian comparison probability heatmaps (one per cancer cohort).

        Args:
            cancer_to_method_scores (Dict[str, Dict[str, Sequence[float]]]): cancer -> {method -> scores across seeds/folds}.
            cancers_order (Sequence[str]): Order of cohorts in the grid.
            methods_order (Optional[Sequence[str]]): Global method ordering. If None, uses union over cancers.
            value_col (str): One of ["Better Prob", "Worse Prob", "Equivalent Prob"] to visualize.
            figsize (Tuple[int, int]): Figure size in inches.
            annot (bool): If True, annotate each cell with numeric values.
            fmt (str): Annotation format passed to seaborn.
            show (bool): If True, calls plt.show().

        Returns:
            Tuple[plt.Figure, np.ndarray, Dict[str, pd.DataFrame], Dict[str, pd.DataFrame]]:
                fig, axes, matrices_by_cancer, comparisons_by_cancer

        Raises:
            ValueError: If value_col is invalid.
            ValueError: If cancers_order contains a cohort not present in cancer_to_method_scores.
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
            methods = union_methods
        else:
            methods = list(methods_order)

        _set_nature_rcparams(fontsize=self.style.fontsize)
        sns.set(style="white", rc={"axes.facecolor": self.style.plot_colors["heatmap_bg"]})

        fig, axes = plt.subplots(1, len(cancers), figsize=figsize)
        if len(cancers) == 1:
            axes = np.array([axes])

        norm = TwoSlopeNorm(vmin=0.0, vcenter=0.5, vmax=1.0)

        mats_by_cancer: Dict[str, pd.DataFrame] = {}
        comps_by_cancer: Dict[str, pd.DataFrame] = {}

        for ax, cancer in zip(axes, cancers):
            comp_df = self.compare_methods(
                method_to_scores=cancer_to_method_scores[cancer],
                methods_order=methods,
            )
            comps_by_cancer[cancer] = comp_df

            mat = self.comparison_to_matrix(
                comparison_df=comp_df,
                methods_order=methods,
                value_col=value_col,
                nan_diagonal=True,
            )
            mats_by_cancer[cancer] = mat

            if value_col == "Better Prob":
                cmap = self.style.pbetter_cmap.copy()
                used_norm = norm
            else:
                cmap = plt.cm.viridis.copy()
                used_norm = None
            cmap.set_bad(color="#D3D3D3")

            sns.heatmap(
                mat,
                ax=ax,
                cmap=cmap,
                norm=used_norm,
                annot=annot,
                fmt=fmt,
                linewidths=0.5,
                linecolor="lightgray",
                cbar=(ax is axes[-1]),
                cbar_kws={"label": value_col} if (ax is axes[-1]) else None,
                square=True,
            )

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

            ax.tick_params(axis="x", rotation=45)
            ax.tick_params(axis="y", rotation=0)

        plt.tight_layout()
        if show:
            plt.show()

        return fig, axes, mats_by_cancer, comps_by_cancer
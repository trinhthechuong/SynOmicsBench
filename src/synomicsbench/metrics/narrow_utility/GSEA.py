from __future__ import annotations

import os
from typing import Dict, Mapping, Tuple, Union

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from synomicsbench.metrics.fidelity.visualization import DATASET_COLORS
from synomicsbench.metrics.narrow_utility.concordance import (
    ConcordanceAnalyzer,
    ConcordanceResult,
)


DATA_COLORS = {
    "real": "#4c72b0",
    "synthetic": "#dd8452",
}


class PCSAnalyzer(ConcordanceAnalyzer):
    """
    Pathway-level concordance (PCS) between original and synthetic GSEA results.

    Reports recall, precision and F1-score of the enriched pathways (F1-PCS), and the
    effect-size calibration of the pathways enriched in the original: Theil-Sen slope of
    the NES (robust with the few significant pathways), Pearson correlation and sign
    concordance.

    Args:
        term_col (str): Pathway term column name.
        nes_col (str): Normalized enrichment score column name.
        sig_col (str): Significance column; FDR q-value or nominal P-value, as the user decides.
        seed (int): Seed of the tiny jitter added to the rank scores.
        sig_thr (float): Significance threshold applied to ``sig_col``.

    Raises:
        ValueError: If sig_thr is not in (0, 1].
    """

    slope_method = "theil-sen"

    def __init__(
        self,
        term_col: str = "Term",
        nes_col: str = "NES",
        sig_col: str = "FDR q-val",
        seed: int = 42,
        sig_thr: float = 0.05,
    ) -> None:
        super().__init__(term_col=term_col, nes_col=nes_col, sig_col=sig_col, seed=seed, sig_thr=sig_thr)

    def gsea_rank_score(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Compute pathway rank score = sign(NES) * -log10(significance) with tiny jitter.

        Args:
            df (pd.DataFrame): GSEA results table.

        Returns:
            pd.DataFrame: Ranked table indexed by term_col with columns rank_score and qval.

        Raises:
            KeyError: If required columns are missing.
        """
        return self.rank_score(df)

    def pathway_concordance_score(self, df_rank: pd.DataFrame) -> ConcordanceResult:
        """
        Compute recall, precision and F1-score of the enriched pathways.

        Args:
            df_rank (pd.DataFrame): Aligned rank table with rank_ori, rank_syn, q_ori, qval.

        Returns:
            ConcordanceResult: Scores and counts.
        """
        return self.concordance_score(df_rank)

    def process_single_gsea_result(
        self,
        gsea_ori: Union[str, "os.PathLike[str]", pd.DataFrame],
        gsea_syn: Union[str, "os.PathLike[str]", pd.DataFrame],
    ) -> Tuple[np.ndarray, np.ndarray, ConcordanceResult]:
        """
        Process original and synthetic GSEA results (paths or DataFrames).

        Args:
            gsea_ori (str | PathLike | pd.DataFrame): Original GSEA table.
            gsea_syn (str | PathLike | pd.DataFrame): Synthetic GSEA table.

        Returns:
            tuple[np.ndarray, np.ndarray, ConcordanceResult]: (x, y, result).
        """
        return self.process_single_result(gsea_ori, gsea_syn)

    def plot_single_gsea_panel(
        self,
        ax: plt.Axes,
        x: np.ndarray,
        y: np.ndarray,
        result: ConcordanceResult,
        tool_name: str,
        show_xlabel: bool = False,
    ) -> None:
        """
        Plot one pathway-level concordance panel in the rank-score plane.

        Args:
            ax (matplotlib.axes.Axes): Matplotlib axis.
            x (np.ndarray): Original rank scores.
            y (np.ndarray): Synthetic rank scores.
            result (ConcordanceResult): Concordance result.
            tool_name (str): Tool name for title.
            show_xlabel (bool): Whether to show x-axis label/ticks.

        Returns:
            None
        """
        s_thr = -np.log10(self.sig_thr)
        lo, hi = -3, 3

        zone1 = (x >= -s_thr) & (x <= 0) & (y >= -s_thr) & (y <= 0)
        zone2 = (x >= 0) & (x <= s_thr) & (y >= 0) & (y <= s_thr)
        zone3 = (x <= -s_thr) & (y <= -s_thr)
        zone4 = (x >= s_thr) & (y >= s_thr)
        other = ~(zone1 | zone2 | zone3 | zone4)

        ax.add_patch(plt.Rectangle((-s_thr, -s_thr), s_thr, s_thr, color="#d0d0f4", alpha=0.4))
        ax.add_patch(plt.Rectangle((0, 0), s_thr, s_thr, color="#d0f4d0", alpha=0.4))
        ax.add_patch(plt.Rectangle((lo, lo), -s_thr - lo, -s_thr - lo, color="#89a5e6", alpha=0.2))
        ax.add_patch(plt.Rectangle((s_thr, s_thr), hi - s_thr, hi - s_thr, color="#66e699", alpha=0.2))

        ax.scatter(x[other], y[other], c="gray", alpha=0.3, s=20)
        ax.scatter(x[zone1], y[zone1], c="#38499b", s=60, edgecolor="k")
        ax.scatter(x[zone2], y[zone2], c="#239933", s=60, edgecolor="k")
        ax.scatter(x[zone3], y[zone3], c="#222e5c", s=70, edgecolor="k")
        ax.scatter(x[zone4], y[zone4], c="#13753a", s=70, edgecolor="k")

        ax.plot([lo, hi], [lo, hi], "--", c="black", lw=1)
        for v in [-s_thr, 0, s_thr]:
            ax.axhline(v, ls=":", c="black", lw=1 if v != 0 else 0.5)
            ax.axvline(v, ls=":", c="black", lw=1 if v != 0 else 0.5)

        ax.set_xlim(lo, hi)
        ax.set_ylim(lo, hi)

        if show_xlabel:
            ax.set_xlabel("Rank score (Original)")
        else:
            ax.set_xlabel("")
            ax.tick_params(axis="x", labelbottom=False)

        ax.set_ylabel("Rank score\n(Synthetic)")

        title_color = DATASET_COLORS.get(tool_name, "black")
        ax.set_title(
            f"{tool_name}\nF1-PCS={result.f1:.3f}",
            fontsize=12,
            color=title_color,
            fontweight="bold",
        )

        ax.text(
            -2.9,
            2.8,
            f"NonSig LL: {result.n_zone1}\n"
            f"NonSig UR: {result.n_zone2}\n"
            f"Sig LL: {result.n_zone3}\n"
            f"Sig UR: {result.n_zone4}\n"
            f"Recall={result.recall:.3f}\n"
            f"Precision={result.precision:.3f}",
            fontsize=10,
            va="top",
            bbox=dict(fc="white", alpha=0.7, ec="none"),
        )

        ax.grid(True)

    def plot_gsea_datasets(
        self,
        ori_data: Union[str, "os.PathLike[str]", pd.DataFrame],
        dataset_dict: Mapping[str, Union[str, "os.PathLike[str]", pd.DataFrame]],
        figsize: Tuple[float, float] = (9, 10),
    ) -> Tuple[plt.Figure, Dict[str, float]]:
        """
        Plot multiple synthetic datasets against one original GSEA file.

        Args:
            ori_data (str | PathLike | pd.DataFrame): Original GSEA data or path.
            dataset_dict (Mapping[str, str | PathLike | pd.DataFrame]): Tool name -> synthetic data or path.
            figsize (tuple[float, float]): Figure size.

        Returns:
            tuple[matplotlib.figure.Figure, dict[str, float]]: (fig, F1-PCS per dataset).
        """
        df_ori = self._load_df(ori_data)

        fig, axes = plt.subplots(3, 2, figsize=figsize, constrained_layout=True)
        axes = axes.flatten()

        f1_dict: Dict[str, float] = {}

        for idx, (tool, data) in enumerate(dataset_dict.items()):
            try:
                x, y, result = self.process_single_gsea_result(df_ori, data)

                row = idx // 2
                is_bottom = row == 2

                self.plot_single_gsea_panel(
                    axes[idx],
                    x,
                    y,
                    result,
                    tool,
                    show_xlabel=is_bottom,
                )

                f1_dict[tool] = result.f1
            except Exception as e:
                print(f"Skipping {tool}: {e}")

        for j in range(len(dataset_dict), len(axes)):
            fig.delaxes(axes[j])

        plt.tight_layout()
        plt.show()

        return fig, f1_dict

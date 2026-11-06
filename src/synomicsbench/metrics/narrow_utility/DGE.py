from __future__ import annotations

import os
from typing import Dict, Mapping, Tuple, Union

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from synomicsbench.metrics.narrow_utility.concordance import (
    ConcordanceAnalyzer,
    ConcordanceResult,
)


DATA_COLORS = {
    "real": "#4c72b0",
    "synthetic": "#dd8452",
}

GCS_ZONE_COLORS = {
    "zone1": "#38499b",  # NonSig LL
    "zone2": "#239933",  # NonSig UR
    "zone3": "#222e5c",  # Sig LL
    "zone4": "#13753a",  # Sig UR
    "other": "gray",
}

GCS_ZONE_BG_COLORS = {
    "zone1": "#d0d0f4",
    "zone2": "#d0f4d0",
    "zone3": "#89a5e6",
    "zone4": "#66e699",
}


class GCSAnalyzer(ConcordanceAnalyzer):
    """
    Gene-level concordance (GCS) between original and synthetic DGE results.

    Reports recall, precision and F1-score of the differentially expressed genes
    (F1-GCS), and the effect-size calibration of the original DEGs: OLS slope of the
    Log2FC, Pearson correlation and sign concordance.

    Args:
        term_col (str): Gene name column.
        nes_col (str): Effect-size column (e.g., Log2FC).
        sig_col (str): Significance column; P-value or Q-value, as the user decides.
        seed (int): Seed of the tiny jitter added to the rank scores.
        sig_thr (float): Significance threshold applied to ``sig_col``.

    Raises:
        ValueError: If sig_thr is not in (0, 1].
    """

    def __init__(
        self,
        term_col: str = "Gene",
        nes_col: str = "Log2FC",
        sig_col: str = "P_value",
        seed: int = 42,
        sig_thr: float = 0.05,
    ) -> None:
        super().__init__(term_col=term_col, nes_col=nes_col, sig_col=sig_col, seed=seed, sig_thr=sig_thr)

    def compute_rank_score(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Compute rank score = sign(Log2FC) * -log10(significance) with tiny jitter.

        Args:
            df (pd.DataFrame): DGE results table.

        Returns:
            pd.DataFrame: Ranked table indexed by term_col with columns rank_score and qval.
        """
        return self.rank_score(df)

    def gene_set_concordance_score(self, df_rank: pd.DataFrame) -> ConcordanceResult:
        """
        Compute recall, precision and F1-score of the differentially expressed genes.

        Args:
            df_rank (pd.DataFrame): Aligned rank table with rank_ori, rank_syn, q_ori, qval.

        Returns:
            ConcordanceResult: Scores and counts.
        """
        return self.concordance_score(df_rank)

    def process_single_dge_result(
        self,
        dge_ori: Union[str, "os.PathLike[str]", pd.DataFrame],
        dge_syn: Union[str, "os.PathLike[str]", pd.DataFrame],
    ) -> Tuple[np.ndarray, np.ndarray, ConcordanceResult]:
        """
        Process original and synthetic DGE results (paths or DataFrames).

        Args:
            dge_ori (str | PathLike | pd.DataFrame): Original DGE table/path.
            dge_syn (str | PathLike | pd.DataFrame): Synthetic DGE table/path.

        Returns:
            tuple[np.ndarray, np.ndarray, ConcordanceResult]: (x, y, result).
        """
        return self.process_single_result(dge_ori, dge_syn)

    def plot_single_gcs_panel(
        self,
        ax: plt.Axes,
        x: np.ndarray,
        y: np.ndarray,
        result: ConcordanceResult,
        tool_name: str,
    ) -> None:
        """
        Plot one gene-level concordance panel in the rank-score plane.

        Args:
            ax (matplotlib.axes.Axes): Target axis.
            x (np.ndarray): Rank scores (original).
            y (np.ndarray): Rank scores (synthetic).
            result (ConcordanceResult): Concordance result.
            tool_name (str): Tool/dataset name for title.

        Returns:
            None
        """
        s_thr = -np.log10(self.sig_thr)
        lo, hi = -2, 2

        zone1 = (x >= -s_thr) & (x <= 0) & (y >= -s_thr) & (y <= 0)
        zone2 = (x >= 0) & (x <= s_thr) & (y >= 0) & (y <= s_thr)
        zone3 = (x <= -s_thr) & (y <= -s_thr)
        zone4 = (x >= s_thr) & (y >= s_thr)
        other = ~(zone1 | zone2 | zone3 | zone4)

        ax.add_patch(
            plt.Rectangle((-s_thr, -s_thr), s_thr, s_thr, color=GCS_ZONE_BG_COLORS["zone1"], alpha=0.4)
        )
        ax.add_patch(
            plt.Rectangle((0, 0), s_thr, s_thr, color=GCS_ZONE_BG_COLORS["zone2"], alpha=0.4)
        )
        ax.add_patch(
            plt.Rectangle((lo, lo), -s_thr - lo, -s_thr - lo, color=GCS_ZONE_BG_COLORS["zone3"], alpha=0.2)
        )
        ax.add_patch(
            plt.Rectangle((s_thr, s_thr), hi - s_thr, hi - s_thr, color=GCS_ZONE_BG_COLORS["zone4"], alpha=0.2)
        )

        ax.scatter(x[other], y[other], c=GCS_ZONE_COLORS["other"], alpha=0.3, s=20)
        ax.scatter(x[zone1], y[zone1], c=GCS_ZONE_COLORS["zone1"], s=60, edgecolor="k")
        ax.scatter(x[zone2], y[zone2], c=GCS_ZONE_COLORS["zone2"], s=60, edgecolor="k")
        ax.scatter(x[zone3], y[zone3], c=GCS_ZONE_COLORS["zone3"], s=70, edgecolor="k")
        ax.scatter(x[zone4], y[zone4], c=GCS_ZONE_COLORS["zone4"], s=70, edgecolor="k")

        ax.plot([lo, hi], [lo, hi], "--", c="black", lw=1)
        for v in [-s_thr, 0, s_thr]:
            ax.axhline(v, ls=":", c="black", lw=1 if v != 0 else 0.5)
            ax.axvline(v, ls=":", c="black", lw=1 if v != 0 else 0.5)

        ax.set_xlim(lo, hi)
        ax.set_ylim(lo, hi)
        ax.set_xlabel("Rank score (Original)")
        ax.set_ylabel("Rank score (Synthetic)")
        ax.set_title(f"{tool_name}\nF1-GCS={result.f1:.3f}")

        ax.text(
            -1.9,
            1.8,
            "Zones\n"
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

    def plot_gcs_datasets(
        self,
        ori_data: Union[str, "os.PathLike[str]", pd.DataFrame],
        dataset_dict: Mapping[str, Union[str, "os.PathLike[str]", pd.DataFrame]],
        figsize: Tuple[int, int] = (18, 10),
    ) -> Tuple[plt.Figure, Dict[str, float]]:
        """
        Plot all datasets in a grid.

        Args:
            ori_data (str | PathLike | pd.DataFrame): Path to original CSV or DataFrame.
            dataset_dict (Mapping[str, str | PathLike | pd.DataFrame]): Tool name -> path or DataFrame.
            figsize (tuple[int, int]): Figure size.

        Returns:
            tuple[matplotlib.figure.Figure, dict[str, float]]: (figure, F1-GCS per dataset).
        """
        df_ori = self._load_df(ori_data)

        fig, axes = plt.subplots(2, 3, figsize=figsize)
        axes = axes.flatten()

        f1_dict: Dict[str, float] = {}

        for idx, (tool, data) in enumerate(dataset_dict.items()):
            try:
                x, y, result = self.process_single_dge_result(df_ori, data)
                self.plot_single_gcs_panel(axes[idx], x, y, result, tool)
                f1_dict[tool] = result.f1

            except Exception as e:
                print(f"Skipping {tool}: {e}")

        for j in range(len(dataset_dict), len(axes)):
            fig.delaxes(axes[j])

        plt.tight_layout()
        plt.show()

        return fig, f1_dict

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, Mapping, Tuple, Union

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


DATA_COLORS = {
    "real": "#4c72b0",
    "synthetic": "#dd8452",
}

DATASET_COLORS = {
    "Origin": "#4d4d4d",
    "Avatars K5": "#66c2a5",
    "Avatars K10": "#fc8d62",
    "CTGAN": "#8da0cb",
    "Gaussian Copula": "#e78ac3",
    "Synthpop": "#a6d854",
    "TVAE": "#ffd92f",
}


@dataclass(frozen=True)
class PCSResult:
    """
    Container for PCS computation outputs.

    Args:
        pcs (float): Pathway Concordance Score.
        n_sign (int): Number of concordant significant pathways (zones 3 + 4).
        n_non_sign (int): Number of concordant non-significant pathways (zones 1 + 2).
        m (float): Normalization constant M used in the PCS formula.
        n_zone1 (int): Count in non-significant lower-left zone.
        n_zone2 (int): Count in non-significant upper-right zone.
        n_zone3 (int): Count in significant lower-left zone.
        n_zone4 (int): Count in significant upper-right zone.
        aligned_size (int): Number of pathways after alignment (inner join).
    """
    pcs: float
    n_sign: int
    n_non_sign: int
    m: float
    n_zone1: int
    n_zone2: int
    n_zone3: int
    n_zone4: int
    aligned_size: int


class PCSAnalyzer:
    """
    Compute PCS from GSEA pathway enrichment tables and generate manuscript-style panels.

    This class preserves the original logic provided in `gsea_pathway_analysis.py`,
    including jitter behavior and normalization by aligned pathways (len(x)).

    Args:
        term_col (str): Pathway term column name.
        nes_col (str): Normalized enrichment score column name.
        q_col (str): FDR q-value column name.
        seed (int): Seed passed to np.random.seed for jitter reproducibility.
        q_thr (float): Q-value threshold for significance zones.
        w (float): Weight for non-significant concordance.

    Raises:
        ValueError: If q_thr is not in (0, 1].
        ValueError: If w is negative.
    """

    def __init__(
        self,
        term_col: str = "Term",
        nes_col: str = "NES",
        q_col: str = "FDR q-val",
        seed: int = 42,
        q_thr: float = 0.05,
        w: float = 0.5,
    ) -> None:
        if not (0.0 < q_thr <= 1.0):
            raise ValueError("q_thr must be in (0, 1].")
        if w < 0:
            raise ValueError("w must be >= 0.")

        self.term_col = term_col
        self.nes_col = nes_col
        self.q_col = q_col
        self.seed = seed
        self.q_thr = q_thr
        self.w = w

    @staticmethod
    def _load_df(data: Union[str, "os.PathLike[str]", pd.DataFrame]) -> pd.DataFrame:
        """Helper to load a CSV if a path is provided, otherwise return the DataFrame."""
        if isinstance(data, pd.DataFrame):
            return data
        return pd.read_csv(data)

    def gsea_rank_score(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Compute pathway rank score = sign(NES) * -log10(FDR-q) with tiny jitter.

        Args:
            df (pd.DataFrame): GSEA results table.

        Returns:
            pd.DataFrame: Ranked table indexed by term_col with columns rank_score and qval.

        Raises:
            KeyError: If required columns are missing.
        """
        np.random.seed(self.seed)

        q = pd.to_numeric(df[self.q_col], errors="coerce").clip(lower=0.001)
        nes = pd.to_numeric(df[self.nes_col], errors="coerce")

        rank_score = np.sign(nes) * (-np.log10(q))

        jitter = np.random.uniform(-1e-10, 1e-10, size=len(rank_score))
        rank_score += jitter

        rnk = (
            df[[self.term_col]]
            .assign(rank_score=rank_score, qval=q)
            .dropna()
            .groupby(self.term_col)
            .mean()
            .sort_values("rank_score", ascending=False)
        )
        return rnk

    @staticmethod
    def align_rank_scores(rnk_ori: pd.DataFrame, rnk_syn: pd.DataFrame) -> pd.DataFrame:
        """
        Inner join on pathway names.

        Args:
            rnk_ori (pd.DataFrame): Original rank table.
            rnk_syn (pd.DataFrame): Synthetic rank table.

        Returns:
            pd.DataFrame: Aligned rank table.
        """
        aligned = (
            rnk_ori.rename(columns={"rank_score": "rank_ori", "qval": "q_ori"}).join(
                rnk_syn.rename(columns={"rank_score": "rank_syn"}),
                how="inner",
            )
        )
        return aligned

    def pathway_concordance_score(self, df_rank: pd.DataFrame) -> Tuple[float, int, int, float]:
        """
        Compute PCS for aligned rank scores.

        Args:
            df_rank (pd.DataFrame): Aligned rank table with rank_ori, rank_syn, q_ori.

        Returns:
            tuple[float, int, int, float]: (PCS, N_sign, N_non_sign, M).
        """
        x = np.asarray(df_rank["rank_ori"].values)
        y = np.asarray(df_rank["rank_syn"].values)

        sign_threshold = -np.log10(self.q_thr)

        zone1_mask = (x >= -sign_threshold) & (x <= 0) & (y >= -sign_threshold) & (y <= 0)
        zone2_mask = (x >= 0) & (x <= sign_threshold) & (y >= 0) & (y <= sign_threshold)

        zone3_mask = (x <= -sign_threshold) & (y <= -sign_threshold)
        zone4_mask = (x >= sign_threshold) & (y >= sign_threshold)

        n_sign = int(np.sum(zone3_mask) + np.sum(zone4_mask))
        n_non_sign = int(np.sum(zone1_mask) + np.sum(zone2_mask))

        num_sign = int(np.sum(df_rank["q_ori"] < self.q_thr))
        num_non_sign = int(len(x) - num_sign)

        m = float(num_sign + self.w * num_non_sign)
        pcs = float((n_sign + self.w * n_non_sign) / m) if m > 0 else np.nan

        return pcs, n_sign, n_non_sign, m

    def process_single_gsea_result(
        self,
        gsea_ori: Union[str, "os.PathLike[str]", pd.DataFrame],
        gsea_syn: Union[str, "os.PathLike[str]", pd.DataFrame],
    ) -> Tuple[np.ndarray, np.ndarray, PCSResult]:
        """
        Process original and synthetic GSEA results (paths or DataFrames).

        Args:
            gsea_ori (str | PathLike | pd.DataFrame): Original GSEA table.
            gsea_syn (str | PathLike | pd.DataFrame): Synthetic GSEA table.

        Returns:
            tuple[np.ndarray, np.ndarray, PCSResult]: (x, y, result).
        """
        df_ori = self._load_df(gsea_ori)
        df_syn = self._load_df(gsea_syn)

        rnk_ori = self.gsea_rank_score(df_ori)
        rnk_syn = self.gsea_rank_score(df_syn)

        aligned = self.align_rank_scores(rnk_ori, rnk_syn)

        x = aligned["rank_ori"].values
        y = aligned["rank_syn"].values

        s_thr = -np.log10(self.q_thr)

        n_zone1 = int(((x >= -s_thr) & (x <= 0) & (y >= -s_thr) & (y <= 0)).sum())
        n_zone2 = int(((x >= 0) & (x <= s_thr) & (y >= 0) & (y <= s_thr)).sum())
        n_zone3 = int(((x <= -s_thr) & (y <= -s_thr)).sum())
        n_zone4 = int(((x >= s_thr) & (y >= s_thr)).sum())

        pcs, n_sign, n_non_sign, m = self.pathway_concordance_score(aligned)

        result = PCSResult(
            pcs=pcs,
            n_sign=n_sign,
            n_non_sign=n_non_sign,
            m=m,
            n_zone1=n_zone1,
            n_zone2=n_zone2,
            n_zone3=n_zone3,
            n_zone4=n_zone4,
            aligned_size=int(len(aligned)),
        )
        return x, y, result

    def plot_single_gsea_panel(
        self,
        ax: plt.Axes,
        x: np.ndarray,
        y: np.ndarray,
        result: PCSResult,
        tool_name: str,
        show_xlabel: bool = False,
    ) -> None:
        """
        Plot one PCS scatter panel (same geometry/logic as original script).

        Args:
            ax (matplotlib.axes.Axes): Matplotlib axis.
            x (np.ndarray): Original rank scores.
            y (np.ndarray): Synthetic rank scores.
            result (PCSResult): PCS result container.
            tool_name (str): Tool name for title.
            show_xlabel (bool): Whether to show x-axis label/ticks.

        Returns:
            None
        """
        s_thr = -np.log10(self.q_thr)
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
            f"{tool_name}\nPCS={result.pcs:.3f} (w={self.w})",
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
            f"Sig UR: {result.n_zone4}\n",
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
            tuple[matplotlib.figure.Figure, dict[str, float]]: (fig, pcs_dict).
        """
        df_ori = self._load_df(ori_data)

        fig, axes = plt.subplots(3, 2, figsize=figsize, constrained_layout=True)
        axes = axes.flatten()

        pcs_dict: Dict[str, float] = {}

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

                pcs_dict[tool] = result.pcs
            except Exception as e:
                print(f"Skipping {tool}: {e}")

        for j in range(len(dataset_dict), len(axes)):
            fig.delaxes(axes[j])

        plt.tight_layout()
        plt.show()

        return fig, pcs_dict
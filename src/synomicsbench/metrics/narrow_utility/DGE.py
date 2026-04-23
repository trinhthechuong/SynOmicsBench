from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Mapping, Tuple, Union

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


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


@dataclass(frozen=True)
class GCSResult:
    """
    Container for GCS computation outputs.

    Args:
        gcs (float): Gene-set Concordance Score (same formula as PCS, renamed).
        n_sign (int): Number of concordant significant pathways (zones 3 + 4).
        n_non_sign (int): Number of concordant non-significant pathways (zones 1 + 2).
        m (float): Normalization constant M used in the GCS formula.
        n_zone1 (int): Count in non-significant lower-left zone.
        n_zone2 (int): Count in non-significant upper-right zone.
        n_zone3 (int): Count in significant lower-left zone.
        n_zone4 (int): Count in significant upper-right zone.
        ori_rank_size (int): Number of ranked pathways in the original ranking.
        aligned_size (int): Number of pathways after alignment (inner join).
    """
    gcs: float
    n_sign: int
    n_non_sign: int
    m: float
    n_zone1: int
    n_zone2: int
    n_zone3: int
    n_zone4: int
    ori_rank_size: int
    aligned_size: int


class GCSAnalyzer:
    """
    Refactor of the original GCS computation code into a class, preserving identical logic.

    Args:
        term_col (str): Column name for pathway / gene-set names.
        nes_col (str): Column name for effect size (e.g., Log2FC).
        q_col (str): Column name for Q-value.
        seed (int): Seed used for np.random.seed to generate jitter.
        q_thr (float): Q-value threshold used to define significance boundary.
        w (float): Weight for non-significant concordance in GCS.

    Raises:
        ValueError: If q_thr is not in (0, 1].
        ValueError: If w is negative.
    """

    def __init__(
        self,
        term_col: str = "Gene",
        nes_col: str = "Log2FC",
        q_col: str = "Q_value",
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

    def compute_rank_score(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Compute rank score = sign(Log2FC) * -log10(Q-value) with tiny jitter.

        Args:
            df (pd.DataFrame): DGE results table.

        Returns:
            pd.DataFrame: Ranked table indexed by term_col with columns rank_score and qval.
        """
        np.random.seed(self.seed)

        q = pd.to_numeric(df[self.q_col], errors="coerce").clip(lower=0.001)
        nes = pd.to_numeric(df[self.nes_col], errors="coerce")

        rank_score = np.sign(nes) * (-np.log10(q))

        jitter = np.random.uniform(-1e-10, 1e-10, size=len(rank_score))
        rank_score = rank_score + jitter

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
        Inner join on pathway / gene names.

        Args:
            rnk_ori (pd.DataFrame): Original rank table indexed by term.
            rnk_syn (pd.DataFrame): Synthetic rank table indexed by term.

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

    def gene_set_concordance_score(
        self,
        df_rank: pd.DataFrame,
        ori_rank_size: int,
    ) -> Tuple[float, int, int, float]:
        """
        Compute GCS using original pathway count to avoid bias due to pathway loss after alignment.

        Args:
            df_rank (pd.DataFrame): Aligned rank table with rank_ori, rank_syn, q_ori.
            ori_rank_size (int): Number of pathways in original ranking.

        Returns:
            tuple[float, int, int, float]: (GCS, N_sign, N_non_sign, M).
        """
        x = df_rank["rank_ori"].values
        y = df_rank["rank_syn"].values

        s_thr = -np.log10(self.q_thr)

        zone1 = (x >= -s_thr) & (x <= 0) & (y >= -s_thr) & (y <= 0)
        zone2 = (x >= 0) & (x <= s_thr) & (y >= 0) & (y <= s_thr)

        zone3 = (x <= -s_thr) & (y <= -s_thr)
        zone4 = (x >= s_thr) & (y >= s_thr)

        n_sign = int(zone3.sum() + zone4.sum())
        n_non_sign = int(zone1.sum() + zone2.sum())

        num_sign = int((df_rank["q_ori"] < self.q_thr).sum())
        num_non_sign = int(ori_rank_size - num_sign)

        m = float(num_sign + self.w * num_non_sign)
        gcs = float((n_sign + self.w * n_non_sign) / m) if m > 0 else np.nan

        return gcs, n_sign, n_non_sign, m

    def process_single_dge_result(
        self,
        dge_ori: Union[str, "os.PathLike[str]", pd.DataFrame],
        dge_syn: Union[str, "os.PathLike[str]", pd.DataFrame],
    ) -> Tuple[np.ndarray, np.ndarray, float, int, int, int, int, float, int, int, int]:
        """
        Process original and synthetic DGE results (paths or DataFrames).

        Args:
            dge_ori (str | PathLike | pd.DataFrame): Original DGE table/path.
            dge_syn (str | PathLike | pd.DataFrame): Synthetic DGE table/path.

        Returns:
            tuple: (x, y, GCS, n_zone1, n_zone2, n_zone3, n_zone4, M, ori_rank_size, aligned_size, seed_used).
        """
        df_ori = self._load_df(dge_ori)
        df_syn = self._load_df(dge_syn)

        rnk_ori = self.compute_rank_score(df_ori)
        rnk_syn = self.compute_rank_score(df_syn)

        ori_rank_size = int(len(rnk_ori))

        aligned = self.align_rank_scores(rnk_ori, rnk_syn)

        x = aligned["rank_ori"].values
        y = aligned["rank_syn"].values

        s_thr = -np.log10(self.q_thr)

        n_zone1 = int(((x >= -s_thr) & (x <= 0) & (y >= -s_thr) & (y <= 0)).sum())
        n_zone2 = int(((x >= 0) & (x <= s_thr) & (y >= 0) & (y <= s_thr)).sum())
        n_zone3 = int(((x <= -s_thr) & (y <= -s_thr)).sum())
        n_zone4 = int(((x >= s_thr) & (y >= s_thr)).sum())

        gcs, _, _, m = self.gene_set_concordance_score(
            aligned,
            ori_rank_size=ori_rank_size,
        )

        return (
            x,
            y,
            gcs,
            n_zone1,
            n_zone2,
            n_zone3,
            n_zone4,
            m,
            ori_rank_size,
            int(len(aligned)),
            int(self.seed),
        )

    def plot_single_gcs_panel(
        self,
        ax: plt.Axes,
        x: np.ndarray,
        y: np.ndarray,
        gcs: float,
        n_zone1: int,
        n_zone2: int,
        n_zone3: int,
        n_zone4: int,
        tool_name: str,
        m: float,
    ) -> None:
        """
        Plot single GCS comparison panel (identical logic and styling to original code).

        Args:
            ax (matplotlib.axes.Axes): Target axis.
            x (np.ndarray): Rank scores (original).
            y (np.ndarray): Rank scores (synthetic).
            gcs (float): GCS value.
            n_zone1 (int): Count in zone1.
            n_zone2 (int): Count in zone2.
            n_zone3 (int): Count in zone3.
            n_zone4 (int): Count in zone4.
            tool_name (str): Tool/dataset name for title.
            m (float): M normalization used in GCS.

        Returns:
            None
        """
        s_thr = -np.log10(self.q_thr)
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
        ax.set_title(f"{tool_name}\nGCS={gcs:.3f} (w={self.w})")

        ax.text(
            -1.9,
            1.8,
            "Zones\n"
            f"NonSig LL: {n_zone1}\n"
            f"NonSig UR: {n_zone2}\n"
            f"Sig LL: {n_zone3}\n"
            f"Sig UR: {n_zone4}\n"
            f"M={m}",
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
            tuple[matplotlib.figure.Figure, dict[str, float]]: (figure, gcs_dict).
        """
        df_ori = self._load_df(ori_data)

        fig, axes = plt.subplots(2, 3, figsize=figsize)
        axes = axes.flatten()

        gcs_dict: Dict[str, float] = {}

        for idx, (tool, data) in enumerate(dataset_dict.items()):
            try:
                (
                    x,
                    y,
                    gcs,
                    n1,
                    n2,
                    n3,
                    n4,
                    m,
                    _ori_rank_size,
                    _aligned_size,
                    _seed_used,
                ) = self.process_single_dge_result(df_ori, data)

                self.plot_single_gcs_panel(
                    axes[idx],
                    x,
                    y,
                    gcs,
                    n1,
                    n2,
                    n3,
                    n4,
                    tool,
                    m,
                )

                gcs_dict[tool] = gcs

            except Exception as e:
                print(f"Skipping {tool}: {e}")

        for j in range(len(dataset_dict), len(axes)):
            fig.delaxes(axes[j])

        plt.tight_layout()
        plt.show()

        return fig, gcs_dict
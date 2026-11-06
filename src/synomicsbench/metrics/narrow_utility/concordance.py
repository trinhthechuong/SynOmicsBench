from __future__ import annotations

import math
import os
from dataclasses import dataclass
from typing import Dict, List, Mapping, Optional, Sequence, Tuple, Union

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from scipy import stats

from synomicsbench.metrics.fidelity.visualization import DATASET_COLORS


TableLike = Union[str, "os.PathLike[str]", pd.DataFrame]

CONCORDANCE_METRICS: Tuple[str, ...] = (
    "Recall",
    "Precision",
    "F1",
    "Slope",
    "Pearson",
    "SignConcordance",
)

CALIBRATION_COLORS = {
    "fit": "#C44E52",
    "identity": "#555555",
    "opposite_sign": "#9a9a9a",
    "discordant_bg": "#f2f2f2",
    "context": "#cfcfcf",
    "default_point": "#4c72b0",
}

HIGHLIGHT_GROUP_COLORS = ["#0072B2", "#D55E00", "#009E73", "#CC79A7"]


def _axis_range(values: np.ndarray) -> Tuple[float, float]:
    """Range of the values, always including 0, padded by 8% and rounded out to 0.5."""
    values = values[np.isfinite(values)]
    if not values.size:
        return -1.0, 1.0
    lo, hi = min(0.0, float(values.min())), max(0.0, float(values.max()))
    pad = 0.08 * (hi - lo)
    return math.floor((lo - pad) * 2) / 2, math.ceil((hi + pad) * 2) / 2


@dataclass(frozen=True)
class ConcordanceResult:
    """
    Significance concordance between an original and a synthetic result table.

    A feature (gene or pathway) is significant when its significance value is below the
    threshold; it is concordant when it is significant in both tables with the same
    effect-size sign.

    Args:
        recall (float): n_sign / n_sig_ori (NaN when the original has no significant feature).
        precision (float): n_sign / n_sig_syn (NaN when the synthetic has no significant feature).
        f1 (float): Harmonic mean of precision and recall; 0 when no feature is concordant.
        n_sign (int): Number of concordant significant features (zones 3 + 4).
        n_sig_ori (int): Number of significant features in the original table.
        n_sig_syn (int): Number of significant features in the synthetic table.
        n_zone1 (int): Count in non-significant lower-left zone.
        n_zone2 (int): Count in non-significant upper-right zone.
        n_zone3 (int): Count in significant lower-left zone.
        n_zone4 (int): Count in significant upper-right zone.
        aligned_size (int): Number of features after alignment (inner join).
    """
    recall: float
    precision: float
    f1: float
    n_sign: int
    n_sig_ori: int
    n_sig_syn: int
    n_zone1: int
    n_zone2: int
    n_zone3: int
    n_zone4: int
    aligned_size: int


class ConcordanceAnalyzer:
    """
    Shared engine of GCSAnalyzer (DGE) and PCSAnalyzer (GSEA).

    Compares an original and a synthetic result table feature by feature on two levels:

    * significance concordance: recall, precision and F1-score of the significant
      features with the same effect-size sign;
    * effect-size calibration on the features significant in the original: slope and
      intercept of the synthetic on the original effect sizes (``slope_method``: OLS or
      Theil-Sen), Pearson correlation and sign concordance.

    Args:
        term_col (str): Feature name column (gene or pathway).
        nes_col (str): Effect-size column (e.g. Log2FC or NES).
        sig_col (str): Significance column (P-value or Q-value, as the user decides).
        seed (int): Seed of the tiny jitter added to the rank scores.
        sig_thr (float): Significance threshold applied to ``sig_col``.

    Raises:
        ValueError: If sig_thr is not in (0, 1].
    """

    min_calibration_size = 3
    slope_method = "ols"
    #: up to this many features per panel, the calibration plot marks each one (filled when
    #: also significant in the synthetic data); above it, small points
    max_marked_features = 100

    def __init__(
        self,
        term_col: str,
        nes_col: str,
        sig_col: str,
        seed: int = 42,
        sig_thr: float = 0.05,
    ) -> None:
        if not (0.0 < sig_thr <= 1.0):
            raise ValueError("sig_thr must be in (0, 1].")

        self.term_col = term_col
        self.nes_col = nes_col
        self.sig_col = sig_col
        self.seed = seed
        self.sig_thr = sig_thr

    # ------------------------------------------------------------------
    # Inputs
    # ------------------------------------------------------------------

    @staticmethod
    def _load_df(data: TableLike) -> pd.DataFrame:
        """Helper to load a CSV if a path is provided, otherwise return the DataFrame."""
        if isinstance(data, pd.DataFrame):
            return data
        return pd.read_csv(data)

    @staticmethod
    def _resolve_metrics(metrics: Union[str, Sequence[str], None]) -> Tuple[List[str], bool]:
        """
        Normalize the ``metrics`` argument.

        Returns:
            tuple[list[str], bool]: (metric names, whether a single name was given).

        Raises:
            ValueError: If a metric name is unknown.
        """
        if metrics is None:
            names, single = list(CONCORDANCE_METRICS), False
        elif isinstance(metrics, str):
            names, single = [metrics], True
        else:
            names, single = list(metrics), False

        unknown = [m for m in names if m not in CONCORDANCE_METRICS]
        if unknown:
            raise ValueError(
                f"Unknown metric(s) {unknown}. Valid metrics: {list(CONCORDANCE_METRICS)}."
            )
        return names, single

    # ------------------------------------------------------------------
    # Significance concordance
    # ------------------------------------------------------------------

    def rank_score(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Compute rank score = sign(effect) * -log10(significance) with tiny jitter.

        Significance values are clipped at 0.001 before the log transform.

        Args:
            df (pd.DataFrame): Result table.

        Returns:
            pd.DataFrame: Ranked table indexed by term_col with columns rank_score and qval.
        """
        q = pd.to_numeric(df[self.sig_col], errors="coerce").clip(lower=0.001)
        nes = pd.to_numeric(df[self.nes_col], errors="coerce")

        rank_score = np.sign(nes) * (-np.log10(q))

        jitter = np.random.RandomState(self.seed).uniform(-1e-10, 1e-10, size=len(rank_score))
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
        Inner join on feature names.

        The original significance column becomes ``q_ori``; ``qval`` holds the synthetic one.

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

    def zone_counts(self, x: np.ndarray, y: np.ndarray) -> Tuple[int, int, int, int]:
        """
        Count features in the four concordance zones of the rank-score plane.

        Zones 1-2 hold features non-significant in both tables with the same sign, zones
        3-4 features significant in both with the same sign.

        Args:
            x (np.ndarray): Original rank scores.
            y (np.ndarray): Synthetic rank scores.

        Returns:
            tuple[int, int, int, int]: (n_zone1, n_zone2, n_zone3, n_zone4).
        """
        s_thr = -np.log10(self.sig_thr)
        n_zone1 = int(((x >= -s_thr) & (x <= 0) & (y >= -s_thr) & (y <= 0)).sum())
        n_zone2 = int(((x >= 0) & (x <= s_thr) & (y >= 0) & (y <= s_thr)).sum())
        n_zone3 = int(((x <= -s_thr) & (y <= -s_thr)).sum())
        n_zone4 = int(((x >= s_thr) & (y >= s_thr)).sum())
        return n_zone1, n_zone2, n_zone3, n_zone4

    def concordance_score(self, df_rank: pd.DataFrame) -> ConcordanceResult:
        """
        Compute recall, precision and F1-score of the significant features.

        Args:
            df_rank (pd.DataFrame): Aligned rank table with rank_ori, rank_syn, q_ori, qval.

        Returns:
            ConcordanceResult: Scores and counts.
        """
        x = np.asarray(df_rank["rank_ori"].values)
        y = np.asarray(df_rank["rank_syn"].values)

        n_zone1, n_zone2, n_zone3, n_zone4 = self.zone_counts(x, y)
        n_sign = n_zone3 + n_zone4

        n_sig_ori = int((df_rank["q_ori"] < self.sig_thr).sum())
        n_sig_syn = int((df_rank["qval"] < self.sig_thr).sum())

        recall = n_sign / n_sig_ori if n_sig_ori > 0 else np.nan
        precision = n_sign / n_sig_syn if n_sig_syn > 0 else np.nan

        if n_sig_ori == 0:
            f1 = np.nan
        elif n_sign == 0:
            f1 = 0.0
        else:
            f1 = 2 * precision * recall / (precision + recall)

        return ConcordanceResult(
            recall=float(recall),
            precision=float(precision),
            f1=float(f1),
            n_sign=n_sign,
            n_sig_ori=n_sig_ori,
            n_sig_syn=n_sig_syn,
            n_zone1=n_zone1,
            n_zone2=n_zone2,
            n_zone3=n_zone3,
            n_zone4=n_zone4,
            aligned_size=int(len(df_rank)),
        )

    def process_single_result(
        self,
        res_ori: TableLike,
        res_syn: TableLike,
    ) -> Tuple[np.ndarray, np.ndarray, ConcordanceResult]:
        """
        Process original and synthetic result tables (paths or DataFrames).

        Args:
            res_ori (str | PathLike | pd.DataFrame): Original result table.
            res_syn (str | PathLike | pd.DataFrame): Synthetic result table.

        Returns:
            tuple[np.ndarray, np.ndarray, ConcordanceResult]: (x, y, result).
        """
        rnk_ori = self.rank_score(self._load_df(res_ori))
        rnk_syn = self.rank_score(self._load_df(res_syn))
        aligned = self.align_rank_scores(rnk_ori, rnk_syn)

        x = aligned["rank_ori"].values
        y = aligned["rank_syn"].values
        return x, y, self.concordance_score(aligned)

    # ------------------------------------------------------------------
    # Effect-size calibration
    # ------------------------------------------------------------------

    def _effect_table(self, df: pd.DataFrame) -> pd.DataFrame:
        """Feature name, effect size and significance, one row per feature."""
        out = pd.DataFrame({
            self.term_col: df[self.term_col].astype(str).values,
            "effect": pd.to_numeric(df[self.nes_col], errors="coerce").values,
            "sig": pd.to_numeric(df[self.sig_col], errors="coerce").values,
        })
        if out[self.term_col].duplicated().any():
            out = out.groupby(self.term_col, as_index=False).mean()
        return out

    def merge_effects(self, res_ori: TableLike, res_syn: TableLike) -> pd.DataFrame:
        """
        Merge original and synthetic effect sizes feature by feature.

        Args:
            res_ori (str | PathLike | pd.DataFrame): Original result table.
            res_syn (str | PathLike | pd.DataFrame): Synthetic result table.

        Returns:
            pd.DataFrame: Columns term_col, effect_ori, sig_ori, effect_syn, sig_syn.
        """
        return self._effect_table(self._load_df(res_ori)).merge(
            self._effect_table(self._load_df(res_syn)),
            on=self.term_col,
            suffixes=("_ori", "_syn"),
        )

    def _calibration_points(self, merged: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
        """Finite effect sizes of the features significant in the original."""
        x, y, _ = self._calibration_points_sig(merged)
        return x, y

    def _calibration_points_sig(self, merged: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """As :meth:`_calibration_points`, with whether each feature is significant in the synthetic."""
        sig = merged[merged["sig_ori"] < self.sig_thr]
        x = sig["effect_ori"].to_numpy(float)
        y = sig["effect_syn"].to_numpy(float)
        ok = np.isfinite(x) & np.isfinite(y)
        syn_sig = (pd.to_numeric(sig["sig_syn"], errors="coerce") < self.sig_thr).to_numpy()
        return x[ok], y[ok], syn_sig[ok]

    def calibration_score(self, merged: pd.DataFrame) -> Dict[str, float]:
        """
        Effect-size calibration on the features significant in the original.

        Synthetic effect sizes are regressed on the original ones, by ordinary least
        squares or, with ``slope_method = "theil-sen"``, by the Theil-Sen estimator (the
        median of the pairwise slopes, resistant to outliers when there are few features).
        A slope of 1 means effect sizes are preserved, below 1 attenuated, above 1
        inflated. Sign concordance is the fraction of features with the same effect-size
        sign (chance level 0.5); features with a zero effect size have no sign and are
        left out of it.

        Args:
            merged (pd.DataFrame): Output of :meth:`merge_effects`.

        Returns:
            dict[str, float]: Slope, Intercept, Pearson, SignConcordance,
            SignConcordance_pvalue (two-sided binomial test against 0.5) and N.
        """
        x, y = self._calibration_points(merged)
        out: Dict[str, float] = {
            "Slope": np.nan,
            "Intercept": np.nan,
            "Pearson": np.nan,
            "N": int(len(x)),
        }
        if len(x) >= self.min_calibration_size:
            if self.slope_method == "theil-sen":
                # joint intercept, median(y - slope * x): with two clusters of features (effect
                # sizes below and above 0), median(y) - slope * median(x) can take its two medians
                # from different clusters
                slope, intercept = stats.theilslopes(y, x, method="joint")[:2]
            else:
                slope, intercept = stats.linregress(x, y)[:2]
            out.update({
                "Slope": float(slope),
                "Intercept": float(intercept),
                "Pearson": float(stats.pearsonr(x, y)[0]),
            })

        signed = (x != 0) & (y != 0)
        n = int(signed.sum())
        k = int((np.sign(x[signed]) == np.sign(y[signed])).sum())
        out["SignConcordance"] = k / n if n else np.nan
        out["SignConcordance_pvalue"] = float(stats.binomtest(k, n, 0.5).pvalue) if n else np.nan
        return out

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def compute_metrics(
        self,
        res_ori: TableLike,
        res_syn: TableLike,
        metrics: Union[str, Sequence[str], None] = None,
    ) -> Union[float, Dict[str, float]]:
        """
        Compute concordance and calibration metrics for one synthetic dataset.

        Args:
            res_ori (str | PathLike | pd.DataFrame): Original result table.
            res_syn (str | PathLike | pd.DataFrame): Synthetic result table.
            metrics (str | Sequence[str] | None): Metric name, list of names, or None for
                all of: Recall, Precision, F1, Slope, Pearson, SignConcordance.

        Returns:
            float | dict[str, float]: The value when one name is given as a string,
            otherwise a dict {metric: value}.

        Raises:
            ValueError: If a metric name is unknown.
        """
        names, single = self._resolve_metrics(metrics)
        df_ori = self._load_df(res_ori)
        df_syn = self._load_df(res_syn)

        values: Dict[str, float] = {}
        if {"Recall", "Precision", "F1"} & set(names):
            _, _, result = self.process_single_result(df_ori, df_syn)
            values.update({"Recall": result.recall, "Precision": result.precision, "F1": result.f1})
        if {"Slope", "Pearson", "SignConcordance"} & set(names):
            values.update(self.calibration_score(self.merge_effects(df_ori, df_syn)))

        if single:
            return values[names[0]]
        return {m: values[m] for m in names}

    def compute_metrics_datasets(
        self,
        ori_data: TableLike,
        dataset_dict: Mapping[str, TableLike],
        metrics: Union[str, Sequence[str], None] = None,
    ) -> pd.DataFrame:
        """
        Compute metrics for several synthetic datasets against one original result table.

        Args:
            ori_data (str | PathLike | pd.DataFrame): Original result table or path.
            dataset_dict (Mapping[str, str | PathLike | pd.DataFrame]): Dataset name -> table or path.
            metrics (str | Sequence[str] | None): As in :meth:`compute_metrics`.

        Returns:
            pd.DataFrame: One row per dataset (index "Dataset"), one column per metric.
        """
        names, _ = self._resolve_metrics(metrics)
        df_ori = self._load_df(ori_data)
        rows = {
            name: self.compute_metrics(df_ori, data, metrics=names)
            for name, data in dataset_dict.items()
        }
        out = pd.DataFrame.from_dict(rows, orient="index", columns=names)
        out.index.name = "Dataset"
        return out

    # ------------------------------------------------------------------
    # Calibration scatter
    # ------------------------------------------------------------------

    def plot_calibration_scatter(
        self,
        ori_data: TableLike,
        dataset_dict: Mapping[str, TableLike],
        highlight: Optional[Mapping[str, Sequence[str]]] = None,
        ncols: int = 3,
        figsize: Optional[Tuple[float, float]] = None,
    ) -> Tuple[plt.Figure, pd.DataFrame]:
        """
        Plot synthetic versus original effect sizes of the features significant in the original.

        One panel per dataset, on shared axes. Dashed line y = x, red line the fit of
        ``slope_method``, grey points features with the opposite sign, shaded the discordant
        quadrants. With at most ``max_marked_features`` features per panel (e.g. pathways),
        filled points are also significant in the synthetic data and open points are not, the
        features not significant in the original are drawn in light grey (not part of the fit),
        and both axes share the range of all the effect sizes.
        The inset gives the slope, Pearson R and sign concordance.

        Args:
            ori_data (str | PathLike | pd.DataFrame): Original result table or path.
            dataset_dict (Mapping[str, str | PathLike | pd.DataFrame]): Dataset name -> table or path.
            highlight (Mapping[str, Sequence[str]] | None): Optional groups of feature names
                drawn on top of each panel, e.g. {"MHC-I": [...], "MHC-II": [...]}.
            ncols (int): Number of panel columns.
            figsize (tuple[float, float] | None): Figure size; defaults to 3.5 x 3.7 per panel.

        Returns:
            tuple[matplotlib.figure.Figure, pd.DataFrame]: (figure, calibration metrics per dataset).
        """
        df_ori = self._load_df(ori_data)
        merged = {name: self.merge_effects(df_ori, data) for name, data in dataset_dict.items()}
        points = {name: self._calibration_points_sig(m) for name, m in merged.items()}

        # few features (pathways): large markers, filled when significant in the synthetic too,
        # with the features not significant in the original as context, on one range of all the
        # effect sizes for both axes; many features (genes): small markers on symmetric axes
        few = max((len(p[0]) for p in points.values()), default=0) <= self.max_marked_features
        if few:
            all_effects = np.concatenate([m[["effect_ori", "effect_syn"]].to_numpy(float).ravel()
                                          for m in merged.values()])
            xlim = ylim = _axis_range(all_effects)
        else:
            all_xy = np.concatenate([np.abs(np.concatenate(p[:2])) for p in points.values()])
            lim = float(np.nanpercentile(all_xy, 99.5)) * 1.08 if all_xy.size else 1.0
            lim = math.ceil(lim * 10) / 10
            xlim = ylim = (-lim, lim)

        n = len(dataset_dict)
        ncols = max(1, min(ncols, n))
        nrows = int(math.ceil(n / ncols))
        if figsize is None:
            figsize = (3.5 * ncols, 3.7 * nrows)
        fig, axes = plt.subplots(nrows, ncols, figsize=figsize, sharex=True, sharey=True, squeeze=False)
        flat = axes.ravel()

        rows = {}
        for ax, name in zip(flat, dataset_dict):
            x, y, syn_sig = points[name]
            res = self.calibration_score(merged[name])
            rows[name] = res
            same = np.sign(x) == np.sign(y)
            color = DATASET_COLORS.get(name, CALIBRATION_COLORS["default_point"])

            ax.fill_between([0, xlim[1]], ylim[0], 0, color=CALIBRATION_COLORS["discordant_bg"], zorder=0, lw=0)
            ax.fill_between([xlim[0], 0], 0, ylim[1], color=CALIBRATION_COLORS["discordant_bg"], zorder=0, lw=0)
            if few:
                rest = merged[name][merged[name]["sig_ori"] >= self.sig_thr]
                ax.scatter(rest["effect_ori"], rest["effect_syn"], s=16, c=CALIBRATION_COLORS["context"],
                           edgecolors="none", zorder=1)
                colors = np.where(same, color, CALIBRATION_COLORS["opposite_sign"])
                ax.scatter(x[syn_sig], y[syn_sig], s=48, c=colors[syn_sig], edgecolors="#444444",
                           linewidths=0.6, zorder=3)
                ax.scatter(x[~syn_sig], y[~syn_sig], s=48, facecolors="white", edgecolors=colors[~syn_sig],
                           linewidths=1.4, zorder=3)
            else:
                ax.scatter(x[same], y[same], s=6, c=color, alpha=0.55, edgecolors="none", zorder=2)
                ax.scatter(x[~same], y[~same], s=6, c=CALIBRATION_COLORS["opposite_sign"], alpha=0.45,
                           edgecolors="none", zorder=2)

            grid = np.array([min(xlim[0], ylim[0]), max(xlim[1], ylim[1])])
            ax.plot(grid, grid, ls="--", color=CALIBRATION_COLORS["identity"], lw=0.9, zorder=3)
            if np.isfinite(res["Slope"]):
                fx = np.array(xlim)
                ax.plot(fx, res["Slope"] * fx + res["Intercept"], color=CALIBRATION_COLORS["fit"],
                        lw=1.6, zorder=4)
            ax.axhline(0, color="black", lw=0.4, alpha=0.4)
            ax.axvline(0, color="black", lw=0.4, alpha=0.4)

            if highlight:
                m = merged[name]
                for idx, members in enumerate(highlight.values()):
                    mm = m[m[self.term_col].isin(members)]
                    ax.scatter(mm["effect_ori"], mm["effect_syn"], s=16,
                               c=HIGHLIGHT_GROUP_COLORS[idx % len(HIGHLIGHT_GROUP_COLORS)],
                               edgecolors="white", linewidths=0.4, zorder=5)

            txt = (f"slope {res['Slope']:.2f}\nR {res['Pearson']:.2f}\n"
                   f"sign conc. {res['SignConcordance']:.2f}")
            ax.text(0.03, 0.97, txt, transform=ax.transAxes, ha="left", va="top", fontsize=7.5,
                    bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="#cccccc", lw=0.5, alpha=0.9),
                    zorder=6)
            ax.set_title(name, fontsize=11, fontweight="bold", color=DATASET_COLORS.get(name, "black"))
            ax.set_xlim(*xlim)
            ax.set_ylim(*ylim)
            ax.set_box_aspect(1)
            ax.tick_params(labelsize=8)

        for ax in flat[n:]:
            ax.set_visible(False)
        for c in range(ncols):
            # the lowest visible panel of each column carries the x axis
            col_axes = [axes[r, c] for r in range(nrows) if r * ncols + c < n]
            if col_axes:
                col_axes[-1].set_xlabel(
                    f"{self.nes_col} original" if few
                    else f"{self.nes_col} original ({self.sig_col} < {self.sig_thr:g})", fontsize=9
                )
                col_axes[-1].xaxis.set_tick_params(labelbottom=True)
        for ax in axes[:, 0]:
            ax.set_ylabel(f"{self.nes_col} synthetic", fontsize=9)

        handles = [
            Line2D([], [], ls="--", color=CALIBRATION_COLORS["identity"], label="y = x"),
            Line2D([], [], color=CALIBRATION_COLORS["fit"], lw=1.6,
                   label="Theil-Sen fit" if self.slope_method == "theil-sen" else "OLS fit"),
            Line2D([], [], marker="o", ls="", color=CALIBRATION_COLORS["opposite_sign"],
                   label="opposite sign", ms=7 if few else 4),
        ]
        if few:
            handles[2:2] = [
                Line2D([], [], marker="o", ls="", mfc="#777777", mec="#444444", ms=7,
                       label=f"significant in synthetic ({self.sig_col} < {self.sig_thr:g})"),
                Line2D([], [], marker="o", ls="", mfc="white", mec="#777777", mew=1.4, ms=7,
                       label="not significant in synthetic"),
            ]
            handles.append(Line2D([], [], marker="o", ls="", color=CALIBRATION_COLORS["context"], ms=4.5,
                                  label="not significant in original"))
        if highlight:
            handles += [
                Line2D([], [], marker="o", ls="", ms=5, label=group,
                       color=HIGHLIGHT_GROUP_COLORS[idx % len(HIGHLIGHT_GROUP_COLORS)])
                for idx, group in enumerate(highlight)
            ]
        fig.legend(handles=handles, loc="lower center", ncol=3 if few else len(handles), fontsize=8,
                   frameon=False, bbox_to_anchor=(0.5, -0.06 if few else -0.035))
        fig.tight_layout(rect=(0, 0.02, 1, 1))

        table = pd.DataFrame.from_dict(rows, orient="index")
        table.index.name = "Dataset"
        return fig, table

import os
import math
import warnings
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.patches as mpatches
from joblib import Parallel, delayed
from scipy.stats import bootstrap

from lifelines import KaplanMeierFitter, CoxPHFitter
from lifelines.statistics import logrank_test
from lifelines.exceptions import ConvergenceWarning
from lifelines.utils import concordance_index

# =============================================================================
# Visualization color palettes (consistent for manuscript-level plots)
# =============================================================================
DATASET_COLORS = {
    "Origin": "#4d4d4d",
    "Avatars": "#66c2a5",
    "Avatars K5": "#66c2a5",
    "Avatars K10": "#fc8d62",
    "CTGAN": "#8da0cb",
    "Gaussian Copula": "#e78ac3",
    "Synthpop": "#a6d854",
    "TVAE": "#ffd92f",
    "Diffusion": "#e5c494",
    "TabDiff": "#e5c494",
}

GROUP_COLORS = {
    "GroupA": "#0072B2",  # Okabe-Ito blue
    "GroupB": "#D55E00",  # Okabe-Ito vermillion
}

class SurvivalEvaluator:
    """
    Perform survival analysis and visualization across multiple datasets
    comparing two phenotype groups.

    Args:
        datasets_dict (Dict[str, pd.DataFrame]): Mapping from dataset names to DataFrames.
        phenotype (Dict[str, List[Any]]): {column_name: [value_A, value_B]}, specifying the phenotype column and comparison values.
        time_target (str): Name of the survival time column.
        event_target (str): Name of the event indicator column.
        dataset_order (Optional[List[str]]): Custom plotting order for datasets. If None, use input order.
        dataset_colors (Optional[Dict[str, str]]): Colors for dataset annotation strips.
        group_colors (Optional[Dict[str, str]]): Colors for phenotype groups (A, B).
        font_scale (float): Global scaling for plot text sizes.

    Returns:
        None

    Raises:
        ValueError: If datasets_dict is empty or phenotype is not a {col: [A,B]} dict.
    """

    def __init__(
        self,
        datasets_dict: Dict[str, pd.DataFrame],
        phenotype: Dict[str, List[Any]],
        time_target: str = "OS",
        event_target: str = "OS_CNSR",
        dataset_order: Optional[List[str]] = None,
        dataset_colors: Optional[Dict[str, str]] = None,
        group_colors: Optional[Dict[str, str]] = None,
        font_scale: float = 1.0,
        is_pdf: bool = False,
        original_name: str = "Origin"
    ) -> None:
        """
        Initialize SurvivalGridEvaluator for grid-based survival comparison.

        Args:
            datasets_dict (Dict[str, pd.DataFrame]): Input datasets.
            phenotype (Dict[str, List[Any]]): {col: [value_A, value_B]}.
            time_target (str): Survival duration column.
            event_target (str): Event indicator column.
            dataset_order (List[str], optional): Custom dataset plotting order.
            dataset_colors (Dict[str, str], optional): Strip colors per dataset.
            group_colors (Dict[str, str], optional): Colors for phenotype groups.
            font_scale (float): Plot font scaling.
            is_pdf (boolean): save as pdf or png.
            original_name (str): Name of the reference dataset (default: "Origin").

        Returns:
            None

        Raises:
            ValueError: On empty datasets or invalid phenotype specification.
        """
        if not datasets_dict:
            raise ValueError("datasets_dict must not be empty.")
        if not isinstance(phenotype, dict) or len(phenotype) != 1:
            raise ValueError("phenotype must be a dict with one mapping {column_name: [valA, valB]}.")
        ph_column, ph_values = next(iter(phenotype.items()))
        if not isinstance(ph_values, (list, tuple)) or len(ph_values) != 2:
            raise ValueError("phenotype value must be a list/tuple of exactly two values: [value_A, value_B].")
        self.datasets_dict = datasets_dict
        self.phenotype_column = ph_column
        self.value_A, self.value_B = ph_values
        self.time_target = time_target
        self.event_target = event_target
        self.dataset_order = dataset_order
        self.dataset_colors = dataset_colors or DATASET_COLORS.copy()
        self.group_colors = group_colors or GROUP_COLORS.copy()
        self.font_scale = font_scale
        self.is_pdf = is_pdf
        self.original_name = original_name
        self.dataset_names = self._get_dataset_order()
        self.summary_df = None
        self.cox_df = None

    def _get_dataset_order(self) -> List[str]:
        """
        Determine the dataset order for visualization.

        Returns:
            List[str]: Dataset names in desired plotting order.

        Raises:
            ValueError: If dataset_order contains a missing dataset.
        """
        if self.dataset_order is None:
            order = list(self.datasets_dict.keys())
        else:
            missing = [d for d in self.dataset_order if d not in self.datasets_dict]
            if missing:
                raise ValueError(f"dataset_order contains datasets absent from datasets_dict: {missing}")
            order = self.dataset_order
        order = [d for d in [self.original_name] if d in order] + [d for d in order if d != self.original_name]
        return order

    def compute_survival_metrics(self) -> pd.DataFrame:
        """
        Compute log-rank test p-values and C-index for each dataset grid panel.

        Args:
            None

        Returns:
            pd.DataFrame: DataFrame with columns ['Dataset', 'pvalue', 'C-index', 'n_A', 'n_B'].
        """
        summary_rows = []
        for ds_name in self.dataset_names:
            df_raw = self.datasets_dict[ds_name].copy()
            df = df_raw.copy()
            df[self.event_target] = pd.to_numeric(df.get(self.event_target, 0), errors="coerce").fillna(0).astype(int)
            df[self.time_target] = pd.to_numeric(df.get(self.time_target, np.nan), errors="coerce")
            df_A = df[df[self.phenotype_column] == self.value_A]
            df_B = df[df[self.phenotype_column] == self.value_B]

            n_A, n_B = len(df_A), len(df_B)
            pvalue = np.nan
            try:
                if n_A > 0 and n_B > 0:
                    gA = df_A.dropna(subset=[self.time_target, self.event_target])
                    gB = df_B.dropna(subset=[self.time_target, self.event_target])
                    if len(gA) > 0 and len(gB) > 0:
                        res = logrank_test(
                            gA[self.time_target], gB[self.time_target],
                            event_observed_A=gA[self.event_target], event_observed_B=gB[self.event_target]
                        )
                        pvalue = float(res.p_value)
            except Exception:
                pvalue = np.nan

            cindex_text = "NA"
            try:
                df_cox = df[[self.time_target, self.event_target]].copy()
                df_cox["phenotype_binary"] = pd.NA
                df_cox.loc[df[self.phenotype_column] == self.value_A, "phenotype_binary"] = 1
                df_cox.loc[df[self.phenotype_column] == self.value_B, "phenotype_binary"] = 0
                df_cox_fit = df_cox.dropna(subset=[self.time_target, "phenotype_binary"])
                df_cox_fit[self.time_target] = pd.to_numeric(df_cox_fit[self.time_target], errors="coerce")
                df_cox_fit = df_cox_fit.dropna(subset=[self.time_target])
                df_cox_fit["phenotype_binary"] = df_cox_fit["phenotype_binary"].astype(int)
                if (
                    len(df_cox_fit) > 0
                    and df_cox_fit["phenotype_binary"].nunique() > 1
                    and df_cox_fit[self.event_target].sum() > 0
                ):
                    cph = CoxPHFitter()
                    cph.fit(df_cox_fit, duration_col=self.time_target, event_col=self.event_target, show_progress=False)
                    partial_h = cph.predict_partial_hazard(df_cox_fit)
                    cindex = concordance_index(df_cox_fit[self.time_target], -partial_h, df_cox_fit[self.event_target])
                    cindex_text = f"{cindex:.3f}"
                else:
                    cindex_text = "insufficient events"
            except Exception:
                cindex_text = "fit error"

            summary_rows.append(
                {
                    "Dataset": ds_name,
                    "pvalue": (np.nan if (pvalue is None or np.isnan(pvalue)) else float(pvalue)),
                    "C-index": cindex_text,
                    "n_A": int(n_A),
                    "n_B": int(n_B),
                }
            )
        summary_df = pd.DataFrame(summary_rows, columns=["Dataset", "pvalue", "C-index", "n_A", "n_B"])
        summary_df["Dataset"] = pd.Categorical(summary_df["Dataset"], categories=self.dataset_names, ordered=True)
        summary_df = summary_df.sort_values("Dataset").reset_index(drop=True)
        self.summary_df = summary_df
        return summary_df

    def compute_survival_scores(self, original_name: Optional[str] = None) -> pd.DataFrame:
        """
        Compute the survival score, 1 - |C_original - C_synthetic|, of every dataset.

        Args:
            original_name (Optional[str]): Reference dataset for score calculation. 
                If None, uses self.original_name.

        Returns:
            pd.DataFrame: DataFrame with the additional column 'Survival_score'.

        Raises:
            KeyError: If required columns or reference row are missing.
            RuntimeError: If compute_survival_metrics() was not called prior.
        """
        if self.summary_df is None:
            raise RuntimeError("Must call compute_survival_metrics() before scoring.")
        df = self.summary_df.copy()
        ref_name = original_name or self.original_name
        if "Dataset" not in df.columns:
            raise KeyError("'Dataset' column not found.")
        if ref_name not in df["Dataset"].values:
            raise KeyError(f"Reference dataset '{ref_name}' not found in summary dataframe.")
        parsed_cindex = []
        for val in df["C-index"]:
            try:
                f = float(str(val).split()[0])
                if not math.isfinite(f):
                    f = np.nan
            except Exception:
                f = np.nan
            parsed_cindex.append(f)
        df["_cindex_parsed"] = parsed_cindex
        c_orig = df.loc[df["Dataset"] == ref_name, "_cindex_parsed"].iloc[0]
        scores = []
        for c_syn in df["_cindex_parsed"]:
            if pd.isna(c_orig) or pd.isna(c_syn):
                score = np.nan
            else:
                diff = abs(c_orig - c_syn)
                score = 1.0 - diff
                score = max(0.0, min(1.0, score))
            scores.append(score)
        df["Survival_score"] = scores
        df = df.drop(columns=["_cindex_parsed"])
        return df

    def _cox_frame(self, ds_name: str) -> pd.DataFrame:
        """
        Survival frame of one dataset restricted to the two phenotype groups.

        Args:
            ds_name (str): Dataset name.

        Returns:
            pd.DataFrame: Columns T (time), E (event, int) and group (1 for value_A, 0 for value_B).
        """
        df = self.datasets_dict[ds_name]
        d = df[df[self.phenotype_column].isin([self.value_A, self.value_B])][
            [self.time_target, self.event_target, self.phenotype_column]
        ].copy()
        d[self.time_target] = pd.to_numeric(d[self.time_target], errors="coerce")
        d[self.event_target] = pd.to_numeric(d[self.event_target], errors="coerce").fillna(0).astype(int)
        d = d.dropna()
        d["group"] = (d[self.phenotype_column] == self.value_A).astype(int)
        d = d.rename(columns={self.time_target: "T", self.event_target: "E"})
        return d[["T", "E", "group"]].reset_index(drop=True)

    @staticmethod
    def _cox_cindex(d: pd.DataFrame) -> Tuple[float, Optional[CoxPHFitter]]:
        """
        Harrell's C-index of a univariate Cox model on the phenotype group.

        Args:
            d (pd.DataFrame): Output of :meth:`_cox_frame`.

        Returns:
            tuple[float, CoxPHFitter | None]: (C-index, fitted model); (NaN, None) when the
            model cannot be fitted (one group only or no event).
        """
        if d["group"].nunique() < 2 or d["E"].sum() == 0:
            return np.nan, None
        # Near-separation of the two groups (common on bootstrap resamples) only triggers
        # convergence warnings; the fitted coefficient is still used as is.
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", ConvergenceWarning)
            cph = CoxPHFitter().fit(d, "T", "E")
        return concordance_index(d["T"], -cph.predict_partial_hazard(d), d["E"]), cph

    @classmethod
    def _bootstrap_cindex(cls, d: pd.DataFrame, idx: np.ndarray) -> float:
        """C-index of one bootstrap resample, with the Cox model refitted."""
        try:
            return cls._cox_cindex(d.iloc[idx].reset_index(drop=True))[0]
        except Exception:
            return np.nan

    @classmethod
    def _cindex_ci(
        cls, d: pd.DataFrame, n_bootstrap: int, confidence_level: float, seed: int
    ) -> Tuple[float, float]:
        """Bootstrap confidence interval of the C-index."""
        res = bootstrap(
            (np.arange(len(d)),),
            lambda i: cls._bootstrap_cindex(d, i),
            vectorized=False,
            n_resamples=n_bootstrap,
            confidence_level=confidence_level,
            method="BCa",
            rng=np.random.default_rng(seed),
        )
        return float(res.confidence_interval.low), float(res.confidence_interval.high)

    def compute_cox_metrics(
        self,
        n_bootstrap: int = 1000,
        confidence_level: float = 0.95,
        seed: int = 0,
        n_jobs: int = -1,
        original_name: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Absolute survival performance of every dataset and its agreement with the original.

        For each dataset, a Cox model with the phenotype group as single covariate (value_A
        coded 1) gives Harrell's C-index and the hazard ratio. The confidence interval of the
        C-index is a bootstrap interval, the Cox model being refitted on every resample.
        Against the reference dataset, ``HR_same_direction`` records whether the hazard ratio
        lies on the same side of 1, and ``Survival_score`` = 1 - |C_synthetic - C_original|.

        Args:
            n_bootstrap (int): Number of bootstrap resamples.
            confidence_level (float): Confidence level of the interval.
            seed (int): Seed of the resampling; the k-th dataset with a C-index (in plotting
                order) is resampled with seed + k.
            n_jobs (int): Parallel jobs for the bootstrap (joblib convention).
            original_name (Optional[str]): Reference dataset; defaults to self.original_name.

        Returns:
            pd.DataFrame: One row per dataset with columns Dataset, n_A, n_B, events_A,
            events_B, logrank_P, C-index, CI_low, CI_high, HR, HR_same_direction,
            Survival_score. The table is also stored in ``self.cox_df``.

        Raises:
            KeyError: If the reference dataset is not in datasets_dict.
        """
        ref_name = original_name or self.original_name
        if ref_name not in self.datasets_dict:
            raise KeyError(f"Reference dataset '{ref_name}' not found in datasets_dict.")

        frames: Dict[str, pd.DataFrame] = {}
        rows = []
        for ds_name in self.dataset_names:
            d = self._cox_frame(ds_name)
            frames[ds_name] = d
            g1, g0 = d[d["group"] == 1], d[d["group"] == 0]
            row: Dict[str, Any] = {
                "Dataset": ds_name,
                "n_A": len(g1),
                "n_B": len(g0),
                "events_A": int(g1["E"].sum()),
                "events_B": int(g0["E"].sum()),
                "logrank_P": np.nan,
                "C-index": np.nan,
                "HR": np.nan,
            }
            if len(g1) > 0 and len(g0) > 0:
                row["logrank_P"] = float(logrank_test(g1["T"], g0["T"], g1["E"], g0["E"]).p_value)
                try:
                    c, cph = self._cox_cindex(d)
                except Exception:
                    c, cph = np.nan, None
                row["C-index"] = c
                if cph is not None:
                    row["HR"] = float(np.exp(cph.params_["group"]))
            rows.append(row)
        table = pd.DataFrame(rows)

        with_c = [r["Dataset"] for r in rows if pd.notna(r["C-index"])]
        intervals = Parallel(n_jobs=n_jobs)(
            delayed(self._cindex_ci)(frames[name], n_bootstrap, confidence_level, seed + k)
            for k, name in enumerate(with_c)
        )
        ci = dict(zip(with_c, intervals))
        table["CI_low"] = [ci[n][0] if n in ci else np.nan for n in table["Dataset"]]
        table["CI_high"] = [ci[n][1] if n in ci else np.nan for n in table["Dataset"]]

        ref = table.set_index("Dataset").loc[ref_name]
        is_ref = table["Dataset"] == ref_name
        table["HR_same_direction"] = [
            float(np.sign(np.log(hr)) == np.sign(np.log(ref["HR"]))) if pd.notna(hr) else np.nan
            for hr in table["HR"]
        ]
        table["Survival_score"] = 1 - (table["C-index"] - ref["C-index"]).abs()
        table.loc[is_ref, ["HR_same_direction", "Survival_score"]] = np.nan

        table = table[[
            "Dataset", "n_A", "n_B", "events_A", "events_B", "logrank_P",
            "C-index", "CI_low", "CI_high", "HR", "HR_same_direction", "Survival_score",
        ]]
        table.attrs["confidence_level"] = confidence_level
        self.cox_df = table
        return table

    def plot_cindex_forest(
        self,
        cox_df: Optional[pd.DataFrame] = None,
        ax: Optional[plt.Axes] = None,
        title: Optional[str] = None,
        original_name: Optional[str] = None,
        figsize: Tuple[float, float] = (6, 6),
    ) -> Tuple[plt.Figure, pd.DataFrame]:
        """
        Forest plot of the C-index of every synthetic dataset with its confidence interval.

        The grey band is the confidence interval of the reference C-index, the solid line its
        point value and the dashed line C = 0.5 (no survival signal). A red cross marks a
        hazard ratio on the opposite side of 1 from the reference (reversed association).

        Args:
            cox_df (Optional[pd.DataFrame]): Output of :meth:`compute_cox_metrics`; computed
                with default settings when None and not computed before.
            ax (Optional[matplotlib.axes.Axes]): Target axis; a new figure when None.
            title (Optional[str]): Panel title; defaults to the endpoint and reference C-index.
            original_name (Optional[str]): Reference dataset; defaults to self.original_name.
            figsize (tuple[float, float]): Figure size when a new figure is created.

        Returns:
            tuple[matplotlib.figure.Figure, pd.DataFrame]: (figure, table plotted).
        """
        if cox_df is None:
            cox_df = self.cox_df
        if cox_df is None:
            cox_df = self.compute_cox_metrics(original_name=original_name)
        ref_name = original_name or self.original_name

        if ax is None:
            fig, ax = plt.subplots(figsize=figsize)
        else:
            fig = ax.figure

        ref = cox_df[cox_df["Dataset"] == ref_name].iloc[0]
        syn = cox_df[cox_df["Dataset"] != ref_name].reset_index(drop=True)

        if pd.notna(ref["CI_low"]):
            ax.axvspan(ref["CI_low"], ref["CI_high"], color="#bdbdbd", alpha=0.45, lw=0, zorder=0)
        if pd.notna(ref["C-index"]):
            ax.axvline(ref["C-index"], color="#4d4d4d", lw=1.4, zorder=1)
        ax.axvline(0.5, color="#d32f2f", lw=1.1, ls="--", zorder=1)

        x_lo, x_hi = 0.3, 0.9
        for i, r in syn.iterrows():
            y = -i
            color = self.dataset_colors.get(str(r["Dataset"]), "#8c8c8c")
            if pd.isna(r["C-index"]):
                ax.text(x_lo + 0.02, y, "N/A", ha="left", va="center", fontsize=7, color="#9e9e9e",
                        style="italic")
                continue
            if pd.notna(r["CI_low"]):
                ax.plot([r["CI_low"], r["CI_high"]], [y, y], color=color, lw=1.6, zorder=2)
            if r["HR_same_direction"] == 0:
                ax.plot(r["C-index"], y, marker="X", ms=8, mfc="#d32f2f", mec="white", mew=0.6,
                        zorder=3, ls="none")
            else:
                ax.plot(r["C-index"], y, marker="o", ms=5.5, mfc=color, mec="black", mew=0.7,
                        zorder=3, ls="none")

        ax.set_yticks([-i for i in range(len(syn))])
        ax.set_yticklabels(syn["Dataset"].astype(str), fontsize=9)
        ax.tick_params(axis="y", length=0)
        ax.set_ylim(-len(syn) + 0.4, 0.6)
        ax.set_xlim(x_lo, x_hi)
        ax.grid(axis="x", alpha=0.3, ls=":", lw=0.6)
        ax.spines[["top", "right"]].set_visible(False)
        ax.set_xlabel(f"C-index ({self._ci_label(cox_df)} CI)", fontsize=10)
        if title is None:
            title = f"{self.time_target}; {ref_name} C = {ref['C-index']:.2f}"
            if pd.notna(ref["CI_low"]):
                title += f" ({ref['CI_low']:.2f}–{ref['CI_high']:.2f})"
        ax.set_title(title, fontsize=10)

        handles = [
            plt.Line2D([], [], marker="o", ls="none", mfc="#bdbdbd", mec="black", ms=5.5,
                       label="Synthetic dataset"),
            plt.Line2D([], [], marker="X", ls="none", mfc="#d32f2f", mec="white", ms=8,
                       label="HR opposite to the reference"),
            mpatches.Patch(color="#bdbdbd", alpha=0.45, label=f"{ref_name} C-index CI"),
            plt.Line2D([], [], color="#d32f2f", ls="--", label="C = 0.5"),
        ]
        ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, -0.16), ncol=2,
                  fontsize=7, frameon=False)
        return fig, cox_df

    @staticmethod
    def _ci_label(cox_df: pd.DataFrame) -> str:
        """Label of the confidence level stored by compute_cox_metrics."""
        level = cox_df.attrs.get("confidence_level")
        return f"{level:.0%}" if level is not None else "bootstrap"

    def plot_grid(
        self,
        figsize: Optional[Tuple[float, float]] = (18, 6),
        show_censors: bool = True,
        ci_show: bool = False,
        title_prefix: Optional[str] = "Survival",
        dataset_strip_height: float = 0.02,
        dataset_strip_y: float = 1.01,
        save_dir: Optional[str] = None
    ) -> Tuple[plt.Figure, pd.DataFrame]:
        """
        Plot a manuscript-style grid of Kaplan–Meier survival curves for all datasets.

        Args:
            figsize (Tuple[float, float], optional): Figure dimensions (W, H).
            show_censors (bool): Whether to display censor marks.
            ci_show (bool): Whether to render CI for KM curves.
            title_prefix (str, optional): Prefix for subplot titles.
            dataset_strip_height (float): Height of colored dataset strip.
            dataset_strip_y (float): Y-position of top dataset strip.
            save_dir (str, optional): If set, save individual dataset KM curves to this folder.

        Returns:
            Tuple[plt.Figure, pd.DataFrame]: The matplotlib Figure and the summary dataframe.

        Raises:
            None
        """
        import scienceplots  # noqa: F401  (registers the "science" matplotlib styles)

        plt.style.use(["science", "nature", "notebook"])
        plt.rcParams.update({
            "font.size": 10 * self.font_scale,
            "axes.titlesize": 11 * self.font_scale,
            "axes.labelsize": 10 * self.font_scale,
            "legend.fontsize": 9 * self.font_scale,
            "xtick.labelsize": 9 * self.font_scale,
            "ytick.labelsize": 9 * self.font_scale,
            "axes.linewidth": 1.0,
            "text.usetex": False,
            "axes.edgecolor": "#333333",
            "xtick.minor.visible": False,
            "ytick.minor.visible": False,
            "xtick.top": False,
            "ytick.right": False,
        })
        fig = plt.figure(figsize=figsize)
        gs = gridspec.GridSpec(2, 4, figure=fig, wspace=0.1, hspace=0.3,
                               width_ratios=[2, 1.25, 1.25, 1.25], height_ratios=[1, 1])
        ax_origin = fig.add_subplot(gs[:, 0])
        ax_origin.set_box_aspect(1)
        axes_small = []
        for r in range(2):
            for c in range(1, 4):
                ax = fig.add_subplot(gs[r, c])
                axes_small.append(ax)
        max_small_axes = len(axes_small)
        synthetic_names = [d for d in self.dataset_names if d != self.original_name]
        color_A = self.group_colors.get("GroupA", "#0072B2")
        color_B = self.group_colors.get("GroupB", "#D55E00")

        def _plot_single(ds_name: str, ax: plt.Axes, is_large: bool = False, save: bool = False) -> None:
            """
            Plot KM curve for a single dataset.

            Args:
                ds_name (str): Dataset name.
                ax (plt.Axes): Matplotlib axes.
                is_large (bool): If True, use larger annotation and legend.
                save (bool): If True, save individual plot.

            Returns:
                None
            """
            df_raw = self.datasets_dict[ds_name].copy()
            df = df_raw.copy()
            df[self.event_target] = pd.to_numeric(df.get(self.event_target, 0), errors="coerce").fillna(0).astype(int)
            df[self.time_target] = pd.to_numeric(df.get(self.time_target, np.nan), errors="coerce")
            df_A = df[df[self.phenotype_column] == self.value_A].copy()
            df_B = df[df[self.phenotype_column] == self.value_B].copy()
            n_A, n_B = len(df_A), len(df_B)
            ds_color = self.dataset_colors.get(ds_name, "#cccccc")
            ax.add_patch(
                plt.Rectangle(
                    (0, dataset_strip_y),
                    1,
                    dataset_strip_height,
                    transform=ax.transAxes,
                    facecolor=ds_color,
                    edgecolor="none",
                    clip_on=False,
                    zorder=10,
                )
            )
            kmf = KaplanMeierFitter()
            plotted_any = False
            for group_df, label, group_color in [
                (df_B, f"{self.value_B} (n={n_B})", color_B),
                (df_A, f"{self.value_A} (n={n_A})", color_A),
            ]:
                if len(group_df) == 0 or not group_df[self.time_target].notna().any():
                    continue
                g = group_df.dropna(subset=[self.time_target, self.event_target])
                if len(g) == 0:
                    continue
                kmf.fit(g[self.time_target], event_observed=g[self.event_target], label=label)
                kmf.plot_survival_function(
                    ax=ax,
                    ci_show=ci_show,
                    show_censors=show_censors,
                    color=group_color,
                    linewidth=2.0 if is_large else 1.8,
                    censor_styles={"ms": 4, "marker": "|", "mew": 1.2} if show_censors else None,
                )
                plotted_any = True
            # Annotations
            pvalue = self.summary_df.loc[self.summary_df["Dataset"] == ds_name, "pvalue"].values[0] \
                if self.summary_df is not None else np.nan
            cindex_text = self.summary_df.loc[self.summary_df["Dataset"] == ds_name, "C-index"].values[0] \
                if self.summary_df is not None else "NA"
            ptext = "p = NA" if (pvalue is None or np.isnan(pvalue)) else f"p = {pvalue:.4g}"
            ax.text(
                0.98, 0.96, ptext, transform=ax.transAxes,
                fontsize=10 * self.font_scale,
                horizontalalignment="right", verticalalignment="top", zorder=10,
            )
            ax.text(
                0.98, 0.88, f"C-index: {cindex_text}", transform=ax.transAxes,
                fontsize=10 * self.font_scale,
                horizontalalignment="right", verticalalignment="top", zorder=10,
            )
            title_t = f"{ds_name}" if title_prefix is None else f"{title_prefix}: {ds_name}"
            ax.set_title(title_t, fontweight="bold", pad=12)
            ax.set_xlabel(f"Time ({self.time_target})")
            ax.set_ylabel("Survival probability" if is_large else "")
            ax.set_ylim(0, 1.02)
            ax.grid(True, axis="y", linestyle="--", linewidth=0.6, alpha=0.5)
            if plotted_any:
                ax.legend(
                    frameon=True, framealpha=1.0, loc="lower left",
                    bbox_to_anchor=(0, 0.02), borderaxespad=0.2,
                )
            else:
                ax.text(
                    0.5, 0.5, "No valid survival data",
                    ha="center", va="center", transform=ax.transAxes,
                    fontsize=11 * self.font_scale,
                )
                leg = ax.get_legend()
                if leg is not None:
                    leg.remove()
            if save and save_dir:
                fig_indiv = plt.figure(figsize=(6, 5))
                ax_indiv = fig_indiv.add_subplot(111)
                _plot_single(ds_name, ax_indiv, is_large=True, save=False)
                fig_indiv.tight_layout()
                if self.is_pdf:
                    outpath = os.path.join(save_dir, f"{ds_name}_KMcurve.pdf")
                else: 
                    outpath = os.path.join(save_dir, f"{ds_name}_KMcurve.png")
                fig_indiv.savefig(outpath, dpi=300)
                plt.close(fig_indiv)

        _plot_single(self.original_name, ax_origin, is_large=True, save=bool(save_dir))
        for i, ds_name in enumerate(synthetic_names):
            if i >= max_small_axes:
                break
            _plot_single(ds_name, axes_small[i], is_large=False, save=bool(save_dir))
        for j in range(len(synthetic_names), max_small_axes):
            axes_small[j].axis("off")
        plt.tight_layout()
        return fig, self.summary_df
import os
import math
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

from lifelines import KaplanMeierFitter, CoxPHFitter
from lifelines.statistics import logrank_test
from lifelines.utils import concordance_index

# =============================================================================
# Visualization color palettes (consistent for manuscript-level plots)
# =============================================================================
DATASET_COLORS = {
    "Origin": "#4d4d4d",
    "Avatars K5": "#66c2a5",
    "Avatars K10": "#fc8d62",
    "CTGAN": "#8da0cb",
    "Gaussian Copula": "#e78ac3",
    "Synthpop": "#a6d854",
    "TVAE": "#ffd92f",
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

    def compute_cindex_scores(self, original_name: Optional[str] = None) -> pd.DataFrame:
        """
        Compute C-index similarity scores between the reference and synthetic datasets.

        Args:
            original_name (Optional[str]): Reference dataset for score calculation. 
                If None, uses self.original_name.

        Returns:
            pd.DataFrame: DataFrame with additional column 'C-index_score'.

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
        df["C-index_score"] = scores
        df = df.drop(columns=["_cindex_parsed"])
        return df

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
            title_t = f"{ds_name}" if title_prefix is None else f"{title_prefix} — {ds_name}"
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
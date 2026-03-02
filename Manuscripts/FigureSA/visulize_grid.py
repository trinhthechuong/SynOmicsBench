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
# Visualization constants for manuscript consistency
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


def plot_survival_grid(
    datasets_dict: Dict[str, pd.DataFrame],
    phenotype: Dict[str, List[Any]],
    treatment: Optional[str] = None,
    time_target: str = "OS",
    event_target: str = "OS_CNSR",
    figsize: Optional[Tuple[float, float]] = (18, 6),
    show_censors: bool = True,
    ci_show: bool = False,
    title_prefix: Optional[str] = "Survival",
    dataset_order: Optional[List[str]] = None,
    dataset_colors: Optional[Dict[str, str]] = None,
    group_colors: Optional[Dict[str, str]] = None,
    dataset_strip_height: float = 0.02,
    dataset_strip_y: float = 1.01,
    font_scale: float = 1.0,
) -> Tuple[plt.Figure, pd.DataFrame]:
    """
    Plot a grid of Kaplan–Meier survival curves with a fixed 2x4 layout:
        - Column 0 (both rows merged): Origin (large plot)
        - Columns 1–3 (2 rows each): synthetic datasets (up to 6)

    Returns:
        (fig, summary_df) as before.
    """
    # ------------------------ Validation ------------------------
    if not datasets_dict:
        raise ValueError("datasets_dict must not be empty.")
    if not isinstance(phenotype, dict) or len(phenotype) == 0:
        raise ValueError("phenotype must be a dict with one mapping {column_name: [valA, valB]}.")
    if len(phenotype) > 1:
        raise ValueError("phenotype must contain exactly one key (one column) to compare.")

    ph_column, ph_values = next(iter(phenotype.items()))
    if not isinstance(ph_values, (list, tuple)) or len(ph_values) != 2:
        raise ValueError("phenotype value must be a list/tuple of exactly two values: [value_A, value_B].")

    val_A, val_B = ph_values

    # ------------------------ Dataset ordering ------------------------
    if dataset_order is None:
        dataset_names = list(datasets_dict.keys())
    else:
        missing = [d for d in dataset_order if d not in datasets_dict]
        if missing:
            raise ValueError(f"dataset_order contains names not present in datasets_dict: {missing}")
        dataset_names = dataset_order

    # Đảm bảo Origin đứng đầu (và tồn tại) để map vào ô lớn
    if "Origin" not in dataset_names:
        raise ValueError("This layout requires a dataset named 'Origin' in datasets_dict.")
    dataset_names = ["Origin"] + [d for d in dataset_names if d != "Origin"]

    # Ta kỳ vọng 1 Origin + 6 synthetic = 7 datasets để lấp đầy 6 ô nhỏ
    if len(dataset_names) > 7:
        # Không bắt buộc raise, nhưng cảnh báo cho người dùng nếu muốn
        # Có thể cắt bớt cho vừa 6 synthetic
        dataset_names = dataset_names[:7]

    dataset_colors = dataset_colors or DATASET_COLORS
    group_colors = group_colors or GROUP_COLORS

    # ------------------------ Global style ------------------------
    plt.style.use(["science", "nature", "notebook"])
    plt.rcParams.update({
        "font.size": 10 * font_scale,
        "axes.titlesize": 11 * font_scale,
        "axes.labelsize": 10 * font_scale,
        "legend.fontsize": 9 * font_scale,
        "xtick.labelsize": 9 * font_scale,
        "ytick.labelsize": 9 * font_scale,
        "axes.linewidth": 1.0,
        "text.usetex": False,
        "axes.edgecolor": "#333333",
        "xtick.minor.visible": False,
        "ytick.minor.visible": False,
        "xtick.top": False,
        "ytick.right": False,
    })

    # ------------------------ Layout với GridSpec 2x4 ------------------------
    # 2 hàng, 4 cột; cột 0 (col=0) gộp 2 hàng cho Origin; 6 ô còn lại cho synthetic
    if figsize is None:
        figsize = (18, 6)

    fig = plt.figure(figsize=figsize)
    gs = gridspec.GridSpec(2, 4, figure=fig, wspace=0.1, hspace=0.3,
                           width_ratios=[2, 1.25, 1.25, 1.25],
                       height_ratios=[1, 1])
    

    # Ax lớn cho Origin: dùng toàn bộ 2 hàng của cột 0
    ax_origin = fig.add_subplot(gs[:, 0])
    ax_origin.set_box_aspect(1) 

    # 6 ô nhỏ bên phải: (row=0..1, col=1..3)
    axes_small: List[plt.Axes] = []
    for r in range(2):        # rows 0,1
        for c in range(1, 4): # cols 1,2,3
            ax = fig.add_subplot(gs[r, c])
            axes_small.append(ax)
    max_small_axes = len(axes_small)  # = 6

    synthetic_names = dataset_names[1:]  # bỏ Origin

    # ------------------------ Hàm con để vẽ một dataset lên ax ------------------------
    summary_rows = []

    color_A = group_colors.get("GroupA", "#0072B2")
    color_B = group_colors.get("GroupB", "#D55E00")

    def _plot_single_dataset(ds_name: str, ax: plt.Axes, is_large: bool = False) -> None:
        nonlocal summary_rows

        df_raw = datasets_dict[ds_name].copy()

        # Filter by treatment if requested
        if treatment is not None and "Arm" in df_raw.columns:
            df = df_raw[df_raw["Arm"] == treatment].copy()
        else:
            df = df_raw.copy()

        # Coerce event/time
        if event_target in df.columns:
            df[event_target] = pd.to_numeric(df[event_target], errors="coerce").fillna(0).astype(int)
        else:
            df[event_target] = 0

        if time_target in df.columns:
            df[time_target] = pd.to_numeric(df[time_target], errors="coerce")
        else:
            df[time_target] = np.nan

        # A vs B subsets
        df_A = df[df[ph_column] == val_A].copy()
        df_B = df[df[ph_column] == val_B].copy()
        n_A, n_B = len(df_A), len(df_B)

        # Dataset strip
        ds_color = dataset_colors.get(ds_name, "#cccccc")
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

        def _plot_group(group_df: pd.DataFrame, label: str, color: str) -> None:
            nonlocal plotted_any
            if len(group_df) == 0:
                return
            if not group_df[time_target].notna().any():
                return
            g = group_df.dropna(subset=[time_target, event_target]).copy()
            if len(g) == 0:
                return
            kmf.fit(g[time_target], event_observed=g[event_target], label=label)
            kmf.plot_survival_function(
                ax=ax,
                ci_show=ci_show,
                show_censors=show_censors,
                color=color,
                linewidth=2.0 if is_large else 1.8,
                censor_styles={"ms": 4, "marker": "|", "mew": 1.2} if show_censors else None,
            )
            plotted_any = True

        _plot_group(df_B, label=f"{val_B} (n={n_B})", color=color_B)
        _plot_group(df_A, label=f"{val_A} (n={n_A})", color=color_A)

        # Log-rank p-value
        pvalue = np.nan
        try:
            if n_A > 0 and n_B > 0:
                gA = df_A.dropna(subset=[time_target, event_target]).copy()
                gB = df_B.dropna(subset=[time_target, event_target]).copy()
                if len(gA) > 0 and len(gB) > 0:
                    res = logrank_test(
                        gA[time_target],
                        gB[time_target],
                        event_observed_A=gA[event_target],
                        event_observed_B=gB[event_target],
                    )
                    pvalue = float(res.p_value)
        except Exception:
            pvalue = np.nan

        # C-index via Cox
        cindex_text = "NA"
        try:
            df_cox = df[[time_target, event_target]].copy()
            df_cox["phenotype_binary"] = pd.NA
            df_cox.loc[df[ph_column] == val_A, "phenotype_binary"] = 1
            df_cox.loc[df[ph_column] == val_B, "phenotype_binary"] = 0
            df_cox_fit = df_cox.dropna(subset=[time_target, "phenotype_binary"]).copy()
            df_cox_fit[time_target] = pd.to_numeric(df_cox_fit[time_target], errors="coerce")
            df_cox_fit = df_cox_fit.dropna(subset=[time_target]).copy()
            df_cox_fit["phenotype_binary"] = df_cox_fit["phenotype_binary"].astype(int)

            if (
                len(df_cox_fit) > 0
                and df_cox_fit["phenotype_binary"].nunique() > 1
                and df_cox_fit[event_target].sum() > 0
            ):
                cph = CoxPHFitter()
                cph.fit(df_cox_fit, duration_col=time_target, event_col=event_target, show_progress=False)
                partial_h = cph.predict_partial_hazard(df_cox_fit)
                cindex = concordance_index(df_cox_fit[time_target], -partial_h, df_cox_fit[event_target])
                cindex_text = f"{cindex:.3f}"
            else:
                cindex_text = "insufficient events"
        except Exception:
            cindex_text = "fit error"

        # Annotation
        ptext = "p = NA" if (pvalue is None or np.isnan(pvalue)) else f"p = {pvalue:.4g}"
        ax.text(
            0.98,
            0.96,
            ptext,
            transform=ax.transAxes,
            fontsize=10 * font_scale,
            horizontalalignment="right",
            verticalalignment="top",
            zorder=10,
        )
        ax.text(
            0.98,
            0.88,
            f"C-index: {cindex_text}",
            transform=ax.transAxes,
            fontsize=10 * font_scale,
            horizontalalignment="right",
            verticalalignment="top",
            zorder=10,
        )

        # Titles and axes
        title_t = f"{ds_name}" if title_prefix is None else f"{title_prefix} — {ds_name}"
        ax.set_title(title_t, fontweight="bold", pad=12)
        ax.set_xlabel(f"Time ({time_target})")
        # chỉ Origin mới ghi label trục y, các panel nhỏ bỏ để đỡ rối
        ax.set_ylabel("Survival probability" if is_large else "")
        ax.set_ylim(0, 1.02)
        ax.grid(True, axis="y", linestyle="--", linewidth=0.6, alpha=0.5)

        # Legend
        if plotted_any:
            ax.legend(
                frameon=True,
                framealpha=1.0,
                loc="lower left",
                bbox_to_anchor=(0, 0.02),
                borderaxespad=0.2,
            )
        else:
            ax.text(
                0.5,
                0.5,
                "No valid survival data",
                ha="center",
                va="center",
                transform=ax.transAxes,
                fontsize=11 * font_scale,
            )
            leg = ax.get_legend()
            if leg is not None:
                leg.remove()

        summary_rows.append(
            {
                "Dataset": ds_name,
                "pvalue": (np.nan if (pvalue is None or np.isnan(pvalue)) else float(pvalue)),
                "C-index": cindex_text,
                "n_A": int(n_A),
                "n_B": int(n_B),
            }
        )

    # ------------------------ Vẽ Origin ------------------------
    _plot_single_dataset("Origin", ax_origin, is_large=True)

    # ------------------------ Vẽ các synthetic ------------------------
    for i, ds_name in enumerate(synthetic_names):
        if i >= max_small_axes:
            # Nếu synthetic > 6, hiện tại chỉ hiển thị 6 đầu tiên
            break
        ax_small = axes_small[i]
        _plot_single_dataset(ds_name, ax_small, is_large=False)

    # Ẩn ô thừa nếu synthetic < 6
    if len(synthetic_names) < max_small_axes:
        for j in range(len(synthetic_names), max_small_axes):
            axes_small[j].axis("off")

    plt.tight_layout()

    # ------------------------ Summary DataFrame ------------------------
    summary_df = pd.DataFrame(summary_rows, columns=["Dataset", "pvalue", "C-index", "n_A", "n_B"])
    summary_df["Dataset"] = pd.Categorical(summary_df["Dataset"], categories=dataset_names, ordered=True)
    summary_df = summary_df.sort_values("Dataset").reset_index(drop=True)

    return fig, summary_df
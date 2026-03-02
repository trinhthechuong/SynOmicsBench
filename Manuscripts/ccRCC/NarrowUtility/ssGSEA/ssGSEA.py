from typing import Dict, Iterable, Any, Tuple, List, Optional
import warnings
import traceback
import os
import concurrent.futures

import numpy as np
import pandas as pd
from scipy.stats import ranksums
from statsmodels.stats.multitest import multipletests
import matplotlib.pyplot as plt



def ssGSEA_differential(
    ssGSEA: Dict[str, pd.DataFrame],
    dataset_metadata: Dict[str, pd.DataFrame],
    phenotypes: Dict[str, Iterable[Any]],
    id_col: str = "Patient",
    term_col: str = "Term",
    sample_col: str = "Name",
    nes_col: str = "NES",
    n_jobs: int = 1,
    alpha: float = 0.05,
) -> Dict[str, pd.DataFrame]:
    """
    Differential analysis on ssGSEA term scores per-dataset using Wilcoxon rank-sum test
    and Benjamini-Hochberg q-value correction.

    Args:
        ssGSEA (Dict[str, pd.DataFrame]): Mapping dataset_name -> ssGSEA results DataFrame.
            Each ssGSEA DataFrame must contain at least columns named by `term_col`, `sample_col`, and `nes_col`.
            Rows are term x sample entries (long format).
        dataset_metadata (Dict[str, pd.DataFrame]): Mapping dataset_name -> metadata DataFrame.
            Each metadata DataFrame must contain the phenotype column (the single key of `phenotypes`)
            and an ID column named `id_col` whose values match the `sample_col` entries in the ssGSEA frames.
        phenotypes (Dict[str, Iterable[Any]]): Single-key dict mapping phenotype column -> two-valued iterable of groups.
            Example: {"PBRM1": ["MUT", "WT"]}
        id_col (str): Column name in metadata that matches sample identifiers used in ssGSEA[sample_col]. Default "Patient".
        term_col (str): Column name in ssGSEA frames that identifies gene set / term. Default "Term".
        sample_col (str): Column name in ssGSEA frames that identifies sample / sample ID. Default "Name".
        nes_col (str): Column name in ssGSEA frames with the normalized enrichment score. Default "NES".
        n_jobs (int): Number of worker threads to use for per-term tests within each dataset. Default 1 (no threading).
        alpha (float): Significance alpha used by multipletests (passed through). Default 0.05.

    Returns:
        Dict[str, pd.DataFrame]: Mapping dataset_name -> DataFrame with columns:
            ["Term", "P_value", "Diff_NES", "Q_value", "Status"].
            Q_value contains Benjamini-Hochberg adjusted p-values computed per-dataset.

    Raises:
        ValueError: If phenotypes does not contain exactly one key with two values.
        ValueError: If a dataset is missing required columns (term_col, sample_col, nes_col) or metadata id_col.
    """
    # Validate phenotypes input
    if not isinstance(phenotypes, dict) or len(phenotypes) != 1:
        raise ValueError("phenotypes must be a dict with a single key mapping to two phenotype values.")
    ph_col, ph_vals = next(iter(phenotypes.items()))
    ph_vals = list(ph_vals)
    if len(ph_vals) != 2:
        raise ValueError("phenotypes must map to exactly two values (e.g. {'PBRM1': ['MUT','WT']}).")
    phenotype_A, phenotype_B = ph_vals

    results: Dict[str, pd.DataFrame] = {}

    # Threading helper
    if n_jobs == -1:
        max_workers = max(1, os.cpu_count() or 1)
    elif n_jobs <= 0:
        max_workers = 1
    else:
        max_workers = int(n_jobs)

    for dataset_name, ssdf in ssGSEA.items():
        # Basic validation
        if not isinstance(ssdf, pd.DataFrame):
            raise ValueError(f"ssGSEA[{dataset_name}] must be a DataFrame.")
        for col in (term_col, sample_col, nes_col):
            if col not in ssdf.columns:
                raise ValueError(f"ssGSEA[{dataset_name}] missing required column: {col}")

        if dataset_name not in dataset_metadata:
            raise ValueError(f"Metadata for dataset '{dataset_name}' not found in dataset_metadata.")

        meta = dataset_metadata[dataset_name]
        if ph_col not in meta.columns:
            raise ValueError(f"Metadata for dataset '{dataset_name}' missing phenotype column '{ph_col}'.")
        if id_col not in meta.columns:
            raise ValueError(f"Metadata for dataset '{dataset_name}' missing id column '{id_col}'.")

        # Build lists of sample IDs for each phenotype, allow metadata to contain extra samples
        samples_A = meta.loc[meta[ph_col] == phenotype_A, id_col].astype(str).tolist()
        samples_B = meta.loc[meta[ph_col] == phenotype_B, id_col].astype(str).tolist()

        present_A = [s for s in samples_A if s in ssdf[sample_col].astype(str).unique()]
        present_B = [s for s in samples_B if s in ssdf[sample_col].astype(str).unique()]

        missing_A = [s for s in samples_A if s not in present_A]
        missing_B = [s for s in samples_B if s not in present_B]
        if missing_A or missing_B:
            warnings.warn(
                f"Dataset '{dataset_name}': some metadata samples not present in ssGSEA and will be ignored. "
                f"Missing A up to 5: {missing_A[:5]} ; Missing B up to 5: {missing_B[:5]}"
            )

        # If either group has no samples present, create NaN-filled result frame
        if len(present_A) == 0 or len(present_B) == 0:
            terms = ssdf[term_col].unique()
            empty_df = pd.DataFrame({
                "Term": terms,
                "P_value": np.nan,
                "Diff_NES": np.nan,
                "Q_value": np.nan,
                "Status": ["No_samples_in_one_group"] * len(terms)
            })
            results[dataset_name] = empty_df
            continue

        # For each term, collect NES vectors for samples
        terms = ssdf[term_col].unique().tolist()

        # prepare a helper to compute per-term stats
        def _process_term(term: Any) -> Tuple[Any, float, float, str]:
            try:
                term_df = ssdf[ssdf[term_col] == term]
                # ensure sample id type consistency
                term_df = term_df.assign(_sid=term_df[sample_col].astype(str))
                a_vals = term_df[term_df["_sid"].isin(present_A)][nes_col].apply(pd.to_numeric, errors="coerce").dropna().to_numpy()
                b_vals = term_df[term_df["_sid"].isin(present_B)][nes_col].apply(pd.to_numeric, errors="coerce").dropna().to_numpy()

                if a_vals.size == 0 or b_vals.size == 0:
                    return term, float("nan"), float("nan"), "No_data_for_term"

                # detect opposing infinities within a group -> mark and skip
                if (np.isposinf(a_vals).any() and np.isneginf(a_vals).any()) or (np.isposinf(b_vals).any() and np.isneginf(b_vals).any()):
                    return term, float("nan"), float("nan"), "Opposing_infs_in_group"

                # identical constant arrays -> p=1
                if np.all(np.isfinite(a_vals)) and np.all(np.isfinite(b_vals)) and a_vals.size and b_vals.size:
                    if np.all(a_vals == a_vals[0]) and np.all(b_vals == b_vals[0]) and a_vals[0] == b_vals[0]:
                        diff_nes = float(np.mean(a_vals) - np.mean(b_vals))
                        return term, 1.0, diff_nes, "Identical"

                # ranksums test (Wilcoxon rank-sum)
                try:
                    _, p = ranksums(a_vals, b_vals)
                except Exception:
                    p = float("nan")

                diff_nes = float(np.nanmean(a_vals) - np.nanmean(b_vals))
                return term, float(p) if np.isfinite(p) else float("nan"), diff_nes, "ok"
            except Exception:
                tb = traceback.format_exc().splitlines()[-1]
                return term, float("nan"), float("nan"), f"error:{tb}"

        # run per-term processing (optionally multithreaded)
        if max_workers == 1:
            rows = [_process_term(t) for t in terms]
        else:
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as exe:
                futures = {exe.submit(_process_term, t): t for t in terms}
                rows = []
                for fut in concurrent.futures.as_completed(futures):
                    try:
                        rows.append(fut.result())
                    except Exception:
                        t = futures[fut]
                        tb = traceback.format_exc().splitlines()[-1]
                        rows.append((t, float("nan"), float("nan"), f"executor_error:{tb}"))

        # collect results preserving original term order
        term_list = [r[0] for r in rows]
        pvals = np.array([r[1] for r in rows], dtype=float)
        diffs = np.array([r[2] for r in rows], dtype=float)
        statuses = [r[3] for r in rows]

        # multiple testing correction per-dataset
        valid_mask = np.isfinite(pvals)
        qvals = np.full_like(pvals, np.nan, dtype=float)
        if valid_mask.any():
            try:
                _, adj_pvals, _, _ = multipletests(pvals[valid_mask], alpha=alpha, method="fdr_bh")
                qvals[valid_mask] = adj_pvals
            except Exception:
                # annotate status for those with finite pvals
                for idx in np.where(valid_mask)[0]:
                    statuses[idx] = statuses[idx] + ";q_adjust_error"

        # assemble dataframe
        df_out = pd.DataFrame({
            "Term": term_list,
            "P_value": pvals,
            "Diff_NES": diffs,
            "Q_value": qvals,
            "Status": statuses
        })

        results[dataset_name] = df_out

    return results



# Consistent color definitions used across SynOmics visualizations
DATA_COLORS = {"real": "#4c72b0", "synthetic": "#dd8452"}
PVAL_BIN_COLORS_DEFAULT = ["#d62728", "#ff7f0e", "#1f77b4", "#cccccc"]  # red, orange, blue, gray


def plot_pathway(
    ssGSEA_comparison: Dict[str, pd.DataFrame],
    ref_pathway_list: List[str],
    highlight_pathways: List[str] = None,
    origin_name: str = "Origin",
    term_col: str = "Term",
    pval_col: str = "adj_pvalues",
    diff_col: str = "Diff_NES",
    pval_bin_colors: List[str] = PVAL_BIN_COLORS_DEFAULT,
    fig_width_min: float = 14.0,
    bubble_size: float = 170,
    show: bool = True,
    save_path: Optional[str] = None,
    return_dataframe: bool = True,
) -> Tuple[plt.Figure, pd.DataFrame]:
    """
    Wrapper to produce a pathway scatter figure for a fixed list of pathways, using explicit column names.

    Args:
        ssGSEA_comparison (Dict[str, pd.DataFrame]): Mapping dataset_name -> ssGSEA comparison DataFrame.
        ref_pathway_list (List[str]): Ordered list of pathways/terms to show.
        highlight_pathways (List[str]): Pathways to highlight on the y-axis.
        origin_name (str): Name of the reference dataset used to order pathways on the y-axis.
        term_col (str): Column name in the input frames that holds pathway/term names. Default "Term".
        pval_col (str): Column name in the input frames that holds adjusted p-values / q-values. Default "adj_pvalues".
        diff_col (str): Column name in the input frames that holds the NES difference (groupA - groupB). Default "Diff_NES".
        pval_bin_colors (List[str]): Four colors for p-value bins [p<0.01, 0.01≤p<0.05, 0.05≤p<0.25, p≥0.25].
        fig_width_min (float): Minimum figure width in inches.
        bubble_size (float): Fixed bubble size (area) for scatter markers.
        show (bool): If True, call plt.show() before returning the figure.
        save_path (Optional[str]): If provided, save the figure to this path (dpi=300).
        return_dataframe (bool): If True return the concatenated dataframe used for plotting along with the Figure.

    Returns:
        Tuple[matplotlib.figure.Figure, pandas.DataFrame]: The created matplotlib Figure and the DataFrame used for plotting.

    Raises:
        ValueError: If ssGSEA_comparison or ref_pathway_list are empty.
        ValueError: If none of the datasets contain the provided term/p-value/diff columns.
    """
    if not ssGSEA_comparison:
        raise ValueError("ssGSEA_comparison must not be empty.")
    if not ref_pathway_list:
        raise ValueError("ref_pathway_list must not be empty.")
    if highlight_pathways is None:
        highlight_pathways = []

    datasets = list(ssGSEA_comparison.keys())
    all_data_to_plot: List[pd.DataFrame] = []
    global_nes_values: List[float] = []
    found_any = False

    for ds_name in datasets:
        df_ds = ssGSEA_comparison.get(ds_name)
        if df_ds is None or not isinstance(df_ds, pd.DataFrame):
            warnings.warn(f"Skipping {ds_name}: not a pandas DataFrame.")
            continue

        # check required columns exist
        if term_col not in df_ds.columns or pval_col not in df_ds.columns or diff_col not in df_ds.columns:
            warnings.warn(
                f"Skipping {ds_name}: missing one of required columns "
                f"({term_col}, {pval_col}, {diff_col})."
            )
            continue

        sub_df = df_ds[df_ds[term_col].isin(ref_pathway_list)].copy()
        if sub_df.empty:
            continue

        found_any = True
        # normalize column names for plotting output
        sub_df = sub_df.rename(columns={term_col: "Term", pval_col: "adj_pvalues", diff_col: "Diff_NES"})
        sub_df["Dataset"] = ds_name

        # sanitize numeric columns
        sub_df["adj_pvalues"] = pd.to_numeric(sub_df["adj_pvalues"], errors="coerce")
        sub_df["Diff_NES"] = pd.to_numeric(sub_df["Diff_NES"], errors="coerce").fillna(0.0)

        # safe -log10 q-value
        sub_df["-log10(qvalue)"] = -np.log10(sub_df["adj_pvalues"].clip(lower=np.nextafter(0, 1)))

        global_nes_values.extend(sub_df["Diff_NES"].tolist())
        all_data_to_plot.append(sub_df[["Dataset", "Term", "adj_pvalues", "Diff_NES", "-log10(qvalue)"]])

    if not found_any:
        raise ValueError("No dataset contained the requested term/p-value/diff columns for the provided reference pathways.")

    df_plot = pd.concat(all_data_to_plot, ignore_index=True)

    # unified NES scale
    max_abs_nes = np.nanmax(np.abs(global_nes_values))
    if not np.isfinite(max_abs_nes) or max_abs_nes == 0:
        max_abs_nes = 1.0

    # p-value bins and colors
    bins = [0, 0.01, 0.05, 0.25, 1.01]
    bin_labels = ["p<0.01", "0.01≤p<0.05", "0.05≤p<0.25", "p≥0.25"]
    color_map = dict(zip(bin_labels, pval_bin_colors))
    df_plot["pvalue_bin"] = pd.cut(df_plot["adj_pvalues"], bins=bins, labels=bin_labels, include_lowest=True, right=False)

    # y ordering using origin if available
    origin_df = df_plot[df_plot["Dataset"] == origin_name].copy()
    if not origin_df.empty:
        origin_df = origin_df.sort_values(by="adj_pvalues", ascending=True, na_position="last")
        sorted_pathways = origin_df["Term"].tolist()
        for p in ref_pathway_list:
            if p not in sorted_pathways:
                sorted_pathways.append(p)
        sorted_pathways = [p for p in sorted_pathways if p in ref_pathway_list]
    else:
        sorted_pathways = [p for p in ref_pathway_list if p in df_plot["Term"].unique()]
        if not sorted_pathways:
            sorted_pathways = sorted(list(df_plot["Term"].unique()))

    y_labels = list(reversed(sorted_pathways))
    y_pos = np.arange(len(y_labels))
    mapping = {p: idx for idx, p in enumerate(y_labels)}

    N_COLS = len(datasets)
    FIG_WIDTH = max(3.5 * N_COLS + 2, fig_width_min)
    FIG_HEIGHT = max(0.6 * len(y_labels) + 3, 7)

    fig, axes = plt.subplots(nrows=1, ncols=N_COLS, figsize=(FIG_WIDTH, FIG_HEIGHT), sharey=True, sharex=True)
    axes_list = [axes] if N_COLS == 1 else list(axes.flat)
    plt.subplots_adjust(left=0.28, right=0.88, top=0.88, bottom=0.08, wspace=0.18)

    for i, ds in enumerate(datasets):
        ax = axes_list[i]
        sub = df_plot[df_plot["Dataset"] == ds].copy()
        sub["y"] = sub["Term"].map(mapping)

        if sub.empty or sub["y"].isna().all():
            ax.text(0.5, 0.5, "No data", ha="center", va="center", fontsize=10, color="grey", transform=ax.transAxes)
            ax.set_xlim(-max_abs_nes * 1.05, max_abs_nes * 1.05)
            ax.set_xticks([])
            ax.set_title(ds, fontsize=10, fontweight="bold", pad=10)
            ax.tick_params(left=False, labelleft=False)
            ax.grid(axis="y", linestyle="--", alpha=0.4)
            continue

        bubble_colors = sub["pvalue_bin"].map(color_map).fillna("#cccccc")

        ax.scatter(
            x=sub["Diff_NES"],
            y=sub["y"],
            s=bubble_size,
            c=bubble_colors,
            edgecolor="k",
            linewidths=0.4,
            alpha=0.95,
            zorder=2,
        )

        ax.axvline(x=0, color="gray", linestyle="--", linewidth=1.2, zorder=1)
        ax.set_xlim(-max_abs_nes * 1.05, max_abs_nes * 1.05)
        ax.set_xlabel(diff_col, fontsize=9, labelpad=6)

        ax.set_yticks(y_pos)
        ax.set_ylim(-0.5, len(y_labels) - 0.5)
        ax.invert_yaxis()
        ax.set_title(ds, fontsize=10, fontweight="bold", pad=10)
        ax.grid(axis="y", linestyle="--", alpha=0.4)

        if i == 0:
            ax.set_yticklabels(y_labels, fontsize=9)
            ax.tick_params(axis="y", which="major", pad=6)
            for label in ax.get_yticklabels():
                pathway_name = label.get_text()
                if pathway_name in (highlight_pathways or []):
                    label.set_color(DATA_COLORS["real"])
                    label.set_fontweight("bold")
                else:
                    label.set_color("black")
        else:
            ax.tick_params(left=False, labelleft=False)

    # remove extra axes if present
    if len(axes_list) > N_COLS:
        for j in range(N_COLS, len(axes_list)):
            fig.delaxes(axes_list[j])

    # legend for p-value bins
    import matplotlib.patches as mpatches
    legend_patches = [mpatches.Patch(color=color_map[l], label=l) for l in bin_labels]
    axes_list[-1].legend(handles=legend_patches, title="Adjusted p-value", bbox_to_anchor=(1.05, 1), loc="upper left", fontsize=8, title_fontsize=9, frameon=False)

    plt.tight_layout(rect=[0, 0.03, 0.88, 0.98])

    if save_path:
        fig.savefig(save_path, dpi=300, bbox_inches="tight")
    if show:
        plt.show()

    df_plot["y"] = df_plot["Term"].map(mapping)
    # keep consistent output column order
    df_plot = df_plot[["Dataset", "Term", "adj_pvalues", "Diff_NES", "-log10(qvalue)", "y", "pvalue_bin"]]

    return (fig, df_plot) if return_dataframe else (fig, None)
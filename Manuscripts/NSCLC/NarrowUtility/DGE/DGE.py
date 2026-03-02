from typing import Dict, Iterable, Any, Tuple, Optional, List
import os
import warnings
import traceback
import concurrent.futures
from scipy.stats import spearmanr
import numpy as np
import pandas as pd
from scipy.stats import ranksums
from statsmodels.stats.multitest import multipletests

# from collections import Iterable
# from typing import Dict, Optional, Tuple, Any, List

def dge_analysis(
    gene_expressions: pd.DataFrame,
    metadata: pd.DataFrame,
    phenotypes: Dict[str, Iterable[Any]],
    id_col: str,
    n_jobs: int = -1,
) -> pd.DataFrame:
    """
    Differential expression (per-gene) using Wilcoxon rank-sum test for gene-by-rows DataFrame.

    Args:
        gene_expressions (pd.DataFrame): Gene-by-samples table where each row is a gene and the first column may be 'Gene'
            (or gene names are already the index). Subsequent columns must be sample IDs that match metadata[id_col].
        metadata (pd.DataFrame): Sample metadata containing at least the phenotype column and id_col.
        phenotypes (Dict[str, Iterable[Any]]): Single-key dict mapping phenotype column -> two phenotype values.
        id_col (str): Column name in metadata that contains sample IDs.
        n_jobs (int): Number of worker threads to use (-1 -> os.cpu_count()). Default: -1.

    Returns:
        pd.DataFrame: DataFrame with columns ["Gene", "P_value", "Log2FC", "Q_value", "Status"] in the same
            row order as the input gene_expressions.

    Raises:
        ValueError: If phenotypes is not a single-key dict with exactly two values, or if after filtering a group
            has no samples present in the expression data.
    """
    # Validate phenotype dict
    if not isinstance(phenotypes, dict) or len(phenotypes) != 1:
        raise ValueError("phenotypes must be a dict with a single key mapping to two phenotype values.")
    ph_col, ph_vals = next(iter(phenotypes.items()))
    ph_vals = list(ph_vals)
    if len(ph_vals) != 2:
        raise ValueError(f"Phenotype values list must contain exactly two values, got: {ph_vals}")
    A_val, B_val = ph_vals

    # Validate metadata columns
    if ph_col not in metadata.columns:
        raise ValueError(f"Phenotype column '{ph_col}' not found in metadata.")
    if id_col not in metadata.columns:
        raise ValueError(f"ID column '{id_col}' not found in metadata.")

    # Prepare expression DataFrame: accept 'Gene' column or index as gene names
    expr_df = gene_expressions.copy()
    if "Gene" in expr_df.columns:
        expr_df.index = expr_df["Gene"].astype(str)
        expr_df = expr_df.drop(columns=["Gene"])
    else:
        expr_df.index = expr_df.index.astype(str)

    # Ensure sample column names are strings
    expr_df.columns = expr_df.columns.astype(str)

    # Build sample lists for each phenotype from metadata
    sampA_all = metadata.loc[metadata[ph_col] == A_val, id_col].astype(str).tolist()
    sampB_all = metadata.loc[metadata[ph_col] == B_val, id_col].astype(str).tolist()

    # Intersect with expression columns (allow metadata to contain extra samples)
    sampA = [s for s in sampA_all if s in expr_df.columns]
    sampB = [s for s in sampB_all if s in expr_df.columns]

    missing_A = [s for s in sampA_all if s not in expr_df.columns]
    missing_B = [s for s in sampB_all if s not in expr_df.columns]
    if missing_A or missing_B:
        warnings.warn(
            "Some samples in metadata are not present in gene_expressions and will be ignored. "
            f"Missing in A (up to 5): {missing_A[:5]} ; Missing in B (up to 5): {missing_B[:5]}",
            UserWarning,
        )

    if len(sampA) == 0 or len(sampB) == 0:
        raise ValueError(
            "After intersecting metadata sample IDs with gene_expressions columns, "
            "one of the phenotype groups has no samples present in the expression data."
        )

    genes = list(expr_df.index)

    # Determine number of workers
    if n_jobs == -1:
        workers = max(1, (os.cpu_count() or 1))
    elif n_jobs <= 0:
        workers = 1
    else:
        workers = int(n_jobs)

    # Helpers
    def _to_float_array(values) -> np.ndarray:
        return np.array(pd.to_numeric(values, errors="coerce"), dtype=float)

    def _analyze_row(row) -> Tuple[Optional[float], Optional[float], str]:
        try:
            a_raw = _to_float_array(row[sampA].values)
            b_raw = _to_float_array(row[sampB].values)

            # opposing infinities in a group => skip
            if np.isposinf(a_raw).any() and np.isneginf(a_raw).any():
                return np.nan, np.nan, "A_contains_posinf_and_neginf"
            if np.isposinf(b_raw).any() and np.isneginf(b_raw).any():
                return np.nan, np.nan, "B_contains_posinf_and_neginf"

            # keep only finite values for testing
            a_finite = a_raw[np.isfinite(a_raw)]
            b_finite = b_raw[np.isfinite(b_raw)]

            if a_finite.size == 0 or b_finite.size == 0:
                return np.nan, np.nan, "No_data"

            # identical constants (non-informative)
            if (
                a_finite.size > 0
                and b_finite.size > 0
                and np.all(a_finite == a_finite[0])
                and np.all(b_finite == b_finite[0])
                and a_finite[0] == b_finite[0]
            ):
                return 1.0, 0.0, "Identical"

            # ranksums test
            try:
                _, p = ranksums(a_finite, b_finite)
            except Exception:
                p = np.nan

            mean_a = float(np.nanmean(a_finite)) if a_finite.size else np.nan
            mean_b = float(np.nanmean(b_finite)) if b_finite.size else np.nan

            # compute log2fc only when both means are positive
            if not np.isfinite(mean_a) or not np.isfinite(mean_b) or mean_a <= 0 or mean_b <= 0:
                status = []
                if not np.isfinite(mean_a) or not np.isfinite(mean_b):
                    status.append("FC_nan")
                if (np.isfinite(mean_a) and mean_a <= 0) or (np.isfinite(mean_b) and mean_b <= 0):
                    status.append("Mean_nonpositive")
                if np.isnan(p):
                    status = status or ["p_nan"]
                return (p if np.isfinite(p) else np.nan), np.nan, ";".join(status or ["ok"])
            try:
                log2fc = float(np.log2(mean_a / mean_b))
            except Exception:
                log2fc = np.nan
                status = ["FC_error"]
                if np.isnan(p):
                    status.append("p_nan")
                return (p if np.isfinite(p) else np.nan), log2fc, ";".join(status)

            status = ["ok"] if (np.isfinite(p) or np.isfinite(log2fc)) else ["p_nan"]
            return (p if np.isfinite(p) else np.nan), log2fc, ";".join(status)
        except Exception:
            tb = traceback.format_exc().splitlines()[-1]
            return np.nan, np.nan, f"error:{tb}"

    # Run analysis (multithreaded, no progress bar)
    results = []
    if workers == 1:
        for g in genes:
            row = expr_df.loc[g]
            if isinstance(row, pd.DataFrame):
                row = row.iloc[0]
            results.append(_analyze_row(row))
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as exe:
            def _row_for_gene(g):
                row = expr_df.loc[g]
                return row.iloc[0] if isinstance(row, pd.DataFrame) else row

            mapped = exe.map(lambda g: _analyze_row(_row_for_gene(g)), genes)
            results = list(mapped)

    # Collect results preserving gene order
    pvals, lfc, status = zip(*results)
    out = pd.DataFrame({
        "Gene": genes,
        "P_value": np.array(pvals, dtype=float),
        "Log2FC": np.array(lfc, dtype=float),
        "Status": list(status),
    })

    # Multiple testing correction (Benjamini-Hochberg FDR)
    p_arr = out["P_value"].to_numpy(dtype=float)
    valid = np.isfinite(p_arr)
    qvals = np.full_like(p_arr, np.nan, dtype=float)
    if valid.any():
        try:
            _, p_adj, _, _ = multipletests(p_arr[valid], method="fdr_bh")
            qvals[valid] = p_adj
        except Exception:
            for idx in np.where(valid)[0]:
                out.at[idx, "Status"] = out.at[idx, "Status"] + ";q_adjust_error"
    out["Q_value"] = qvals

    out = out[["Gene", "P_value", "Log2FC", "Q_value", "Status"]]
    return out



def _to_set(pathways: Iterable[Any], case_sensitive: bool = False) -> set:
    if pathways is None:
        return set()
    if not case_sensitive:
        return {str(x).strip().lower() for x in pathways if pd.notna(x)}
    else:
        return {str(x).strip() for x in pathways if pd.notna(x)}


def compute_jaccard_indices(
    original_pathways: Iterable[Any],
    synth_pathways_dict: Dict[str, Iterable[Any]],
    case_sensitive: bool = False,
) -> pd.DataFrame:
    """
    The Jaccard index is defined as:
        J(A, B) = |A ∩ B| / |A ∪ B|
    """
    if not isinstance(synth_pathways_dict, dict):
        raise ValueError("synth_pathways_dict must be a dict mapping dataset name -> iterable of pathways")

    A = _to_set(original_pathways, case_sensitive=case_sensitive)
    rows = []
    for ds_name, synth_paths in synth_pathways_dict.items():
        B = _to_set(synth_paths, case_sensitive=case_sensitive)
        inter = A.intersection(B)
        union = A.union(B)
        inter_size = len(inter)
        union_size = len(union)

        if union_size == 0:
            # both sets empty -> identical
            j = 1.0
        else:
            j = inter_size / union_size

        rows.append(
            {
                "Dataset": ds_name,
                "Original_count": len(A),
                "Synthetic_count": len(B),
                "Intersection": inter_size,
                "Union": union_size,
                "Jaccard": j,
            }
        )

    df = pd.DataFrame(rows, columns=["Dataset", "Original_count", "Synthetic_count", "Intersection", "Union", "Jaccard"])
    return df




def extract_significant_genes(
    df: pd.DataFrame,
    term_col: str = "Gene",
    adj_p_col: str = "P_value",
    threshold: float = 0.05,
) -> List[str]:
    """
    Return a list of significant gene terms from a results table.

    Args:
        df (pd.DataFrame): Results table containing a term column and a p/q-value column.
        term_col (str): Column name containing gene/term identifiers. Default: "Gene".
        adj_p_col (str): Column name containing adjusted p-values (or raw p-values). Default: "P_value".
        threshold (float): Significance threshold. Terms with values < threshold are returned. Default: 0.05.

    Returns:
        List[str]: Ordered list of gene/term names that passed the threshold. Returns an empty list on invalid input.
    """
    if df is None or df.empty:
        return []

    # Ensure term column exists
    if term_col not in df.columns:
        return []

    # If requested p-value column not present, try common alternatives
    if adj_p_col not in df.columns:
        for alt in ("Q_value", "padj", "adj.P.Val", "adj_p", "adj_p_value", "FDR"):
            if alt in df.columns:
                adj_p_col = alt
                break
        else:
            return []

    # If a Status column exists, only keep rows whose Status contains the token 'ok' (case-insensitive).
    # If Status is not present, do not filter by status.
    if "Status" in df.columns:
        status_series = df["Status"].astype(str)
        # match whole word 'ok' in semi-colon separated flags or plain values
        mask_ok = status_series.str.contains(r"\bok\b", case=False, regex=True, na=False)
        df = df.loc[mask_ok]

    if df.empty:
        return []

    # Robust numeric conversion for p-value-like entries:
    # - Strings like "<1e-5" or ">0.1" are handled by stripping leading '<' or '>' before conversion.
    p_series = df[adj_p_col].astype(str).str.strip()
    p_series_clean = p_series.str.replace(r"^[<>]=?", "", regex=True)
    p_numeric = pd.to_numeric(p_series_clean, errors="coerce")

    # Select rows where p < threshold
    mask_sig = p_numeric < float(threshold)
    sub = df.loc[mask_sig].copy()
    if sub.empty:
        return []

    # Drop missing/empty term values and preserve order and uniqueness
    sub = sub[sub[term_col].notna()]
    terms = [str(x).strip() for x in sub[term_col].tolist()]
    # preserve original order but remove exact duplicates
    seen = set()
    unique_terms = []
    for t in terms:
        if t not in seen and t != "":
            seen.add(t)
            unique_terms.append(t)
    return unique_terms


def compare_spearman_degs(
    dges_results: Dict[str, pd.DataFrame],
    origin: Optional[str] = None,
    term_col: str = "Gene",
    lfc_col: str = "Log2FC",
    q_col: str = "Q_value",
    min_terms: int = 3,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Compute Spearman correlation between an origin DEG ranking and one or more other DEG rankings
    using a simple rank score = sign(Log2FC) * (-log10(Q_value)).

    Args:
        dges_results (Dict[str, pd.DataFrame]): Mapping dataset_name -> DataFrame containing genes and columns
            for log2 fold-change and adjusted p-values (or q-values).
        origin (Optional[str]): Name of the reference dataset in dges_results. If None, uses "Origin" if present,
            otherwise uses the first key in dges_results.
        term_col (str): Column name containing gene identifiers. If missing, function will use the DataFrame index.
        lfc_col (str): Column name for log2 fold-change. Default "Log2FC".
        q_col (str): Column name for adjusted p-values (Q-values). Default "Q_value".
        min_terms (int): Minimum number of overlapping terms required to compute Spearman correlation.

    Returns:
        Tuple[pd.DataFrame, pd.DataFrame]: 
            - spearman_df (pd.DataFrame): Rows for each dataset (excluding origin) with columns
              ["Dataset", "Spearman_rho", "p_value", "n_terms_used"].
            - pivot_df (pd.DataFrame): Pivot table (index=Gene, columns=Dataset) of computed rank scores.

    Raises:
        ValueError: If dges_results is empty or if the specified origin is not found.
        ValueError: If required numeric columns (lfc_col, q_col) are missing when automatic score computation is needed.
    """
    if not dges_results:
        raise ValueError("dges_results must be a non-empty dict of name -> DataFrame.")

    # determine origin dataset name
    if origin is None:
        origin = "Origin" if "Origin" in dges_results else next(iter(dges_results.keys()))
    if origin not in dges_results:
        raise ValueError(f"Origin dataset '{origin}' not found in dges_results keys.")

    records: List[tuple] = []
    for name, df in dges_results.items():
        if df is None or df.empty:
            continue

        # extract gene identifiers
        if term_col in df.columns:
            genes = df[term_col].astype(str).tolist()
            df_indexed = df.reset_index(drop=True)
        else:
            # fall back to index
            genes = df.index.astype(str).tolist()
            df_indexed = df.copy().reset_index(drop=True)

        # ensure required numeric columns exist
        if lfc_col not in df_indexed.columns or q_col not in df_indexed.columns:
            raise ValueError(f"Dataset '{name}' must contain '{lfc_col}' and '{q_col}' for automatic rank score.")

        # coerce to numeric
        lfc_s = pd.to_numeric(df_indexed[lfc_col], errors="coerce")
        q_s = pd.to_numeric(df_indexed[q_col], errors="coerce")

        # compute score = sign(LFC) * (-log10(q))  ; q <= 0 or NaN -> score = NaN
        q_positive = q_s.where(q_s > 0.0, np.nan)
        with np.errstate(divide="ignore"):
            neglogq = -np.log10(q_positive)
        score = np.sign(lfc_s) * neglogq

        # append records (align by position)
        n = min(len(genes), len(score))
        for i in range(n):
            g = genes[i]
            v = score.iat[i]
            records.append((g, name, float(v) if np.isfinite(v) else np.nan))

    if not records:
        raise ValueError("No valid records extracted from dges_results.")

    proc_df = pd.DataFrame(records, columns=[term_col, "Dataset", "Score"])

    # pivot to Genes x Datasets
    pivot_df = proc_df.pivot_table(index=term_col, columns="Dataset", values="Score", aggfunc="first")

    if origin not in pivot_df.columns:
        raise ValueError(f"Origin '{origin}' not present in computed pivot table columns.")

    origin_vals = pivot_df[origin]

    results = []
    for dataset in pivot_df.columns:
        if dataset == origin:
            continue
        y = pivot_df[dataset]
        valid_mask = origin_vals.notna() & y.notna() & np.isfinite(origin_vals) & np.isfinite(y)
        n_terms = int(valid_mask.sum())
        if n_terms < min_terms:
            rho = np.nan
            pval = np.nan
        else:
            try:
                rho, pval = spearmanr(origin_vals[valid_mask], y[valid_mask])
            except Exception:
                rho = np.nan
                pval = np.nan
        results.append({
            "Dataset": dataset,
            "Spearman_rho": float(rho) if np.isfinite(rho) else np.nan,
            "p_value": float(pval) if np.isfinite(pval) else np.nan,
            "n_terms_used": n_terms,
        })

    spearman_df = pd.DataFrame(results)

    return spearman_df, pivot_df
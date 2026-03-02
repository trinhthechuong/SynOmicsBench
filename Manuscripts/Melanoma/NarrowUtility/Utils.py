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




def extract_significances(
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


def compare_spearman(
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
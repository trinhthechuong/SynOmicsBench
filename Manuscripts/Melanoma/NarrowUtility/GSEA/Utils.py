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





def spearman_across_datasets(
    gsea_overall: Dict[str, pd.DataFrame],
    origin: Optional[str] = "Origin",
    term_col: str = "Term",
    score_col: str = "NES",
    min_terms: int = 3,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Compute Spearman correlations between an origin GSEA ranking and other datasets.

    Args:
        gsea_overall (Dict[str, pd.DataFrame]): Mapping dataset_name -> GSEA DataFrame. Each DataFrame must
            contain term identifiers (column `term_col` or use the index) and a numeric score column `score_col`
            (e.g. "NES").
        origin (Optional[str]): Name of the reference dataset in gsea_overall. If None, uses "Origin" if present,
            otherwise the first key in gsea_overall. Default: "Origin".
        term_col (str): Column name that contains term identifiers. If a DataFrame lacks this column, its index
            will be used as term identifiers. Default: "Term".
        score_col (str): Column name containing numeric scores to correlate (e.g. "NES"). Default: "NES".
        min_terms (int): Minimum number of overlapping terms required to compute Spearman correlation. If fewer,
            rho and p_value will be set to NaN for that dataset. Default: 3.

    Returns:
        Tuple[pd.DataFrame, pd.DataFrame]: 
            - spearman_df (pd.DataFrame): DataFrame with rows per dataset (excluding origin) and columns
              ["Dataset", "Spearman_rho", "p_value", "n_terms_used"].
            - pivot_df (pd.DataFrame): Pivot table with index=term, columns=dataset, values=score_col (numeric).

    Raises:
        ValueError: If gsea_overall is empty, or if the chosen origin is not present after resolution.
        ValueError: If none of the datasets contain usable term identifiers or score values.
    """
    if not isinstance(gsea_overall, dict) or len(gsea_overall) == 0:
        raise ValueError("gsea_overall must be a non-empty dict mapping dataset name -> DataFrame.")

    # Determine origin dataset name
    if origin is None:
        origin = "Origin" if "Origin" in gsea_overall else next(iter(gsea_overall.keys()))
    if origin not in gsea_overall:
        # if origin string provided but not present, try falling back to first key
        if origin is not None:
            raise ValueError(f"Origin dataset '{origin}' not found in gsea_overall keys.")
        origin = next(iter(gsea_overall.keys()))

    records: List[tuple] = []
    any_valid = False
    for name, df in gsea_overall.items():
        if df is None or not isinstance(df, pd.DataFrame):
            continue

        # Extract term identifiers: prefer column term_col, else use index
        if term_col in df.columns:
            terms = df[term_col].astype(str).tolist()
            score_series = df[score_col] if score_col in df.columns else None
        else:
            # use index as term identifiers
            terms = df.index.astype(str).tolist()
            score_series = df[score_col] if score_col in df.columns else None

        if score_series is None:
            # try to locate score_col in a case-insensitive way
            cols_lower = {c.lower(): c for c in df.columns}
            if score_col.lower() in cols_lower:
                score_series = df[cols_lower[score_col.lower()]]
            else:
                # no usable score column for this dataset: skip
                continue

        # Coerce score to numeric
        score_num = pd.to_numeric(score_series, errors="coerce")
        if score_num.isna().all():
            # no valid numeric scores -> skip
            continue

        any_valid = True
        # align by position
        n = min(len(terms), len(score_num))
        for i in range(n):
            val = score_num.iat[i] if hasattr(score_num, "iat") else score_num.iloc[i]
            records.append((str(terms[i]), name, float(val) if np.isfinite(val) else np.nan))

    if not any_valid or len(records) == 0:
        raise ValueError("No dataset contained usable term identifiers and numeric score values.")

    proc_df = pd.DataFrame(records, columns=["Term", "Dataset", "Score"])

    # Build pivot table: index Terms x columns Datasets
    pivot_df = proc_df.pivot_table(index="Term", columns="Dataset", values="Score", aggfunc="first")

    if origin not in pivot_df.columns:
        raise ValueError(f"After processing, origin '{origin}' not present in pivot table columns.")

    origin_values = pivot_df[origin]

    results: List[dict] = []
    for dataset in pivot_df.columns:
        if dataset == origin:
            continue
        y = pivot_df[dataset]

        # valid when both sides are finite numbers
        valid_mask = origin_values.notna() & y.notna() & np.isfinite(origin_values) & np.isfinite(y)
        n_terms_used = int(valid_mask.sum())
        if n_terms_used < int(min_terms):
            rho = float("nan")
            pval = float("nan")
        else:
            try:
                rho, pval = spearmanr(origin_values[valid_mask], y[valid_mask])
                # spearmanr may return masked values, coerce
                rho = float(rho) if np.isfinite(rho) else float("nan")
                pval = float(pval) if np.isfinite(pval) else float("nan")
            except Exception:
                rho = float("nan")
                pval = float("nan")

        results.append({
            "Dataset": dataset,
            "Spearman_rho": rho,
            "p_value": pval,
            "n_terms_used": n_terms_used,
        })

    spearman_df = pd.DataFrame(results)

    return spearman_df, pivot_df



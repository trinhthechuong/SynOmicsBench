"""
Recycled narrow-utility computation helpers (DGE / GSEA / ssGSEA).

The functions here are ported *verbatim in logic* from the existing manuscript
scripts/notebooks so that recomputing a dimension reproduces the stored tables:

- ``dge_analysis``  -> ``Manuscript/Melanoma/NarrowUtility/DGE/DGE.py``
- ``gsea_prerank``  -> ``Manuscript/Melanoma/NarrowUtility/GSEA/GSEA_CRPR_PD.ipynb``
- ``ssgsea_scores`` -> ``Manuscript/Melanoma/NarrowUtility/ssGSEA/ssGSEA_CRPR_PD.ipynb``

They are placed in the package (additively) rather than imported from the
Manuscript tree, which is not an importable package.
"""

from __future__ import annotations

import os
import warnings
import traceback
import concurrent.futures
from typing import Any, Dict, Iterable, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
from scipy.stats import ranksums
from statsmodels.stats.multitest import multipletests


# ---------------------------------------------------------------------------
# Phenotype labelling & gene-matrix preparation
# ---------------------------------------------------------------------------

def derive_labels(
    df: pd.DataFrame,
    source_col: str,
    responder_values: Sequence[str],
    progressor_values: Sequence[str],
    label_col: str,
    label_values: Tuple[str, str],
) -> pd.DataFrame:
    """Add a two-group ``label_col`` derived from ``source_col`` (e.g. BR -> Labels).

    Rows whose ``source_col`` is in neither group get NaN and are ignored downstream.
    """
    out = df.copy()
    group_a, group_b = label_values
    # Build as an object-dtype column so string labels can be assigned (pandas 2.x
    # refuses to place strings into a float column initialised with NaN).
    labels = pd.Series(pd.NA, index=out.index, dtype=object)
    labels[out[source_col].isin(list(responder_values))] = group_a
    labels[out[source_col].isin(list(progressor_values))] = group_b
    out[label_col] = labels
    return out


def build_gene_matrix(df: pd.DataFrame, gene_cols: Sequence[str]) -> pd.DataFrame:
    """Return a gene-by-sample DataFrame with a leading ``Gene`` column.

    Sample columns are the DataFrame index (Patient / Patient_ID), matching the
    manuscript driver which reads the CSVs with ``index_col=0`` and transposes.
    """
    present = [c for c in gene_cols if c in df.columns]
    genes_exp = df[present]
    genes_exp_t = genes_exp.T.reset_index()
    genes_exp_t.columns.values[0] = "Gene"
    return genes_exp_t


# ---------------------------------------------------------------------------
# DGE (differential gene expression) — Wilcoxon rank-sum + BH-FDR + Log2FC
# ---------------------------------------------------------------------------

def dge_analysis(
    gene_expressions: pd.DataFrame,
    metadata: pd.DataFrame,
    phenotypes: Dict[str, Iterable[Any]],
    id_col: str,
    n_jobs: int = -1,
) -> pd.DataFrame:
    """Per-gene differential expression (Wilcoxon rank-sum), ported from DGE.py.

    Returns a table with columns ``[Gene, P_value, Log2FC, Q_value, Status]`` in the
    same row order as ``gene_expressions``.
    """
    if not isinstance(phenotypes, dict) or len(phenotypes) != 1:
        raise ValueError("phenotypes must be a dict with a single key mapping to two phenotype values.")
    ph_col, ph_vals = next(iter(phenotypes.items()))
    ph_vals = list(ph_vals)
    if len(ph_vals) != 2:
        raise ValueError(f"Phenotype values list must contain exactly two values, got: {ph_vals}")
    A_val, B_val = ph_vals

    if ph_col not in metadata.columns:
        raise ValueError(f"Phenotype column '{ph_col}' not found in metadata.")
    if id_col not in metadata.columns:
        raise ValueError(f"ID column '{id_col}' not found in metadata.")

    expr_df = gene_expressions.copy()
    if "Gene" in expr_df.columns:
        expr_df.index = expr_df["Gene"].astype(str)
        expr_df = expr_df.drop(columns=["Gene"])
    else:
        expr_df.index = expr_df.index.astype(str)
    expr_df.columns = expr_df.columns.astype(str)

    sampA_all = metadata.loc[metadata[ph_col] == A_val, id_col].astype(str).tolist()
    sampB_all = metadata.loc[metadata[ph_col] == B_val, id_col].astype(str).tolist()
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

    if n_jobs == -1:
        workers = max(1, (os.cpu_count() or 1))
    elif n_jobs <= 0:
        workers = 1
    else:
        workers = int(n_jobs)

    def _to_float_array(values) -> np.ndarray:
        return np.array(pd.to_numeric(values, errors="coerce"), dtype=float)

    def _analyze_row(row) -> Tuple[Optional[float], Optional[float], str]:
        try:
            a_raw = _to_float_array(row[sampA].values)
            b_raw = _to_float_array(row[sampB].values)
            if np.isposinf(a_raw).any() and np.isneginf(a_raw).any():
                return np.nan, np.nan, "A_contains_posinf_and_neginf"
            if np.isposinf(b_raw).any() and np.isneginf(b_raw).any():
                return np.nan, np.nan, "B_contains_posinf_and_neginf"
            a_finite = a_raw[np.isfinite(a_raw)]
            b_finite = b_raw[np.isfinite(b_raw)]
            if a_finite.size == 0 or b_finite.size == 0:
                return np.nan, np.nan, "No_data"
            if (
                a_finite.size > 0
                and b_finite.size > 0
                and np.all(a_finite == a_finite[0])
                and np.all(b_finite == b_finite[0])
                and a_finite[0] == b_finite[0]
            ):
                return 1.0, 0.0, "Identical"
            try:
                _, p = ranksums(a_finite, b_finite)
            except Exception:
                p = np.nan
            mean_a = float(np.nanmean(a_finite)) if a_finite.size else np.nan
            mean_b = float(np.nanmean(b_finite)) if b_finite.size else np.nan
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

    pvals, lfc, status = zip(*results)
    out = pd.DataFrame({
        "Gene": genes,
        "P_value": np.array(pvals, dtype=float),
        "Log2FC": np.array(lfc, dtype=float),
        "Status": list(status),
    })
    p_arr = out["P_value"].to_numpy(dtype=float)
    valid = np.isfinite(p_arr)
    qvals = np.full_like(p_arr, np.nan, dtype=float)
    if valid.any():
        try:
            _, p_adj, _, _ = multipletests(p_arr[valid], method="fdr_bh")
            qvals[valid] = p_adj
        except Exception:
            pass
    out["Q_value"] = qvals
    out = out[["Gene", "P_value", "Log2FC", "Q_value", "Status"]]
    return out


# ---------------------------------------------------------------------------
# GSEA (pre-ranked) — recycled from GSEA_CRPR_PD.ipynb
# ---------------------------------------------------------------------------

def gsea_prerank(
    dge_table: pd.DataFrame,
    gene_set: str,
    seed: int,
    permutation_num: int = 10000,
    threads: int = 4,
) -> pd.DataFrame:
    """Run pre-ranked GSEA on a DGE table and return a table with Term/NES/FDR q-val.

    Ranking metric = ``sign(Log2FC) * -log10(P_value)`` with a tiny seeded jitter to
    break ties (matching the manuscript notebook).
    """
    import gseapy

    df = dge_table.copy()
    if "Status" in df.columns:
        df = df[df["Status"].astype(str).str.contains(r"\bok\b", case=False, regex=True, na=False)]
    df = df.dropna(subset=["Gene", "Log2FC", "P_value"])

    p = pd.to_numeric(df["P_value"], errors="coerce")
    lfc = pd.to_numeric(df["Log2FC"], errors="coerce")
    rng = np.random.default_rng(seed)
    jitter = rng.uniform(-1e-10, 1e-10, size=len(df))
    rank_metric = np.sign(lfc) * (-np.log10(p.clip(lower=1e-300))) + jitter

    rnk = (
        pd.DataFrame({"Gene": df["Gene"].astype(str).values, "score": rank_metric.values})
        .dropna()
        .groupby("Gene", as_index=True)["score"]
        .mean()
        .sort_values(ascending=False)
    )
    rnk = rnk.reset_index()

    pre = gseapy.prerank(
        rnk=rnk,
        gene_sets=gene_set,
        threads=threads,
        permutation_num=permutation_num,
        outdir=None,
        seed=seed,
        verbose=False,
    )
    res = pre.res2d.reset_index()
    res = _standardize_gsea_columns(res)
    return res


def _standardize_gsea_columns(res: pd.DataFrame) -> pd.DataFrame:
    """Ensure a GSEA result table exposes ``Term``, ``NES`` and ``FDR q-val`` columns."""
    res = res.copy()
    cols = {c.lower(): c for c in res.columns}
    if "Term" not in res.columns:
        for cand in ("term", "name"):
            if cand in cols:
                res = res.rename(columns={cols[cand]: "Term"})
                break
    if "NES" not in res.columns and "nes" in cols:
        res = res.rename(columns={cols["nes"]: "NES"})
    if "FDR q-val" not in res.columns:
        for cand in ("fdr q-val", "fdr", "fdr_qval", "fdr q val"):
            if cand in cols:
                res = res.rename(columns={cols[cand]: "FDR q-val"})
                break
    return res


# ---------------------------------------------------------------------------
# ssGSEA — recycled from ssGSEA_CRPR_PD.ipynb
# ---------------------------------------------------------------------------

def ssgsea_scores(
    gene_matrix: pd.DataFrame,
    gene_set: str,
    sample_norm_method: str = "log_rank",
) -> pd.DataFrame:
    """Run ssGSEA on a gene-by-sample matrix and return a long table (Name, Term, NES).

    ``gene_matrix`` must have a ``Gene`` column (genes) and one column per sample.
    """
    import gseapy

    df = gene_matrix.copy()
    if "Gene" in df.columns:
        df = df.set_index("Gene")
    ss = gseapy.ssgsea(
        data=df,
        gene_sets=gene_set,
        sample_norm_method=sample_norm_method,
        no_plot=True,
        outdir=None,
    )
    res = ss.res2d.copy()
    # gseapy ssgsea res2d columns: Name (sample), Term, ES, NES
    cols = {c.lower(): c for c in res.columns}
    if "NES" not in res.columns and "nes" in cols:
        res = res.rename(columns={cols["nes"]: "NES"})
    if "Name" not in res.columns and "name" in cols:
        res = res.rename(columns={cols["name"]: "Name"})
    if "Term" not in res.columns and "term" in cols:
        res = res.rename(columns={cols["term"]: "Term"})
    return res


def pivot_ssgsea(long_df: pd.DataFrame) -> pd.DataFrame:
    """Pivot a long ssGSEA table (Name, Term, NES) to samples×pathways of NES values."""
    df = long_df.copy()
    df["NES"] = pd.to_numeric(df["NES"], errors="coerce")
    return df.pivot(index="Name", columns="Term", values="NES")

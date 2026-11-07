"""
Per-dimension runners for the automatic benchmark.

Each runner evaluates one meta-score dimension over a list of candidate synthetic
datasets and returns a long DataFrame with columns ``['Model', 'Seed', 'Value']``
(``Value`` is the higher-is-better score for that candidate). Runners support:

- ``mode="compute"`` : recompute the dimension from the raw data (reuses the
  existing metric classes / recycled helpers).
- ``mode="reuse"``   : load precomputed intermediate artifacts and (re)score.
- ``mode="skip"``    : return an empty frame.

They never write into existing result directories; any transient output goes to
``config.output_dir``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Union

import numpy as np
import pandas as pd

from synomicsbench.processing.metadata import MetaData
from synomicsbench.processing.postprocessing import post_masking
from synomicsbench.metrics.fidelity.UnivariateSimilarity import UnivariateSimilarity
from synomicsbench.metrics.fidelity.PairwiseSimilarity import PairwiseSimilarity
from synomicsbench.metrics.narrow_utility.DGE import GCSAnalyzer
from synomicsbench.metrics.narrow_utility.GSEA import PCSAnalyzer
from synomicsbench.metrics.narrow_utility.survival_analysis import SurvivalEvaluator
from synomicsbench.metrics.narrow_utility import cell_deconvolution as celldeco

from . import compute as _compute
from . import privacy as _privacy
from .config import BenchmarkConfig


ORIGIN = "Origin"


@dataclass
class Candidate:
    """A single synthetic dataset to evaluate."""
    method: str            # display name, e.g. "Gaussian Copula"
    seed: int
    data: Union[str, pd.DataFrame]

    @property
    def stem_key(self) -> str:
        return f"{self.method}_{self.seed}"


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def load_frame(src: Union[str, pd.DataFrame], id_column: str) -> pd.DataFrame:
    """Load a dataset (path or DataFrame), using ``id_column`` as the index if present."""
    df = pd.read_csv(src, index_col=0) if isinstance(src, str) else src.copy()
    # If the ID column is a regular column, make it the index (matches the manuscript readers).
    if id_column in df.columns:
        df = df.set_index(id_column)
    return df


def load_metadata(config: BenchmarkConfig) -> dict:
    if isinstance(config.metadata, dict):
        return config.metadata
    if isinstance(config.metadata, str):
        return MetaData.load(config.metadata)
    raise ValueError("config.metadata must be a dict or a path to a metadata JSON.")


def _sub_metadata(metadata: dict, columns: Sequence[str]) -> dict:
    return {c: metadata[c] for c in columns if c in metadata}


def _maybe_mask(df: pd.DataFrame, config: BenchmarkConfig) -> pd.DataFrame:
    """Apply ``post_masking`` if fidelity masking is enabled (no-op without indicators)."""
    return post_masking(df) if config.fidelity_masking else df


def _fidelity_metadata(block: pd.DataFrame, config: BenchmarkConfig,
                       ordinal_features=None, transcriptomic_cols=None) -> dict:
    """Regenerate fidelity metadata for a block, mirroring the manuscript notebooks."""
    return MetaData.get_metadata(
        data=block,
        threshold_unique_values=config.threshold_unique_values,
        ordinal_features=ordinal_features,
        transcriptomic_cols=transcriptomic_cols,
    )


def _tmp_dir(config: BenchmarkConfig, name: str) -> str:
    path = os.path.join(config.output_dir, "_work", name)
    os.makedirs(path, exist_ok=True)
    return path


def _empty() -> pd.DataFrame:
    return pd.DataFrame(columns=["Model", "Seed", "Value"])


# ---------------------------------------------------------------------------
# Univariate
# ---------------------------------------------------------------------------

def run_univariate(original: pd.DataFrame, candidates: List[Candidate],
                   config: BenchmarkConfig, mode: str) -> pd.DataFrame:
    if mode == "skip":
        return _empty()
    clinical, omic = config.resolve_columns(original.columns)
    rows = []
    if mode == "compute":
        ordinal = config.ordinal_features(load_metadata(config))
        # Clinical: mask (re-introduce missing values, drop indicators) + regenerate metadata.
        mor_clin = _maybe_mask(original[clinical], config)
        meta_clin = _fidelity_metadata(mor_clin, config, ordinal_features=ordinal)
        # Transcriptomic: no masking, regenerate metadata (low-unique genes -> categorical).
        mor_omic = original[omic]
        meta_omic = _fidelity_metadata(mor_omic, config, ordinal_features=None)
        for cand in candidates:
            syn = load_frame(cand.data, config.id_column)
            msyn_clin = _maybe_mask(syn[clinical], config)
            clin_mean = _uni_block_mean(mor_clin, msyn_clin, meta_clin, config, f"{cand.stem_key}_clin")
            omic_mean = _uni_block_mean(mor_omic, syn[omic], meta_omic, config, f"{cand.stem_key}_omic")
            rows.append({"Model": cand.method, "Seed": cand.seed, "Value": 0.5 * (clin_mean + omic_mean)})
    elif mode == "reuse":
        pre = _require(config.precomputed_dir, "precomputed_dir", "Univariate")
        for cand in candidates:
            stem = config.name_map[cand.method]
            clin = pd.read_csv(os.path.join(
                pre, "BroadUtility", "UniClinicalSimi", f"UniClinicalSimi_{cand.seed}",
                f"Detail_score_{stem}_{cand.seed}.csv"))["Score"].fillna(0).mean()
            omic = pd.read_csv(os.path.join(
                pre, "BroadUtility", "UniTranscriptomicsSimi", f"UniTranscriptomicsSimi_{cand.seed}",
                f"Detail_score_{stem}_{cand.seed}.csv"))["Score"].fillna(0).mean()
            rows.append({"Model": cand.method, "Seed": cand.seed, "Value": 0.5 * (clin + omic)})
    return pd.DataFrame(rows)


def _uni_block_mean(orig_block, syn_block, metadata, config, tag) -> float:
    uni = UnivariateSimilarity(output_dir=_tmp_dir(config, "univariate"), logger_name=tag)
    uni.get_univariate_score(original_data=orig_block, synthetic_data=syn_block, metadata=metadata, save=False)
    return float(uni.get_detail_df()["Score"].fillna(0).mean())


# ---------------------------------------------------------------------------
# Bivariate
# ---------------------------------------------------------------------------

def run_bivariate(original: pd.DataFrame, candidates: List[Candidate],
                  config: BenchmarkConfig, mode: str) -> pd.DataFrame:
    if mode == "skip":
        return _empty()
    clinical, omic = config.resolve_columns(original.columns)
    rows = []
    if mode == "compute":
        ordinal = config.ordinal_features(load_metadata(config))
        # Clinical block: mask + metadata with ordinal features.
        mor_clin = _maybe_mask(original[clinical], config)
        meta_clin = _fidelity_metadata(mor_clin, config, ordinal_features=ordinal)
        # Transcriptomic block: no masking.
        mor_omic = original[omic]
        meta_omic = _fidelity_metadata(mor_omic, config, ordinal_features=None)
        # Cross-group: mask the full feature frame, split into (clinical, transcriptomic).
        mor_full = _maybe_mask(original[list(clinical) + list(omic)], config)
        clin_feat = [c for c in clinical if c in mor_full.columns]
        trans_feat = [c for c in omic if c in mor_full.columns]
        meta_cross = _fidelity_metadata(mor_full, config, ordinal_features=None, transcriptomic_cols=trans_feat)
        for cand in candidates:
            syn = load_frame(cand.data, config.id_column)
            msyn_clin = _maybe_mask(syn[clinical], config)
            clin_mean = _pairwise_block_mean(mor_clin, msyn_clin, meta_clin, config, f"{cand.stem_key}_clin")
            omic_mean = _pairwise_block_mean(mor_omic, syn[omic], meta_omic, config, f"{cand.stem_key}_omic")
            msyn_full = _maybe_mask(syn[list(clinical) + list(omic)], config)
            cross_mean = _pairwise_cross_mean(mor_full, msyn_full, clin_feat, trans_feat, meta_cross, config, cand.stem_key)
            rows.append({"Model": cand.method, "Seed": cand.seed,
                         "Value": (clin_mean + omic_mean + cross_mean) / 3.0})
    elif mode == "reuse":
        pre = _require(config.precomputed_dir, "precomputed_dir", "Bivariate")
        for cand in candidates:
            stem = config.name_map[cand.method]
            s = cand.seed
            clin = np.load(os.path.join(pre, "BroadUtility", "PairwiseClinical",
                                        f"PairwiseClinical_{s}", f"bivariate_{stem}_{s}_all.npy"))
            omic = np.load(os.path.join(pre, "BroadUtility", "PairwiseTranscriptomicsSimi",
                                        f"PairwiseTranscriptomicsSimi_{s}", f"{stem}_{s}_all.npy"))
            cross = pd.read_csv(os.path.join(pre, "BroadUtility", "PairwiseCrossGroup",
                                             f"CrossGroup_{s}", f"{stem}_{s}_cross_group_full.csv"))["Score"].fillna(0)
            value = (np.nanmean(clin) + np.nanmean(omic) + cross.mean()) / 3.0
            rows.append({"Model": cand.method, "Seed": cand.seed, "Value": value})
    return pd.DataFrame(rows)


def _pairwise_block_mean(orig_block, syn_block, meta, config, tag) -> float:
    ps = PairwiseSimilarity(orig_block, syn_block, meta, output_dir=_tmp_dir(config, "bivariate"),
                            save=False, name=tag)
    res = ps.get_pairwise_scores(method=config.corr_method, n_bins=config.n_bins)
    return float(np.nanmean(res["PairwiseScore"]))


def _pairwise_cross_mean(orig_full, syn_full, clin_feat, trans_feat, meta_full, config, tag) -> float:
    ps = PairwiseSimilarity(orig_full, syn_full, meta_full, output_dir=_tmp_dir(config, "bivariate"),
                            save=False, name=f"{tag}_cross")
    ps.get_pairwise_scores(method=config.corr_method, n_bins=config.n_bins)
    cross = ps.get_cross_group_associations(list(clin_feat), list(trans_feat))
    return float(cross["Score"].fillna(0).mean())


# ---------------------------------------------------------------------------
# DGE (F1-GCS)
# ---------------------------------------------------------------------------

def run_dge(original: pd.DataFrame, candidates: List[Candidate],
            config: BenchmarkConfig, mode: str) -> pd.DataFrame:
    if mode == "skip":
        return _empty()
    rows = []
    analyzer = GCSAnalyzer(term_col="Gene", nes_col="Log2FC", sig_col="P_value", seed=42, sig_thr=0.05)
    if mode == "compute":
        _, omic = config.resolve_columns(original.columns)
        origin_dge = _dge_table(original, omic, config)
        for cand in candidates:
            # A degenerate synthetic can collapse a phenotype group (e.g. no PD in BR), which
            # makes _dge_table raise. Record NaN for that one candidate instead of aborting the
            # whole dimension for every other candidate.
            try:
                syn = load_frame(cand.data, config.id_column)
                syn_dge = _dge_table(syn, omic, config)
                f1 = float(analyzer.process_single_dge_result(origin_dge, syn_dge)[2].f1)
            except Exception as exc:
                print(f"[autobenchmark] DGE skipped for {cand.method} (seed {cand.seed}): "
                      f"{type(exc).__name__}: {exc}", flush=True)
                f1 = float("nan")
            rows.append({"Model": cand.method, "Seed": cand.seed, "Value": f1})
    elif mode == "reuse":
        pre = _require(config.precomputed_dir, "precomputed_dir", "DGE")
        base = os.path.join(pre, "NarrowUtility", "DGE", "CRPR_PD")
        origin_path = os.path.join(base, f"Seed_{candidates[0].seed}", "DGE_Origin.csv")
        for cand in candidates:
            stem = config.name_map[cand.method]
            syn_path = os.path.join(base, f"Seed_{cand.seed}", f"DGE_{stem}_{cand.seed}.csv")
            f1 = analyzer.process_single_dge_result(origin_path, syn_path)[2].f1
            rows.append({"Model": cand.method, "Seed": cand.seed, "Value": float(f1)})
    return pd.DataFrame(rows)


def _dge_table(df: pd.DataFrame, gene_cols, config: BenchmarkConfig) -> pd.DataFrame:
    labelled = _compute.derive_labels(df, config.phenotype_source_col, config.responder_values,
                                      config.progressor_values, config.label_col, config.label_values)
    meta = pd.DataFrame({config.id_column: labelled.index, config.label_col: labelled[config.label_col].values})
    gene_matrix = _compute.build_gene_matrix(labelled, gene_cols)
    phenotypes = {config.label_col: list(config.label_values)}
    return _compute.dge_analysis(gene_matrix, meta, phenotypes, id_col=config.id_column, n_jobs=-1)


# ---------------------------------------------------------------------------
# GSEA (F1-PCS)
# ---------------------------------------------------------------------------

def run_gsea(original: pd.DataFrame, candidates: List[Candidate],
             config: BenchmarkConfig, mode: str) -> pd.DataFrame:
    if mode == "skip":
        return _empty()
    rows = []
    analyzer = PCSAnalyzer(term_col="Term", nes_col="NES", sig_col="FDR q-val", seed=42, sig_thr=0.05)
    if mode == "compute":
        gene_set = _require(config.gene_set, "gene_set", "GSEA")
        _, omic = config.resolve_columns(original.columns)
        origin_dge = _dge_table(original, omic, config)
        origin_gsea = _compute.gsea_prerank(origin_dge, gene_set, seed=42, permutation_num=config.gsea_permutations)
        for cand in candidates:
            syn = load_frame(cand.data, config.id_column)
            syn_dge = _dge_table(syn, omic, config)
            syn_gsea = _compute.gsea_prerank(syn_dge, gene_set, seed=cand.seed,
                                             permutation_num=config.gsea_permutations)
            f1 = analyzer.process_single_gsea_result(origin_gsea, syn_gsea)[2].f1
            rows.append({"Model": cand.method, "Seed": cand.seed, "Value": float(f1)})
    elif mode == "reuse":
        pre = _require(config.precomputed_dir, "precomputed_dir", "GSEA")
        base = os.path.join(pre, "NarrowUtility", "GSEA", "CRPR_PD")
        origin_path = os.path.join(base, f"Seed_{candidates[0].seed}", "GSEA_Origin.csv")
        for cand in candidates:
            stem = config.name_map[cand.method]
            syn_path = os.path.join(base, f"Seed_{cand.seed}", f"GSEA_{stem}_{cand.seed}.csv")
            f1 = analyzer.process_single_gsea_result(origin_path, syn_path)[2].f1
            rows.append({"Model": cand.method, "Seed": cand.seed, "Value": float(f1)})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# ssGSEA (KSComplement)
# ---------------------------------------------------------------------------

def run_ssgsea(original: pd.DataFrame, candidates: List[Candidate],
               config: BenchmarkConfig, mode: str) -> pd.DataFrame:
    if mode == "skip":
        return _empty()
    rows = []
    if mode == "compute":
        gene_set = _require(config.gene_set, "gene_set", "ssGSEA")
        _, omic = config.resolve_columns(original.columns)
        origin_pivot = _ssgsea_pivot(original, omic, gene_set)
        for cand in candidates:
            syn = load_frame(cand.data, config.id_column)
            syn_pivot = _ssgsea_pivot(syn, omic, gene_set)
            common = origin_pivot.columns.intersection(syn_pivot.columns)
            meta = MetaData.get_metadata(data=origin_pivot[common], threshold_unique_values=10, ordinal_features=None)
            uni = UnivariateSimilarity(output_dir=_tmp_dir(config, "ssgsea"), logger_name=f"{cand.stem_key}")
            uni.get_univariate_score(original_data=origin_pivot[common], synthetic_data=syn_pivot[common],
                                     metadata=meta, save=False)
            value = float(uni.get_detail_df()["Score"].fillna(0).mean())
            rows.append({"Model": cand.method, "Seed": cand.seed, "Value": value})
    elif mode == "reuse":
        pre = _require(config.precomputed_dir, "precomputed_dir", "ssGSEA")
        for cand in candidates:
            stem = config.name_map[cand.method]
            path = os.path.join(pre, "NarrowUtility", "ssGSEA", "KSStatistic", f"Seed_{cand.seed}",
                                f"Detail_score_{stem}_{cand.seed}.csv")
            value = float(pd.read_csv(path)["Score"].fillna(0).mean())
            rows.append({"Model": cand.method, "Seed": cand.seed, "Value": value})
    return pd.DataFrame(rows)


def _ssgsea_pivot(df: pd.DataFrame, gene_cols, gene_set) -> pd.DataFrame:
    gene_matrix = _compute.build_gene_matrix(df, gene_cols)
    long = _compute.ssgsea_scores(gene_matrix, gene_set)
    return _compute.pivot_ssgsea(long)


# ---------------------------------------------------------------------------
# Cell deconvolution (Aitchison score)
# ---------------------------------------------------------------------------

def run_cell_deconvolution(original: pd.DataFrame, candidates: List[Candidate],
                           config: BenchmarkConfig, mode: str) -> pd.DataFrame:
    if mode == "skip":
        return _empty()
    if mode == "compute":
        raise ValueError(
            "Cell deconvolution cannot be computed inside the pipeline (CIBERSORTx is external). "
            "Use mode='reuse' with config.cibersortx_dir pointing at CIBERSORTx result CSVs."
        )
    cdir = _require(config.cibersortx_dir, "cibersortx_dir", "Cell Deconvolution")
    origin = pd.read_csv(os.path.join(cdir, "CIBERSORTx_Origin_Results.csv"), index_col=0)
    cell_types = origin.iloc[:, 0:22].mean().sort_values(ascending=False).keys().tolist()[0:config.top_k_cell_types]
    rows = []
    for cand in candidates:
        stem = config.name_map[cand.method]
        syn_path = os.path.join(cdir, f"CIBERSORTx_{stem}_{cand.seed}_Results.csv")
        syn = pd.read_csv(syn_path, index_col=0)
        dist = celldeco.aitchison_distance(origin, syn, cell_types)
        rows.append({"Model": cand.method, "Seed": cand.seed, "Value": float(celldeco.aitchison_score(dist))})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Survival (C-index score)
# ---------------------------------------------------------------------------

def run_survival(original: pd.DataFrame, candidates: List[Candidate],
                 config: BenchmarkConfig, mode: str) -> pd.DataFrame:
    if mode == "skip":
        return _empty()
    if mode == "compute":
        return _survival_compute(original, candidates, config)
    # reuse
    pre = _require(config.precomputed_dir, "precomputed_dir", "Survival Analysis")
    rows = []
    for cand in candidates:
        vals = []
        for endpoint, sub in zip(config.survival_endpoints, ("OS", "PFS")):
            path = os.path.join(pre, "NarrowUtility", "SA", "SurvivalAnalysis", sub,
                                f"Seed_{cand.seed}", f"score_{sub.lower()}.csv")
            df = pd.read_csv(path, index_col=0)
            vals.append(_cindex_for(df, cand.method))
        rows.append({"Model": cand.method, "Seed": cand.seed, "Value": float(np.mean(vals))})
    return pd.DataFrame(rows)


def _cindex_for(df: pd.DataFrame, method: str) -> float:
    row = df[df["Dataset"] == method]
    return float(pd.to_numeric(row["C-index_score"], errors="coerce").fillna(0).iloc[0]) if len(row) else 0.0


def _survival_compute(original: pd.DataFrame, candidates: List[Candidate],
                      config: BenchmarkConfig) -> pd.DataFrame:
    # Build a single datasets_dict {Origin + each candidate}, with Labels derived.
    def prep(df):
        return _compute.derive_labels(df, config.phenotype_source_col, config.responder_values,
                                      config.progressor_values, config.label_col, config.label_values)
    # Key synthetic datasets by "{method}_{seed}" so multiple seeds of the same method
    # don't collide in the datasets_dict.
    datasets = {ORIGIN: prep(original)}
    for cand in candidates:
        datasets[cand.stem_key] = prep(load_frame(cand.data, config.id_column))

    # C-index score per candidate per endpoint (OS, PFS).
    per_endpoint = []
    for (time_col, event_col) in config.survival_endpoints:
        ev = SurvivalEvaluator(datasets_dict=datasets, phenotype={config.label_col: list(config.label_values)},
                               time_target=time_col, event_target=event_col, original_name=ORIGIN)
        ev.compute_survival_metrics()
        scored = ev.compute_cindex_scores(original_name=ORIGIN)
        per_endpoint.append(scored.set_index("Dataset")["C-index_score"])
    combined = pd.concat(per_endpoint, axis=1)
    rows = []
    for cand in candidates:
        if cand.stem_key in combined.index:
            value = float(pd.to_numeric(combined.loc[cand.stem_key], errors="coerce").fillna(0).mean())
        else:
            value = 0.0
        rows.append({"Model": cand.method, "Seed": cand.seed, "Value": value})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Network preservation (normalized Z-summary)
# ---------------------------------------------------------------------------

def run_network(original: pd.DataFrame, candidates: List[Candidate],
                config: BenchmarkConfig, mode: str) -> pd.DataFrame:
    if mode == "skip":
        return _empty()
    if mode == "reuse":
        table = pd.read_csv(_require(config.network_csv, "network_csv", "Network Preservation"))
        table = table.rename(columns={"Tool": "Model", "Method": "Model"})
        values = table.set_index(["Model", "Seed"])["Value"]
        rows = [{"Model": c.method, "Seed": c.seed, "Value": float(values.get((c.method, c.seed), np.nan))}
                for c in candidates]
        return pd.DataFrame(rows)

    from synomicsbench.metrics.fidelity.NetworkPreservation import NetworkPreservation

    _, omic = config.resolve_columns(original.columns)
    npres = NetworkPreservation(
        output_dir=_tmp_dir(config, "network"),
        n_genes=config.network_n_genes,
        n_permutations=config.network_n_permutations,
        log_transform=config.network_log_transform,
        threads=config.network_threads,
    )
    npres.build_reference(original[omic])
    syns = {cand.stem_key: load_frame(cand.data, config.id_column)[omic] for cand in candidates}
    scores = npres.evaluate(syns, metrics="Zsummary_norm")
    return pd.DataFrame([{"Model": c.method, "Seed": c.seed,
                          "Value": float(scores.loc[c.stem_key, "Zsummary_norm"])} for c in candidates])


# ---------------------------------------------------------------------------
# Privacy (one dimension per attack category; value = 1 - risk)
# ---------------------------------------------------------------------------

def run_privacy(original: pd.DataFrame, candidates: List[Candidate],
                config: BenchmarkConfig, mode: str,
                privacy_csv=None) -> Dict[str, pd.DataFrame]:
    """Privacy scores (1 - mean risk) of the four attack categories.

    ``compute`` runs the attacks (against ``config.privacy_control`` when given, which gives
    residual risks); ``reuse`` reads a long risk table (``privacy_csv``, see
    :func:`~synomicsbench.metrics.autobenchmark.privacy.category_risks_from_table`) or the
    saved anonymeter pickles under ``config.privacy_pickle_dir``.

    Returns:
        dict: dimension name -> DataFrame [Model, Seed, Value].
    """
    if mode == "skip":
        return {}
    if mode == "compute":
        risks = _privacy_compute(original, candidates, config)
    elif privacy_csv is not None:
        table = _privacy.category_risks_from_table(privacy_csv)
        risks = {dim: {(r.Model, r.Seed): r.Risk for r in sub.itertuples()}
                 for dim, sub in table.groupby("Dimension")}
    else:
        pdir = _require(config.privacy_pickle_dir, "privacy_pickle_dir", "Privacy")
        tools = list(dict.fromkeys(c.method for c in candidates))
        risks = {}
        for seed in sorted({c.seed for c in candidates}):
            for dim, by_tool in _privacy.category_risks_from_pickles(pdir, seed, tools).items():
                risks.setdefault(dim, {}).update({(tool, seed): r for tool, r in by_tool.items()})

    out = {}
    for dim, by_key in risks.items():
        rows = [{"Model": c.method, "Seed": c.seed, "Value": 1.0 - float(by_key[(c.method, c.seed)])}
                for c in candidates if (c.method, c.seed) in by_key]
        out[dim] = pd.DataFrame(rows, columns=["Model", "Seed", "Value"])
    return out


def _privacy_compute(original: pd.DataFrame, candidates: List[Candidate],
                     config: BenchmarkConfig) -> Dict[str, Dict[tuple, float]]:
    """Run the four anonymeter attacks live (via the ``metrics.privacy`` functions).

    Stochastic and slow. The clinical columns are always known to the attacker; univariate
    singling out, linkability and inference run at every knowledge level (named gene sets,
    then gene fractions), multivariate singling out on all columns. With
    ``config.privacy_control`` the risks are residual risks.

    Returns:
        dict: dimension name -> {(method, seed): mean risk}.
    """
    from synomicsbench.metrics.privacy.inference import eval_inference_genes_clinical
    from synomicsbench.metrics.privacy.knowledge import knowledge_levels
    from synomicsbench.metrics.privacy.linkability import eval_linkability_genes_clinical
    from synomicsbench.metrics.privacy.singling_out import (
        eval_singling_out_multivariate, eval_singling_out_univariate)

    clinical, transcriptomic = config.resolve_columns(original.columns)
    cols = list(clinical) + list(transcriptomic)
    ori = original[cols]
    syns = {cand.stem_key: load_frame(cand.data, config.id_column)[cols] for cand in candidates}
    control = None
    if config.privacy_control is not None:
        control = load_frame(config.privacy_control, config.id_column)[cols]

    uni = eval_singling_out_univariate(
        ori, syns, n_attacks=config.privacy_n_attacks, max_attempts=config.privacy_max_attempts,
        proportions=tuple(config.privacy_so_uni_proportions), seed=config.privacy_seed,
        control=control, clinical_cols=clinical, transcriptomic_cols=transcriptomic,
        gene_sets=config.privacy_gene_sets, feature_seed=config.privacy_feature_seed)
    multi = eval_singling_out_multivariate(
        ori, syns, n_cols_list=tuple(config.privacy_so_multi_n_cols),
        n_attacks=config.privacy_n_attacks, max_attempts=config.privacy_max_attempts,
        seed=config.privacy_seed, control=control)
    link = eval_linkability_genes_clinical(
        ori, syns, clinical_cols=clinical, transcriptomic_cols=transcriptomic,
        n_neighbors=config.privacy_link_n_neighbors,
        proportions=tuple(config.privacy_link_proportions), seed=config.privacy_feature_seed,
        control=control, gene_sets=config.privacy_gene_sets)
    infer: Dict[str, list] = {key: [] for key in syns}
    for _, level_cols in knowledge_levels(clinical, transcriptomic, tuple(config.privacy_link_proportions),
                                          config.privacy_gene_sets, config.privacy_feature_seed):
        level = eval_inference_genes_clinical(
            ori, syns, clinical_cols=clinical, transcriptomic_cols=level_cols[len(clinical):],
            control=control)
        for key, items in level.items():
            infer[key].extend(items)

    by_stem = _privacy.category_risks_from_attacks(uni, multi, link, infer)
    return {dim: {(c.method, c.seed): risks[c.stem_key] for c in candidates if c.stem_key in risks}
            for dim, risks in by_stem.items()}


# ---------------------------------------------------------------------------
# util
# ---------------------------------------------------------------------------

def _require(value, name, dim):
    if value is None:
        raise ValueError(f"config.{name} is required for dimension '{dim}'.")
    return value

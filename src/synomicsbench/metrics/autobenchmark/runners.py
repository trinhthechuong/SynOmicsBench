"""
Per-dimension runners for the automatic benchmark.

Each runner computes one meta-score dimension for a list of candidate synthetic datasets and
returns a long DataFrame with columns ``['Model', 'Seed', 'Value']``. ``Value`` is a score
(higher = better), or a risk for the privacy dimensions (lower = better). Every dimension is
computed from the original and synthetic data, except Cell Deconvolution, which reads the
CIBERSORTx results given in ``config.cibersortx``.

Intermediate files go to ``<config.output_dir>/_work``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Union

import numpy as np
import pandas as pd

from synomicsbench.processing.metadata import MetaData
from synomicsbench.processing.postprocessing import post_masking

from . import compute as _compute
from . import privacy as _privacy
from .config import BenchmarkConfig, PRIVACY_DIMS


ORIGIN = "Origin"

#: Summary columns of a CIBERSORTx result table (not cell types).
CIBERSORTX_STAT_COLUMNS = ("P-value", "Correlation", "RMSE", "Absolute score (sig.score)")


@dataclass
class Candidate:
    """A single synthetic dataset to evaluate.

    ``name`` is the dataset name given by the user (mapping key or file stem); it locates
    the dataset's CIBERSORTx result. It defaults to ``"<method>_<seed>"``.
    """
    method: str            # display name, e.g. "Gaussian Copula"
    seed: int
    data: Union[str, pd.DataFrame]
    name: Optional[str] = None

    @property
    def stem_key(self) -> str:
        return f"{self.method}_{self.seed}"

    @property
    def label(self) -> str:
        return self.name or self.stem_key


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def load_frame(src: Union[str, pd.DataFrame], id_column: str) -> pd.DataFrame:
    """Load a dataset (CSV path or DataFrame), using ``id_column`` as the index if present."""
    if isinstance(src, str):
        df = pd.read_csv(src)
        if id_column not in df.columns and df.columns[0].startswith("Unnamed"):
            df = df.set_index(df.columns[0])
            df.index.name = None
    else:
        df = src.copy()
    if id_column in df.columns:
        df = df.set_index(id_column)
    return df


def load_metadata(config: BenchmarkConfig) -> dict:
    """The feature-type dict of ``config.metadata`` (empty without metadata)."""
    if config.metadata is None:
        return {}
    if isinstance(config.metadata, dict):
        return config.metadata
    return MetaData.load(config.metadata)


def _maybe_mask(df: pd.DataFrame, config: BenchmarkConfig) -> pd.DataFrame:
    """Apply ``post_masking`` if fidelity masking is enabled (no-op without indicators)."""
    return post_masking(df) if config.fidelity_masking else df


def _fidelity_metadata(block: pd.DataFrame, config: BenchmarkConfig,
                       ordinal_features=None, transcriptomic_cols=None) -> dict:
    """Feature types of a block for the fidelity metrics."""
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


def _rows(candidates: List[Candidate], values: Dict[str, float]) -> pd.DataFrame:
    return pd.DataFrame([{"Model": c.method, "Seed": c.seed, "Value": float(values.get(c.stem_key, np.nan))}
                         for c in candidates], columns=["Model", "Seed", "Value"])


def _warn(cand: Candidate, dim: str, exc: Exception) -> None:
    print(f"[autobenchmark] {dim}: {cand.label} scored NaN ({type(exc).__name__}: {exc})", flush=True)


# ---------------------------------------------------------------------------
# Univariate
# ---------------------------------------------------------------------------

def run_univariate(original: pd.DataFrame, candidates: List[Candidate],
                   config: BenchmarkConfig, cache: Optional[dict] = None) -> pd.DataFrame:
    """Mean of the clinical and transcriptomic univariate similarities."""
    from synomicsbench.metrics.fidelity.UnivariateSimilarity import UnivariateSimilarity

    def block_mean(orig_block, syn_block, metadata, tag) -> float:
        uni = UnivariateSimilarity(output_dir=_tmp_dir(config, "univariate"), logger_name=tag)
        uni.get_univariate_score(original_data=orig_block, synthetic_data=syn_block,
                                 metadata=metadata, save=False)
        return float(uni.get_detail_df()["Score"].fillna(0).mean())

    clinical, omic = config.resolve_columns(original.columns)
    ordinal = config.ordinal_features(load_metadata(config))
    mor_clin = _maybe_mask(original[clinical], config)
    meta_clin = _fidelity_metadata(mor_clin, config, ordinal_features=ordinal)
    mor_omic = original[omic]
    meta_omic = _fidelity_metadata(mor_omic, config, ordinal_features=None)
    values = {}
    for cand in candidates:
        syn = load_frame(cand.data, config.id_column)
        clin = block_mean(mor_clin, _maybe_mask(syn[clinical], config), meta_clin, f"{cand.stem_key}_clin")
        omic_mean = block_mean(mor_omic, syn[omic], meta_omic, f"{cand.stem_key}_omic")
        values[cand.stem_key] = 0.5 * (clin + omic_mean)
    return _rows(candidates, values)


# ---------------------------------------------------------------------------
# Bivariate
# ---------------------------------------------------------------------------

def run_bivariate(original: pd.DataFrame, candidates: List[Candidate],
                  config: BenchmarkConfig, cache: Optional[dict] = None) -> pd.DataFrame:
    """Mean of the clinical, transcriptomic and clinical-transcriptomic pairwise similarities."""
    from synomicsbench.metrics.fidelity.PairwiseSimilarity import PairwiseSimilarity

    def block_mean(orig_block, syn_block, meta, tag) -> float:
        ps = PairwiseSimilarity(orig_block, syn_block, meta, output_dir=_tmp_dir(config, "bivariate"),
                                save=False, name=tag)
        res = ps.get_pairwise_scores(method=config.corr_method, n_bins=config.n_bins)
        return float(np.nanmean(res["PairwiseScore"]))

    def cross_mean(orig_full, syn_full, clin_feat, trans_feat, meta_full, tag) -> float:
        ps = PairwiseSimilarity(orig_full, syn_full, meta_full, output_dir=_tmp_dir(config, "bivariate"),
                                save=False, name=f"{tag}_cross")
        ps.get_pairwise_scores(method=config.corr_method, n_bins=config.n_bins)
        cross = ps.get_cross_group_associations(list(clin_feat), list(trans_feat))
        return float(cross["Score"].fillna(0).mean())

    clinical, omic = config.resolve_columns(original.columns)
    ordinal = config.ordinal_features(load_metadata(config))
    mor_clin = _maybe_mask(original[clinical], config)
    meta_clin = _fidelity_metadata(mor_clin, config, ordinal_features=ordinal)
    mor_omic = original[omic]
    meta_omic = _fidelity_metadata(mor_omic, config, ordinal_features=None)
    mor_full = _maybe_mask(original[list(clinical) + list(omic)], config)
    clin_feat = [c for c in clinical if c in mor_full.columns]
    trans_feat = [c for c in omic if c in mor_full.columns]
    meta_cross = _fidelity_metadata(mor_full, config, ordinal_features=None, transcriptomic_cols=trans_feat)
    values = {}
    for cand in candidates:
        syn = load_frame(cand.data, config.id_column)
        clin = block_mean(mor_clin, _maybe_mask(syn[clinical], config), meta_clin, f"{cand.stem_key}_clin")
        omic_mean = block_mean(mor_omic, syn[omic], meta_omic, f"{cand.stem_key}_omic")
        msyn_full = _maybe_mask(syn[list(clinical) + list(omic)], config)
        cross = cross_mean(mor_full, msyn_full, clin_feat, trans_feat, meta_cross, cand.stem_key)
        values[cand.stem_key] = (clin + omic_mean + cross) / 3.0
    return _rows(candidates, values)


# ---------------------------------------------------------------------------
# DGE (F1-GCS) and GSEA (F1-PCS)
# ---------------------------------------------------------------------------

def _gene_bounds(original: pd.DataFrame, gene_cols, cache: Optional[dict]):
    """Per-gene (min, max) of the original data, computed once per run."""
    if cache is not None and "gene_bounds" in cache:
        return cache["gene_bounds"]
    genes = original[list(gene_cols)].apply(pd.to_numeric, errors="coerce")
    bounds = (genes.min(), genes.max())
    if cache is not None:
        cache["gene_bounds"] = bounds
    return bounds


def _dge_table(df: pd.DataFrame, gene_cols, config: BenchmarkConfig, bounds) -> pd.DataFrame:
    """Wilcoxon DGE of the two phenotype groups of ``df``.

    The gene values are clipped to the per-gene range of the original data (``bounds``):
    generators can emit values far outside it, which distort the mean-based Log2FC. With
    ``config.log_transform`` the values are then transformed to log2(x + 1).
    """
    labelled = _compute.derive_labels(df, config.phenotype_source_col, config.responder_values,
                                      config.progressor_values, config.label_col, config.label_values)
    present = [c for c in gene_cols if c in labelled.columns]
    lower, upper = bounds
    expr = labelled[present].clip(lower=lower[present], upper=upper[present], axis=1)
    if config.log_transform:
        expr = np.log2(expr + 1)
    meta = pd.DataFrame({config.id_column: labelled.index, config.label_col: labelled[config.label_col].values})
    gene_matrix = _compute.build_gene_matrix(expr, present)
    phenotypes = {config.label_col: list(config.label_values)}
    return _compute.dge_analysis(gene_matrix, meta, phenotypes, id_col=config.id_column, n_jobs=-1,
                                 log_transformed=config.log_transform)


def _cached_dge(key: str, df: pd.DataFrame, gene_cols, config: BenchmarkConfig,
                cache: Optional[dict], bounds) -> pd.DataFrame:
    """DGE table of one dataset, computed once per run (DGE and GSEA share it)."""
    if cache is None:
        return _dge_table(df, gene_cols, config, bounds)
    store = cache.setdefault("dge", {})
    if key not in store:
        store[key] = _dge_table(df, gene_cols, config, bounds)
    return store[key]


def run_dge(original: pd.DataFrame, candidates: List[Candidate],
            config: BenchmarkConfig, cache: Optional[dict] = None) -> pd.DataFrame:
    """F1-GCS of the genes differentially expressed between the two phenotype groups."""
    from synomicsbench.metrics.narrow_utility.DGE import GCSAnalyzer

    analyzer = GCSAnalyzer(term_col="Gene", nes_col="Log2FC", sig_col="P_value", seed=42, sig_thr=0.05)
    _, omic = config.resolve_columns(original.columns)
    bounds = _gene_bounds(original, omic, cache)
    origin_dge = _cached_dge(ORIGIN, original, omic, config, cache, bounds)
    values = {}
    for cand in candidates:
        # A synthetic dataset may lack one phenotype group; it then scores NaN (ranked last).
        try:
            syn_dge = _cached_dge(cand.stem_key, load_frame(cand.data, config.id_column), omic, config, cache,
                                  bounds)
            values[cand.stem_key] = float(analyzer.process_single_dge_result(origin_dge, syn_dge)[2].f1)
        except Exception as exc:
            _warn(cand, "DGE", exc)
    return _rows(candidates, values)


def run_gsea(original: pd.DataFrame, candidates: List[Candidate],
             config: BenchmarkConfig, cache: Optional[dict] = None) -> pd.DataFrame:
    """F1-PCS of the pre-ranked GSEA pathways of the two phenotype groups."""
    from synomicsbench.metrics.narrow_utility.GSEA import PCSAnalyzer

    analyzer = PCSAnalyzer(term_col="Term", nes_col="NES", sig_col="FDR q-val", seed=42, sig_thr=0.05)
    _, omic = config.resolve_columns(original.columns)
    bounds = _gene_bounds(original, omic, cache)
    origin_dge = _cached_dge(ORIGIN, original, omic, config, cache, bounds)
    origin_gsea = _compute.gsea_prerank(origin_dge, config.gene_set, seed=42,
                                        permutation_num=config.gsea_permutations)
    values = {}
    for cand in candidates:
        try:
            syn_dge = _cached_dge(cand.stem_key, load_frame(cand.data, config.id_column), omic, config, cache,
                                  bounds)
            syn_gsea = _compute.gsea_prerank(syn_dge, config.gene_set, seed=cand.seed,
                                             permutation_num=config.gsea_permutations)
            values[cand.stem_key] = float(analyzer.process_single_gsea_result(origin_gsea, syn_gsea)[2].f1)
        except Exception as exc:
            _warn(cand, "GSEA", exc)
    return _rows(candidates, values)


# ---------------------------------------------------------------------------
# ssGSEA (KSComplement)
# ---------------------------------------------------------------------------

def run_ssgsea(original: pd.DataFrame, candidates: List[Candidate],
               config: BenchmarkConfig, cache: Optional[dict] = None) -> pd.DataFrame:
    """Mean KS-complement of the ssGSEA scores of every pathway."""
    from synomicsbench.metrics.fidelity.UnivariateSimilarity import UnivariateSimilarity

    def pivot(df):
        long = _compute.ssgsea_scores(_compute.build_gene_matrix(df, omic), config.gene_set)
        return _compute.pivot_ssgsea(long)

    _, omic = config.resolve_columns(original.columns)
    origin_pivot = pivot(original)
    values = {}
    for cand in candidates:
        syn_pivot = pivot(load_frame(cand.data, config.id_column))
        common = origin_pivot.columns.intersection(syn_pivot.columns)
        meta = MetaData.get_metadata(data=origin_pivot[common], threshold_unique_values=10, ordinal_features=None)
        uni = UnivariateSimilarity(output_dir=_tmp_dir(config, "ssgsea"), logger_name=cand.stem_key)
        uni.get_univariate_score(original_data=origin_pivot[common], synthetic_data=syn_pivot[common],
                                 metadata=meta, save=False)
        values[cand.stem_key] = float(uni.get_detail_df()["Score"].fillna(0).mean())
    return _rows(candidates, values)


# ---------------------------------------------------------------------------
# Cell deconvolution (Aitchison score)
# ---------------------------------------------------------------------------

_ORIGINAL_KEYS = ("original", "Original", "Origin", "origin")


def _cibersortx_paths(config: BenchmarkConfig) -> Dict[str, object]:
    """Dataset name -> CIBERSORTx result (path or DataFrame) of ``config.cibersortx``."""
    src = config.cibersortx
    if src is None:
        raise ValueError("Cell deconvolution needs the CIBERSORTx results: set cibersortx= to a "
                         "directory or to a mapping {'original': path, <dataset name>: path}.")
    if isinstance(src, dict):
        return dict(src)
    if not os.path.isdir(src):
        raise FileNotFoundError(f"cibersortx directory not found: {src}")
    paths = {}
    for fname in sorted(os.listdir(src)):
        if not fname.lower().endswith(".csv"):
            continue
        name = fname[:-4]
        if name.startswith("CIBERSORTx_") and name.endswith("_Results"):
            name = name[len("CIBERSORTx_"):-len("_Results")]
        paths[name] = os.path.join(src, fname)
    return paths


def _read_fractions(src) -> pd.DataFrame:
    df = pd.read_csv(src, index_col=0) if isinstance(src, str) else src.copy()
    return df.drop(columns=[c for c in CIBERSORTX_STAT_COLUMNS if c in df.columns])


def run_cell_deconvolution(original: pd.DataFrame, candidates: List[Candidate],
                           config: BenchmarkConfig, cache: Optional[dict] = None) -> pd.DataFrame:
    """Aitchison score of the mean cell-type composition (CIBERSORTx results)."""
    from synomicsbench.metrics.narrow_utility import cell_deconvolution as celldeco

    paths = _cibersortx_paths(config)
    origin_key = next((k for k in _ORIGINAL_KEYS if k in paths), None)
    if origin_key is None:
        raise ValueError(f"No CIBERSORTx result of the original data (named one of {_ORIGINAL_KEYS}) "
                         f"in cibersortx; found: {sorted(paths)[:10]}.")
    origin = _read_fractions(paths[origin_key])
    cell_types = origin.mean().sort_values(ascending=False).index[:config.top_k_cell_types].tolist()
    values, missing = {}, []
    for cand in candidates:
        key = next((k for k in (cand.label, cand.stem_key) if k in paths), None)
        if key is None:
            missing.append(cand.label)
            continue
        syn = _read_fractions(paths[key])
        values[cand.stem_key] = celldeco.aitchison_score(celldeco.aitchison_distance(origin, syn, cell_types))
    if missing:
        raise ValueError(f"No CIBERSORTx result for {missing}; cibersortx has {sorted(paths)}.")
    return _rows(candidates, values)


# ---------------------------------------------------------------------------
# Survival (survival score)
# ---------------------------------------------------------------------------

def run_survival(original: pd.DataFrame, candidates: List[Candidate],
                 config: BenchmarkConfig, cache: Optional[dict] = None) -> pd.DataFrame:
    """Survival score: mean over the endpoints of 1 - |C_original - C_synthetic|."""
    from synomicsbench.metrics.narrow_utility.survival_analysis import SurvivalEvaluator

    def prep(df):
        return _compute.derive_labels(df, config.phenotype_source_col, config.responder_values,
                                      config.progressor_values, config.label_col, config.label_values)

    datasets = {ORIGIN: prep(original)}
    for cand in candidates:
        datasets[cand.stem_key] = prep(load_frame(cand.data, config.id_column))

    per_endpoint = []
    for time_col, event_col in config.survival_endpoints:
        ev = SurvivalEvaluator(datasets_dict=datasets, phenotype={config.label_col: list(config.label_values)},
                               time_target=time_col, event_target=event_col, original_name=ORIGIN)
        ev.compute_survival_metrics()
        scored = ev.compute_survival_scores(original_name=ORIGIN)
        per_endpoint.append(scored.set_index("Dataset")["Survival_score"])
    combined = pd.concat(per_endpoint, axis=1).apply(pd.to_numeric, errors="coerce").fillna(0)
    values = {c.stem_key: float(combined.loc[c.stem_key].mean()) if c.stem_key in combined.index else 0.0
              for c in candidates}
    return _rows(candidates, values)


# ---------------------------------------------------------------------------
# Network preservation (normalized Z-summary)
# ---------------------------------------------------------------------------

def run_network(original: pd.DataFrame, candidates: List[Candidate],
                config: BenchmarkConfig, cache: Optional[dict] = None) -> pd.DataFrame:
    """Normalized median Z-summary of the WGCNA modules of the original data."""
    from synomicsbench.metrics.fidelity.NetworkPreservation import NetworkPreservation

    _, omic = config.resolve_columns(original.columns)
    npres = NetworkPreservation(
        output_dir=_tmp_dir(config, "network"),
        n_genes=config.network_n_genes,
        n_permutations=config.network_n_permutations,
        log_transform=config.log_transform,
        threads=config.network_threads,
    )
    npres.build_reference(original[omic])
    syns = {cand.stem_key: load_frame(cand.data, config.id_column)[omic] for cand in candidates}
    scores = npres.evaluate(syns, metrics="Zsummary_norm")
    return _rows(candidates, scores["Zsummary_norm"].to_dict())


# ---------------------------------------------------------------------------
# Privacy (one dimension per attack category; value = risk)
# ---------------------------------------------------------------------------

def run_privacy(original: pd.DataFrame, candidates: List[Candidate], config: BenchmarkConfig,
                dims: Sequence[str] = PRIVACY_DIMS) -> Dict[str, pd.DataFrame]:
    """Risks of the requested attack categories, run with Anonymeter.

    The attacker knows the clinical columns and part of ``config.privacy_known_genes``
    (default: all genes): one knowledge level per gene set of ``config.privacy_gene_sets`` and
    per fraction of ``config.privacy_proportions``. Univariate singling out and linkability
    attack the columns of each level, inference infers each clinical column from the genes of
    each level, and multivariate singling out combines ``config.privacy_so_multi_n_cols``
    attributes of all the attacked columns; the random draws of the attacks of each
    synthetic dataset (singling-out predicates, target records) use the seed of that dataset. The risk of an attack is the mean over its
    evaluations. With
    ``config.privacy_control``, the attacks run on the columns shared with the control cohort
    and the risks are residual risks; otherwise the risk is floored at the naive baseline.

    Returns:
        dict: dimension name -> DataFrame [Model, Seed, Value].
    """
    from synomicsbench.metrics.privacy.inference import eval_inference_genes_clinical
    from synomicsbench.metrics.privacy.linkability import eval_linkability_genes_clinical
    from synomicsbench.metrics.privacy.singling_out import (
        eval_singling_out_multivariate, eval_singling_out_univariate)

    clinical, genes = config.resolve_columns(original.columns)
    if config.privacy_known_genes is not None:
        known = set(config.privacy_known_genes)
        genes = [g for g in genes if g in known]
    control = None
    if config.privacy_control is not None:
        control = load_frame(config.privacy_control, config.id_column)
        clinical = [c for c in clinical if c in control.columns]
        genes = [g for g in genes if g in control.columns]
        print(f"[autobenchmark] privacy: {len(clinical)} clinical columns and {len(genes)} genes "
              "shared with the control cohort are attacked.", flush=True)
    if not genes:
        raise ValueError("No gene column left for the privacy attacks (check privacy_known_genes "
                         "and the columns of privacy_control).")
    cols = clinical + genes
    ori = original[cols]
    syns = {cand.stem_key: load_frame(cand.data, config.id_column)[cols] for cand in candidates}
    if control is not None:
        control = control[cols]

    # the random draws of the attacks (predicates, target records) of each synthetic dataset
    # use the seed of that dataset
    seeds = {cand.stem_key: cand.seed for cand in candidates}
    uni = multi = link = infer = None
    if "Singling-out (uni)" in dims:
        uni = {}
        for key, frame in syns.items():
            uni.update(eval_singling_out_univariate(
                ori, {key: frame}, n_attacks=config.privacy_n_attacks,
                max_attempts=config.privacy_max_attempts, proportions=config.privacy_proportions,
                gene_sets=config.privacy_gene_sets, seed=config.privacy_seed,
                evaluator_seed=seeds[key], control=control,
                clinical_cols=clinical, transcriptomic_cols=genes))
    if "Singling-out (multi)" in dims:
        multi = {}
        for key, frame in syns.items():
            multi.update(eval_singling_out_multivariate(
                ori, {key: frame}, n_cols_list=tuple(config.privacy_so_multi_n_cols),
                n_attacks=config.privacy_n_attacks, max_attempts=config.privacy_max_attempts,
                evaluator_seed=seeds[key], control=control))
    if "Linkability" in dims:
        link = {}
        for key, frame in syns.items():
            link.update(eval_linkability_genes_clinical(
                ori, {key: frame}, clinical_cols=clinical, transcriptomic_cols=genes,
                n_neighbors=config.privacy_link_n_neighbors, proportions=config.privacy_proportions,
                gene_sets=config.privacy_gene_sets, seed=config.privacy_seed,
                evaluator_seed=seeds[key], control=control))
    if "Inference" in dims:
        infer = {}
        for key, frame in syns.items():
            infer.update(eval_inference_genes_clinical(
                ori, {key: frame}, clinical_cols=clinical, transcriptomic_cols=genes,
                proportions=config.privacy_proportions, gene_sets=config.privacy_gene_sets,
                seed=config.privacy_seed, evaluator_seed=seeds[key], control=control))

    by_stem = _privacy.category_risks_from_attacks(uni, multi, link, infer)
    return {dim: _rows(candidates, by_stem[dim]) for dim in dims if by_stem.get(dim)}

"""
Configuration for the automatic benchmark pipeline.

`BenchmarkConfig` collects everything the pipeline needs to run all metric
dimensions in one pass and reproduce the manuscript's per-seed results:
the clinical/transcriptomic column partition, the phenotype split used by the
narrow-utility metrics, the survival endpoints, the Hallmark gene set, the
rank-derived meta-score weights, and the optional "reuse" hooks that point at
already-computed intermediate artifacts (privacy pickles, CIBERSORTx results,
per-dimension score tables).

Nothing here mutates existing package code; this module only *reads* the
existing metric classes when the runners are invoked.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple


# Canonical SDG method display-name -> file-stem map (fixed order, as in the manuscript).
NAME_MAP: Dict[str, str] = {
    "Avatars K5": "avatarsk5",
    "Avatars K10": "avatarsk10",
    "CTGAN": "ctgan",
    "Gaussian Copula": "gaussiancopula",
    "Synthpop": "synthpop",
    "TVAE": "tvae",
}

# The eight meta-score dimensions, grouped into the three equally-weighted pillars.
BROAD_DIMS: Tuple[str, ...] = ("Univariate", "Bivariate")
NARROW_DIMS: Tuple[str, ...] = ("DGE", "GSEA", "ssGSEA", "Cell Deconvolution", "Survival Analysis")
PRIVACY_DIMS: Tuple[str, ...] = ("Privacy",)
ALL_DIMS: Tuple[str, ...] = BROAD_DIMS + NARROW_DIMS + PRIVACY_DIMS

# Per-dimension execution mode.
#   "compute" : recompute the dimension from the raw data
#   "reuse"   : load precomputed intermediate artifacts / score tables and (re)score
#   "skip"    : do not evaluate this dimension
VALID_MODES = ("compute", "reuse", "skip")


@dataclass
class BenchmarkConfig:
    """Drive the automatic benchmark. Melanoma-appropriate defaults are provided.

    Args:
        id_column: Sample-ID column in the raw CSVs (dropped/used as index internally).
        gene_start_column: First transcriptomic column; every column from here to the
            end of the feature block (before any appended helper column) is a gene.
            Used only when ``clinical_cols`` / ``transcriptomic_cols`` are not given.
        clinical_cols / transcriptomic_cols: Explicit column partition. If ``None`` they
            are derived from ``gene_start_column``.
        metadata: Flat feature-type dict (``feature_metadata.json`` format) or a path to it.
        phenotype_source_col: Clinical column the two-group split is derived from ("BR").
        responder_values / progressor_values: Values of ``phenotype_source_col`` mapping to
            each group.
        label_col: Name of the derived two-group column ("Labels").
        label_values: (group_A, group_B) labels written into ``label_col``.
        gene_set: Path to the Hallmark ``.gmt`` used by GSEA/ssGSEA.
        gsea_permutations: Permutations for ``gseapy.prerank``.
        survival_endpoints: List of ``(time_col, event_col)`` endpoints (OS, PFS).
        corr_method / n_bins: Pairwise-similarity correlation settings.
        threshold_unique_values: Used only if metadata must be generated on the fly.
        weights: (broad, narrow, privacy) meta-score weights (equal thirds by default).
        modes: Per-dimension mode override (dimension name -> one of VALID_MODES).
        precomputed_dir: Root of the per-dimension precomputed tables (for reuse mode).
        cibersortx_dir: Directory of CIBERSORTx result CSVs (required for Cell Deconvolution).
        privacy_pickle_dir: Root of the saved anonymeter evaluator pickles.
        top_k_cell_types: Number of most-abundant cell types used for Aitchison distance.
        output_dir: Where the pipeline writes its report (never an existing results dir).
        name_map: Display-name -> file-stem map for locating reuse artifacts.
    """

    # --- column layout ---
    id_column: str = "Patient"
    gene_start_column: str = "A1BG"
    clinical_cols: Optional[List[str]] = None
    transcriptomic_cols: Optional[List[str]] = None
    metadata: Optional[object] = None  # dict or path

    # --- narrow-utility phenotype split ---
    phenotype_source_col: str = "BR"
    responder_values: Sequence[str] = ("CR", "PR")
    progressor_values: Sequence[str] = ("PD",)
    label_col: str = "Labels"
    label_values: Tuple[str, str] = ("Responder", "Progressor")

    # --- GSEA / ssGSEA ---
    gene_set: Optional[str] = None
    gsea_permutations: int = 10000

    # --- survival ---
    survival_endpoints: List[Tuple[str, str]] = field(
        default_factory=lambda: [("OS", "dead"), ("PFS", "progressed")]
    )

    # --- fidelity ---
    corr_method: str = "spearman"
    n_bins: int = 10
    threshold_unique_values: int = 10
    # Fidelity masking: apply ``post_masking`` (use the missingindicator_* columns to
    # re-introduce the missing values into the data, then drop the indicator columns)
    # before scoring — matching the manuscript's univariate/bivariate/cross-group runs.
    fidelity_masking: bool = True
    # Ordinal clinical features for fidelity metadata. Leave ``None`` (default) to read
    # them straight from the input ``metadata`` (its ``ordinal_categorical`` entries) — the
    # processing pipeline already records these, so the user need not re-enter them. Provide
    # an explicit list only to override what the metadata says.
    clinical_ordinal_features: Optional[List[str]] = None

    # --- meta-score ---
    weights: Tuple[float, float, float] = (1 / 3, 1 / 3, 1 / 3)
    # Dimensions whose per-(method, seed) values are collapsed to the per-method mean
    # before ranking. The manuscript's 5-seed MetaScore collapsed DGE/GSEA/Privacy this
    # way (it averaged each method's 5 seed scores into one value), so this is the default
    # for exact consistency with the published results. Set to () to instead rank every
    # dimension per-seed. Has no effect on single-seed runs.
    collapse_dims: Tuple[str, ...] = ("DGE", "GSEA", "Privacy")

    # --- per-dimension modes & reuse hooks ---
    modes: Dict[str, str] = field(default_factory=dict)
    precomputed_dir: Optional[str] = None
    cibersortx_dir: Optional[str] = None
    privacy_pickle_dir: Optional[str] = None
    top_k_cell_types: int = 10

    # --- privacy compute mode (only used when Privacy mode == "compute") ---
    # Runs the anonymeter attacks live via the existing src functions. Stochastic and slow;
    # meant for NEW datasets (won't reproduce the manuscript). Defaults match the src signatures.
    privacy_seed: int = 42
    privacy_n_attacks: int = 10_000
    privacy_max_attempts: int = 1_000_000
    privacy_so_uni_proportions: Tuple[float, ...] = (0.25, 0.50, 0.75, 1.0)
    privacy_so_multi_n_cols: Tuple[int, ...] = (2, 3, 5, 7, 10, 20, 50)
    privacy_link_proportions: Tuple[float, ...] = (0.25, 0.50, 0.75, 1.0)
    privacy_link_n_neighbors: int = 1

    # --- output ---
    output_dir: str = "autobenchmark_results"
    name_map: Dict[str, str] = field(default_factory=lambda: dict(NAME_MAP))
    # Regex used to auto-parse (method, seed) from a dataset name or filename when they are
    # not given explicitly — e.g. "gaussiancopula_0.csv" -> method="gaussiancopula", seed=0.
    # If it doesn't match (no trailing "_<int>"), the dataset is treated as a single seed.
    name_pattern: str = r"(?P<method>.+)_(?P<seed>\d+)$"

    def mode_for(self, dimension: str, default: str = "compute") -> str:
        """Return the execution mode for a dimension, validating the value."""
        mode = self.modes.get(dimension, default)
        if mode not in VALID_MODES:
            raise ValueError(
                f"Invalid mode '{mode}' for dimension '{dimension}'. "
                f"Expected one of {VALID_MODES}."
            )
        return mode

    def ordinal_features(self, metadata: Optional[dict] = None) -> List[str]:
        """Ordinal clinical features for fidelity metadata.

        Uses the explicit ``clinical_ordinal_features`` if set; otherwise reads the
        ``ordinal_categorical`` entries from the supplied metadata dict (the processing
        pipeline's ``feature_metadata.json`` format).
        """
        if self.clinical_ordinal_features is not None:
            return list(self.clinical_ordinal_features)
        if metadata:
            return [c for c, t in metadata.items() if t == "ordinal_categorical"]
        return []

    def resolve_columns(self, columns: Sequence[str]) -> Tuple[List[str], List[str]]:
        """Return (clinical_cols, transcriptomic_cols) for the given feature columns.

        Uses the explicit lists if provided, otherwise splits at ``gene_start_column``.
        The ``id_column`` is never included in either block.
        """
        cols = [c for c in columns if c != self.id_column]
        if self.clinical_cols is not None and self.transcriptomic_cols is not None:
            return list(self.clinical_cols), list(self.transcriptomic_cols)
        if self.gene_start_column not in cols:
            raise ValueError(
                f"gene_start_column '{self.gene_start_column}' not found in the data columns; "
                "pass clinical_cols/transcriptomic_cols explicitly."
            )
        start = cols.index(self.gene_start_column)
        clinical = cols[:start]
        transcriptomic = cols[start:]
        return clinical, transcriptomic

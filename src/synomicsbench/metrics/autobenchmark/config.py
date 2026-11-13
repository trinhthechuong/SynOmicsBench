"""
Configuration for the automatic benchmark pipeline.

`BenchmarkConfig` collects what the pipeline needs to compute the twelve metrics from the
original and synthetic data: the clinical/transcriptomic column partition, the phenotype split
used by the biological-utility metrics, the survival endpoints, the gene set of GSEA/ssGSEA,
the CIBERSORTx results (the only input computed outside the package), the network and
privacy-attack settings, and the meta-score weights and weighting scenarios.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple, Union


# Display name -> file stem of the synthesizers shipped with SynOmicsBench; any other method
# keeps the name parsed from its file name or mapping key.
NAME_MAP: Dict[str, str] = {
    "Avatars": "avatars",
    "CTGAN": "ctgan",
    "Gaussian Copula": "gaussiancopula",
    "Synthpop": "synthpop",
    "TVAE": "tvae",
    "TabDiff": "tabdiff",
}

# The twelve meta-score dimensions, grouped into the three pillars. DGE and GSEA are scored
# with F1-GCS and F1-PCS; each privacy dimension is the risk of one attack category (residual
# risk when a control cohort is given). Every dimension is "higher = better" except the
# privacy risks (LOWER_IS_BETTER).
BROAD_DIMS: Tuple[str, ...] = ("Univariate", "Bivariate", "Network Preservation")
NARROW_DIMS: Tuple[str, ...] = ("DGE", "GSEA", "ssGSEA", "Cell Deconvolution", "Survival Analysis")
PRIVACY_DIMS: Tuple[str, ...] = ("Singling-out (uni)", "Singling-out (multi)", "Linkability", "Inference")
ALL_DIMS: Tuple[str, ...] = BROAD_DIMS + NARROW_DIMS + PRIVACY_DIMS
LOWER_IS_BETTER: Tuple[str, ...] = PRIVACY_DIMS
PILLARS: Dict[str, Tuple[str, ...]] = {
    "Statistical fidelity": BROAD_DIMS,
    "Biological utility": NARROW_DIMS,
    "Privacy": PRIVACY_DIMS,
}

#: Metric names accepted by ``metrics=`` -> dimension.
METRICS: Dict[str, str] = {
    "univariate": "Univariate",
    "bivariate": "Bivariate",
    "network": "Network Preservation",
    "f1_gcs": "DGE",
    "f1_pcs": "GSEA",
    "ssgsea": "ssGSEA",
    "cell_deconvolution": "Cell Deconvolution",
    "survival": "Survival Analysis",
    "singling_out_uni": "Singling-out (uni)",
    "singling_out_multi": "Singling-out (multi)",
    "linkability": "Linkability",
    "inference": "Inference",
}

#: Metric groups accepted by ``metrics=``.
METRIC_GROUPS: Dict[str, Tuple[str, ...]] = {
    "all": ALL_DIMS,
    "fidelity": BROAD_DIMS,
    "utility": NARROW_DIMS,
    "privacy": PRIVACY_DIMS,
}

#: Pillar weights (statistical fidelity, biological utility, privacy) of the weighting
#: scenarios reported by default: equal weights and the three use cases of the SynOmicsBench
#: manuscript.
SCENARIOS: Dict[str, Tuple[float, float, float]] = {
    "Equal weights": (1 / 3, 1 / 3, 1 / 3),
    "Controlled sharing within a research consortium": (0.3, 0.5, 0.2),
    "Public release for open challenges or hackathons": (0.2, 0.3, 0.5),
    "Method development and pipeline testing": (0.3, 0.2, 0.5),
}

#: Short description of each default scenario, shown in the report.
SCENARIO_DESCRIPTIONS: Dict[str, str] = {
    "Equal weights": "No pillar is preferred.",
    "Controlled sharing within a research consortium": (
        "Access is governed by a data transfer agreement, so the legal framework carries most "
        "of the privacy burden. Biological utility comes first, as the goal is faithful "
        "downstream discovery, then statistical fidelity, its prerequisite, then privacy."),
    "Public release for open challenges or hackathons": (
        "No governance layer restricts access, so the protection rests on the data themselves "
        "and privacy weighs most. Biological utility comes second, so that models trained on "
        "the data generalize to real patients; statistical fidelity comes last."),
    "Method development and pipeline testing": (
        "Synthetic data embedded in software packages, tutorials and public code repositories, "
        "with no governance layer: privacy weighs most. Statistical fidelity comes second, as "
        "the software must behave as it would on real data; biological utility comes last."),
}

#: Bundled MSigDB Hallmark gene sets (v2025.1, human gene symbols, CC BY 4.0), the default
#: gene set of GSEA and ssGSEA.
HALLMARK_GMT: str = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                                 "data", "h.all.v2025.1.Hs.symbols.gmt")


def resolve_metrics(metrics: Union[None, str, Iterable[str]]) -> List[str]:
    """Dimensions selected by ``metrics``, in the order of ``ALL_DIMS``.

    ``metrics`` is ``None`` or ``"all"``, a group (``"fidelity"``, ``"utility"``,
    ``"privacy"``), a metric name of ``METRICS``, a dimension name, or a list of these.

    Raises:
        ValueError: For an unknown name, listing the valid ones.
    """
    if metrics is None:
        return list(ALL_DIMS)
    items = [metrics] if isinstance(metrics, str) else list(metrics)
    chosen = set()
    for item in items:
        key = str(item).strip()
        low = key.lower()
        if low in METRIC_GROUPS:
            chosen.update(METRIC_GROUPS[low])
        elif low in METRICS:
            chosen.add(METRICS[low])
        elif key in ALL_DIMS:
            chosen.add(key)
        else:
            valid = ", ".join(list(METRIC_GROUPS) + list(METRICS))
            raise ValueError(f"Unknown metric '{item}'. Valid names: {valid}.")
    return [d for d in ALL_DIMS if d in chosen]


@dataclass
class BenchmarkConfig:
    """Settings of the automatic benchmark. The defaults match the Melanoma cohort of SynOmicsBench.

    Args:
        id_column: Sample-ID column; used as the index when present.
        gene_start_column: First transcriptomic column. Used only when ``clinical_cols`` and
            ``transcriptomic_cols`` are not given: the columns before it are clinical, the
            others are genes.
        clinical_cols: Clinical columns (explicit partition, with ``transcriptomic_cols``).
        transcriptomic_cols: Gene columns (explicit partition, with ``clinical_cols``).
        metadata: Optional feature-type dict (``feature_metadata.json`` format) or path to it;
            its ``ordinal_categorical`` columns are treated as ordinal by the fidelity metrics.
        phenotype_source_col: Clinical column the two compared groups are derived from (DGE,
            GSEA, survival).
        responder_values: Values of ``phenotype_source_col`` of the first group.
        progressor_values: Values of ``phenotype_source_col`` of the second group.
        label_col: Name of the derived two-group column.
        label_values: Names of the two groups in ``label_col``.
        log_transform: The gene values are on a linear scale (e.g. TPM): transform them to
            log2(x + 1) before DGE, GSEA and network preservation.
        gene_set: ``.gmt`` file of GSEA and ssGSEA (default: the bundled MSigDB Hallmark sets).
        gsea_permutations: Permutations of the pre-ranked GSEA.
        survival_endpoints: ``(time_col, event_col)`` of each endpoint (e.g. OS and PFS); the
            survival score is their mean.
        corr_method: Correlation of the bivariate similarity.
        n_bins: Bins of the bivariate similarity of numerical-categorical pairs.
        threshold_unique_values: Columns with fewer unique values are categorical.
        fidelity_masking: Re-introduce the missing values recorded in ``missingindicator_*``
            columns before the fidelity metrics.
        clinical_ordinal_features: Ordinal clinical columns; ``None`` reads them from ``metadata``.
        network_n_genes: Most variable genes of the network.
        network_n_permutations: Permutations of the module preservation statistics.
        network_threads: Threads of WGCNA. The network settings are those of
            :class:`~synomicsbench.metrics.fidelity.NetworkPreservation.NetworkPreservation`
            (needs R with the WGCNA package).
        cibersortx: CIBERSORTx results (the only input computed outside the package): a
            directory with one CSV per dataset, or a mapping ``{"original": path, name: path}``,
            where ``name`` is the name of a synthetic dataset. In a directory, the files are
            ``<name>.csv`` or ``CIBERSORTx_<name>_Results.csv``, and the original data is
            ``original``, ``Original`` or ``Origin``.
        top_k_cell_types: Most abundant cell types (in the original data) used by the
            Aitchison distance.
        privacy_control: Optional control cohort (path or DataFrame): patients of the same
            population that the generators never saw. The privacy dimensions are then
            Anonymeter's residual risks; only the columns shared with the control are attacked.
        privacy_known_genes: Genes the attacker knows besides the clinical columns (default:
            all genes). The four attacks use these columns: inference infers each clinical
            column from the known genes.
        privacy_proportions: Fractions of the known genes held by the attacker in univariate
            singling out, linkability and inference: one evaluation per fraction, the genes of
            a fraction below 1 drawn with ``privacy_seed``. The risk is the mean over the levels.
        privacy_gene_sets: Optional named gene sets added as further levels, e.g.
            ``{"FGES": FGES_GMT}`` (see :func:`synomicsbench.metrics.privacy.knowledge.knowledge_levels`).
        privacy_n_attacks: Predicates of each singling-out attack.
        privacy_max_attempts: Maximum predicate generation attempts of singling out.
        privacy_so_multi_n_cols: Numbers of attributes combined in a multivariate
            singling-out predicate; the risk is the mean over these numbers.
        privacy_link_n_neighbors: Neighbours of the linkability attack.
        privacy_seed: Seed of the gene sampling of ``privacy_proportions``. The random draws
            of the four attacks on a synthetic dataset (singling-out predicates, target records
            of linkability and inference) use the seed of that dataset, so a run is repeatable.
        weights: Pillar weights (statistical fidelity, biological utility, privacy) of the
            meta-score (equal thirds by default). Pillars without a metric are left out and
            the other weights are rescaled to sum to 1.
        scenarios: Weighting scenarios of the sensitivity analysis, name -> weights; the
            report describes those of ``SCENARIO_DESCRIPTIONS``.
        collapse_dims: Dimensions whose values are averaged per method before ranking.
        on_error: ``"warn"`` records a failing metric in ``BenchmarkResult.errors`` and goes
            on; ``"raise"`` stops at the first failure.
        resume: Every metric is saved in ``output_dir/_work/values`` as soon as it is computed.
            With ``resume=True``, a run with the same inputs and settings reads the saved
            metrics back and computes only the missing ones (e.g. after a job was stopped).
        output_dir: Directory of the report and of the intermediate files.
        name_map: Display name -> file stem, used to name the methods parsed from file names.
        name_pattern: Regex parsing ``(method, seed)`` from a dataset name such as
            ``gaussiancopula_0``; without a trailing ``_<int>`` the dataset is a single seed.
    """

    # --- column layout ---
    id_column: str = "Patient"
    gene_start_column: str = "A1BG"
    clinical_cols: Optional[List[str]] = None
    transcriptomic_cols: Optional[List[str]] = None
    metadata: Optional[object] = None  # dict or path

    # --- phenotype split (DGE, GSEA, survival) ---
    phenotype_source_col: str = "BR"
    responder_values: Sequence[str] = ("CR", "PR")
    progressor_values: Sequence[str] = ("PD",)
    label_col: str = "Labels"
    label_values: Tuple[str, str] = ("Responder", "Progressor")

    # --- gene expression scale (DGE, GSEA, network) ---
    log_transform: bool = False

    # --- GSEA / ssGSEA ---
    gene_set: str = HALLMARK_GMT
    gsea_permutations: int = 10000

    # --- survival ---
    survival_endpoints: List[Tuple[str, str]] = field(
        default_factory=lambda: [("OS", "dead"), ("PFS", "progressed")]
    )

    # --- fidelity ---
    corr_method: str = "spearman"
    n_bins: int = 10
    threshold_unique_values: int = 10
    fidelity_masking: bool = True
    clinical_ordinal_features: Optional[List[str]] = None

    # --- network preservation ---
    network_n_genes: int = 10_000
    network_n_permutations: int = 200
    network_threads: int = 8

    # --- cell deconvolution ---
    cibersortx: Optional[Union[str, Dict[str, object]]] = None
    top_k_cell_types: int = 10

    # --- privacy ---
    privacy_control: Optional[object] = None  # path or DataFrame
    privacy_known_genes: Optional[List[str]] = None
    privacy_proportions: Tuple[float, ...] = (1.0,)
    privacy_gene_sets: Optional[object] = None  # .gmt path or {name: genes or .gmt path}
    privacy_n_attacks: int = 10_000
    privacy_max_attempts: int = 1_000_000
    privacy_so_multi_n_cols: Tuple[int, ...] = (2, 3, 5, 7, 10, 20, 50)
    privacy_link_n_neighbors: int = 1
    privacy_seed: int = 42

    # --- meta-score ---
    weights: Tuple[float, float, float] = (1 / 3, 1 / 3, 1 / 3)
    scenarios: Dict[str, Tuple[float, float, float]] = field(default_factory=lambda: dict(SCENARIOS))
    collapse_dims: Tuple[str, ...] = ()

    # --- run ---
    on_error: str = "warn"
    resume: bool = False
    output_dir: str = "autobenchmark_results"
    name_map: Dict[str, str] = field(default_factory=lambda: dict(NAME_MAP))
    name_pattern: str = r"(?P<method>.+)_(?P<seed>\d+)$"

    def __post_init__(self):
        if self.on_error not in ("warn", "raise"):
            raise ValueError(f"on_error must be 'warn' or 'raise', not '{self.on_error}'.")
        self.privacy_proportions = tuple(self.privacy_proportions)
        if not all(0 < p <= 1 for p in self.privacy_proportions):
            raise ValueError(f"privacy_proportions must be fractions in (0, 1], not {self.privacy_proportions}.")
        for name, w in [("weights", self.weights)] + [(f"scenario '{k}'", v) for k, v in self.scenarios.items()]:
            if len(w) != 3 or min(w) < 0 or sum(w) <= 0:
                raise ValueError(f"{name} must be three non-negative weights (statistical fidelity, "
                                 f"biological utility, privacy) with a positive sum, not {w}.")

    def ordinal_features(self, metadata: Optional[dict] = None) -> List[str]:
        """Ordinal clinical features of the fidelity metrics.

        Uses ``clinical_ordinal_features`` if set, otherwise the ``ordinal_categorical``
        entries of ``metadata``, otherwise none.
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
                f"gene_start_column '{self.gene_start_column}' is not a column of the data "
                f"(first columns: {cols[:5]}); set gene_start_column, or clinical_cols and "
                "transcriptomic_cols."
            )
        start = cols.index(self.gene_start_column)
        return cols[:start], cols[start:]

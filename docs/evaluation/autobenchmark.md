# Automatic Benchmark

The **Automatic Benchmark** orchestrates every evaluation dimension — Statistical Fidelity, Biological Utility, and Privacy — into a single reproducible run. Instead of computing each metric separately and manually aggregating the results, `BenchmarkRunner` evaluates twelve dimensions for every candidate synthetic dataset, builds a rank-derived meta-score, and emits a comprehensive report — including the composite figure used to identify the most balanced SDG method.

| Pillar | Dimensions (value, higher = better) |
|---|---|
| Statistical fidelity | Univariate, Bivariate, Network Preservation (normalized Z-summary) |
| Biological utility | DGE (F1-GCS), GSEA (F1-PCS), ssGSEA, Cell Deconvolution, Survival Analysis (C-index score) |
| Privacy | Singling-out (uni), Singling-out (multi), Linkability, Inference — each scored as 1 − risk, the residual risk when an external control cohort is given |

For every dimension, all candidate datasets (method × seed) are ranked jointly (rank 1 = best, ties share the minimum rank, missing values rank last); a method's dimension score is the mean rank of its seeds. A pillar's score is the mean of its dimensions' scores, and the meta-score is the weighted sum of the three pillar scores (lower = better).

---

## Configuration (`BenchmarkConfig`)

A single `BenchmarkConfig` dataclass drives the whole run. The most commonly used fields:

| Group | Field | Default | Purpose |
|---|---|---|---|
| Column layout | `id_column` | `"Patient"` | Sample-ID column in the raw CSVs |
| | `gene_start_column` | `"A1BG"` | First transcriptomic column — everything from here to the end is treated as a gene |
| | `clinical_cols` / `transcriptomic_cols` | `None` | Explicit column partition; overrides splitting at `gene_start_column` |
| Phenotype split | `phenotype_source_col` | `"BR"` | Clinical column the two-group split is derived from |
| | `responder_values` / `progressor_values` | `("CR", "PR")` / `("PD",)` | Values mapped into each group for the biological-utility metrics |
| GSEA | `gene_set` | `None` | Path to the Hallmark `.gmt` used by GSEA/ssGSEA |
| | `gsea_permutations` | `10000` | Permutations for `gseapy.prerank` |
| Survival | `survival_endpoints` | `[("OS", "dead"), ("PFS", "progressed")]` | `(time_col, event_col)` pairs evaluated via Cox models |
| Network | `network_csv` | `None` | Precomputed normalized Z-summary (`Model`/`Tool`, `Seed`, `Value`) for `"reuse"` mode |
| | `network_log_transform`, `network_n_genes`, `network_n_permutations`, `network_threads` | `False`, `10000`, `200`, `8` | Settings of `NetworkPreservation` in `"compute"` mode (needs R with WGCNA) |
| Meta-score | `weights` | `(1/3, 1/3, 1/3)` | (statistical fidelity, biological utility, privacy) pillar weights for the composite |
| | `collapse_dims` | `()` | Dimensions collapsed to a per-method mean *before* ranking (none by default: every seed is ranked) |
| Per-dimension modes | `modes` | `{}` | Override per dimension: `"compute"` / `"reuse"` / `"skip"` |
| | `precomputed_dir`, `cibersortx_dir`, `privacy_pickle_dir` | `None` | Locations of precomputed artifacts for `"reuse"` mode |
| Live privacy attacks | `privacy_control` | `None` | External control cohort (path or DataFrame, same columns as the original); enables the residual risk |
| | `privacy_gene_sets`, `privacy_feature_seed` | `None`, `42` | Named gene sets and seed of the gene fractions defining the attacker knowledge levels |
| | `privacy_seed`, `privacy_n_attacks`, `privacy_max_attempts` | `42`, `10000`, `1000000` | Seed and sizing of the singling-out attacks run live under `mode="compute"` |
| | `privacy_so_uni_proportions`, `privacy_so_multi_n_cols` | see source | Gene fractions of univariate singling out / predicate widths of multivariate singling out |
| | `privacy_link_proportions`, `privacy_link_n_neighbors` | see source | Gene fractions of linkability and inference / neighbor count |
| Output | `output_dir` | `"autobenchmark_results"` | Where `write_report` writes everything — must not already exist |

---

## Running the Benchmark

```python
from synomicsbench.metrics.autobenchmark import BenchmarkConfig, BenchmarkRunner, PRIVACY_DIMS, write_report

config = BenchmarkConfig(
    id_column="Patient",
    gene_start_column="A1BG",
    metadata="feature_metadata.json",
    gene_set="h.all.v2023.hallmark.gmt",
    survival_endpoints=[("OS", "dead"), ("PFS", "progressed")],
    output_dir="autobenchmark_results",
    modes={"Cell Deconvolution": "reuse", "Network Preservation": "reuse",
           **{dim: "compute" for dim in PRIVACY_DIMS}},
    cibersortx_dir="CIBERSORTx_results",
    network_csv="network_preservation.csv",
    privacy_control="control_cohort.csv",
    privacy_seed=42,
    privacy_n_attacks=2000,
)

runner = BenchmarkRunner(config)
result = runner.run(
    original_data="original_melanoma.csv",
    datasets="synthetic_datasets/",   # a directory of gaussiancopula_0.csv, gaussiancopula_1.csv, ...
    seed=42,
)

paths = write_report(result, config)
print(f"Full interactive report: {paths['report_html']}")
```

`datasets` accepts a directory/glob path, a `{name: data}` mapping, or a list of `Candidate`/dict/path entries — see `BenchmarkRunner._candidates` for the exact rules.

!!! warning "Name your files so multi-seed runs are recognized"
    `BenchmarkRunner` groups replicate seeds of the *same* method by parsing each candidate's
    file/dataset name against `BenchmarkConfig.name_pattern` (default:
    `r"(?P<method>.+)_(?P<seed>\d+)$"`). Name synthetic datasets `<method>_<seed>.csv` — e.g.
    `gaussiancopula_0.csv`, `gaussiancopula_1.csv`, `gaussiancopula_42.csv` — so they are all
    recognized as multiple seeds of **Gaussian Copula** and averaged together.

    If the trailing `_<seed>` is missing or inconsistent, each file's full name is treated as
    its own distinct method instead of being aggregated — you will silently end up with more
    "methods" in the report than you actually ran.

---

## Compute vs. Reuse Modes

Each dimension runs in one of three modes, resolved via `BenchmarkConfig.mode_for()`:

| Dimension | Default mode | Notes |
|---|---|---|
| Univariate, Bivariate, DGE, GSEA, ssGSEA, Survival Analysis | `compute` | Recomputed directly from `original_data` + candidates on every run |
| Network Preservation | `compute` | `"compute"` builds the WGCNA networks through rpy2 (R with WGCNA required); `"reuse"` reads `network_csv` |
| Cell Deconvolution | `reuse` | **Reuse-only** — `mode="compute"` raises `ValueError` (CIBERSORTx runs externally); needs `cibersortx_dir` pointing at `CIBERSORTx_*_Results.csv` files |
| Singling-out (uni/multi), Linkability, Inference | `reuse` | Supports **both**. `"reuse"` reads a long risk table (`privacy_csv` argument to `run()`: one row per evaluation with method, seed, attack and risk) or saved anonymeter pickles (`privacy_pickle_dir`); `"compute"` runs the four live anonymeter attacks via the `privacy_*` config fields, against `privacy_control` when given — slower and stochastic, intended for genuinely new datasets rather than reproducing a saved run |

Any dimension can also be set to `"skip"` via `modes`, and a failed dimension (e.g. a missing precomputed artifact) is reported as missing rather than aborting the whole run.

---

## Worked Example

[View the full interactive report](../assets/examples/autobenchmark_report_melanoma.html) — a 5-seed Melanoma run comparing six SDG methods (Avatars K5/K10, CTGAN, Gaussian Copula, Synthpop, TVAE) generated by `write_report`/`write_html_report` with the earlier eight-dimension meta-score (one overall privacy score, GCS/PCS).

---

See [Statistical Fidelity](statistical-fidelity.md), [Biological Utility](index.md#biological-utility), and [Privacy](privacy.md) for the definitions and standalone usage of each underlying metric.

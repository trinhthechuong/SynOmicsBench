# Automatic Benchmark

The **Automatic Benchmark** orchestrates every evaluation dimension — Statistical Fidelity, Biological Utility, and Privacy — into a single reproducible run. Instead of computing each metric separately and manually aggregating the results, `BenchmarkRunner` evaluates all eight dimensions (Univariate, Bivariate, DGE, GSEA, ssGSEA, Cell Deconvolution, Survival Analysis, Privacy) for every candidate synthetic dataset, builds a rank-derived meta-score, and emits a comprehensive report — including the composite figure used to identify the most balanced SDG method.

---

## Configuration (`BenchmarkConfig`)

A single `BenchmarkConfig` dataclass drives the whole run. The most commonly used fields:

| Group | Field | Default | Purpose |
|---|---|---|---|
| Column layout | `id_column` | `"Patient"` | Sample-ID column in the raw CSVs |
| | `gene_start_column` | `"A1BG"` | First transcriptomic column — everything from here to the end is treated as a gene |
| | `clinical_cols` / `transcriptomic_cols` | `None` | Explicit column partition; overrides splitting at `gene_start_column` |
| Phenotype split | `phenotype_source_col` | `"BR"` | Clinical column the two-group split is derived from |
| | `responder_values` / `progressor_values` | `("CR", "PR")` / `("PD",)` | Values mapped into each group for the narrow-utility metrics |
| GSEA | `gene_set` | `None` | Path to the Hallmark `.gmt` used by GSEA/ssGSEA |
| | `gsea_permutations` | `10000` | Permutations for `gseapy.prerank` |
| Survival | `survival_endpoints` | `[("OS", "dead"), ("PFS", "progressed")]` | `(time_col, event_col)` pairs evaluated via Cox models |
| Meta-score | `weights` | `(1/3, 1/3, 1/3)` | (broad, narrow, privacy) pillar weights for the composite |
| | `collapse_dims` | `("DGE", "GSEA", "Privacy")` | Dimensions collapsed to a per-method mean *before* ranking (matches the manuscript's 5-seed MetaScore) |
| Per-dimension modes | `modes` | `{}` | Override per dimension: `"compute"` / `"reuse"` / `"skip"` |
| | `precomputed_dir`, `cibersortx_dir`, `privacy_pickle_dir` | `None` | Locations of precomputed artifacts for `"reuse"` mode |
| Live privacy attacks | `privacy_seed`, `privacy_n_attacks`, `privacy_max_attempts` | `42`, `10000`, `1000000` | Sizing/reproducibility for anonymeter attacks run live under `mode="compute"` |
| | `privacy_so_uni_proportions`, `privacy_so_multi_n_cols` | see source | Singling-out attack sampling proportions / column-subset sizes |
| | `privacy_link_proportions`, `privacy_link_n_neighbors` | see source | Linkability attack sampling proportions / neighbor count |
| Output | `output_dir` | `"autobenchmark_results"` | Where `write_report` writes everything — must not already exist |

---

## Running the Benchmark

```python
from synomicsbench.metrics.autobenchmark import BenchmarkConfig, BenchmarkRunner, write_report

config = BenchmarkConfig(
    id_column="Patient",
    gene_start_column="A1BG",
    metadata="feature_metadata.json",
    gene_set="h.all.v2023.hallmark.gmt",
    survival_endpoints=[("OS", "dead"), ("PFS", "progressed")],
    output_dir="autobenchmark_results",
    modes={"Cell Deconvolution": "reuse", "Privacy": "compute"},
    cibersortx_dir="CIBERSORTx_results",
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
| Cell Deconvolution | `reuse` | **Reuse-only** — `mode="compute"` raises `ValueError` (CIBERSORTx runs externally); needs `cibersortx_dir` pointing at `CIBERSORTx_*_Results.csv` files |
| Privacy | `reuse` | Supports **both**. `"reuse"` reads a precomputed CSV (`privacy_csv` argument to `run()`) or saved anonymeter pickles (`privacy_pickle_dir`); `"compute"` runs the four live anonymeter attacks (singling-out uni/multi, linkability, inference) via the `privacy_*` config fields — slower and stochastic, intended for genuinely new datasets rather than reproducing a saved run |

Any dimension can also be set to `"skip"` via `modes`, and a failed dimension (e.g. a missing precomputed artifact) is reported as missing rather than aborting the whole run.

---

## Worked Example

[View the full interactive report](../assets/examples/autobenchmark_report_melanoma.html) — a 5-seed Melanoma run comparing six SDG methods (Avatars K5/K10, CTGAN, Gaussian Copula, Synthpop, TVAE) across all eight dimensions, generated by `write_report`/`write_html_report`.

---

See [Statistical Fidelity](statistical-fidelity.md), [Biological Utility](index.md#biological-utility), and [Privacy](privacy.md) for the definitions and standalone usage of each underlying metric.

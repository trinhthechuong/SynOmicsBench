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

## Meta-Score & Composite Ranking

For each dimension, every (method, seed) candidate's score is ranked (higher score = better = lower rank), then averaged per method across seeds — this is `build_metascore`'s output, the *meta-score*. Dimensions in `collapse_dims` are first collapsed to one value per method before ranking.

The composite combines the eight per-dimension meta-scores into three equally-weighted pillars:

$$
\text{Broad Utility} = \frac{w_{broad}}{2}\left(\text{rank}_{Univariate} + \text{rank}_{Bivariate}\right)
$$

$$
\text{Narrow Utility} = \frac{w_{narrow}}{5}\sum_{d\, \in\, \{DGE,\, GSEA,\, ssGSEA,\, Cell\ Deconv,\, Survival\}} \text{rank}_d
$$

$$
\text{Privacy} = w_{privacy} \cdot \text{rank}_{Privacy}
$$

$$
\text{Total} = \text{Broad Utility} + \text{Narrow Utility} + \text{Privacy}
$$

**Lower Total = a more balanced method.** The composite is only built once all eight dimensions are present in a run.

---

## Report Outputs

`write_report(result, config)` writes everything into `config.output_dir` and returns a dict of paths:

| File | Contents |
|---|---|
| `per_dimension_long.csv` | Every `(Dimension, Model, Seed, Value)` row |
| `per_metric_values.csv` / `per_metric_ranks.csv` | Method × dimension tables (mean value / mean rank) |
| `metascore.json` | The rank-derived meta-score per dimension |
| `metascore_composite.{csv,png,pdf}` | Composite pillar scores + the stacked-bar figure (only if all eight dimensions ran) |
| `per_metric_scores.png` | Grouped bar chart of per-dimension values, one color per SDG method |
| `REPORT.md` | Human-readable Markdown summary |
| `report.html` | Self-contained HTML report (hero banner, chip stats, rank heatmap, radar chart, tables — no external assets) |

---

## Worked Example: Melanoma, 5 Seeds

A 5-seed run comparing six SDG methods (Avatars K5/K10, CTGAN, Gaussian Copula, Synthpop, TVAE) across all eight dimensions:

**Per-metric scores (mean over seeds, higher = better)**

| Model           |   Univariate |   Bivariate |    DGE |   GSEA |   ssGSEA |   Cell Deconvolution |   Survival Analysis |   Privacy |
|:----------------|-------------:|------------:|-------:|-------:|---------:|---------------------:|--------------------:|----------:|
| Avatars K10     |       0.8433 |      0.9317 | 0.579  | 0.4324 |   0.6326 |               0.5224 |              0.9251 |    0.8525 |
| Avatars K5      |       0.8572 |      0.9337 | 0.5884 | 0.3946 |   0.6805 |               0.5473 |              0.9197 |    0.8479 |
| CTGAN           |       0.7665 |      0.9162 | 0.4748 | 0.1541 |   0.7179 |               0.2755 |              0.7737 |    0.8483 |
| Gaussian Copula |       0.8933 |      0.9376 | 0.6279 | 0.2784 |   0.8617 |               0.4606 |              0.9405 |    0.8585 |
| Synthpop        |       0.9237 |      0.9249 | 0.5297 | 0.3081 |   0.7245 |               0.65   |              0.7807 |    0.6111 |
| TVAE            |       0.8021 |      0.9078 | 0.5643 | 0.5135 |   0.6488 |               0.3614 |              0.8489 |    0.8388 |

**Composite (lower Total = more balanced)**

|                 |   Broad Utility |   Narrow Utility |   Privacy |   Total |
|:----------------|----------------:|-----------------:|----------:|--------:|
| TVAE            |           8.567 |            5.307 |     7     |  20.873 |
| CTGAN           |           8.433 |            7.693 |     3.667 |  19.793 |
| Synthpop        |           3.5   |            5.04  |     8.667 |  17.207 |
| Avatars K5      |           3.633 |            3.68  |     5.333 |  12.647 |
| Avatars K10     |           5.033 |            4.227 |     2     |  11.26  |
| Gaussian Copula |           1.833 |            3.44  |     0.333 |   5.607 |

**Most balanced method: Gaussian Copula** (Total = 5.607) — the strongest and most consistent performer across statistical fidelity, biological utility, and privacy risk in this cohort.

[View the full interactive report](../assets/examples/autobenchmark_report_melanoma.html) generated by `write_html_report` for this run — including the per-dimension rank heatmap and radar chart.

---

See [Statistical Fidelity](statistical-fidelity.md), [Biological Utility](index.md#biological-utility), and [Privacy](privacy.md) for the definitions and standalone usage of each underlying metric.

# Automatic Benchmark

The **Automatic Benchmark** compares synthetic datasets with the original data in one call. `run_benchmark` computes the metrics you choose, ranks every synthetic dataset into a rank-derived meta-score, shows how the ranking depends on the weights of the three pillars, and writes a report.

Everything is computed from the original and synthetic data, except cell deconvolution: CIBERSORTx runs outside Python, so its result files are the only input you prepare yourself.

---

## Quick start

`run_benchmark` needs to know the columns of your cohort: they differ from one dataset to the next, so declare them first.

```python
from synomicsbench.metrics.autobenchmark import run_benchmark

res = run_benchmark(
    original="original_data.csv",
    synthetic="synthetic/",                 # one CSV per dataset: gaussiancopula_0.csv, ctgan_0.csv, ...
    metrics="all",
    # columns of your cohort
    id_column="...",                        # sample identifier
    gene_start_column="...",                # first gene column: the columns before it are clinical
    phenotype_source_col="...",             # column that holds the group of each patient
    responder_values=("...",),              # values of that column in group 1
    progressor_values=("...",),             # values of that column in group 2
    survival_endpoints=[("...", "...")],    # (time column, event column) of each endpoint
    # other inputs
    log_transform=False,                    # True if the gene values are on a linear scale (e.g. TPM)
    cibersortx="cibersortx_results/",       # only needed for cell deconvolution
    output_dir="benchmark",
)

res.ranking        # meta-score of every method, best (lowest) first
res.errors         # metrics that could not be computed, with the reason
res.report_html    # benchmark/report.html
```

**Example: the Melanoma cohort of SynOmicsBench.** The columns used by the benchmark are:

| Patient | BR | OS | dead | PFS | progressed | A1BG, A1BG-AS1, ... |
|---|---|---|---|---|---|---|
| sample identifier | best response: CR, PR, SD, PD | overall survival (months) | 1 = death | progression-free survival (months) | 1 = progression | gene expression (TPM) |

The responders (CR, PR) are compared with the progressors (PD):

```python
res = run_benchmark(
    original="original_data.csv",
    synthetic="synthetic/",
    metrics="all",
    id_column="Patient",
    gene_start_column="A1BG",
    phenotype_source_col="BR",
    responder_values=("CR", "PR"),
    progressor_values=("PD",),
    survival_endpoints=[("OS", "dead"), ("PFS", "progressed")],
    log_transform=True,
    cibersortx="cibersortx_results/",
    output_dir="benchmark",
)
```

- **Groups.** DGE, GSEA and survival compare group 1 with group 2. You choose the groups: `responder_values=("CR", "PR", "SD")` puts stable disease in group 1, and any two-group split stored in one column works (e.g. a mutation status). Patients whose value is in neither list are left out of these three metrics.
- **Survival.** `survival_endpoints` is a list, also for one endpoint: `[("OS", "dead")]`. With several endpoints, the survival score is their mean.
- **Checks.** The columns each selected metric needs are checked before anything is computed: a column that is not found stops the run at once with its name. If your cohort has no groups or no survival data, leave the corresponding metrics out (see below).
- **Names of the files.** Each synthetic file name gives the method and the seed: `gaussiancopula_0.csv` is seed 0 of Gaussian Copula. A method's score is the mean over its seeds. `synthetic` can also be a mapping `{name: path or DataFrame}`. Keep the original data out of the `synthetic` directory.

Computing every metric on a cohort of ~20,000 genes takes hours: GSEA runs 10,000 permutations per dataset, network preservation builds WGCNA networks in R, and the privacy attacks scale with the number of columns. Start with a few metrics to check the setup.

### Only some metrics

The column settings of the Quick start are left out below for brevity.

```python
# Biological utility only: DGE concordance and survival
res = run_benchmark("original_data.csv", "synthetic/", metrics=["f1_gcs", "survival"])

# The four privacy attacks, against a control cohort
res = run_benchmark("original_data.csv", "synthetic/", metrics="privacy",
                    privacy_control="control_cohort.csv")
```

The meta-score is computed on the metrics that were run: a pillar with no metric is left out, and the weights of the other pillars are rescaled to sum to 1.

---

## Metrics

| Name in `metrics=` | Metric | Pillar | Value | Needs |
|---|---|---|---|---|
| `univariate` | Univariate similarity | Statistical fidelity | score, higher is better | |
| `bivariate` | Bivariate similarity | Statistical fidelity | score | |
| `network` | [Network preservation](statistical-fidelity.md#co-expression-network-preservation) (normalized Z-summary) | Statistical fidelity | score | R with WGCNA |
| `f1_gcs` | [F1-GCS](biological-utility/dge.md) | Biological utility | score | phenotype groups |
| `f1_pcs` | [F1-PCS](biological-utility/gsea.md) | Biological utility | score | phenotype groups, gene set |
| `ssgsea` | [ssGSEA](biological-utility/ssgsea.md) (KS-complement) | Biological utility | score | gene set |
| `cell_deconvolution` | [Cell deconvolution](biological-utility/cell-deconvolution.md) (Aitchison score) | Biological utility | score | CIBERSORTx results |
| `survival` | [Survival score](biological-utility/survival-analysis.md) | Biological utility | score | phenotype groups, survival columns |
| `singling_out_uni` | Singling out, univariate | Privacy | risk, lower is better | |
| `singling_out_multi` | Singling out, multivariate | Privacy | risk | |
| `linkability` | Linkability | Privacy | risk | |
| `inference` | Attribute inference | Privacy | risk | |

Groups: `"all"`, `"fidelity"`, `"utility"`, `"privacy"`. With `"all"` or `"utility"` and no CIBERSORTx results, cell deconvolution is left out and reported in `res.errors`.

GSEA and ssGSEA use the MSigDB Hallmark gene sets bundled with SynOmicsBench unless you pass `gene_set="my_sets.gmt"`.

---

## Cell deconvolution: the CIBERSORTx results

Run CIBERSORTx on the original data and on every synthetic dataset, then pass the result files:

- as a directory, with one CSV per dataset named after it (`ctgan_0.csv`, or CIBERSORTx's own `CIBERSORTx_ctgan_0_Results.csv`) and the original data as `original.csv`, `Origin.csv` or `CIBERSORTx_Origin_Results.csv`;
- or as a mapping: `cibersortx={"original": "cbx/original.csv", "ctgan_0": "cbx/ctgan_0.csv", ...}`.

Each dataset is one CIBERSORTx run: the mixture file is its gene expression, genes in rows and patients in columns. SynOmicsBench used the LM22 signature matrix in absolute mode with B-mode batch correction, quantile normalization disabled and 1,000 permutations.

The cell types are the columns of the files (CIBERSORTx's `P-value`, `Correlation` and `RMSE` columns are ignored); the score uses the `top_k_cell_types` (10) most abundant cell types of the original data.

---

## Privacy

The four attacks run with [Anonymeter](https://arxiv.org/abs/2211.10459), with the [adversary model](privacy.md#adversary-model) of the privacy page. The adversary knows the clinical columns and, by default, all the genes; `privacy_known_genes=[...]` restricts the genes of every attack. `privacy_proportions` and `privacy_gene_sets` set the levels of adversary knowledge, as `proportions` and `gene_sets` do for the [privacy functions](privacy.md#adversary-model). With `privacy_control` (patients of the same population that the generators never saw), the risks are residual risks, and only the columns shared with the control cohort are attacked. When an attack is run with several settings (knowledge levels, predicate widths, inferred columns), its risk is the mean over them. The random draws of the attacks on a synthetic dataset use the seed of that dataset, so a run can be repeated.

---

## How the meta-score is computed

1. On every metric, all synthetic datasets (method × seed) are ranked together: rank 1 is the highest score, or the lowest risk. Ties share the lowest rank. A dataset without a value (e.g. a synthetic cohort without one of the phenotype groups) gets a score of 0, or the highest risk, and ranks last.
2. The rank-derived score of a method on a metric is the mean rank of its datasets.
3. A pillar score is the mean of the rank-derived scores of its metrics.
4. The meta-score is the weighted sum of the pillar scores, with `weights=(statistical fidelity, biological utility, privacy)`, equal by default. Lower is better.

### Sensitivity to the weights

The right weights depend on how the synthetic data will be shared. The report gives the ranking under four scenarios (`scenarios`), those of the SynOmicsBench manuscript, described on the [Leaderboard](leaderboard.md#data-sharing-scenarios):

| Scenario | Statistical fidelity | Biological utility | Privacy |
|---|---|---|---|
| Equal weights | 1/3 | 1/3 | 1/3 |
| Controlled sharing within a research consortium | 0.3 | 0.5 | 0.2 |
| Public release for open challenges or hackathons | 0.2 | 0.3 | 0.5 |
| Method development and pipeline testing | 0.3 | 0.2 | 0.5 |

It also draws a triangle of all the weights (step 0.01), coloured by the method ranked first: moving the pointer shows the weights and the ranking at that point. The same analysis is available in Python:

```python
from synomicsbench.metrics.autobenchmark import scenario_table, weight_sweep

scenario_table(res.metascore, {"Privacy first": (0.2, 0.2, 0.6)})
sweep, summary = weight_sweep(res.metascore)   # summary: share of the weights where each method ranks first
```

---

## Output files

`output_dir` contains:

| File | Content |
|---|---|
| `report.html` | Self-contained report: ranking, sensitivity to the weights, metric values |
| `REPORT.md` | The same tables in Markdown |
| `per_dimension_long.csv` | Every (metric, method, seed, value) |
| `per_metric_values.csv`, `per_metric_ranks.csv` | Mean value and rank-derived score, method × metric |
| `metascore.json`, `metascore_composite.csv` | Rank-derived score per metric; weighted pillar scores and meta-score |
| `metascore_scenarios.csv`, `weight_sweep_summary.csv` | Ranking under each scenario and over all weights |
| `metascore_composite.png` / `.pdf`, `per_metric_scores.png` | Figures |
| `result.pkl` | The `BenchmarkResult`, to rewrite the report with `write_report` |
| `_work/values/` | The values of every metric, saved as soon as it is computed (see `resume`) |
| `_work/` | Other intermediate files |

---

## Example report

The example report benchmarks the Melanoma cohort as in the SynOmicsBench manuscript: six SDG methods (Avatars, CTGAN, Gaussian Copula, Synthpop, TVAE, TabDiff) × five seeds, the twelve metrics, the Gide et al. cohort as privacy control and the six levels of adversary knowledge.

```python
from synomicsbench.metrics.autobenchmark import FGES_GMT, run_benchmark

res = run_benchmark(
    original="melanoma/original_data.csv",
    synthetic="melanoma/synthetic/",                  # avatars_0.csv ... tabdiff_42.csv
    metrics="all",
    id_column="Patient",
    gene_start_column="A1BG",
    phenotype_source_col="BR",
    responder_values=("CR", "PR"),
    progressor_values=("PD",),
    survival_endpoints=[("OS", "dead"), ("PFS", "progressed")],
    log_transform=True,                               # gene values on a linear scale
    cibersortx="melanoma/cibersortx/",                # CIBERSORTx (LM22) results
    privacy_control="melanoma/gide_control.csv",      # Gide et al., aligned to the cohort
    privacy_proportions=(0.05, 0.25, 0.5, 0.75, 1.0),
    privacy_gene_sets={"FGES": FGES_GMT},
    output_dir="melanoma_benchmark",
)
```

[Open the example report](../assets/examples/autobenchmark_report_melanoma.html). The ranks are computed over these 30 datasets only, so the share of the weights where each method ranks first differs from the [Leaderboard](leaderboard.md), which pools the 90 datasets of the three cohorts.

---

## Advanced settings

All settings are fields of `BenchmarkConfig`; `run_benchmark` accepts any of them as keyword arguments, or a whole `config=`.

| Field | Default | Purpose |
|---|---|---|
| `clinical_cols` / `transcriptomic_cols` | `None` | Explicit column partition instead of `gene_start_column` |
| `metadata` | `None` | `feature_metadata.json` of the processing pipeline; its ordinal columns are treated as ordinal by the fidelity metrics |
| `label_values` | `("Responder", "Progressor")` | Names of the two phenotype groups |
| `gene_set`, `gsea_permutations` | Hallmark, `10000` | GSEA and ssGSEA |
| `network_n_genes`, `network_n_permutations`, `network_threads`, `network_log_transform` | `10000`, `200`, `8`, `False` | Network preservation |
| `privacy_proportions`, `privacy_gene_sets`, `privacy_seed` | `(1.0,)`, `None`, `42` | Levels of adversary knowledge: fractions of the genes and named gene sets (e.g. `{"FGES": FGES_GMT}`) |
| `privacy_n_attacks`, `privacy_max_attempts`, `privacy_so_multi_n_cols` | `10000`, `1000000`, `(2, 3, 5, 7, 10, 20, 50)` | Singling-out attacks |
| `privacy_link_n_neighbors` | `1` | Linkability attack |
| `weights`, `scenarios` | equal, the four above | Meta-score and sensitivity analysis; a scenario that puts no weight on the evaluated pillars is left out |
| `log_transform` | `False` | Gene values on a linear scale: log2(x + 1) before DGE, GSEA and network preservation |
| `collapse_dims` | `()` | Metrics averaged per method before ranking |
| `on_error` | `"warn"` | `"raise"` stops at the first metric that fails |
| `resume` | `False` | `True` reads back the metrics already saved in `output_dir/_work/values` by a run with the same inputs and settings, and computes only the missing ones, e.g. after a job was stopped |
| `name_map`, `name_pattern` | | Display names and seed parsing of the dataset names |

# What's new in 1.2.0

Version 1.2.0 adds the evaluation metrics of the revised SynOmicsBench benchmark and a simpler automatic benchmark. Every metric reproduces the numbers reported in the revised manuscript.

## New metrics

### Statistical fidelity

- **Co-expression network preservation** ([`NetworkPreservation`](evaluation/statistical-fidelity.md#co-expression-network-preservation)): a WGCNA network of the original data is compared with each synthetic dataset through the normalized median Z-summary of module preservation, the adjusted Rand index of the module labels and the true-positive rate of the strongest 5% of edges. Requires R with the WGCNA package (called through rpy2).

### Biological utility

- **F1-GCS and F1-PCS** ([DGE](evaluation/biological-utility/dge.md), [GSEA](evaluation/biological-utility/gsea.md)): the concordance of significant genes and pathways is reported as recall, precision and F1-score.
- **Effect-size calibration**: slope (OLS for genes, Theil–Sen for pathways), Pearson correlation and sign concordance of the synthetic versus original effect sizes (Log2FC, NES), with `plot_calibration_scatter`.
- **Survival analysis** ([`compute_cox_metrics`](evaluation/biological-utility/survival-analysis.md#c-index-confidence-interval-hazard-ratio-and-its-direction)): C-index with a bootstrap confidence interval, hazard ratio, whether its direction matches the original, and the survival score; `plot_cindex_forest` draws the forest plot.

### Privacy

- **Control cohort** ([Privacy](evaluation/privacy.md)): every attack accepts `control=`, a dataset of patients the generator never saw, and reports Anonymeter's residual risk. Without a control, the attack risk is compared with the naive baseline.
- **Levels of adversary knowledge** ([Adversary model](evaluation/privacy.md#adversary-model)): univariate singling out, linkability and attribute inference take the same `proportions` (random gene subsets) and `gene_sets` (named gene panels); the TME-related functional gene expression signatures (FGES) are bundled as `FGES_GMT`. Singling out runs the polars implementation of Anonymeter's evaluator used for the manuscript. `evaluator_seed` seeds the random draws of the four attacks (predicates, target records), so that an evaluation can be repeated.
- **`privacy_risk_table`** collects the risks of any attack into one table.

### Automatic benchmark

- **One call**: [`run_benchmark`](evaluation/autobenchmark.md) computes the selected metrics from the original and synthetic data, ranks them and writes the report. Only the CIBERSORTx results of cell deconvolution come from outside the package.
- **Any subset of metrics**: `metrics=["f1_gcs", "survival"]`, `metrics="privacy"`, ...; the meta-score uses the pillars that were evaluated.
- The meta-score ranks **twelve metrics** in three pillars: Univariate, Bivariate and Network preservation; F1-GCS, F1-PCS, ssGSEA, Cell deconvolution and Survival analysis; and the risks of univariate singling out, multivariate singling out, linkability and inference, ranked lowest first.
- **Sensitivity to the weights**: the report gives the ranking under equal weights and the three data-sharing scenarios of the manuscript, and an interactive weight triangle. See the [example report](assets/examples/autobenchmark_report_melanoma.html).
- **Privacy as in the manuscript**: `privacy_proportions` and `privacy_gene_sets` set the levels of adversary knowledge of the privacy metrics.
- **Long runs**: every metric is saved as soon as it is computed, and `resume=True` computes only the metrics a stopped run did not save.

## Benchmark Leaderboard

The [Benchmark Leaderboard](evaluation/leaderboard.md) ranks the six SDG methods over the 90 synthetic datasets of the manuscript, under equal weights and the three data-sharing scenarios, with the interactive weight triangle.

## API changes

| Before | 1.2.0 |
|---|---|
| `GCSAnalyzer(q_col=..., q_thr=...)`, `PCSAnalyzer(q_col=..., q_thr=...)` | `sig_col=`, `sig_thr=`: choose a P-value or a Q-value column (defaults: `"P_value"` for DGE, `"FDR q-val"` for GSEA) |
| GCS/PCS weight `w` | Removed; `gene_set_concordance_score` and `pathway_concordance_score` return the recall |
| (new) | `compute_metrics(..., metrics=)` returns a float for one metric name, a dict for a list |
| `SurvivalEvaluator.compute_cindex_scores`, column `C-index_score` | `compute_survival_scores`, column `Survival_score` |
| `eval_singling_out_univariate` / `eval_linkability_genes_clinical`: four gene fractions by default | All the genes passed as `transcriptomic_cols` by default (`proportions=(1.0,)`) |
| `eval_inference_genes_clinical` returned `(secret, results)` pairs for the genes passed | Takes `proportions`, `gene_sets` and `seed` like the other attacks and returns `(level, secret, results)`; `privacy_risk_table` adds a `Secret` column |
| `overall_privacy_from_attacks`, `overall_privacy_from_pickles`, `overall_privacy_from_csv` | Removed; the automatic benchmark ranks each attack category |
| `BenchmarkConfig(modes=..., precomputed_dir=..., privacy_pickle_dir=..., network_csv=..., cibersortx_dir=...)` | Removed: every metric is computed; `cibersortx=` takes a directory or a mapping |
| `BenchmarkRunner.run(..., dimensions=)` | `run_benchmark(..., metrics=)` or `BenchmarkRunner.run(..., metrics=)` |
| `gene_set` required for GSEA and ssGSEA | MSigDB Hallmark gene sets bundled as the default |

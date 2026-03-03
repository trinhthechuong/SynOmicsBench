# Survival Analysis Validation

SynOmicBench evaluates the utility of synthetic multi-omic data by assessing its ability to preserve clinical prognostic signals. This is critical for biomedical research, where synthetic datasets must support the same survival-based discoveries as real data without compromising patient privacy.

## Overview

The survival analysis module validates whether prognostic gene signatures and clinical features identified in original data maintain their predictive power in synthetic counterparts. This involves comparing Kaplan-Meier (KM) survival curves and Cox Proportional Hazards (CPH) model performance across datasets.

### Key Metrics

- **Log-rank Test P-value**: Assesses whether the survival difference between phenotype groups (e.g., responder vs. non-responder) is statistically significant.
- **Concordance Index (C-index)**: Measures the predictive accuracy of survival models. SynOmicBench calculates a "C-index score" representing the similarity between original and synthetic model performance:
    $Score = 1 - |C_{orig} - C_{syn}|$
- **Hazard Ratio Preservation**: Evaluates if the direction and magnitude of risk associations remain consistent.

## Methodology

SynOmicBench uses a grid-based evaluation framework to compare the original dataset against multiple synthetic replicates.

1. **Phenotype Grouping**: Users specify a clinical phenotype (e.g., `Benefit` for immunotherapy response) and two groups to compare.
2. **Model Fitting**: Kaplan-Meier survival functions are estimated for each group within each dataset.
3. **Cox Modeling**: A Cox Proportional Hazards model is fitted to predict survival time based on the binary phenotype.
4. **Visualization**: A standardized grid of survival curves allows for qualitative comparison of survival trajectories and censorship patterns.

## Benchmark Results

Benchmark results across TCGA and clinical trial datasets (ccRCC, Melanoma, NSCLC) demonstrate varying degrees of survival signal preservation:

- **Top Performers**: **Gaussian Copula** and **Avatars** consistently show the highest C-index similarity scores (>0.90) and maintain the statistical significance of prognostic markers.
- **Deep Learning Challenges**: TVAE and CTGAN occasionally struggle with survival-relevant correlations, sometimes producing "insufficient events" errors or non-significant log-rank tests if the synthetic data lacks the necessary multi-feature dependencies.
- **Replicate Stability**: Gaussian Copula shows the lowest variance across different synthesis seeds, making it highly reliable for survival-based downstream tasks.

### Key Findings
!!! success "High Fidelity in Statistical Models"
    Gaussian Copula preserves the non-linear dependencies between gene expression and survival outcomes better than deep generative models for small-to-medium cohorts.

!!! tip "C-index as a Utility Proxy"
    The C-index similarity score is a robust metric for determining if a synthetic dataset is "safe" for preliminary prognostic biomarker discovery.

## Visualization

The following figure illustrates a typical survival analysis benchmark, comparing the original dataset (left) with synthetic models.

![Survival Analysis Benchmark](../../assets/figures/narrow-utility-survival.png)
*Figure 8: Kaplan-Meier survival curve grid comparing Original data with synthetic replicates. The top strips indicate the synthesizer, with p-values and C-indices annotated.*

## Code Example

The `SurvivalEvaluator` class provides a high-level API for running these comparisons.

```python
from SynOmics.metrics.narrow_utility.survival_analysis import SurvivalEvaluator

# Define datasets and comparison groups
datasets = {
    "Origin": real_df,
    "Gaussian Copula": gc_df,
    "CTGAN": ctgan_df
}

phenotype = {"Benefit": ["Responder", "Non-Responder"]}

# Initialize evaluator
evaluator = SurvivalEvaluator(
    datasets_dict=datasets,
    phenotype=phenotype,
    time_target="OS",
    event_target="OS_CNSR"
)

# Compute metrics
summary_df = evaluator.compute_survival_metrics()
scored_df = evaluator.compute_cindex_scores()

# Plot KM grid
fig, _ = evaluator.plot_grid(figsize=(15, 5))
fig.savefig("survival_benchmark.png")
```

## Clinical Significance

Preserving survival signals is the "gold standard" for synthetic omics utility. If a synthetic dataset maintains the same survival separations as the real data, it can be used for:
- Testing survival analysis pipelines.
- Educational demonstrations of clinical prognosis.
- Preliminary hypothesis generation for new prognostic biomarkers.

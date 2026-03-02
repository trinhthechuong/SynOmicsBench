# Single-sample Gene Set Enrichment Analysis (ssGSEA)

## Overview
Single-sample Gene Set Enrichment Analysis (ssGSEA) represents a critical component of narrow utility evaluation in SynOmicBench. While standard Gene Set Enrichment Analysis (GSEA) compares groups of samples (e.g., tumor vs. normal), ssGSEA calculates an enrichment score for each individual sample across a defined set of biological pathways or gene signatures. This per-sample resolution is essential for precision medicine applications, where understanding the unique molecular landscape of a single patient's tumor can guide personalized therapeutic decisions.

In the context of synthetic data generation, preserving the distribution and inter-sample variability of these enrichment scores is a high-bar requirement. It tests whether the synthetic generation method has captured not just the general biological signals, but the complex, high-dimensional correlation structures that define individual sample heterogeneity. A high-quality synthetic dataset should allow a researcher to perform the same patient stratification or pathway-level clustering as they would with the original data.

## Methodology
The ssGSEA evaluation in SynOmicBench follows a rigorous pipeline to compare the biological fidelity of synthetic cohorts against their original counterparts. This process is designed to expose failures in capturing the co-expression patterns within gene sets.

### Pathway Selection
We utilize established gene set databases, primarily focusing on the Hallmark gene sets from the Molecular Signatures Database (MSigDB). These gene sets represent well-defined biological processes, such as the cell cycle, immune response, and metabolic pathways, with minimal redundancy and high consensus in the biological literature. This selection provides a broad yet manageable scope for evaluating the functional preservation of synthetic transcriptomic data.

### Score Calculation
For both original and synthetic datasets, ssGSEA scores are calculated using a rank-based enrichment method. The process involves several mathematical steps:
1.  **Gene Ranking**: Within each sample, genes are ranked according to their expression levels.
2.  **Cumulative Distribution**: An enrichment score (ES) is calculated as the difference between the weighted cumulative distribution functions of genes within a specific set and those outside the set.
3.  **Normalization**: The resulting scores are normalized to allow for comparison across different pathways and samples, providing a relative measure of pathway activity.

### Statistical Comparison
The primary metric for evaluation is the preservation of the distribution of these scores. We assess whether the synthetic data maintains the same mean, variance, and overall shape of the pathway activity distribution seen in the original data. We employ several statistical tests, including:
*   **Kolmogorov-Smirnov (KS) Test**: To determine if the distributions of ssGSEA scores for the original and synthetic samples differ significantly.
*   **Jensen-Shannon Divergence**: To quantify the similarity between the probability distributions of the enrichment scores.
*   **Correlation preservation**: We examine whether the co-regulation between different biological pathways (e.g., the coordination between DNA repair and cell cycle progression) is maintained in the synthetic output.

## Benchmark Results
Our benchmarking reveals significant performance differences across various synthetic data generation architectures when subjected to ssGSEA evaluation. This test is particularly effective at highlighting the "blunting" of biological signals common in many generative models.

![ssGSEA Evaluation Results](../../assets/figures/narrow-utility-ssgsea.png)
*Figure 6: Comparison of ssGSEA score distributions and pathway-pathway correlations across different synthetic generation methods, illustrating the preservation of sample-level heterogeneity.*

### Performance Analysis
Through extensive testing across multiple TCGA datasets, we have identified several tiers of performance among synthetic generation methods:

1.  **High Fidelity (Avatars, Copula)**: Methods that explicitly model or preserve the underlying correlation structure of the data, such as Avatar-based approaches and Gaussian Copulas, demonstrate superior performance. These methods successfully capture the sample-level heterogeneity, resulting in ssGSEA score distributions that closely mirror the original data.
2.  **Moderate Fidelity (VAEs, Diffusion Models)**: Modern generative architectures like Variational Autoencoders (VAEs) and Denoising Diffusion Probabilistic Models (DDPMs) often capture broad utility metrics well. However, they frequently struggle with the precise per-sample enrichment scores, often producing "blurred" biological signals where the extremes of pathway activity (high or low activity outliers) are compressed.
3.  **Low Fidelity (Standard GANs, Independent Sampling)**: Methods that ignore feature-feature correlations or suffer from mode collapse fail this test entirely. Because ssGSEA relies heavily on the coordinated expression of entire gene sets, any breakdown in these correlations leads to wildly inaccurate enrichment scores.

## Key Findings
!!! note "Biological Heterogeneity"
    Avatars-based methods are particularly effective at preserving patient-level pathway heterogeneity. This suggests that the local structure preservation inherent in the Avatar approach is well-suited for maintaining the subtle molecular differences that distinguish individual samples within a clinical cohort.

!!! warning "Correlation Collapse"
    Many synthetic generation methods suffer from "correlation collapse" when evaluated via ssGSEA. Even if the univariate distributions of individual genes appear well-preserved, the failure to maintain the coordinated expression patterns within a gene set leads to inaccurate enrichment scores. This renders the synthetic data less useful for pathway-level clinical research and patient stratification.

!!! tip "Precision Medicine Readiness"
    For synthetic data to be considered "precision medicine ready," it must pass the ssGSEA benchmark. This ensures that downstream tasks, such as predicting pathway-based drug responses, remain valid when applied to synthetic patients.

## Code Example
The following snippet demonstrates how to perform ssGSEA-based evaluation using the SynOmicBench API. This allows developers to quickly assess their models' biological fidelity.

```python
import pandas as pd
from synomicbench.evaluation import NarrowUtilityEvaluator
from synomicbench.datasets import load_tcga_data

# Load original and synthetic datasets for evaluation
# In this example, we compare original BRCA data with Avatar-generated synthetic data
original_data = load_tcga_data("BRCA", type="original")
synthetic_data = load_tcga_data("BRCA", type="avatar")

# Initialize the evaluator specifically for ssGSEA narrow utility
# We use the MSigDB Hallmark gene sets as our reference pathways
evaluator = NarrowUtilityEvaluator(
    method="ssgsea",
    gene_sets="msigdb_hallmark",
    normalization="z-score"
)

# Run the comprehensive evaluation pipeline
# This calculates enrichment scores, distribution metrics, and correlations
results = evaluator.evaluate(original_data, synthetic_data)

# Access the summary statistics of the evaluation
print(f"Mean KS-Statistic across all pathways: {results['summary']['mean_ks']:.4f}")
print(f"Percentage of pathways passing similarity threshold: {results['summary']['pass_rate']}%")

# Generate a comparative visualization for a specific pathway of interest
# This helps in visually confirming the preservation of pathway activity distributions
results.plot_pathway_comparison(
    pathway_name="HALLMARK_P53_PATHWAY",
    save_path="p53_comparison.png"
)

# Export the full results for detailed reporting
results.to_csv("ssgsea_detailed_results.csv")
```

By integrating ssGSEA into the evaluation framework, SynOmicBench ensures that synthetic data isn't just statistically similar on a surface level, but retains the deep biological insights required for advanced genomic analysis and clinical research.

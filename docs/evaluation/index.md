# Evaluation Framework

SynOmicBench evaluates synthetic cancer omics data across three complementary dimensions to ensure that generated datasets are statistically similar to the original, biologically meaningful for downstream analyses, and safe for data sharing. This multidimensional approach addresses the fundamental trade-off between biological utility and patient privacy.

---

## Evaluation Dimensions

Our evaluation framework is organized into three distinct pillars, each measuring different aspects of synthetic data quality:

### [Broad Utility](broad-utility.md)

Broad utility assesses how well the synthetic data preserves the global statistical properties of the original dataset. This includes:

- **Univariate Similarity**: Preservation of marginal distributions for individual features using Kolmogorov-Smirnov and Chi-squared tests
- **Bivariate Similarity**: Maintenance of inter-variable relationships and correlation structures
- **Visualization**: PCA and UMAP embeddings to assess global structural similarity

This dimension provides the first line of evaluation for any synthetic data generation method.

### [Narrow Utility](narrow-utility/index.md)

Narrow utility focuses on task-specific performance in clinically relevant downstream analyses. Statistical fidelity does not always guarantee that biological signals are preserved for scientific discovery. This dimension includes:

- **Differential Gene Expression (DGE)**: Comparison of log-fold changes and p-values between original and synthetic cohorts
- **Gene Set Enrichment (GSEA/ssGSEA)**: Validation that biological pathway activities and functional signatures are recoverable
- **Cell Deconvolution**: Consistency in estimating immune cell fractions from bulk transcriptomics
- **Survival Analysis**: Preservation of Kaplan-Meier survival curves and Hazard Ratios for clinical outcomes

These tasks directly assess whether synthetic data can support real-world biological research.

### [Privacy Risk](privacy.md)

Privacy evaluation quantifies the disclosure vulnerability of the synthetic data, aligned with European Data Protection Board (EDPB) principles. This includes:

- **Singling-Out**: The risk of isolating a unique individual in the dataset based on their attributes
- **Linkability**: The risk of connecting records from the synthetic dataset to the original or other external datasets
- **Inference**: The risk of deducing sensitive attribute values from other available information

Privacy assessment ensures that synthetic data meets requirements for safe data sharing.

### [Meta-Ranking & Stability](meta-ranking.md)

Meta-ranking aggregates performance across all metrics to provide a comprehensive comparison of synthetic data generation methods. This includes:

- **Aggregate Performance**: Combined rankings across broad utility, narrow utility, and privacy dimensions
- **Stability Analysis**: Assessment of method consistency across different cancer types (ccRCC, Melanoma, NSCLC)
- **Cross-Cohort Validation**: Evaluation of generalizability across biological contexts

---

## Bayesian Comparison Framework

Traditional p-values often fail to provide a clear picture of which synthetic data generation (SDG) method is truly superior, especially when dealing with high-dimensional omics data across different cancer cohorts. SynOmicBench implements a rigorous Bayesian comparison approach to address this limitation.

### Methodology

We perform pairwise Bayesian comparisons following the framework proposed by Benavoli et al., using the *baycomp* Python library. For each cancer cohort, all SDG methods are compared pairwise based on their performance scores across five independent replicates. A Bayesian correlated t-test is applied to estimate posterior probabilities for three mutually exclusive hypotheses:

- **Better probability** ($P(SDG_{1} > SDG_{2})$): the probability that $SDG_{1}$ outperforms $SDG_{2}$
- **Worse probability** ($P(SDG_{1} < SDG_{2})$): the probability that $SDG_{1}$ underperforms $SDG_{2}$
- **Practical equivalent probability**: the probability that the performance difference lies within a predefined Region of Practical Equivalence (ROPE)

### Region of Practical Equivalence (ROPE)

The ROPE threshold is set to 0.01, below which performance differences are considered negligible. This allows us to distinguish between statistically significant differences and practically meaningful differences.

### Visualization

The resulting "better" probabilities are visualized as $N \times N$ heatmaps, where each cell represents $P(row > column)$, defined as the posterior probability that the method in the row outperforms the method in the column for the corresponding cohort.

### Implementation

The Bayesian comparison framework is implemented in `src/SynOmics/metrics/fidelity/BayesianComparison.py` and `src/SynOmics/metrics/narrow_utility/BayesianComparison.py`, providing consistent comparison capabilities across all evaluation dimensions.

---

## Benchmarked Synthesizers

SynOmicBench evaluates five state-of-the-art synthetic data generation methods:

1. **Gaussian Copula**: A statistical model that captures multivariate dependencies through copula functions. It models marginal distributions independently and then uses a Gaussian copula to capture correlations between variables.

2. **CTGAN (Conditional Tabular GAN)**: A deep learning-based generative adversarial network specifically designed for tabular data. It uses mode-specific normalization and conditional generation to handle mixed data types and imbalanced categorical variables.

3. **TVAE (Tabular Variational Autoencoder)**: A variational autoencoder adapted for tabular data generation. It learns a compressed latent representation of the data and generates new samples by sampling from the learned latent distribution.

4. **Synthpop**: A tree-based synthesis method originally designed for sensitive health data. It uses Classification and Regression Trees (CART) to sequentially model each variable conditional on previously modeled variables.

5. **Avatars**: An ensemble-based method that combines k-means clustering with Gaussian Copula synthesis. It first clusters high-dimensional features to reduce dimensionality, then generates synthetic data within each cluster.

Each method is evaluated across 90 synthetic datasets (30 per cancer type: ccRCC, Melanoma, NSCLC) using five independent random seeds to assess stability and reproducibility.

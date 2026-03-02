# Framework Content Migration Notes

## Processing Pipeline (from docs/framework/processing.md)

The `SynOmics.processing` module provides a comprehensive suite of utilities for cleaning, transforming, and integrating omics and clinical data. It handles:
- High dimensionality through feature filtering
- Mixed data types (numerical, ordinal, categorical)
- Missing data via MICE and KNN imputation
- Identifier mapping for transcriptomics and clinical integration

### DataProcessor Class
Static methods for preprocessing operations:
- `remove_low_expression_genes`: Filters genes by expression threshold and variance
- `remove_overmissing_features` / `remove_overmissing_entities`: Removes columns/rows exceeding missingness percentage
- `standardization`: Scales numerical features (standard, min-max, robust)
- `mice_imputation`: Uses miceforest for multiple imputation
- `knn_imputation`: Robust KNN-based imputation handling mixed data types

### Postprocessing
Utilities maintain data integrity:
- `apply_min_max`: Clips values to original range
- `apply_rounding`: Restores original decimal precision
- `post_masking`: Re-introduces NaN values after synthesis
- `anonymize_ids`: Replaces patient IDs with UUIDs

### Metadata Management
`MetaData` class classifies features into:
- numerical
- dummy_categorical
- ordinal_categorical
- missing_categorical (indicators like `missingindicator_Age`)

### Gene Query Utilities
`GeneQuery` class interfaces with MyGeneInfo:
- `convert_genes`: Maps Ensembl IDs to HUGO symbols
- `check_duplicates`: Groups genes with identical expression profiles

### Data Integration Pipeline
`DataIntegrationPipeline` coordinates preprocessing, integration, and imputation into a single workflow.

---

## Synthesizer: CTGAN (from docs/framework/synthesizers/ctgan.md)

**Implementation**: `CTGANsynthesizer`
**Methodology**: Conditional Generative Adversarial Network with mode-specific normalization
**Key Strength**: Learns complex distributions and relationships in mixed datasets

### Training Parameters
- `data`: Input training DataFrame
- `seed`: Random seed for reproducibility
- `epochs`: Number of training epochs (default: 100)
- `cuda`: GPU acceleration if available (default: True)
- `verbose`: Print training progress (default: True)

### Sampling Parameters
- `n_samples`: Number of synthetic rows to generate
- `seed`: Random seed for sampling

### Performance
- High variability due to stochastic GAN training
- Generally lower fidelity on specialized omic datasets vs statistical methods
- Better at capturing complex non-linear relationships in large-scale datasets
- Requires more tuning of epochs and architecture

### Implementation Details
1. Discrete column detection from metadata
2. Seeding of Python, NumPy, PyTorch
3. Generator and discriminator network training
4. Model saved to `CTGAN_model.pkl`

---

## Synthesizer: TVAE (from docs/framework/synthesizers/tvae.md)

**Implementation**: `TVAEsynthesizer`
**Methodology**: Tabular Variational Autoencoder with encoder-decoder architecture
**Key Strength**: Learns compact latent representations of high-dimensional data

### Training Parameters
- `data`: Input training DataFrame
- `seed`: Random seed for reproducibility
- `epochs`: Number of training epochs (default: 100)
- `cuda`: GPU acceleration if available (default: True)
- `verbose`: Print training progress (default: True)

### Sampling Parameters
- `n_samples`: Number of synthetic rows to generate
- `seed`: Random seed for sampling

### Performance
- More stable training and sampling than CTGAN
- Moderate fidelity on specific metrics
- Latent space modeling offers different privacy characteristics
- Flexible deep-learning alternative

### Implementation Details
1. Discrete column detection from metadata
2. Seeding of Python, NumPy, PyTorch
3. Encoder maps data to latent space; decoder reconstructs
4. Model saved to `TVAE_model.pkl`

---

## Synthesizer: Gaussian Copula (from docs/framework/synthesizers/gaussian-copula.md)

**Implementation**: `GaussianCopulasynthesizer`
**Methodology**: Multivariate normal distribution modeling of transformed marginals
**Key Strength**: Most balanced performance across univariate similarity, bivariate fidelity, and privacy

### Training Parameters
- `data`: Input training DataFrame
- `seed`: Random seed for reproducibility
- `n_jobs`: Parallel worker threads (default: 8)
- `chunk_size`: Chunk size for parallel processing (default: 20)

### Sampling Parameters
- `n_samples`: Number of synthetic rows to generate
- `seed`: Random seed for sampling

### Metadata Support
- `dummy_categorical`: One-hot encoded
- `ordinal_categorical`: Integer encoded with order preserved
- `missing_categorical`: Binary indicator for missing values
- Other values treated as numerical

### Performance
- Balanced fidelity across clinical and omic data types
- Robust handling of high-dimensional omic data through parallelized implementation
- Faster training times compared to deep learning methods

### Implementation Details
1. Preprocess: Split columns, apply dummy/ordinal encoding
2. Fit: Train GaussianMultivariate_Parallel model
3. Sample: Draw samples from fitted multivariate normal
4. Postprocess: Invert encodings, round, clip to min-max, anonymize

---

## Synthesizer: Synthpop (from docs/framework/synthesizers/synthpop.md)

**Implementation**: `SynthpopSynthesizer`
**Methodology**: Classification and Regression Trees (CART) via R's synthpop package
**Key Strength**: Exceptional univariate similarity, particularly for categorical/ordinal variables

### Training Parameters
- `data`: Training dataset
- `seed`: Random seed

### Sampling Parameters
- `n_samples`: "auto" uses training dataset size, or specify integer
- `seed`: Random seed for R environment
- `method`: Synthesis method, default "cart" or "parametric"
- `n_datasets`: Number of synthetic datasets to generate (default: 1)
- `visit_sequence`: Custom order for variable synthesis (optional)
- `predictor_matrix`: Matrix defining variable dependencies (optional)

### Performance
- Top univariate similarity scores (e.g., 0.952 on ccRCC clinical data)
- Highly effective for mixed data, preserving clinical feature distributions
- CART method captures non-linear dependencies between variables

### Implementation Details
1. R integration via rpy2 with local R installation and synthpop package
2. Categorical columns converted to R factors before synthesis
3. `syn()` function executed with specified method and visit sequence
4. R data frames converted back to pandas DataFrames

---

## Synthesizer: Avatars (from docs/framework/synthesizers/avatars.md)

**Methodology**: Local neighborhood-based synthesis using K-Nearest Neighbors
**Key Strength**: Exceptional bivariate fidelity, preserves correlations in high-dimensional omic data
**Privacy Mechanism**: Each synthetic record is an "avatar" from K nearest neighbors

### Configuration
- Commonly evaluated with K=5 and K=10
- Smaller K → higher utility, lower privacy
- Larger K → higher diversity/privacy, potential fidelity cost

### Performance
- Top bivariate fidelity scores (e.g., 0.954 on ccRCC omic data)
- Outperforms statistical copulas and deep learning models on bivariate metrics
- Excellent at maintaining covariance structure of transcriptomic features

### Key Features
- Non-parametric (no distributional assumptions)
- Local fidelity (preserves record-neighbor relationships)
- Scalable to high-dimensional omic data

### Implementation Considerations
1. Distance metric choice (Euclidean, Manhattan) impacts neighborhood quality
2. K selection balances utility-privacy trade-off
3. Dimensionality reduction (PCA) often needed for extremely high-dimensional data

---

## BaseSynthesizer API (from docs/framework/synthesizers/base.md)

Core component providing unified interface for all synthesis workflows.

### Class Definition
`BaseSynthesizer(output_path, metadata=None)`

### Arguments
- `output_path` (str, required): Path to save metadata, models, and synthetic data
- `metadata` (dict, optional): Column-type metadata; keys are column names, values are type strings

### Key Methods
- `__init__`: Initializes synthesizer, creates output directory, sets up logging
- `generate`: Executes full pipeline: preprocess → fit → sample → postprocess → save
- `preprocess`: Transforms original data before fitting (override if needed)
- `fit`: Trains synthesizer model (must implement in subclasses)
- `sample`: Generates synthetic records (must implement in subclasses)
- `postprocess`: Applies constraints (rounding, min-max scaling, anonymization)

### Generate Parameters
- `data`: Original input data to learn from
- `data_ids`: Optional list of IDs to anonymize
- `enforce_rounding`: Round to match original precision (default: True)
- `enforce_min_max`: Clip to original min-max ranges (default: True)
- `n_samples`: Number of synthetic records to generate
- `fit_params`: Parameters for fit method
- `sample_params`: Parameters for sample method
- `output_filename`: Filename for saved synthetic data (default: "synthetic_data.csv")
- `save_index`: Whether to save index (default: False)

### Utility Methods
- `set_metadata`: Update column-type dictionary
- `detect_discrete_columns`: Identify discrete columns from metadata
- `detect_numerical_columns`: Identify numerical columns from metadata
- `save_synthetic_data`: Handle saving single or multiple DataFrames

### Custom Implementation Example
Inherit from BaseSynthesizer and implement fit() and sample() methods.

---

## Synthesizers Overview (from docs/framework/synthesizers/index.md)

Six primary synthesizers ranging from statistical models to deep learning:

| Synthesizer | Category | Key Characteristic | Best For |
|:---|:---|:---|:---|
| **Gaussian Copula** | Statistical | Models dependencies using copula functions | Balanced performance, numerical data |
| **CTGAN** | Deep Learning | Conditional GAN for tabular data | Complex distributions, categorical data |
| **TVAE** | Deep Learning | Variational Autoencoder for tabular data | Dense data, efficient training |
| **Synthpop** | Regression-based | Sequential classification and regression trees | High fidelity, large datasets |
| **Avatars K5** | K-Anonymity | Differential privacy inspired via K-anonymity | Privacy-centric generation (K=5) |
| **Avatars K10** | K-Anonymity | Higher privacy threshold K-anonymity | Strict privacy requirements (K=10) |

### Selection Criteria
**Statistical & Regression Methods**:
- Gaussian Copula: Captures linear/non-linear correlations, computationally efficient baseline
- Synthpop: Highly flexible, strong at preserving marginal distributions

**Deep Learning Methods**:
- CTGAN: Handles imbalanced categorical features with conditional generator
- TVAE: Converges faster than GANs, excellent structural preservation

**Privacy-Centric Methods**:
- Avatars (K5/K10): Formal privacy guarantees through K-anonymity

### Unified Workflow
All synthesizers follow same lifecycle:
1. Initialization (output path + metadata)
2. Preprocessing (data transformations)
3. Fitting (model training)
4. Sampling (synthetic record generation)
5. Postprocessing (constraint enforcement)

---

## Computational Resources (from docs/evaluation/computational-resources.md)

### Training Time Comparison
| Synthesizer | Typical Training Time | Hardware Recommendation | Scalability |
|:---|:---|:---|:---|
| Gaussian Copula | Very Fast (Seconds to Minutes) | CPU | High |
| Synthpop | Moderate (Minutes) | CPU (Multi-core) | Moderate |
| Avatars (K=5/10) | Fast (Seconds to Minutes) | CPU | Moderate to High |
| TVAE | Slow (Minutes to Hours) | GPU Recommended | Moderate |
| CTGAN | Very Slow (Hours) | GPU Highly Recommended | Moderate |

### Memory Requirements
- **Low Footprint**: Gaussian Copula, Avatars (avoid large intermediate weights)
- **High Footprint**: CTGAN, TVAE (neural network architectures, large VRAM for omics)

### Scalability for High-Dimensional Data
1. Feature selection/dimensionality reduction needed for CTGAN/TVAE
2. Parallelization in Synthpop/Gaussian Copula leverages multi-core processing

### Resource Monitoring
- `monitor_resources` decorator tracks execution time, RAM usage, CPU/GPU utilization

### Benchmark Environment
- CPU: Multi-core (Intel Xeon, AMD EPYC)
- GPU: NVIDIA Tesla V100/A100 (for deep learning)
- RAM: 64GB+ for high-dimensional omics
- OS: Linux (Ubuntu 20.04/22.04)

---

## Predictive Modeling Validation (from docs/evaluation/narrow-utility/predictive-modeling.md)

Evaluates predictive utility of synthetic data through machine learning model comparison.

### Key Metrics
- **TSTR** (Train-on-Synthetic-Test-on-Real): Trains on synthetic, tests on real data (primary utility measure)
- **TRTS** (Train-on-Real-Test-on-Synthetic): Trains on real, tests on synthetic (distributional similarity)
- **CV-Score**: Average performance (ROC-AUC, F1) over multiple folds
- **Wilcoxon P-value**: Statistical test for significance across CV folds

### Methodology
1. Stratified K-Fold CV on both datasets
2. Parallel evaluation per fold (Real training vs Synthetic training)
3. Common real test fold for fair comparison
4. Scoring metrics calculated per fold
5. Results include fold-level scores, improvement flag, p-value

### Performance Stability
- Methods capturing multivariate correlations (Gaussian Copula) → lower variance
- Deep generative models (CTGAN) → may require more samples for stable boundaries

### Key Findings
- TSTR performance correlates with broad utility metrics (pairwise correlation preservation)
- **Gaussian Copula** often matches/exceeds original performance (TSTR ≥ 95% of original)
- **TVAE/CTGAN** show promising results with higher variance in high-dimensional omics
- Synthetic data can act as regularization, improving generalization

### Significance in Precision Medicine
- Enables sharing "prediction-ready" synthetic datasets without exposing private data
- Allows benchmarking new ML architectures on realistic multi-omic data
- Validates clinical scoring systems on diverse synthetic cohorts

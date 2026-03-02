# Generate Synthetic Data

> All SDG methods are integrated from external libraries. We do not reimplement the core algorithms.

## SDG Methods

SynOmicBench integrates five synthetic data generation (SDG) methods through their official libraries:

* **CTGAN** — [https://github.com/sdv-dev/CTGAN](https://github.com/sdv-dev/CTGAN)  
  Conditional Generative Adversarial Network with mode-specific normalization. Learns complex distributions and relationships in mixed datasets. High variability due to stochastic GAN training, better at capturing complex non-linear relationships in large-scale datasets.

* **TVAE** — [https://github.com/sdv-dev/SDV](https://github.com/sdv-dev/SDV)  
  Tabular Variational Autoencoder with encoder-decoder architecture. Learns compact latent representations of high-dimensional data. More stable training and sampling than CTGAN, offering a flexible deep-learning alternative with different privacy characteristics.

* **Gaussian Copula** — [https://github.com/sdv-dev/SDV](https://github.com/sdv-dev/SDV)  
  Multivariate normal distribution modeling of transformed marginals. Most balanced performance across univariate similarity, bivariate fidelity, and privacy. Robust handling of high-dimensional omic data through parallelized implementation with faster training times compared to deep learning methods.

* **Synthpop** — [https://github.com/thomvolker/synthpop](https://github.com/thomvolker/synthpop)  
  Classification and Regression Trees (CART) via R's synthpop package. Exceptional univariate similarity, particularly for categorical and ordinal variables. Top univariate similarity scores, highly effective for mixed data, preserving clinical feature distributions through CART method capturing non-linear dependencies.

* **Avatars** — [https://www.octopize.io/](https://www.octopize.io/)  
  Local neighborhood-based synthesis using K-Nearest Neighbors. Exceptional bivariate fidelity, preserves correlations in high-dimensional omic data. Each synthetic record is an "avatar" from K nearest neighbors, outperforming statistical copulas and deep learning models on bivariate metrics.

---

## Benchmarking Description

Five SDG methods were benchmarked across three cancer types (NSCLC, melanoma, ccRCC), each repeated 5 times with different random seeds for reproducibility:

* **Methods**: CTGAN, TVAE, Gaussian Copula, Synthpop, Avatars
* **Cancer types**: 3 (NSCLC, melanoma, clear cell renal cell carcinoma)
* **Seeds**: 5 independent runs per method per cancer type
* **Total synthetic datasets generated**: 90 (30 per cancer type)

This comprehensive benchmarking design enables statistical assessment of each method's consistency and performance across diverse multi-omic contexts.

---

## High-Dimensional Adaptations

Naive fitting of synthetic data generation methods often fails on high-dimensional and heterogeneous multi-omic datasets. SynOmicBench implements specialized adaptations to handle these challenges:

### Gaussian Copula

The Gaussian Copula synthesizer required several adaptations to handle high-dimensional omic features and mixed data types:

* **One-hot encoding for categorical features**: Categorical variables are expanded into binary indicator columns before fitting
* **OrdinalEncoder for ordinal features**: Preserves ordinal relationships through integer encoding
* **Parallel univariate fitting using joblib**: Distributes computation across multiple cores to handle thousands of features
* **Vectorized batch chunking**: Processes data in batches to manage memory constraints
* **Reverse one-hot decoding using highest probability**: Reconstructs categorical variables by selecting the category with maximum probability
* **Rounding ordinal synthetic values**: Ensures generated ordinal values match the original discrete scale

### Avatars

Avatars is a proprietary method requiring specialized handling for large datasets:

* **Proprietary** (Octopize license required)
* **Python API client used**: Integration through Octopize's official Python SDK
* **Split datasets into blocks < 4,000 records**: Large datasets are partitioned to meet API constraints
* **Upload and anonymize per block**: Each block is processed independently through the Avatars service
* **Merge synthetic blocks**: Recombined into a single synthetic dataset
* **Feature clustering**: Reduces dimensionality while preserving correlation structure:
  * Spearman correlation (numerical features)
  * Cramér's V (categorical features)
  * Distance matrix: d = 1 − |correlation|
  * Hierarchical clustering (average linkage)

### Synthpop

Synthpop faces computational challenges with high-dimensional predictors. A custom predictor matrix optimization addresses this:

* **Custom predictor matrix**: Defines which variables predict each target feature
* **Association matrix threshold**: d_ij ≤ 0.7 filters for strong associations only
* **Max 500 predictors per feature**: Limits computational burden while retaining key relationships
* **Graph-based ranking**: Prioritizes predictors using:
  * Degree centrality (primary criterion)
  * Eigenvector centrality (tie-breaking)
* **Lower-triangular predictor structure**: Ensures proper variable ordering and avoids circular dependencies

---

## Usage Example

```python
from SynOmics.synthesizer.CTGANsynthesizer import CTGANSynthesizer

# Initialize synthesizer with output path
synthesizer = CTGANSynthesizer(
    output_path="./output/ctgan",
    metadata={"Age": "numerical", "Gender": "dummy_categorical"}
)

# Generate synthetic data
synthetic_data = synthesizer.generate(
    data=real_data,
    n_samples=1000,
    epochs=100,
    seed=42
)
```

All synthesizers follow the `BaseSynthesizer` API with a consistent pipeline:

1. **Preprocess**: Transform data (encoding, scaling)
2. **Fit**: Train the generative model
3. **Sample**: Generate synthetic records
4. **Postprocess**: Apply constraints (rounding, clipping, anonymization)
5. **Save**: Export to CSV with metadata

---

## Key Considerations

* **Method selection**: Choose based on your data characteristics and evaluation priorities:
  * Univariate similarity → Synthpop
  * Bivariate fidelity → Avatars
  * Balanced performance → Gaussian Copula
  * Complex non-linear patterns → CTGAN/TVAE

* **High-dimensional data**: Use adaptations (parallel fitting, feature clustering, predictor matrix optimization) for datasets with >1,000 features

* **Reproducibility**: Always set random seeds across all methods for consistent benchmarking

* **Privacy-utility trade-off**: Deep learning methods (CTGAN, TVAE) may provide different privacy characteristics compared to statistical methods (Gaussian Copula, Synthpop)

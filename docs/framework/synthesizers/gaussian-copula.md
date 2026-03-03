# Gaussian Copula Synthesizer

The `GaussianCopulasynthesizer` generates synthetic data by modeling the dependency structure of the input variables using a Gaussian Copula. It transforms the marginal distributions of each variable into standard normal distributions, estimates a correlation matrix, and then reverses the transformation during sampling.

## Overview

- **Implementation**: `GaussianCopulasynthesizer`
- **Methodology**: Multivariate normal distribution modeling of transformed marginals.
- **Key Strength**: Most balanced performance across univariate similarity, bivariate fidelity, and privacy preservation.

## Initialization

```python
from SynOmics.synthesizer import GaussianCopulasynthesizer

synthesizer = GaussianCopulasynthesizer(
    output_path="outputs/gaussian_copula",
    metadata=metadata
)
```

### Parameters

- `output_path` (str): Directory where model artifacts and logs will be saved.
- `metadata` (dict, optional): A dictionary mapping column names to their types. Supported types:
    - `"dummy_categorical"`: One-hot encoded.
    - `"ordinal_categorical"`: Integer encoded with order preserved.
    - `"missing_categorical"`: Binary indicator for missing values.
    - Any other value is treated as numerical.

## Training (Fit)

The `fit` method preprocesses the data by encoding categorical variables and then fits the Gaussian Multivariate model in parallel.

```python
synthesizer.fit(
    data=train_df,
    seed=42,
    n_jobs=8,
    chunk_size=20
)
```

### Fit Parameters

- `data` (pd.DataFrame): The input training data.
- `seed` (int, optional): Random seed for reproducibility.
- `n_jobs` (int): Number of parallel worker threads for fitting (default: 8).
- `chunk_size` (int): Chunk size for parallel processing (default: 20).

## Sampling

```python
synthetic_df = synthesizer.sample(
    n_samples=100,
    seed=42
)
```

### Sample Parameters

- `n_samples` (int): Number of synthetic rows to generate.
- `seed` (int, optional): Random seed for sampling.

## Performance Characteristics

In the SynOmicBench evaluation, the Gaussian Copula method demonstrated:

- **Balanced Fidelity**: Provided consistent performance across clinical and omic data types without extreme failures in specific dimensions.
- **Robustness**: Handled high-dimensional omic data effectively through its parallelized implementation.
- **Efficiency**: Faster training times compared to deep learning-based methods like CTGAN.

## Implementation Details

The synthesizer follows a structured pipeline:

1.  **Preprocess**: Splits columns based on metadata, applies dummy encoding for categorical features, and ordinal encoding for ordered categories.
2.  **Fit**: Trains a `GaussianMultivariate_Parallel` model.
3.  **Sample**: Draws samples from the fitted multivariate normal distribution.
4.  **Postprocess**: Inverts encodings, rounds numerical values, clips to original min-max ranges, and anonymizes identifiers.

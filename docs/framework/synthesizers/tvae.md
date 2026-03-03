# TVAE Synthesizer

The `TVAEsynthesizer` uses a Tabular Variational Autoencoder (TVAE) to generate synthetic data. It models the data using an encoder-decoder architecture with a latent space representation.

## Overview

- **Implementation**: `TVAEsynthesizer`
- **Methodology**: Variational Autoencoder adapted for tabular data with discrete and continuous variables.
- **Key Strength**: Can learn compact latent representations of high-dimensional data.

## Initialization

```python
from SynOmics.synthesizer import TVAEsynthesizer

synthesizer = TVAEsynthesizer(
    output_path="outputs/tvae",
    metadata=metadata
)
```

### Parameters

- `output_path` (str): Directory where model artifacts and logs will be saved.
- `metadata` (dict, optional): A dictionary mapping column names to their types.

## Training (Fit)

The `fit` method trains the TVAE model. Like CTGAN, it automatically identifies discrete columns based on the provided metadata.

```python
synthesizer.fit(
    data=train_df,
    seed=42,
    epochs=100,
    cuda=True,
    verbose=True
)
```

### Fit Parameters

- `data` (pd.DataFrame): The input training data.
- `seed` (int, optional): Random seed for reproducible training.
- `epochs` (int): Number of training epochs (default: 100).
- `cuda` (bool): Whether to use GPU acceleration if available (default: True).
- `verbose` (bool): If True, prints training progress (default: True).
- `**kwargs`: Extra parameters passed directly to the underlying `TVAE` model.

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
- `**kwargs`: Extra parameters for the model's sample function.

## Performance Characteristics

In the SynOmicBench evaluation, TVAE showed:

- **Consistency**: Often demonstrated more stable training and sampling than CTGAN.
- **Moderate Fidelity**: While generally lower in fidelity than Gaussian Copula or Synthpop on specific metrics, it provides a flexible deep-learning alternative.
- **Privacy**: Latent space modeling may offer different privacy characteristics compared to direct sampling methods.

## Implementation Details

The synthesizer leverages the `ctgan` library's `TVAE` implementation. During training, it:

1.  **Discrete Column Detection**: Automatically identifies categorical columns from the metadata.
2.  **Seeding**: Seeds Python, NumPy, and PyTorch (if available) to improve reproducibility.
3.  **Model Training**: Trains an encoder network to map data to a latent space and a decoder network to reconstruct data.
4.  **Save/Load**: The fitted model is saved to `TVAE_model.pkl` in the output directory.

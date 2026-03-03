# CTGAN Synthesizer

The `CTGANsynthesizer` uses Conditional Generative Adversarial Networks (CTGAN) to generate synthetic data. It is designed to handle mixed data types and unbalanced categorical variables by utilizing a conditional generator and training-by-sampling approach.

## Overview

- **Implementation**: `CTGANsynthesizer`
- **Methodology**: Generative Adversarial Network with mode-specific normalization and a conditional generator.
- **Key Strength**: Capable of learning complex distributions and relationships in mixed datasets.

## Initialization

```python
from SynOmics.synthesizer import CTGANsynthesizer

synthesizer = CTGANsynthesizer(
    output_path="outputs/ctgan",
    metadata=metadata
)
```

### Parameters

- `output_path` (str): Directory where model artifacts and logs will be saved.
- `metadata` (dict, optional): A dictionary mapping column names to their types.

## Training (Fit)

The `fit` method trains the CTGAN model. It automatically detects discrete columns based on the provided metadata.

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
- `**kwargs`: Extra parameters passed directly to the underlying `CTGAN` model.

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

In the SynOmicBench evaluation, CTGAN showed:

- **High Variability**: Results can vary significantly between runs due to the stochastic nature of GAN training.
- **Fidelity**: Generally lower fidelity on specialized omic datasets compared to traditional statistical methods like Gaussian Copula or Synthpop.
- **Complexity**: Better at capturing complex non-linear relationships in large-scale datasets, but may require more tuning of epochs and network architecture.

## Implementation Details

The synthesizer leverages the `ctgan` library. During training, it:

1.  **Discrete Column Detection**: Automatically identifies categorical columns from the metadata.
2.  **Seeding**: Seeds Python, NumPy, and PyTorch (if available) to improve reproducibility.
3.  **Model Training**: Trains a generator and discriminator network.
4.  **Save/Load**: The fitted model is saved to `CTGAN_model.pkl` in the output directory.

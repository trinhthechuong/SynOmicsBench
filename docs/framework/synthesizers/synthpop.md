# Synthpop Synthesizer

The `SynthpopSynthesizer` uses the `synthpop` R package via `rpy2` to generate synthetic data. It specializes in using conditional trees (CART) or other parametric methods for synthesis.

## Overview

- **Implementation**: `SynthpopSynthesizer`
- **Methodology**: Classification and Regression Trees (CART) or parametric models using R's `synthpop` package.
- **Key Strength**: Exceptional univariate similarity, particularly for categorical and ordinal variables.

## Initialization

```python
from SynOmics.synthesizer import SynthpopSynthesizer

synthesizer = SynthpopSynthesizer(
    output_path="outputs/synthpop",
    metadata=metadata,
    r_home="/usr/lib/R"  # Optional: path to R home
)
```

### Parameters

- `output_path` (str): Directory where model artifacts and logs will be saved.
- `metadata` (dict, optional): A dictionary mapping column names to their types.
- `r_home` (str, optional): Path to the R installation directory.
- `r_terminal` (str): R executable name or path (default: 'R').

## Training (Fit)

The `fit` method for Synthpop stores the training DataFrame for use during the R call in the `sample` step.

```python
synthesizer.fit(
    data=train_df,
    seed=42
)
```

### Fit Parameters

- `data` (pd.DataFrame): The training dataset.
- `seed` (int): Random seed.

## Sampling

The `sample` method executes the R `synthpop::syn` function.

```python
synthetic_df = synthesizer.sample(
    n_samples="auto",
    seed=42,
    method="cart",
    n_datasets=1
)
```

### Sample Parameters

- `n_samples` (int or 'auto'): Number of rows to synthesize; 'auto' uses the training dataset size.
- `seed` (int): Random seed for the R environment.
- `discrete_columns` (list[str], optional): Explicit list of categorical columns.
- `method` (str): Synthesis method (default: `"cart"`). Other options include `"parametric"`.
- `n_datasets` (int): Number of synthetic datasets to generate (default: 1).
- `visit_sequence` (list[str], optional): Custom order for variable synthesis.
- `predictor_matrix` (pd.DataFrame, optional): Matrix defining variable dependencies.
- `**kwargs`: Extra parameters passed to the R `syn` function.

## Performance Characteristics

In the SynOmicBench evaluation, Synthpop achieved:

- **Top Univariate Similarity**: Recorded the best univariate similarity scores (e.g., 0.952 on ccRCC clinical data).
- **Excellent for Mixed Data**: Highly effective at preserving the distributions of clinical features.
- **Dependency Handling**: The CART method inherently captures non-linear dependencies between variables.

## Implementation Details

The synthesizer bridges Python and R:

1.  **R Integration**: Uses `rpy2` to interact with a local R installation and the `synthpop` package.
2.  **Factor Conversion**: Automatically converts categorical columns into R factors before synthesis.
3.  **Synthesis**: Executes the `syn()` function using the specified method and visit sequence.
4.  **Data Recovery**: Converts the resulting R data frames back into pandas DataFrames.

# Getting Started with SynOmicBench

This tutorial provides an end-to-end guide to using SynOmicBench for generating and evaluating synthetic multi-omics data. You will learn how to install the framework, prepare your data, and run a complete synthesis pipeline.

## Installation

You can install SynOmicBench directly from source to ensure you have the latest features and research benchmarks.

### From Source

Clone the repository and install the dependencies:

```bash
git clone https://github.com/SynOmicBench/SynOmicBench.git
cd SynOmicBench
pip install -e .
```

### Dependencies

SynOmicBench requires Python 3.9+ and several scientific computing libraries including:
- `pandas` and `numpy` for data manipulation
- `scikit-learn` for preprocessing and encoding
- `sdmetrics` for evaluation metrics
- `miceforest` for MICE imputation

## Quick Example

Here's a minimal example showing how to synthesize data using the Gaussian Copula model.

```python
import pandas as pd
from SynOmics.synthesizer.GaussianCopulasynthesizer import GaussianCopulasynthesizer

# 1. Load your data
data = pd.read_csv("your_omics_data.csv")

# 2. Define column types (metadata)
# Types: "numerical", "dummy_categorical", "ordinal_categorical", "missing_categorical"
metadata = {col: "numerical" for col in data.columns}

# 3. Initialize and run the pipeline
synthesizer = GaussianCopulasynthesizer(output_path="./results", metadata=metadata)
synthetic_data = synthesizer.generate(
    data=data,
    n_samples=len(data),
    output_filename="synthetic_output.csv"
)

print(f"Generated synthetic data with shape: {synthetic_data.shape}")
```

---

## Step-by-Step Walkthrough

Let's dive deeper into the full pipeline, from raw data to evaluation.

### 1. Load and Clean Data

Omics datasets are often high-dimensional and contain many zeros or missing values. We'll use the `DataProcessor` utility to handle these.

```python
from SynOmics.processing.preprocessing import DataProcessor

# Load a sample transcriptomics dataset (e.g., ccRCC)
df = pd.read_csv("ccRCC_data.csv")

# Remove genes with near-zero variance or no expression
df_cleaned = DataProcessor.remove_low_expression_genes(
    df, 
    variance_threshold=0.0005
)

# Handle missing values using MICE imputation
df_imputed = DataProcessor.mice_imputation(
    df_cleaned, 
    iterations=10, 
    add_indicators=True
)
```

### 2. Prepare Metadata

SynOmicBench uses a metadata dictionary to understand how to treat each column during synthesis and post-processing.

```python
# Identify feature types
# In transcriptomics, most features are numerical
metadata = {col: "numerical" for col in df_imputed.columns}

# If you have clinical data, specify categorical columns
# metadata["gender"] = "dummy_categorical"
# metadata["stage"] = "ordinal_categorical"
```

### 3. Initialize the Synthesizer

Initialize a synthesizer by providing an output directory where logs, models, and synthetic datasets will be saved.

```python
from SynOmics.synthesizer.GaussianCopulasynthesizer import GaussianCopulasynthesizer

output_dir = "./syn_results"
synthesizer = GaussianCopulasynthesizer(
    output_path=output_dir, 
    metadata=metadata
)
```

### 4. Generate Synthetic Data

The `generate()` method handles the entire workflow: preprocessing, model fitting, sampling, and post-processing (rounding and min-max clipping).

```python
synthetic_df = synthesizer.generate(
    data=df_imputed,
    n_samples=300,            # Number of rows to generate
    enforce_rounding=True,    # Ensure output matches original precision
    enforce_min_max=True,     # Clip values to original range
    output_filename="ccRCC_synthetic.csv"
)
```

**Expected Console Output:**
```text
========== Synthesizer Initialized ==========
Class: GaussianCopulasynthesizer
Output path: ./syn_results
Log file: ./syn_results/GaussianCopulasynthesizer_12345.log
============================================
Pipeline started for GaussianCopulasynthesizer (n_samples=300, ...)
Preprocessed data shape: (311, 2000)
Model fit complete.
Generated 300 synthetic samples with Gaussian Copula
Saved synthetic data to ./syn_results/ccRCC_synthetic.csv
Pipeline complete.
```

### 5. Evaluate Fidelity

After generation, it's crucial to verify that the synthetic data preserves the statistical properties of the original data. We use `UnivariateSimilarity` to compare column distributions.

```python
from SynOmics.metrics.fidelity.UnivariateSimilarity import UnivariateSimilarity

# Initialize evaluator
evaluator = UnivariateSimilarity(output_dir="./evaluation_results")

# Compute univariate similarity score (0 to 1)
score = evaluator.get_univariate_score(
    original_data=df_imputed,
    synthetic_data=synthetic_df,
    metadata=metadata,
    save=True
)

print(f"Overall Fidelity Score: {score:.4f}")
```

This will generate:
1. `Detail_score_UnivariateSimilarity.csv`: Individual scores for every gene.
2. `UnivariateSimilarity.png`: A histogram visualizing the score distribution.

## Next Steps

Now that you've completed your first synthesis, explore more advanced topics:

- [Framework Overview](../framework/index.md): Understand the `BaseSynthesizer` architecture.
- [Evaluation Metrics](../evaluation/index.md): Learn about Multivariate similarity and Privacy metrics.
- [Preprocessing Details](../processing/index.md): Advanced imputation and feature engineering.

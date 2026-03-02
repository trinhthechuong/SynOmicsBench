# Getting Started

## Installation

You can install SynOmicBench directly from source to ensure you have the latest features and research benchmarks.

### From Source

Clone the repository and install the dependencies:

```bash
git clone https://github.com/SynOmicBench/SynOmicBench.git
cd SynOmicBench
pip install -e .
```

**Python Version**: 3.11+ (tested with 3.11.5)

A `requirements.txt` file is provided in the repository root for reference.

### From Singularity

Singularity container instructions coming soon.

---

## Quick Example

Here's a complete example showing how to generate synthetic data using GaussianCopula and evaluate fidelity:

```python
import pandas as pd
import numpy as np
from SynOmics.synthesizer.GaussianCopulasynthesizer import GaussianCopulasynthesizer
from SynOmics.processing.metadata import MetaData

original_data = pd.read_csv("your_original_data.csv")

ordinal_features = ["Mstage", "Tx_Start_ECOG",
                    "numPriorTherapies", "biopsyContext"]

metadata = MetaData.get_metadata(
    data=original_data,
    ordinal_features=ordinal_features
)

output_path = "./results"

synth = GaussianCopulasynthesizer(
    output_path=output_path,
    metadata=metadata
)

synthetic_data = synth.generate(
    data=original_data,
    n_samples=original_data.shape[0],
    output_filename="synthetic_data.csv",
)

from SynOmics.metrics.fidelity.UnivariateSimilarity import UnivariateSimilarity

evaluator = UnivariateSimilarity(output_dir="./evaluation_results")

score = evaluator.get_univariate_score(
    original_data=original_data,
    synthetic_data=synthetic_data,
    metadata=metadata,
    save=True
)

print(f"Overall Fidelity Score: {score:.4f}")
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

- [Synthesizer API](../api/index.md): Understand the `BaseSynthesizer` architecture.
- [Evaluation Metrics](../evaluation/index.md): Learn about Multivariate similarity and Privacy metrics.
- [Preprocessing Guide](../preprocessing/index.md): Advanced imputation and feature engineering.

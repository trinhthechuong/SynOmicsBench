# Preprocessing Data

The `synomicsbench.processing` module provides a comprehensive suite of utilities for cleaning, transforming, and integrating omics and clinical data. This processing pipeline minimizes the confounding impact of data quality on generative model effectiveness, ensuring unbiased comparability among the evaluated synthetic data generation methods. As illustrated in Figure 2, the pipeline follows five sequential steps: 1) Data Filtering, 2) Transcriptomic Harmonization, 3) Feature type classification, 4) Multivariate missing data imputation, and 5) Data Integration. The pipeline is flexible and configurable, allowing users to customize preprocessing steps based on their specific datasets and analysis requirements.


## Data Integration Pipeline

![Data Integration Pipeline](../assets/figures/processing_pipeline.png)

***Figure 1**: Standardized preprocessing pipeline for clinical-transcriptomic data integration.*

The `DataIntegrationPipeline` ensures data quality and consistency before synthetic data generation or downstream analysis.

## Pipeline Execution

The following example demonstrates how to configure and execute the complete data integration pipeline:

```python
import pandas as pd
from synomicsbench.processing.pipeline import DataIntegrationPipeline

output_dir = "./integrationpipeline_output"

imputer = "mice"
imputer_params = {
    "iterations": 10,
    "n_estimators": 100,
    "random_state": 42
}

ordinal_cat_columns = [
    "MSKCC",
    "Number_of_Prior_Therapies",
    "ORR",
    "ExtremeResponder",
    "Benefit"
]

steps_config = {
    "remove_undefined": True,
    "remove_duplicates": True,
    "remove_overmissing_samples": True,
    "remove_low_expression_genes": True,
    "check_duplicate_genes": True,
    "mapping_genes": True,
    "feature_engineering": True,
    "integrate_data": True,
}

pipeline = DataIntegrationPipeline(
    output_dir=output_dir,
    logger="Integration_final"
)

results = pipeline.run_pipeline(
    clinical_data=clinical_data_1,
    transcriptomics_data=omics_data_t,
    clinical_id_column="RNA_ID",
    transcriptomics_id_column="Sample",
    integration_id_column="Patient_ID",
    steps_config=steps_config,
    overmissing_samples_threshold=50,
    overmissing_features_threshold=50,
    unique_threshold=10,
    scaler="minmax",
    ordinal_cat_columns=ordinal_cat_columns,
    imputer=imputer,
    imputer_params=imputer_params,
    low_expression_variance_threshold=0.0005,
    add_indicators=True,
    verbose=True,
)
```

The `steps_config` dictionary controls which preprocessing steps are executed, allowing flexible pipeline customization based on data characteristics and analysis requirements. The pipeline returns processed clinical and transcriptomics data ready for synthesis or downstream analysis.

## Pipeline Steps

The data integration pipeline executes configurable steps in sequence, controlled by `steps_config`.

```text
remove_undefined → remove_duplicates → remove_overmissing_samples →
(transcriptomics only) remove_low_expression_genes → check_duplicate_genes → mapping_genes →
feature_engineering → integrate_data
```

| Step key | What it does | Where it runs | Implementation (code) | Key params |
|---|---|---|---|---|
| `remove_undefined` | Drop rows with missing IDs | Clinical + transcriptomics | `DataProcessor.remove_unknown_entities(...)` | `*_id_column` |
| `remove_duplicates` | Remove exact duplicate rows/cols | Clinical + transcriptomics | `DataProcessor.remove_duplications(..., axis=0/1)` | `axis` |
| `remove_overmissing_samples` | Drop rows with missingness > threshold | Clinical + transcriptomics | `DataProcessor.remove_overmissing_entities(...)` | `overmissing_samples_threshold` |
| `remove_low_expression_genes` | Filter zero-sum / near-zero variance genes | Transcriptomics | `DataProcessor.remove_low_expression_genes(...)` | `low_expression_variance_threshold` |
| `check_duplicate_genes` | Find identical expression profiles | Transcriptomics | `GeneQuery.check_duplicates(...)` | (none) |
| `mapping_genes` | Map Ensembl IDs → HUGO symbols | Transcriptomics | `GeneQuery.mapping_genes(...)` | (none) |
| `feature_engineering` | Type classification + encoding + scaling + imputation | Clinical + transcriptomics | `DataProcessor.feature_engineering(...)` | `data_type`, `imputer`, `imputer_params`, `scaler`, `unique_threshold`, `ordinal_cat_columns` |
| `integrate_data` | Merge clinical + transcriptomics on common ID | Final integration | `DataIntegrationPipeline.integrate_data(...)` | `integration_id_column` |

!!! tip
    If you only need one step (e.g., just filtering, encoding, or imputation), you can call the
    preprocessing utilities directly—see the section below.

## Utility Functions (`DataProcessor`)

All helper functions are available in `synomicsbench.processing.preprocessing.DataProcessor`. These are useful when you want to execute specific preprocessing steps without running the full `DataIntegrationPipeline`.

### Available Methods

| Method | Description | Key Parameters |
|---|---|---|
| `remove_duplications` | Drops duplicate rows or columns | `axis=0/1` |
| `remove_unknown_entities` | Removes rows with missing IDs | `id_column` |
| `remove_overmissing_entities` | Drops rows with missingness above threshold | `threshold` |
| `find_missing_percent` | Calculates missingness percentage | |
| `remove_overmissing_features` | Drops columns with missingness above threshold | `threshold` |
| `remove_low_expression_genes` | Filters near-zero variance genes | `gene_id_column`, `variance_threshold` |
| `encode_dummy_features` | One-hot encodes categorical data | |
| `encode_ordinal_features` | Ordinal encodes categorical data | |
| `standardization` | Scales numerical features | `scaler='minmax'/'standard'` |
| `mice_imputation` | Multiple Imputation by Chained Equations | `iterations`, `n_estimators`, `add_indicators` |
| `extract_missingindicator_columns` | Extracts generated missingness indicators | |
| `inverse_dummy_features` | Reverses dummy encoding | `dummy_cat_columns` |
| `inverse_ordinal_features` | Reverses ordinal encoding | `encoder` |
| `inverse_standardization` | Reverses scaling | `scaler` |
| `knn_imputation` | k-Nearest Neighbors imputation | `n_neighbors`, `dummy_cat_columns`, `ordinal_cat_columns` |
| `feature_engineering` | Type classification, encoding, scaling, and imputation pipeline | `data_type`, `imputer`, `imputer_params`, `scaler` |

### Example Usage

The following example demonstrates how to use `DataProcessor` for targeted data cleaning, encoding, and imputation:

```python
import pandas as pd
import numpy as np
from synomicsbench.processing.preprocessing import DataProcessor

# 0. Sample Data
df = pd.DataFrame(
    {
        "Patient_ID": ["P1", "P2", None, "P2"],
        "sex": ["M", "F", "F", "F"],
        "stage": ["I", "II", "II", None],
        "age": [63, np.nan, 55, 55],
        "geneA": [0.1, 0.0, 0.0, 0.0],
    }
)

# 1. Filtering & QC
df_clean = DataProcessor.remove_unknown_entities(df, id_column="Patient_ID")
df_clean = DataProcessor.remove_duplications(df_clean, axis=0)

# 2. Encoding
cat_encoded = DataProcessor.encode_dummy_features(df_clean[["sex"]])
ord_encoded, ord_encoder = DataProcessor.encode_ordinal_features(df_clean[["stage"]].fillna("missing"))

# 3. Scaling
num_scaled, num_scaler = DataProcessor.standardization(df_clean[["age"]].fillna(df_clean["age"].median()), scaler="minmax")

# 4. Imputation (MICE)
# Requires miceforest: pip install miceforest
df_imputed = DataProcessor.mice_imputation(df, iterations=10, n_estimators=100, add_indicators=True)

# 5. Extract Imputation Indicators
indicators = DataProcessor.extract_missingindicator_columns(df_imputed)
```

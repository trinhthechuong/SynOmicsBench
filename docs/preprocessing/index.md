# Preprocessing Data

The `SynOmics.processing` module provides a comprehensive suite of utilities for cleaning, transforming, and integrating omics and clinical data. This processing pipeline minimizes the confounding impact of data quality on generative model effectiveness, ensuring unbiased comparability among the evaluated synthetic data generation methods. As illustrated in Figure 2, the pipeline follows five sequential steps: 1) Data Filtering, 2) Transcriptomic Harmonization, 3) Feature type classification, 4) Multivariate missing data imputation, and 5) Data Integration. The pipeline is flexible and configurable, allowing users to customize preprocessing steps based on their specific datasets and analysis requirements.


## Data Integration Pipeline

![Data Integration Pipeline](../assets/figures/processing_pipeline.png)

***Figure 2**: Standardized preprocessing pipeline for clinical-transcriptomic data integration.*

The `DataIntegrationPipeline` ensures data quality and consistency before synthetic data generation or downstream analysis.

## Pipeline Execution

The following example demonstrates how to configure and execute the complete data integration pipeline:

```python
import pandas as pd
from SynOmics.processing.pipeline import DataIntegrationPipeline

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

## Standalone preprocessing utilities (`DataProcessor`)

All helpers live in `SynOmics.processing.preprocessing.DataProcessor`. These are useful when you
don’t want to run the full `DataIntegrationPipeline`.

### Setup used in examples

```python
import pandas as pd
import numpy as np

from SynOmics.processing.preprocessing import DataProcessor

df = pd.DataFrame(
    {
        "Patient_ID": ["P1", "P2", None, "P2"],
        "sex": ["M", "F", "F", "F"],
        "stage": ["I", "II", "II", None],
        "age": [63, np.nan, 55, 55],
        "geneA": [0.1, 0.0, 0.0, 0.0],
        "geneB": [1.0, 1.0, 1.0, 1.0],
    }
)
```

### Filtering & QC

??? tip "remove_duplications(data, axis)"
    ```python
    # Drop duplicate rows
    df_no_dup_rows = DataProcessor.remove_duplications(df, axis=0)

    # Drop duplicate columns
    df_no_dup_cols = DataProcessor.remove_duplications(df, axis=1)
    ```

??? tip "remove_unknown_entities(data, id_column)"
    ```python
    df_known = DataProcessor.remove_unknown_entities(df, id_column="Patient_ID")
    ```

??? tip "remove_overmissing_entities(data, threshold)"
    ```python
    df_rows_ok = DataProcessor.remove_overmissing_entities(df, threshold=50)
    ```

??? tip "find_missing_percent(data)"
    ```python
    missing_summary = DataProcessor.find_missing_percent(df)
    ```

??? tip "remove_overmissing_features(data, threshold)"
    ```python
    df_cols_ok = DataProcessor.remove_overmissing_features(df, threshold=50)
    ```

??? tip "remove_low_expression_genes(data, gene_id_column='gene_id', variance_threshold=...)"
    ```python
    # Orientation: samples as rows, genes as columns
    expr = df[["geneA", "geneB"]]
    expr_filtered = DataProcessor.remove_low_expression_genes(expr, variance_threshold=0.0005)

    # Orientation: genes as rows (with a gene_id column)
    expr_gene_rows = pd.DataFrame(
        {"gene_id": ["geneA", "geneB"], "S1": [0.1, 1.0], "S2": [0.0, 1.0]}
    )
    expr_gene_rows_filtered = DataProcessor.remove_low_expression_genes(
        expr_gene_rows, gene_id_column="gene_id", variance_threshold=0.0005
    )
    ```

??? tip "encode_dummy_features(data)"
    ```python
    cat = df[["sex"]]
    cat_dummy = DataProcessor.encode_dummy_features(cat)
    ```

??? tip "encode_ordinal_features(data)"
    ```python
    ord_df = df[["stage"]].fillna("missing")
    ord_encoded, ord_encoder = DataProcessor.encode_ordinal_features(ord_df)
    ```

??? tip "standardization(data, scaler)"
    ```python
    num = df[["age"]]
    num_scaled, scaler_obj = DataProcessor.standardization(num.fillna(num.median()), scaler="minmax")
    ```


??? tip "mice_imputation(data, ...)"
    !!! note
        Requires optional dependency `miceforest`.

    ```python
    # pip install miceforest
    df_imputed = DataProcessor.mice_imputation(df, iterations=10, n_estimators=100, add_indicators=True)
    ```

??? tip "extract_missingindicator_columns(data)"
    ```python
    missing_indicators_only = DataProcessor.extract_missingindicator_columns(imputed)
    ```

??? tip "inverse_dummy_features(data, dummy_cat_columns)"
    ```python
    # Build a small dummy-encoded frame to decode
    dummy_frame = pd.DataFrame(
        {"sex_F": [0, 1, 1], "sex_M": [1, 0, 0]},
        index=[0, 1, 2],
    )
    decoded = DataProcessor.inverse_dummy_features(dummy_frame, dummy_cat_columns=["sex"])
    ```

??? tip "inverse_ordinal_features(data, encoder)"
    ```python
    decoded_stage = DataProcessor.inverse_ordinal_features(ord_encoded, ord_encoder)
    ```

??? tip "inverse_standardization(data, scaler)"
    ```python
    num_restored = DataProcessor.inverse_standardization(num_scaled, scaler_obj)
    ```

??? tip "knn_imputation(data, ...)"
    ```python
    df_knn_full = DataProcessor.knn_imputation(
        data=df[["sex", "stage", "age"]].copy(),
        dummy_cat_columns=["sex"],
        ordinal_cat_columns=["stage"],
        numerical_columns=["age"],
        scaler="minmax",
        n_neighbors=5,
        add_indicators=True,
        verbose=False,
    )
    ```

??? tip "feature_engineering(data, data_type, ...)"
    ```python
    processed, numerical_features, dummy_features = DataProcessor.feature_engineering(
        data=df[["sex", "stage", "age"]].copy(),
        data_type="clinical",
        overmissing_threshold=50,
        imputer="knn",
        ordinal_cat_columns=["stage"],
        unique_threshold=10,
        scaler="minmax",
        imputer_params={"n_neighbors": 5},
        add_indicators=True,
        verbose=False,
    )
    ```

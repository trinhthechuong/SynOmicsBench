# Data Processing Pipeline

The `SynOmics.processing` module provides a comprehensive suite of utilities for cleaning, transforming, and integrating omics and clinical data. It handles everything from initial data cleaning to advanced imputation and gene identifier mapping.

## Overview

The processing pipeline is designed to handle the specific challenges of multi-omics datasets:
- **High Dimensionality**: Efficiently filter low-variance or over-missing features.
- **Mixed Data Types**: Support for numerical, ordinal, and categorical (dummy) clinical variables.
- **Missing Data**: Advanced imputation using MICE (Multiple Imputation by Chained Equations) or KNN (K-Nearest Neighbors).
- **Identifier Mapping**: Integration of transcriptomics (Ensembl) and clinical data via patient identifiers and gene symbol mapping.

## DataProcessor Class

The `DataProcessor` class in `SynOmics.processing.preprocessing` contains the core logic for data manipulation. Most methods are static and can be used independently or as part of a larger pipeline.

### Preprocessing Functions

#### `remove_low_expression_genes`
Removes genes from transcriptomics data based on total expression and variance.

```python
from SynOmics.processing.preprocessing import DataProcessor

# data can be samples x genes or genes x samples
filtered_df = DataProcessor.remove_low_expression_genes(
    data=expression_df,
    gene_id_column="gene_id", # if genes are rows
    variance_threshold=0.0005
)
```

#### `remove_overmissing_features` / `remove_overmissing_entities`
Filters columns or rows that exceed a specific missingness percentage.

```python
# Remove columns with more than 50% missing values
clean_df = DataProcessor.remove_overmissing_features(df, threshold=50.0)

# Remove rows (samples) with more than 30% missing values
clean_df = DataProcessor.remove_overmissing_entities(df, threshold=30.0)
```

#### `standardization`
Scales numerical features using standard, min-max, or robust scaling.

```python
scaled_df, scaler = DataProcessor.standardization(df, scaler='minmax')
```

### Imputation

The framework supports two primary imputation methods via `impute_router` or `mice_imputation` and `knn_imputation`.

#### `mice_imputation`
Uses the `miceforest` library to perform MICE. It automatically handles categorical data if cast to the `category` dtype.

```python
imputed_df = DataProcessor.mice_imputation(
    data=df,
    iterations=20,
    n_estimators=300,
    add_indicators=True
)
```

#### `knn_imputation`
A robust KNN-based imputer that handles mixed data types by specifically managing dummy and ordinal columns.

```python
imputed_df = DataProcessor.knn_imputation(
    data=df,
    dummy_cat_columns=['Gender', 'Smoker'],
    ordinal_cat_columns=['Stage'],
    numerical_columns=['Age', 'BMI'],
    n_neighbors=5
)
```

## Postprocessing

Postprocessing ensures that synthetic or imputed data adheres to the original data's constraints.

### Constraint Enforcement

Utilities in `SynOmics.processing.postprocessing` help maintain data integrity:
- `apply_min_max`: Clips values to the original range.
- `apply_rounding`: Restores original decimal precision.
- `post_masking`: Re-introduces `NaN` values based on missingness indicators (useful after synthesis).

```python
from SynOmics.processing.postprocessing import apply_min_max, apply_rounding

# Enforce original boundaries
processed_df = apply_min_max(synthetic_df, num_cols, min_vals, max_vals)

# Restore precision
processed_df = apply_rounding(processed_df, num_cols, rounding_digits)
```

### Anonymization
`anonymize_ids` replaces patient identifiers with UUIDs and maintains a mapping for internal reference.

## Metadata Management

The `MetaData` class classifies features into types, which is essential for synthesis and evaluation.

### Feature Classification
The `get_metadata` method categorizes columns into:
- `numerical`
- `dummy_categorical`
- `ordinal_categorical`
- `missing_categorical` (for indicators like `missingindicator_Age`)

```python
from SynOmics.processing.metadata import MetaData

metadata = MetaData.get_metadata(
    data=df,
    threshold_unique_values=10,
    ordinal_features=['Stage']
)
```

The resulting dictionary is often saved as `feature_metadata.json` to guide the synthesis pipeline.

## Gene Query Utilities

The `GeneQuery` class interfaces with `MyGeneInfo` to manage transcriptomics identifiers.

- `convert_genes`: Maps Ensembl IDs to HUGO symbols.
- `check_duplicates`: Groups genes with identical expression profiles across samples (common in processed datasets).

```python
from SynOmics.processing.gene_query import GeneQuery

query = GeneQuery(fields=["symbol"], scopes=["ensemblgene"], species=["human"], output_dir="results")
mapping_df = query.convert_genes(expression_df)
```

## Data Integration Pipeline

The `DataIntegrationPipeline` class coordinates these steps into a single workflow.

```python
from SynOmics.processing.pipeline import DataIntegrationPipeline

pipeline = DataIntegrationPipeline(output_dir="output")
results = pipeline.run_pipeline(
    clinical_data=raw_clinical,
    transcriptomics_data=raw_transcript,
    clinical_id_column="PatientID",
    transcriptomics_id_column="SampleID",
    integration_id_column="PATIENT_ID",
    imputer="mice"
)

# Access integrated data
final_df = results['integrated_data']
```

The pipeline logs every step, including the number of features removed and the time taken for each operation, ensuring transparency in the data preparation process.

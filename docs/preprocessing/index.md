# Preprocessing Data

The `SynOmics.processing` module provides a comprehensive suite of utilities for cleaning, transforming, and integrating omics and clinical data. It addresses key challenges in multi-omics research, including high dimensionality through feature filtering, mixed data types (numerical, ordinal, categorical), missing data via MICE and KNN imputation, and identifier mapping for seamless transcriptomics and clinical integration.

## Data Integration Pipeline

![Data Integration Pipeline](../assets/figures/processing_pipeline.png)

*Figure 2: Standardized preprocessing pipeline for clinical-transcriptomic data integration.*

The `DataIntegrationPipeline` class coordinates preprocessing, integration, and imputation into a single unified workflow. This pipeline ensures data quality and consistency before synthetic data generation or downstream analysis.

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

The data integration pipeline executes the following configurable preprocessing steps in sequence:

### remove_undefined

Removes samples with undefined or missing identifiers in the ID columns. This ensures all samples can be uniquely identified and tracked throughout the pipeline.

### remove_duplicates

Identifies and removes duplicate rows (samples) or columns (features) based on exact matches. This prevents redundant information from biasing downstream analysis or synthetic data generation.

### remove_overmissing_samples

Filters out samples (rows) that exceed a specified missingness threshold (e.g., 50% missing values). Samples with excessive missing data are often unreliable and can reduce model quality.

### remove_low_expression_genes

Filters genes (features) based on expression level and variance thresholds. Genes with consistently low expression or near-zero variance across samples provide minimal information and can be safely excluded to reduce dimensionality.

### check_duplicate_genes

Identifies genes with identical expression profiles across all samples. Such duplicate genes may result from redundant probes or isoforms and are flagged for potential removal or merging.

### mapping_genes

Maps Ensembl gene identifiers to HUGO gene symbols using the MyGeneInfo API. This standardizes gene nomenclature and facilitates integration with external databases and pathway analysis tools.

### feature_engineering

Performs feature type classification (numerical, ordinal categorical, dummy categorical), encoding of categorical variables, scaling of numerical features, and imputation of missing values using either MICE (Multiple Imputation by Chained Equations) or KNN methods. Optionally adds missingness indicator columns to preserve information about missing data patterns.

### integrate_data

Merges processed clinical and transcriptomics data on a common patient identifier column. The integration step produces a unified dataset suitable for multi-omics analysis and synthetic data generation.
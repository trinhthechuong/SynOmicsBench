# SynOmicBench

SynOmicBench is a comprehensive benchmarking framework for evaluating synthetic data generation in omics and clinical contexts. It provides tools for data preprocessing, multi-omic integration, synthetic data generation using various state-of-the-art models, and a suite of utility metrics to assess the fidelity and utility of generated datasets.

## Core Modules

### Pipeline & Processing
- **DataIntegrationPipeline**: Manages the end-to-end workflow of cleaning, normalizing, and merging clinical and transcriptomics datasets.
- **DataProcessor**: Provides low-level utilities for duplicate removal, missing value handling (KNN and MICE imputation), encoding (dummy and ordinal), and standardization.
- **MetaData**: Automatically classifies feature types (numerical, categorical, ordinal) to guide downstream synthesis and evaluation.
- **GeneQuery**: Maps Ensembl IDs to HUGO symbols and handles gene-level metadata.

### Synthesizers
The framework supports multiple synthesis engines through a unified `BaseSynthesizer` interface:
- **CTGAN / TVAE**: Deep learning-based generative adversarial networks and variational autoencoders.
- **GaussianCopula**: Statistical model for capturing multivariate dependencies.
- **Synthpop**: Tree-based synthesis specifically designed for sensitive health data.
- **MICE**: Multiple Imputation by Chained Equations adapted for synthesis.

### Metrics & Evaluation
SynOmicBench evaluates synthetic data across several dimensions:
- **Fidelity**: Distributional similarity, pairwise correlations, and visualization (PCA, UMAP).
- **Narrow Utility**: Performance on specific downstream tasks like Differential Gene Expression (DGE) analysis, Survival Analysis, and Gene Set Enrichment Analysis (GSEA).
- **Privacy**: Assessment of membership inference risks and attribute disclosure.

## Installation

```bash
pip install -e .
```

## Quick Start

```python
from SynOmics.pipeline.DataIntegration import DataIntegrationPipeline

# Initialize pipeline
pipeline = DataIntegrationPipeline(output_dir="./output")

# Run integration and preprocessing
results = pipeline.run_pipeline(
    clinical_data=clinical_df,
    transcriptomics_data=transcriptomics_df,
    clinical_id_column="PatientID",
    transcriptomics_id_column="SampleID"
)
```
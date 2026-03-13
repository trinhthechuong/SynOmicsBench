# SynOmicBench

[![Documentation](https://img.shields.io/badge/docs-GitHub%20Pages-blue.svg)](https://trinhthechuong.github.io/SynOmicBench/)
[![Docstring Coverage](https://img.shields.io/badge/docstrings-77%25-yellowgreen.svg)](#)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-red.svg)](https://www.python.org/downloads/release/python-3110/)

**SynOmicBench** is a unified benchmarking framework for synthetic data generation (SDG) tailored to high-dimensional clinical and transcriptomic cancer data.

Achieving a trade-off between **biological utility** and **patient privacy** is critical for precision oncology. Meta-analysis of synthetic data often lacks rigorous biological validation. SynOmicBench fills this gap by providing a reproducible pipeline for generating, evaluating, and benchmarking synthetic multi-omic datasets.

---

## Overview

SynOmicBench is the first disease-agnostic benchmarking study tailored to high-dimensional clinical transcriptomic cancer data. It compares synthetic data generation methods across three cancer types (ccRCC, Melanoma, NSCLC) using a standardized pipeline that combines:

- **Standardized Preprocessing**: Automated data filtering, harmonization, and integration
- **Multidimensional Evaluation**: Statistical fidelity, biological utility, and privacy risk assessment
- **Bayesian Comparison**: Rigorous meta-ranking across multiple cohorts and replicates

---

## Key Features

- **Standardized Preprocessing**: Automated pipeline for data filtering, harmonization, and integration of clinical and transcriptomic data
- **State-of-the-Art SDG Methods**: Integrated support for:
  - CTGAN
  - TVAE
  - Gaussian Copula
  - Synthpop
  - Avatars (K5/K10)
- **Comprehensive Evaluation Framework**:
  - **Statistical Fidelity**: Univariate/bivariate similarity, KS tests, PCA/UMAP
  - **Biological Utility**: DGE, GSEA, ssGSEA, Cell Type Deconvolution, Survival Analysis
  - **Privacy Risk**: Singling-out, Linkability, Inference (EDPB-aligned)
- **Biological Validation**: Downstream bioinformatics tasks to ensure synthetic data supports real research
- **Bayesian Comparison**: Uncertainty-aware method comparison across replicates

---

## Benchmarked Datasets

| Characteristic | ccRCC | Melanoma | NSCLC |
|---------------|-------|----------|-------|
| Number of patients | 311 | 121 | 152 |
| Clinical features | 52 | 47 | 14 |
| Transcriptomics features | 40,934 | 18,760 | 21,969 |
| Study source | Braun et al. (2020) | Liu et al. (2019) | Ravi et al. (2023) |

---

## Installation

```bash
git clone https://github.com/trinhthechuong/SynOmicBench.git
cd SynOmicBench
pip install -e .
```

---

## Quick Start

### 1. Preprocess Your Data

```python
from SynOmics.processing.pipeline import DataIntegrationPipeline

pipeline = DataIntegrationPipeline(output_dir="./output", logger="my_pipeline")
results = pipeline.run_pipeline(
    clinical_data=clinical_df,
    transcriptomics_data=omics_df,
    clinical_id_column="Patient_ID",
    transcriptomics_id_column="Sample",
    integration_id_column="Patient_ID"
)
```

### 2. Generate Synthetic Data

```python
from SynOmics.synthesizer.GaussianCopulasynthesizer import GaussianCopulasynthesizer

synth = GaussianCopulasynthesizer(output_path="./results", metadata=metadata)
synthetic_data = synth.generate(
    data=original_data,
    n_samples=original_data.shape[0],
    seed=42
)
```

### 3. Evaluate

```python
from SynOmics.metrics.fidelity.UnivariateSimilarity import UnivariateSimilarity

uni = UnivariateSimilarity(output_dir="./evaluation")
score = uni.get_univariate_score(
    original_data=original,
    synthetic_data=synthetic,
    metadata=metadata
)
```

---

## Documentation

- [**Full Documentation**](https://trinhthechuong.github.io/SynOmicBench/)
- [**Getting Started**](https://trinhthechuong.github.io/SynOmicBench/getting-started/)
- [**Preprocessing Pipeline**](https://trinhthechuong.github.io/SynOmicBench/preprocessing/)
- [**SDG Methods**](https://trinhthechuong.github.io/SynOmicBench/synthetic-data/)
- [**Evaluation Framework**](https://trinhthechuong.github.io/SynOmicBench/evaluation/)
- [**API Reference**](https://trinhthechuong.github.io/SynOmicBench/api/)

---

## Key Results

- **No single method dominated all dimensions** — Gaussian Copula achieved the most balanced performance
- **Metric-based similarity alone is insufficient** to ensure preservation of higher-order molecular dependencies
- **Synthetic data consistently reproduced signal directionality** but with attenuated effect sizes
- Synthetic data can support biological hypothesis generation when carefully validated

---

## Citation

If you use SynOmicBench in your research, please cite:

> Trinh, T. C., Woillard, J. B., Uguzzoni, G., & Battail, C. (2024). **A unified benchmark of synthetic data generation for clinical and transcriptomic cancer data.** (Manuscript in preparation)

---

## License

This project is licensed under the MIT License.

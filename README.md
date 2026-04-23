# SynOmicsBench

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.19660703.svg)](https://zenodo.org/records/19660703)
[![CI](https://github.com/trinhthechuong/SynOmicsBench/actions/workflows/ci.yml/badge.svg)](https://github.com/trinhthechuong/SynOmicsBench/actions/workflows/ci.yml)
[![Documentation](https://img.shields.io/badge/docs-GitHub%20Pages-blue.svg)](https://trinhthechuong.github.io/SynOmicsBench/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-red.svg)](https://www.python.org/downloads/release/python-3120/)


**SynOmicsBench** is a unified benchmarking framework for synthetic data generation (SDG) tailored to high-dimensional clinical and transcriptomic cancer data.

Achieving a trade-off between **biological utility** and **patient privacy** is critical for secure data sharing when applying transcriptomic clinical datasets to artificial intelligence in precision oncology. Meta-analysis of synthetic data often lacks rigorous biological validation. SynOmicsBench fills this gap by providing a reproducible, multidimensional pipeline for generating, evaluating, and benchmarking synthetic multi-omic datasets.

---

## 🔬 Framework Overview

![Framework Overview](docs/assets/figures/Figure_1_Graphical_abstract.png)

SynOmicsBench is the first disease-agnostic benchmarking study tailored to high-dimensional clinical transcriptomic cancer data. It compares synthetic data generation methods across three cancer types using a standardized pipeline that combines:

- **Standardized Preprocessing**: Automated data filtering, harmonization, and integration.
- **Multidimensional Evaluation**: Assessing Statistical Fidelity, Downstream Biological Utility, and Privacy Risk.
- **State-of-the-Art SDG Methods**: Native support for **CTGAN, TVAE, Gaussian Copula, Synthpop, and Avatars (K5/K10)**.

---

## 🛠 Installation

SynOmicsBench can be installed in three different ways depending on your environment. **Python 3.12+** is required.

### Option 1: From PyPI (Recommended)
You can easily install the latest stable release via pip:
```bash
pip install synomicsbench
```

### Option 2: From Source (GitHub)
For developers or if you want the very latest features. We strongly suggest using [`uv`](https://docs.astral.sh/uv/) for the fastest dependency resolution:
```bash
git clone https://github.com/trinhthechuong/SynOmicsBench.git
cd SynOmicsBench

# With uv (Fastest)
uv sync
source .venv/bin/activate

# Or with traditional pip
pip install -e .
```

### Option 3: Pre-built Container (Apptainer/Singularity)
For HPC environments or reproducible workflows, you can pull our fully prepared Apptainer container which contains all dependencies (including heavy ML frameworks and R):

```bash
# Pull the latest SynOmicsBench container
apptainer pull synomicsbench.sif oras://ghcr.io/trinhthechuong/synomicsbench:latest

# Verify the container is working and the package is ready
apptainer exec synomicsbench.sif python -c "import synomicsbench; print('OK: SynOmicsBench is ready!')"
```
*(To use the container for your scripts, simply mount your directories via `--bind` and run your Python scripts using `apptainer exec`)*

---

## 🚀 Quick Start

Here is a brief example of how to generate synthetic data with Gaussian Copula and evaluate its statistical fidelity:

```python
import pandas as pd
from synomicsbench.synthesizer.GaussianCopulasynthesizer import GaussianCopulasynthesizer
from synomicsbench.processing.metadata import MetaData
from synomicsbench.metrics.fidelity.UnivariateSimilarity import UnivariateSimilarity 

# 1. Load Data & Prepare Metadata
original_data = pd.read_csv("your_clinical_transcriptomic_data.csv")
ordinal_features = ["Mstage", "Tx_Start_ECOG", "numPriorTherapies"]
metadata = MetaData.get_metadata(data=original_data, ordinal_features=ordinal_features)

# 2. Generate Synthetic Data
synth = GaussianCopulasynthesizer(output_path="./results", metadata=metadata)
synthetic_data = synth.generate(
    data=original_data, 
    n_samples=original_data.shape[0]
)

# 3. Evaluate Fidelity
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

## 📚 Documentation

For complete API references, tutorials, and full benchmarking results, check out the **[SynOmicsBench Official Documentation](https://trinhthechuong.github.io/SynOmicsBench/)**:

- [**Getting Started**](https://trinhthechuong.github.io/SynOmicsBench/getting-started/): Step-by-step setup guides.
- [**Preprocessing Pipeline**](https://trinhthechuong.github.io/SynOmicsBench/preprocessing/): Harmonizing multimodal data.
- [**SDG Methods**](https://trinhthechuong.github.io/SynOmicsBench/synthetic-data/): Deep dive into generation models.
- [**Evaluation Framework**](https://trinhthechuong.github.io/SynOmicsBench/evaluation/): Understand our metrics for Privacy and Biological signal preservation.

---

## 📝 Citation

If you use SynOmicsBench in your research, please cite:

> Trinh, T. C., Woillard, J. B., Uguzzoni, G., & Battail, C. (2024). **A unified benchmark of synthetic data generation for clinical and transcriptomic cancer data.** *(Manuscript in preparation)*

## 📄 License
This project is open-sourced under the MIT License.

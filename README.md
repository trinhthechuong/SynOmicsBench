# SynOmicsBench

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.19660703.svg)](https://zenodo.org/records/19660703)
[![CI](https://github.com/trinhthechuong/SynOmicsBench/actions/workflows/ci.yml/badge.svg)](https://github.com/trinhthechuong/SynOmicsBench/actions/workflows/ci.yml)
[![Documentation](https://img.shields.io/badge/docs-GitHub%20Pages-blue.svg)](https://trinhthechuong.github.io/SynOmicsBench/)
[![PyPI](https://img.shields.io/pypi/v/synomicsbench)](https://pypi.org/project/synomicsbench/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-red.svg)](https://www.python.org/downloads/release/python-3120/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![Container](https://img.shields.io/badge/container-Apptainer-blue.svg)](https://github.com/trinhthechuong/SynOmicsBench/pkgs/container/synomicsbench)


**SynOmicsBench** is a unified benchmarking framework for synthetic data generation (SDG) for clinical transcriptomic cancer cohorts.

Achieving a trade-off between **biological utility** and **patient privacy** is critical for secure data sharing when applying transcriptomic clinical datasets to artificial intelligence in precision oncology. Here, we present the **SynOmicsBench** framework. SynOmicsBench combines standardized preprocessing with multidimensional evaluation, prioritizing downstream biological validation alongside statistical fidelity and attack-based privacy assessment. This work provides a reproducible decision-support tool for method selection and promotes biologically informed, privacy-aware adoption of synthetic data in precision oncology.

---

## 🔬 Framework Overview

![Framework Overview](https://github.com/user-attachments/assets/2cf2423c-dc24-4f85-b97f-2160bfc9ebf4)

SynOmicsBench compares synthetic data generation methods using a standardized pipeline that combines:

- **Standardized Preprocessing**: Automated data filtering, harmonization, and integration.
- **Multidimensional Evaluation**: Assessing Statistical Fidelity, Downstream Biological Utility, and Privacy Risk.
- **State-of-the-Art SDG Methods**: Native support for **CTGAN, TVAE, Gaussian Copula, Synthpop, and Avatars (K5/K10)**. 

---

## 🛠 Installation

SynOmicsBench can be installed in three different ways depending on your environment. **Python 3.12+** is required.

### Option 1: From PyPI (Recommended)

```bash
pip install synomicsbench
```

### Option 2: From Source (GitHub)
We recommend using [`uv`](https://docs.astral.sh/uv/) for fast, reliable dependency management. This method uses the provided uv.lock file to ensure reproducible installations.
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

Here is a minimal end-to-end example: preprocess data, generate synthetic samples with Gaussian Copula, and evaluate statistical fidelity.

```python
import pandas as pd
from synomicsbench.processing.preprocessing import DataProcessor
from synomicsbench.processing.metadata import MetaData
from synomicsbench.synthesizer.GaussianCopulasynthesizer import GaussianCopulasynthesizer
from synomicsbench.metrics.fidelity.UnivariateSimilarity import UnivariateSimilarity

# ── 1. Load & preprocess ──────────────────────────────────────────────────────
original_data = pd.read_csv("your_clinical_transcriptomic_data.csv")

original_data = DataProcessor.remove_unknown_entities(original_data, id_column="Patient_ID")
original_data = DataProcessor.remove_duplications(original_data, axis=0).reset_index(drop=True)
original_data = DataProcessor.mice_imputation(original_data, iterations=10, n_estimators=100)

# ── 2. Build metadata ─────────────────────────────────────────────────────────
ordinal_features = ["Mstage", "Tx_Start_ECOG", "numPriorTherapies"]
metadata = MetaData.get_metadata(
    data=original_data,
    ordinal_features=ordinal_features,
    threshold_unique_values=10,
)

# ── 3. Generate synthetic data ────────────────────────────────────────────────
synth = GaussianCopulasynthesizer(output_path="./results", metadata=metadata)
synthetic_data = synth.generate(
    data=original_data,
    seed=42,
    n_samples=original_data.shape[0],
    output_filename="synthetic_data.csv",
)

# ── 4. Evaluate statistical fidelity ─────────────────────────────────────────
evaluator = UnivariateSimilarity(output_dir="./results/evaluation")
score = evaluator.get_univariate_score(
    original_data=original_data,
    synthetic_data=synthetic_data,
    metadata=metadata,
    save=True,
)
print(f"Univariate Fidelity Score: {score:.4f}")
```

---

## 📚 Documentation

For complete API references, tutorials, and full benchmarking results, check out the **[SynOmicsBench Official Documentation](https://trinhthechuong.github.io/SynOmicsBench/)**:

- [**Getting Started**](https://trinhthechuong.github.io/SynOmicsBench/getting-started/): Step-by-step setup guides.
- [**Preprocessing Pipeline**](https://trinhthechuong.github.io/SynOmicsBench/preprocessing/): Harmonizing multimodal data.
- [**SDG Methods**](https://trinhthechuong.github.io/SynOmicsBench/synthetic-data/): Deep dive into generation models.
- [**Evaluation Framework**](https://trinhthechuong.github.io/SynOmicsBench/evaluation/): Understand our metrics for Privacy and Biological signal preservation.

---

## 📄 License
This project is open-sourced under the MIT License.

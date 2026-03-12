# SynOmicBench

[![Documentation](https://img.shields.io/badge/docs-GitHub%20Pages-blue.svg)](https://trinhthechuong.github.io/SynOmicBench/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-red.svg)](https://www.python.org/downloads/release/python-3110/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**SynOmicBench** is a unified benchmarking framework for synthetic data generation (SDG) tailored to high-dimensional clinical and transcriptomic cancer data.

Achieving a trade-off between **biological utility** and **patient privacy** is critical for precision oncology. Meta-analysis of synthetic data often lacks rigorous biological validation. SynOmicBench fills this gap by providing a reproducible pipeline for generating, evaluating, and benchmarking synthetic multi-omic datasets.

---

## 🚀 Key Features

- **Standardized Preprocessing**: Automated pipeline for data filtering, harmonization, and integration.
- **State-of-the-Art SDG Methods**: Integrated support for CTGAN, TVAE, Gaussian Copula, Synthpop, and Avatars.
- **Multidimensional Evaluation**:
    - **Broad Utility**: Statistical fidelity and structural similarity (KS tests, PCA/UMAP).
    - **Narrow Utility**: Biological signal preservation (DGE, GSEA, Cell Deconvolution, Survival).
    - **Privacy Risk**: Rigorous assessment based on EDPB principles (Singling-out, Linkability, Inference).
- **Bayesian Comparison**: Rigorous meta-ranking of methods across multiple cancer cohorts and replicates.

---

## 📖 Quick Links

- [**Full Documentation**](https://trinhthechuong.github.io/SynOmicBench/)
- [**Getting Started**](https://trinhthechuong.github.io/SynOmicBench/getting-started/)
- [**SDG Methods**](https://trinhthechuong.github.io/SynOmicBench/synthetic-data/)
- [**Evaluation Framework**](https://trinhthechuong.github.io/SynOmicBench/evaluation/)

---

## 🛠️ Installation

```bash
git clone https://github.com/trinhthechuong/SynOmicBench.git
cd SynOmicBench
pip install -e .
```

For detailed usage examples, see the [Getting Started](https://trinhthechuong.github.io/SynOmicBench/getting-started/) guide.

---

## ⚖️ Citation

If you use SynOmicBench in your research, please cite:

> Trinh, T. C., Woillard, J. B., Uguzzoni, G., & Battail, C. (2024). **A unified benchmark of synthetic data generation for clinical and transcriptomic cancer data.** (Manuscript in preparation)

---

## 📜 License

This project is licensed under the MIT License.
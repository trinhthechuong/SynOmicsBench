# SynOmicsBench

**SynOmicsBench** is a unified benchmarking framework for synthetic data generation (SDG) for clinical transcriptomic cancer cohorts.

Achieving a trade-off between **biological utility** and **patient privacy** is critical for secure data sharing when applying transcriptomic clinical datasets to artificial intelligence in precision oncology. Here, we present the **SynOmicsBench** framework. SynOmicsBench combines standardized preprocessing with multidimensional evaluation, prioritizing downstream biological validation alongside statistical fidelity and attack-based privacy assessment. This work provides a reproducible decision-support tool for method selection and promotes biologically informed, privacy-aware adoption of synthetic data in precision oncology.

---

## Installation

```bash
pip install synomicsbench
```

Python 3.12+ is required.

---

## Quick Start

```python
import pandas as pd
from synomicsbench.processing.preprocessing import DataProcessor
from synomicsbench.processing.metadata import MetaData
from synomicsbench.synthesizer.GaussianCopulasynthesizer import GaussianCopulasynthesizer
from synomicsbench.metrics.fidelity.UnivariateSimilarity import UnivariateSimilarity

# 1. Preprocess
data = pd.read_csv("clinical_transcriptomic_data.csv")
data = DataProcessor.remove_unknown_entities(data, id_column="Patient_ID")
data = DataProcessor.remove_duplications(data, axis=0).reset_index(drop=True)
data = DataProcessor.mice_imputation(data, iterations=10, n_estimators=100)

# 2. Metadata
metadata = MetaData.get_metadata(
    data=data,
    ordinal_features=["Mstage", "Tx_Start_ECOG", "numPriorTherapies"],
    threshold_unique_values=10,
)

# 3. Generate synthetic data
synth = GaussianCopulasynthesizer(output_path="./results", metadata=metadata)
synthetic_data = synth.generate(
    data=data,
    seed=42,
    n_samples=data.shape[0],
    output_filename="synthetic_data.csv",
)

# 4. Evaluate
evaluator = UnivariateSimilarity(output_dir="./results/evaluation")
score = evaluator.get_univariate_score(
    original_data=data,
    synthetic_data=synthetic_data,
    metadata=metadata,
    save=True,
)
print(f"Univariate Fidelity Score: {score:.4f}")
```

---

## Documentation

Full documentation, API reference, and benchmarking results:
**[https://trinhthechuong.github.io/SynOmicsBench/](https://trinhthechuong.github.io/SynOmicsBench/)**

---

## Citation

If you use SynOmicsBench in your research, please cite:

> Trinh, T. C., Woillard, J. B., Uguzzoni, G., & Battail, C. (2024). **A unified benchmark of synthetic data generation for clinical and transcriptomic cancer data.** *(Manuscript in preparation)*

---

## License

MIT License

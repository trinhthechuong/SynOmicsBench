# Getting Started

## Installation

You can install SynOmicBench directly from source to ensure you have the latest features and research benchmarks.

### From Source

Clone the repository and install the dependencies:

```bash
git clone https://github.com/SynOmicBench/SynOmicBench.git
cd SynOmics
pip install -e .
```

**Python Version**: 3.9 

A `requirements.txt` file is provided in the repository root for reference.

### From Singularity

Singularity container instructions coming soon.

---

## Quick Example

Here's a complete example showing how to generate synthetic data using GaussianCopula and evaluate fidelity:

```python
import pandas as pd
import numpy as np
from SynOmics.synthesizer.GaussianCopulasynthesizer import GaussianCopulasynthesizer
from SynOmics.processing.metadata import MetaData
from SynOmics.metrics.fidelity.UnivariateSimilarity import UnivariateSimilarity 

original_data = pd.read_csv("your_original_data.csv")

ordinal_features = ["Mstage", "Tx_Start_ECOG", "numPriorTherapies", "biopsyContext"]

# Create metadata object to specify feature types and properties
metadata = MetaData.get_metadata(data=original_data,ordinal_features=ordinal_features
)

#Generate synthetic data
output_path = "./results"

synth = GaussianCopulasynthesizer(output_path=output_path, metadata=metadata)

synthetic_data = synth.generate(data=original_data, n_samples=original_data.shape[0], output_filename="synthetic_data.csv")

#Evaluate fidelity using Univariate Similarity
evaluator = UnivariateSimilarity(output_dir="./evaluation_results")

score = evaluator.get_univariate_score(original_data=original_data, synthetic_data=synthetic_data, metadata=metadata, save=True)

print(f"Overall Fidelity Score: {score:.4f}")
```

---

## Next Steps

Now that you've completed your first synthesis, explore more advanced topics:
- [Preprocessing Data](../preprocessing/index.md):How to harmonize and integrate multimodal data.

- [Generate Synthetic Data](../synthetic-data/index.md): Detailed descriptions of each synthesis method and their adaptations.

- [Evaluation Metrics](../evaluation/index.md): Deep dive into Statistical fidelity, Biology utility and Privacy metrics.


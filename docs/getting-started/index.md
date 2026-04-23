# Getting Started

## Installation

SynOmicsBench can be installed in multiple ways depending on your use case and environment. Choose the method that best fits your workflow.

### Prerequisites

- **Python Version**: 3.12 or higher
- **Operating System**: Linux, macOS, or Windows (with WSL recommended)

---

### Option 1: From PyPI (Recommended)

```bash
pip install synomicsbench
```

---

### Option 2: From Source (GitHub)

We recommend using [uv](https://docs.astral.sh/uv/) for fast, reliable dependency management. This method uses the provided `uv.lock` file to ensure reproducible installations.

#### Clone and Install

```bash
git clone https://github.com/trinhthechuong/SynOmicsBench.git
cd SynOmicsBench

# With uv (Fastest)
uv sync
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Or with traditional pip
pip install -e .
```

---

### Option 3: Pre-built Container (Apptainer/Singularity)

For HPC environments or reproducible workflows, you can pull our fully prepared Apptainer container which contains all dependencies (including heavy ML frameworks and R):

#### Pull the Container

```bash
# Pull the latest SynOmicsBench container
apptainer pull synomicsbench.sif oras://ghcr.io/trinhthechuong/synomicsbench:latest
```

#### Launch Interactive Shell

Open a shell session inside the container with your workspace mounted:

```bash
# Mount your workspace directory to /mnt inside the container
apptainer shell --bind /path/to/your/workspace:/mnt synomicsbench.sif
```

#### Running Scripts Directly

You can also execute scripts directly without entering the shell:

```bash
# Verify the container is working and the package is ready
apptainer exec synomicsbench.sif python -c "import synomicsbench; print('OK: SynOmicsBench is ready!')"

# Run your analysis scripts and mount directories
apptainer exec --bind /path/to/your/workspace:/mnt synomicsbench.sif python /mnt/your_script.py
```

#### Container Best Practices

- **Data Persistence**: Always use `--bind` to mount your data directories. Changes inside the container (outside mounted paths) are ephemeral.
- **HPC Integration**: Most HPC systems support Singularity/Apptainer natively. Check your cluster documentation for specific submission scripts.
- **GPU Access**: Add `--nv` flag for NVIDIA GPU access: `apptainer shell --nv --bind ... synomicsbench.sif`

---

## Quick Example

Here's a complete example showing how to generate synthetic data using GaussianCopula and evaluate fidelity:

```python
import pandas as pd
import numpy as np
from synomicsbench.synthesizer.GaussianCopulasynthesizer import GaussianCopulasynthesizer
from synomicsbench.processing.metadata import MetaData
from synomicsbench.metrics.fidelity.UnivariateSimilarity import UnivariateSimilarity 

# Load your clinical-transcriptomic dataset
original_data = pd.read_csv("your_original_data.csv")

# Identify ordinal features for specialized handling
ordinal_features = ["Mstage", "Tx_Start_ECOG", "numPriorTherapies", "biopsyContext"]

# Create metadata object to specify feature types and properties
metadata = MetaData.get_metadata(
    data=original_data,
    ordinal_features=ordinal_features
)

# Initialize and run the synthesizer
output_path = "./results"
synth = GaussianCopulasynthesizer(output_path=output_path, metadata=metadata)

synthetic_data = synth.generate(
    data=original_data, 
    n_samples=original_data.shape[0], 
    output_filename="synthetic_data.csv"
)

# Evaluate fidelity using Univariate Similarity
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

## Next Steps

Now that you've completed your first synthesis, explore more advanced topics:

- [Preprocessing Data](../preprocessing/index.md):How to harmonize and integrate multimodal data.

- [Generate Synthetic Data](../synthetic-data/index.md): Detailed descriptions of each synthesis method and their adaptations.

- [Evaluation Metrics](../evaluation/index.md): Deep dive into Statistical fidelity, Biology utility and Privacy metrics.


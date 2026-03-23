# Getting Started

## Installation

SynOmicBench can be installed in multiple ways depending on your use case and environment. Choose the method that best fits your workflow.

### Prerequisites

- **Python Version**: 3.12 or higher
- **Operating System**: Linux, macOS, or Windows (with WSL recommended)

---

### Method 1: From Source with uv (Recommended)

We recommend using [uv](https://docs.astral.sh/uv/) for fast, reliable dependency management. This method uses the provided `uv.lock` file to ensure reproducible installations.

#### Install uv

If you don't have uv installed:

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
irm https://astral.sh/uv/install.ps1 | iex
```

#### Clone and Install

```bash
git clone https://github.com/trinhthechuong/SynOmicBench.git
cd SynOmicBench

# Sync dependencies from uv.lock and install package
uv sync
```

This will:

- Create a virtual environment automatically
- Install exact dependencies from `uv.lock` for reproducibility
- Install SynOmics in editable mode for development
- Work without requiring pip or any other package manager

#### Activate the Environment

```bash
# Activate the uv-managed virtual environment
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Verify installation
python -c "import SynOmics; print('SynOmics successfully installed!')"
```

---

### Method 2: From Source with pip

For traditional pip-based installation:

```bash
git clone https://github.com/trinhthechuong/SynOmicBench.git
cd SynOmicBench

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install package
pip install -e .
```

The package dependencies are defined in `pyproject.toml` and will be installed automatically.

---

### Method 3: Using Singularity/Apptainer Container

For HPC environments or reproducible containerized workflows, we provide a pre-built Singularity/Apptainer container with SynOmics and all dependencies pre-installed.

#### Pull the Container

```bash
# Using Apptainer (recommended for newer systems)
apptainer pull synomicsbench_public_test.sif oras://ghcr.io/trinhthechuong/synomicsbench:v20250319

# Or using Singularity (legacy)
singularity pull synomicsbench_public_test.sif oras://ghcr.io/trinhthechuong/synomicsbench:v20250319
```

#### Launch Interactive Shell

Open a shell session inside the container with your workspace mounted:

```bash
# Mount your workspace directory to /mnt inside the container
singularity shell --bind /path/to/your/workspace:/mnt --writable synomicsbench_public_test.sif
```

Replace `/path/to/your/workspace` with your actual workspace path. For example:

```bash
# Example: Mounting a project directory
singularity shell --bind /bettik/PROJECTS/pr-ai4drug/trinhtc/workspace:/mnt --writable synomicsbench_public_test.sif
```

#### Using the Container

Once inside the container shell:

```bash
# Navigate to your mounted workspace
cd /mnt

# SynOmics is already installed and available
python -c "import SynOmics; print(SynOmics.__version__)"

# Run your analysis scripts
python your_analysis.py
```

The container includes:

- **Pre-installed SynOmics** package with all dependencies
- **uv** package manager for additional dependencies
- **Python 3.12+** environment ready to use
- All required system libraries and tools

#### Running Scripts Directly

You can also execute scripts directly without entering the shell:

```bash
singularity exec --bind /path/to/your/workspace:/mnt synomicsbench_public_test.sif python /mnt/your_script.py
```

#### Container Best Practices

- **Data Persistence**: Always use `--bind` to mount your data directories. Changes inside the container (outside mounted paths) are ephemeral.
- **Writable Mode**: Use `--writable` flag if you need to install additional packages or modify the environment.
- **HPC Integration**: Most HPC systems support Singularity/Apptainer natively. Check your cluster documentation for specific submission scripts.
- **GPU Access**: Add `--nv` flag for NVIDIA GPU access: `singularity shell --nv --bind ... synomicsbench_public_test.sif`

---

## Quick Example

Here's a complete example showing how to generate synthetic data using GaussianCopula and evaluate fidelity:

```python
import pandas as pd
import numpy as np
from SynOmics.synthesizer.GaussianCopulasynthesizer import GaussianCopulasynthesizer
from SynOmics.processing.metadata import MetaData
from SynOmics.metrics.fidelity.UnivariateSimilarity import UnivariateSimilarity 

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


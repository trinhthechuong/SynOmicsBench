# Generate Synthetic Data

## Synthetic Data Generation (SDG) Methods

SynOmicsBench benchmarks six synthetic data generation (SDG) methods through their official libraries. Each card links to the original publication of the method.

<div class="sdg-cards-grid">
  <!-- Avatars -->
  <a href="https://www.nature.com/articles/s41746-023-00771-5" target="_blank" class="sdg-card">
    <div class="sdg-card-front">
      <img src="../assets/figures/avatars.png" alt="Avatars Logo" class="sdg-logo">
      <h3>Avatars</h3>
    </div>
  </a>

  <!-- CTGAN -->
  <a href="https://papers.nips.cc/paper_files/paper/2019/hash/254ed7d2de3b23ab10936522dd547b78-Abstract.html" target="_blank" class="sdg-card">
    <div class="sdg-card-front">
      <img src="../assets/figures/neural_network.png" alt="CTGAN Logo" class="sdg-logo">
      <h3>CTGAN</h3>
    </div>
  </a>

  <!-- Gaussian Copula -->
  <a href="https://doi.org/10.1109/DSAA.2016.49" target="_blank" class="sdg-card">
    <div class="sdg-card-front">
      <img src="../assets/figures/copulas.png" alt="Gaussian Copula Logo" class="sdg-logo">
      <h3>Gaussian Copula</h3>
    </div>
  </a>

  <!-- Synthpop -->
  <a href="https://www.jstatsoft.org/article/view/v074i11" target="_blank" class="sdg-card">
    <div class="sdg-card-front">
      <img src="../assets/figures/synthpop.png" alt="Synthpop Logo" class="sdg-logo">
      <h3>Synthpop</h3>
    </div>
  </a>



  <!-- TVAE -->
  <a href="https://papers.nips.cc/paper_files/paper/2019/hash/254ed7d2de3b23ab10936522dd547b78-Abstract.html" target="_blank" class="sdg-card">
    <div class="sdg-card-front">
      <img src="../assets/figures/neural_network.png" alt="TVAE Logo" class="sdg-logo">
      <h3>TVAE</h3>
    </div>
  </a>

  <!-- TabDiff -->
  <a href="https://arxiv.org/abs/2410.20626" target="_blank" class="sdg-card">
    <div class="sdg-card-front">
      <img src="../assets/figures/neural_network.png" alt="TabDiff Logo" class="sdg-logo">
      <h3>TabDiff</h3>
    </div>
  </a>
</div>

Six SDG methods were benchmarked across three cancer types (NSCLC, melanoma, ccRCC), each repeated 5 times with different random seeds to assess the robustness of each method.

Naive fitting of synthetic data generation methods often fails on high-dimensional and heterogeneous multi-omic datasets. Therefore, we designed adaptations for each method to handle these challenges. 

- CTGAN and TVAE requires GPU for training on high-dimensional data.
- Gaussian Copula requires a suitable encoding for categorical variables.
- Synthpop requires a custom predictor matrix optimization to handle high-dimensional data.
- TabDiff requires a GPU and a memory-efficient attention (`use_sdpa=True`, the default) to train on thousands of gene columns.
- Avatars requires a feature clustering to partition the features into batch before submitting to the API.

Each adaptation is described in detail in the Supplementary Methods of the SynOmicsBench manuscript.

### References

If you use one of these methods, please cite its original publication:

- **Avatars**: Guillaudeux, M. *et al.* Patient-centric synthetic data generation, no reason to risk re-identification in biomedical data analysis. *npj Digit. Med.* **6**, 1–10 (2023). [doi:10.1038/s41746-023-00771-5](https://doi.org/10.1038/s41746-023-00771-5)
- **CTGAN** and **TVAE**: Xu, L., Skoularidou, M., Cuesta-Infante, A. & Veeramachaneni, K. Modeling Tabular data using Conditional GAN. *Advances in Neural Information Processing Systems* **32** (2019).
- **Gaussian Copula**: Patki, N., Wedge, R. & Veeramachaneni, K. The Synthetic Data Vault. *2016 IEEE International Conference on Data Science and Advanced Analytics (DSAA)*, 399–410 (2016). [doi:10.1109/DSAA.2016.49](https://doi.org/10.1109/DSAA.2016.49)
- **Synthpop**: Nowok, B., Raab, G. M. & Dibben, C. synthpop: Bespoke Creation of Synthetic Data in R. *J. Stat. Softw.* **74**, 1–26 (2016).
- **TabDiff**: Shi, J. *et al.* TabDiff: a Mixed-type Diffusion Model for Tabular Data Generation. *The Thirteenth International Conference on Learning Representations (ICLR)* (2025).

---

## Usage Example

### 1. Gaussian Copula

```python
from synomicsbench.synthesizer.GaussianCopulasynthesizer import GaussianCopulasynthesizer
from synomicsbench.processing.metadata import MetaData

original_data = pd.read_csv("original_data.csv")
metadata = MetaData.get_metadata(
    data=original_data,
    ordinal_features= [] #your ordinal feature list,
    threshold_unique_values = 10
)

seed = 42 

output_path = "gaussiancopula_result"
synth = GaussianCopulasynthesizer(output_path=output_path, metadata=metadata)

synthetic_data = synth.generate(
data=original_data,
n_samples=original_data.shape[0],
seed=seed,
fit_params={"n_jobs": -1, "chunk_size": 1000},
output_filename="gaussiancopula_synthetic_data.csv",
)
```

### 2. CTGAN

```python
import pandas as pd
from synomicsbench.synthesizer.CTGANsynthesizer import CTGANsynthesizer

synthesizer = CTGANsynthesizer(output_path=f"ctgan_result", metadata=metadata)
synthetic_data = synthesizer.generate(
    data=original_data,
    n_samples=original_data.shape[0],
    seed=4,
    fit_params={"epochs": 200, "verbose": False, "cuda": True},
    output_filename="synthetic_data_ctgan.csv"
)
```

### 3. TVAE

```python
import pandas as pd
from synomicsbench.synthesizer.TVAEsynthesizer import TVAEsynthesizer

synthesizer = TVAEsynthesizer(output_path=f"tvae_result", metadata=metadata)

synthetic_data = synthesizer.generate(
    data=original_data,
    n_samples=original_data.shape[0],
    seed=42,
    fit_params={"epochs": 500, "verbose": False, "cuda": True},
    output_filename="synthetic_data_tvae.csv"
)
```

### 4. Synthpop

> [!NOTE] 
> Synthpop requires R installation. You can install R from [CRAN](https://cran.r-project.org/). If you don't have R, you can try the [apptainer image](../getting-started/index.md).

```python
import pandas as pd
import numpy as np
from synomicsbench.synthesizer.Synthpopsynthesizer import SynthpopSynthesizer

# Prepare categorical features
grouped_metadata = MetaData.grouping_features_astype(original_data, metadata)
categorical_features = grouped_metadata.get("ordinal_categorical") + \
                       grouped_metadata.get("dummy_categorical") + \
  

# Load and configure predictor matrix for high-dimensional data
predictor_matrix = np.load("synthpop/predictor_matrix.npy")
predictor_df = pd.DataFrame(predictor_matrix, index=original_data.columns, columns=original_data.columns)

synth = SynthpopSynthesizer(output_path=f"synthpop_result", metadata=metadata)
synthetic_data = synth.generate(
    data=original_data, 
    seed=42, 
    n_samples=original_data.shape[0], 
    sample_params={
        "discrete_columns": categorical_features,
        "method": "cart",
        "predictor_matrix": predictor_df
    }, 
    output_filename="synthpop_synthetic_data.csv"
)
```

### 5. TabDiff

```python
from synomicsbench.synthesizer.TabDiffsynthesizer import TabDiffsynthesizer

synthesizer = TabDiffsynthesizer(output_path="tabdiff_result", metadata=metadata)
synthetic_data = synthesizer.generate(
    data=original_data,
    data_ids=list(original_data.index),
    n_samples=original_data.shape[0],
    seed=42,
    fit_params={
        "epochs": 3000,            # TabDiff default: 8000
        "cuda": True,
    },
    output_filename="synthetic_data_tabdiff.csv",
)
```

Every other hyperparameter is read from TabDiff's own `tabdiff_configs.toml`. Any of them can be changed through `config_overrides`, which mirrors the TOML nesting. TabDiff's periodic evaluation (a checkpoint and a sampled cohort every `check_val_every` epochs) is off by default, since its metrics are not used here; `periodic_eval=True` turns it back on. The per-epoch training curve is written to `train_log.csv` in `output_path`.

For runs longer than one cluster job, `checkpoint_every` saves the full training state to `resume.pt`, and `deadline` (a Unix time) stops training safely before the walltime, raising `TrainingPaused`. Calling `generate` again with the same arguments and `output_path` resumes from `resume.pt`.

### 6. Avatars

> [!NOTE] 
> Avatars requires a proprietary Octopize license. The example below highlights the specialized adaptations (data block chunking and feature clustering) used in SynOmicsBench to handle high-dimensional omic data over the API.

```python
import pandas as pd
import json
from avatars.manager import Manager
from avatars.models import JobKind

# Authenticate with the Avatars API
manager = Manager(base_url="https://www.octopize.app/api")
manager.authenticate("user@company.com", "password", should_verify_compatibility=False)

# Load clustered features optimized for high-dimensional data
with open("avatars/cluster_final.json", "r") as f:
    cluster_features = json.load(f)

k = 10
seed = 42

# Process data iteratively in partitioned blocks
for i in range(len(cluster_features)):
    data_clean = pd.read_csv(f"avatars/original_blocks/original_block_{i}.csv").drop(columns=["Patient_ID"])
    
    table_name = f"block_{i}"
    runner = manager.create_runner(f"Job_Block_{i}", seed=seed)
    runner.add_table(table_name, data_clean)
    runner.set_parameters(table_name, k=k)
    
    # Run the synthesis job
    runner.run(jobs_to_run=[JobKind.standard])
    
    # Retrieve and save the synthetic data block
    synthetic_df = runner.sensitive_unshuffled(table_name)
    synthetic_df.to_csv(f"synthetic_block_{i}.csv", index=False)

#Once all blocks are generated, concatenate them to form the final synthetic dataset
concat_syns = []

for i in range(0, len(cluster_features)):
    block = pd.read_csv(f"synthetic_block_{i}.csv", index_col =False)
    concat_syns.append(block)

synthetic_data = pd.concat(concat_syns, axis = 1)
```
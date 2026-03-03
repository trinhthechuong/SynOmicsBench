You are responsible for restructuring and refining the **SynOmicBench Documentation Website**.
This is a documentation redesign and structuring task. Follow all structural, formatting, and content instructions exactly as specified.

Do NOT remove or modify any file paths. Claude will operate directly on the specified directories.

---

# 1. GLOBAL STRUCTURE REQUIREMENTS (MANDATORY)

## Navigation Tabs

Remove all framework-specific tabs.

The documentation must contain the following **main tabs in this exact order**:

1. HOME
2. GETTING STARTED
3. PREPROCESSING DATA
4. GENERATE SYNTHETIC DATA
5. EVALUATION
6. API

---

## Global Design Rules

* Primary color: `#FFE4E1`
* No icons anywhere in the documentation
* Figure captions:

  * Must ALWAYS appear below figures
  * Insert a blank line before the caption
* Table captions:

  * Must ALWAYS appear above tables

These formatting rules are non-negotiable.

---

# 2. HOME PAGE

## Keep

* The current structure is acceptable

## Modify

1. Add an **Abstract section**
2. Remove the **Key Findings section**
3. Follow the Introduction and first sections of the manuscript markdown files
4. Add Figure 1 (PDF file)
5. Add a new section: **Explore the Documentation**

Inside this section, add navigation blocks linking to:

* Getting Started
* Preprocessing Data
* Generate Synthetic Data
* Evaluation Results
* API

6. Add a **Citations section**

---

# 3. GETTING STARTED

## Installation Section

Provide two installation methods:

### A. From Source

* I will provide a `requirements.txt` file
* Document dependency installation process

### B. From Singularity

* Provide Singularity usage instructions

---

## Quick Example Section

Include the following code exactly as shown (fix syntax errors but preserve logic):

```python
import pandas as pd
import numpy as np
from SynOmics.synthesizer.GaussianCopulasynthesizer import GaussianCopulasynthesizer
from SynOmics.processing.metadata import MetaData

original_data = pd.read_csv("your_original_data.csv")

ordinal_features = ["Mstage", "Tx_Start_ECOG",
                    "numPriorTherapies", "biopsyContext"]

metadata = MetaData.get_metadata(
    data=original_data,
    ordinal_features=ordinal_features
)

output_path = "./results"

synth = GaussianCopulasynthesizer(
    output_path=output_path,
    metadata=metadata
)

synthetic_data = synth.generate(
    data=original_data,
    n_samples=original_data.shape[0],
    output_filename="synthetic_data.csv",
)

from SynOmics.metrics.fidelity.UnivariateSimilarity import UnivariateSimilarity

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

# 4. PREPROCESSING DATA

## Add Figure

Add the following pipeline figure:

/Users/thechuongtrinh/Workspace/SynOmicBench/manu_md/figures/processing_pipeline.pdf

Figure caption must appear below the figure.

---

## Include Pipeline Execution Code

Include the following script:

```python
import pandas as pd
from SynOmics.processing.pipeline import DataIntegrationPipeline

output_dir = "./integrationpipeline_output"

imputer = "mice"
imputer_params = {
    "iterations": 10,
    "n_estimators": 100,
    "random_state": 42
}

ordinal_cat_columns = [
    "MSKCC",
    "Number_of_Prior_Therapies",
    "ORR",
    "ExtremeResponder",
    "Benefit"
]

steps_config = {
    "remove_undefined": True,
    "remove_duplicates": True,
    "remove_overmissing_samples": True,
    "remove_low_expression_genes": True,
    "check_duplicate_genes": True,
    "mapping_genes": True,
    "feature_engineering": True,
    "integrate_data": True,
}

pipeline = DataIntegrationPipeline(
    output_dir=output_dir,
    logger="Integration_final"
)

results = pipeline.run_pipeline(
    clinical_data=clinical_data_1,
    transcriptomics_data=omics_data_t,
    clinical_id_column="RNA_ID",
    transcriptomics_id_column="Sample",
    integration_id_column="Patient_ID",
    steps_config=steps_config,
    overmissing_samples_threshold=50,
    overmissing_features_threshold=50,
    unique_threshold=10,
    scaler="minmax",
    ordinal_cat_columns=ordinal_cat_columns,
    imputer=imputer,
    imputer_params=imputer_params,
    low_expression_variance_threshold=0.0005,
    add_indicators=True,
    verbose=True,
)
```

---

# 5. GENERATE SYNTHETIC DATA

You will later receive the `.py` files used for SDG generation.
Integrate those scripts into the documentation.

Clearly state:

> All SDG methods are integrated from external libraries. We do not reimplement the core algorithms.

For each method, mention the official library and include the GitHub link:

* CTGAN — [https://github.com/sdv-dev/CTGAN](https://github.com/sdv-dev/CTGAN)
* TVAE — [https://github.com/sdv-dev/SDV](https://github.com/sdv-dev/SDV)
* Gaussian Copula — [https://github.com/sdv-dev/SDV](https://github.com/sdv-dev/SDV)
* Synthpop — [https://github.com/thomvolker/synthpop](https://github.com/thomvolker/synthpop)
* Avatars — [https://www.octopize.io/](https://www.octopize.io/)

---

## Benchmarking Description

Include this structured explanation:

* Five SDG methods were benchmarked:
  CTGAN, TVAE, Gaussian Copula, Synthpop, Avatars
* Applied across three cancer types
* Repeated 5 times with different seeds
* Total synthetic datasets generated: 90 (30 per cancer type)

---

## High-Dimensional Adaptations

Explain why naive fitting failed (high-dimensional and heterogeneous data).

Then describe adaptations:

### Gaussian Copula

* One-hot encoding for categorical features
* OrdinalEncoder for ordinal features
* Parallel univariate fitting using joblib
* Vectorized batch chunking
* Reverse one-hot decoding using highest probability
* Rounding ordinal synthetic values

### Avatars

* Proprietary (Octopize license required)
* Python API client used
* Split datasets into blocks < 4,000 records
* Upload and anonymize per block
* Merge synthetic blocks
* Feature clustering:

  * Spearman correlation (numerical)
  * Cramér’s V (categorical)
  * Distance matrix: d = 1 − |correlation|
  * Hierarchical clustering (average linkage)

### Synthpop

* Custom predictor matrix
* Association matrix threshold: d_ij ≤ 0.7
* Max 500 predictors per feature
* Graph-based ranking:

  * Degree centrality (primary)
  * Eigenvector centrality (tie-break)
* Lower-triangular predictor structure

Mention:

* Avatars adaptation: feature clustering
* Synthpop adaptation: predictor matrix optimization

---

# 6. EVALUATION

## Overview Page

* Show evaluation dimensions as clickable tabs
* Do NOT show key findings
* Remove computational resources section
* Bayesian Comparison Framework

---

## Broad Utility Reference Folder

/Users/thechuongtrinh/Workspace/SynOmicBench/Manuscripts/{cancer}/BroadUtility

## Narrow Utility Reference Folder

/Users/thechuongtrinh/Workspace/SynOmicBench/Manuscripts/{cancer}/NarrowUtility

---

## Dimension-Specific References

Univariate:
/Users/thechuongtrinh/Workspace/SynOmicBench/Manuscripts/ccRCC/BroadUtility/UniSimi_Transcriptome.ipynb

Bivariate:
/Users/thechuongtrinh/Workspace/SynOmicBench/Manuscripts/ccRCC/BroadUtility/PairwiseTranscriptomics.py

DGE:
/Users/thechuongtrinh/Workspace/SynOmicBench/Manuscripts/Melanoma/NarrowUtility/DGE/GCS_analysis.ipynb
Show scatter plots:
/Users/thechuongtrinh/Workspace/SynOmicBench/Manuscripts/Melanoma/NarrowUtility/DGE/GCS/Seed_42.pdf

GSEA:
/Users/thechuongtrinh/Workspace/SynOmicBench/Manuscripts/Melanoma/NarrowUtility/GSEA/PCS_analysis.ipynb
Show scatter plots:
/Users/thechuongtrinh/Workspace/SynOmicBench/Manuscripts/Melanoma/NarrowUtility/GSEA/PCS/Seed_42.pdf

ssGSEA:
/Users/thechuongtrinh/Workspace/SynOmicBench/Manuscripts/Melanoma/NarrowUtility/ssGSEA/ssGSEA_KS.ipynb
Visualization:
/Users/thechuongtrinh/Workspace/SynOmicBench/Manuscripts/FiguressGSEA/Figure6a_KSC_ssGSEA.ipynb

Cell Type Deconvolution:
/Users/thechuongtrinh/Workspace/SynOmicBench/Manuscripts/Melanoma/NarrowUtility/CellDecovo/AitchisonDistance_final.ipynb

Survival Analysis:
/Users/thechuongtrinh/Workspace/SynOmicBench/Manuscripts/Melanoma/NarrowUtility/SA/SurvivalAnalysis.ipynb

---

## Privacy

* Introduce three risks:

  * Singling-out
  * Linkability
  * Inference
* Mention that Annonymeter framework was used
* Provide code examples from:
  /Users/thechuongtrinh/Workspace/SynOmicBench/Manuscripts/{cancer}/Privacy
* Show current visualizations for each risk

---

## Meta-Ranking

Use code in:
/Users/thechuongtrinh/Workspace/SynOmicBench/Manuscripts/MetaScore

Follow description from Methods section.

---

# 7. API

* Show docstrings in standard documentation format
* Follow conventional API reference style

---

Ensure:

* Clear hierarchy
* Consistent formatting
* Professional scientific tone
* Strict compliance with directory paths
* No icons
* Correct caption placement

---
# Privacy Assessment

Privacy evaluation quantifies the risk that synthetic data may inadvertently expose information about individuals in the original dataset. Following the European Data Protection Board (EDPB) framework, we assess three independent privacy risks using the Anonymeter library: **singling out**, **linkability**, and **inference**.

---

## Singling Out Risk

Singling out measures the ability to isolate a specific individual in the dataset using unique predicates derived from synthetic data. Two attack modes are evaluated:

- **Univariate**: predicates from single features
- **Multivariate**: predicates from multiple attribute combinations.

---

```python
from SynOmics.metrics.privacy.singling_out import (
    eval_singling_out_univariate,
    eval_singling_out_multivariate,
)
from SynOmics.processing.postprocessing import post_masking
import pandas as pd

# Load and preprocess data
original = pd.read_csv("original_data.csv")

syn = pd.read_csv("synthetic_data.csv")

# Univariate singling-out
uni_results = eval_singling_out_univariate(
    ori=original,
    syns={"Gaussian Copula": syn},
    n_attacks=10_000,
    proportions=[0.25, 0.50, 0.75, 1.0], # 25%, 50%, 75%, 100% of attributes
    seed=42,
)

# Print risk at each proportion
for evaluator in uni_results["Gaussian Copula"]:
    print(f"Risk: {evaluator.risk()}")
```

---

## Linkability Risk

Linkability assesses whether an attacker can use synthetic data to connect disjoint attribute sets (clinical features and gene expression) belonging to the same individual, using Gower-distance nearest neighbors.

```python
from SynOmics.metrics.privacy.linkability import eval_linkability_genes_clinical

# Example: define clinical and transcriptomic column indices or names
clinical_features = [0, 1, 2, 3]  # or column names: ["age", "sex", "stage", "grade"]
gene_features = list(range(4, ori.shape[1]))  # or column names: ["GeneA", "GeneB", ...]

# Link gene expression to clinical attributes
link_results = eval_linkability_genes_clinical(
    ori=ori,
    syns={"Gaussian Copula": syn},
    clinical_cols=clinical_features,
    transcriptomic_cols=gene_features,
    n_neighbors=1,
    proportions=[0.25, 0.50, 0.75, 1.0],  # 25%, 50%, 75%, 100% of gene features
    seed=42,
)

for evaluator in link_results["Gaussian Copula"]:
    print(f"Linkability risk: {evaluator.risk()}")
```

---

## Inference Risk

Inference quantifies the ability to deduce sensitive clinical attributes from auxiliary gene expression features using k-nearest neighbor prediction.

```python
from SynOmics.metrics.privacy.inference import eval_inference_genes_clinical

# Example: define clinical and transcriptomic column indices or names
clinical_features = [0, 1, 2, 3]  # or column names: ["age", "sex", "stage", "grade"]
gene_features = list(range(4, ori.shape[1]))  # or column names: ["GeneA", "GeneB", ...]

# Evaluate inference risk for each clinical variable
inf_results = eval_inference_genes_clinical(
    ori=ori,
    syns={"Gaussian Copula": syn},
    clinical_cols=clinical_features,
    transcriptomic_cols=gene_features,
)

for secret_name, result in inf_results["Gaussian Copula"]:
    if isinstance(result, dict):
        print(f"{secret_name}: ERROR - {result['error']}")
    else:
        print(f"{secret_name}: risk = {result.risk().value:.4f}")
```

---

## Overall Privacy Score

For each attack configuration $c$, the effective risk accounts for failed attacks:

$$R(c) = \max\bigl(R_\text{attack}(c),\; R_\text{naive}(c)\bigr)$$

For each privacy category $m$, the risk is averaged over all configurations:

$$\bar{R}_m = \frac{1}{|C_m|}\sum_{c \in C_m} R_m(c)$$

The overall privacy risk aggregates four categories (univariate singling-out, multivariate singling-out, linkability, inference):

$$R_\text{overall} = \frac{1}{4}\sum_{m=1}^{4} \bar{R}_m$$

$$\textbf{Privacy Score} = 1 - R_\text{overall}$$

Higher values indicate stronger privacy preservation.

Example notebooks:

-   [Overall Privacy Score](../assets/examples/OveralScore_Bayesian.ipynb) for a complete example of privacy overall score evaluation.

# Single-sample Gene Set Enrichment Analysis (ssGSEA)

ssGSEA calculates pathway enrichment scores for each individual sample, enabling per-sample assessment of biological pathway activity. In synthetic data evaluation, preserving the distribution of these enrichment scores tests whether generation methods capture the complex correlation structures underlying individual sample heterogeneity.

## KS-Complement Score

Preservation is measured using the KS-Complement score, which quantifies how well the distribution of Normalized Enrichment Scores (NES) is preserved across all 50 Hallmark pathways:

$$\text{KSComplement}_p = 1 - \text{KS}\!\bigl(\text{CDF}(\text{NES}_p^{\text{original}}),\;\text{CDF}(\text{NES}_p^{\text{synthetic}})\bigr)$$

The overall performance for a given method is the mean KS-Complement score across all pathways.

## Code Example

The ssGSEA evaluation reuses the `UnivariateSimilarity` class from `synomicsbench.metrics.fidelity` to compare NES distributions pathway-by-pathway:

```python
from synomicsbench.metrics.fidelity.UnivariateSimilarity import UnivariateSimilarity
from synomicsbench.processing.metadata import MetaData
import pandas as pd

# Load ssGSEA NES matrices (rows = samples, columns = pathways)
ori_ssgsea = pd.read_csv("ssGSEA_Origin.csv")
df_pivot_ori = ori_ssgsea.pivot(index="Name", columns="Term", values="NES")

syn_ssgsea = pd.read_csv("ssGSEA_gaussiancopula_0.csv")
df_pivot_syn = syn_ssgsea.pivot(index="Name", columns="Term", values="NES")

# Auto-detect metadata (all pathways are numerical)
metadata = MetaData.get_metadata(
    data=df_pivot_ori,
    threshold_unique_values=10,
    ordinal_features=None
)

# Compute KS-Complement scores across all pathways
uni = UnivariateSimilarity(output_dir="results/ssgsea")
scores = uni.get_univariate_score(
    original_data=df_pivot_ori,
    synthetic_data=df_pivot_syn,
    metadata=metadata
)
detail_df = uni.get_detail_df()

print(f"Mean KS-Complement Score: {scores:.4f}")
```

The `df_pivot_ori` and `df_pivot_syn` objects are DataFrames where rows represent samples and columns correspond to Hallmark pathways:

| Patient | HALLMARK_ADIPOGENESIS | HALLMARK_ALLOGRAFT_REJECTION | HALLMARK_ANDROGEN_RESPONSE |
| :--- | :---: | :---: | :---: |
| **Patient1** | 0.3660 | 0.1872 | 0.3924 |
| **Patient2** | 0.3632 | 0.2673 | 0.4165 |
| **Patient3** | 0.4251 | 0.2897 | 0.4295 |
| **Patient4** | 0.3856 | 0.2036 | 0.4002 |
| **Patient5** | 0.3489 | 0.3721 | 0.3289 |
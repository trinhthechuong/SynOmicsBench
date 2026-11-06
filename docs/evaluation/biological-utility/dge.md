# Differential Gene Expression (DGE)

DGE analysis identifies genes with statistically significant expression changes between biological conditions. SynOmicsBench compares the DGE results of the original and synthetic data on two levels: whether the synthetic data recover the same differentially expressed genes (DEGs) with the same direction (**F1-GCS**), and whether the effect sizes of the original DEGs are preserved (**effect-size calibration**).

## Gene Concordance Score (F1-GCS)

### Step 1: Rank Score Calculation

Each gene $i$ is assigned a rank score combining effect size and significance:

$$\text{RS}_i = \text{sign}(\log_2\text{FC}_i) \times \bigl(-\log_{10}(s_i)\bigr)$$

where $s_i$ is the significance value of the gene (column `sig_col`: nominal P-value or FDR Q-value, as the user decides), clipped at 0.001.

### Step 2: Concordance Zone Identification

A significance boundary is defined at $s_{\text{thr}} = -\log_{10}(\alpha)$, with $\alpha$ = `sig_thr` (default 0.05). In the $\text{RS}_\text{original}$ vs $\text{RS}_\text{synthetic}$ plane, the genes significant in both datasets with the same direction (zones 3 & 4) are the concordant DEGs, counted as $N_\text{sig}$.

### Step 3: Recall, Precision and F1-score

$$\text{Recall} = \frac{N_\text{sig}}{N_\text{sig}^\text{original}}, \qquad \text{Precision} = \frac{N_\text{sig}}{N_\text{sig}^\text{synthetic}}, \qquad \text{F1-GCS} = \frac{2 \cdot \text{Precision} \cdot \text{Recall}}{\text{Precision} + \text{Recall}}$$

Recall is the fraction of the original DEGs recovered with the same direction; precision the fraction of the synthetic DEGs that are concordant original DEGs. When the synthetic data have no DEG, precision is undefined (NaN) and F1-GCS is 0; F1-GCS is 0 whenever no gene is concordant.

## Effect-size calibration

On the genes significant in the original data, the synthetic Log2FC is regressed on the original Log2FC:

- **Slope** (OLS): 1 means effect sizes are preserved, below 1 attenuated, above 1 inflated;
- **Slope_robust** (Theil–Sen): resistant to the extreme synthetic Log2FC some generators produce;
- **Pearson**: how tightly the genes follow the regression line;
- **SignConcordance**: fraction of the original DEGs whose synthetic Log2FC has the same sign (chance level 0.5). Genes with a zero Log2FC have no sign and are left out.

Genes with a non-finite Log2FC are dropped; slope and correlation need at least 3 genes.

## Code Example

```python
import pandas as pd
from synomicsbench.metrics.narrow_utility.DGE import GCSAnalyzer

original_dge = pd.read_csv("original_dge_path.csv")
synthetic_dge = pd.read_csv("synthetic_dge_path.csv")

analyzer = GCSAnalyzer(
    term_col="Gene",
    nes_col="Log2FC",
    sig_col="P_value",   # or "Q_value"
    sig_thr=0.05,
)

# One metric -> float
f1 = analyzer.compute_metrics(original_dge, synthetic_dge, metrics="F1")

# Several metrics -> dict (metrics=None returns all of them)
scores = analyzer.compute_metrics(
    original_dge, synthetic_dge,
    metrics=["Recall", "Precision", "F1", "Slope", "Pearson", "SignConcordance"],
)
```

Available metrics: `Recall`, `Precision`, `F1`, `Slope`, `Slope_robust`, `Pearson`, `SignConcordance`.

To compare several synthetic datasets at once:

```python
dataset_dict = {
    "Avatars K5": "DGE/avatarsk5_0.csv",
    "CTGAN": "DGE/ctgan_0.csv",
    "Gaussian Copula": "DGE/gaussiancopula_0.csv",
    "Synthpop": "DGE/synthpop_0.csv",
    "TVAE": "DGE/tvae_0.csv",
    "Diffusion": "DGE/tabdiff_0.csv",
}

table = analyzer.compute_metrics_datasets("DGE/origin.csv", dataset_dict)
# one row per dataset, one column per metric
```

## Scatter Plot Visualization

### Concordance zones

The rank-score plot shows the concordance zones of every gene; recall, precision and F1-GCS are given in each panel:

```python
fig, f1_dict = analyzer.plot_gcs_datasets(
    ori_data="DGE/origin.csv",
    dataset_dict=dataset_dict,
    figsize=(18, 10),
)
fig.savefig("dge_gcs_scatter.png", dpi=300, bbox_inches="tight")
```

![DGE GCS Scatter Plots](../../assets/figures/melanoma_dge_gcs.png)

*Scatter plots of gene rank scores (Original vs. Synthetic) for each SDG method in the Melanoma cohort. Points in colored zones indicate concordant genes.*

### Effect-size calibration

The calibration plot shows the synthetic versus original Log2FC of the original DEGs, with the identity line, the OLS fit and, in each panel, the slope, Pearson R and sign concordance. Groups of genes can be highlighted:

```python
fig, calibration = analyzer.plot_calibration_scatter(
    ori_data="DGE/origin.csv",
    dataset_dict=dataset_dict,
    highlight={
        "MHC-I": ["HLA-A", "HLA-B", "HLA-C", "B2M"],
        "MHC-II": ["HLA-DRA", "HLA-DRB1", "HLA-DPA1"],
    },
)
fig.savefig("dge_calibration_scatter.png", dpi=300, bbox_inches="tight")
```

`calibration` is a table with the slope, intercept, Theil–Sen slope, Pearson correlation, sign concordance (with its binomial test P-value) and number of genes of each dataset.

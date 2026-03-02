# Gene Set Enrichment Analysis (GSEA)

Gene Set Enrichment Analysis (GSEA) is a powerful tool for identifying biological processes, pathways, or gene sets that are coordinately regulated in response to a biological stimulus or condition. Unlike Differential Gene Expression (DGE) analysis, which focuses on individual genes, GSEA considers entire functional units of biology, making it more robust to individual gene variability and more informative about the biological mechanism.

## Overview

In SynOmicBench, GSEA preservation is a key "narrow utility" metric. It assesses whether synthetic data can replicate the higher-level biological signals and pathway-level regulatory structures present in the original dataset. Evaluating GSEA in synthetic data is inherently more challenging than DGE because it depends on the complex, multivariate correlation structure of thousands of genes.

The benchmark compares the enrichment results (e.g., Normalized Enrichment Scores, NES) between real and synthetic data, ensuring that biological "storylines" remain intact for researchers working with synthetic data.

## Methodology

The evaluation of GSEA in SynOmicBench follows a rigorous pipeline:

1.  **Selection of Biological Contrast**: Identical to the DGE evaluation, a biological comparison of interest is defined (e.g., immunotherapy treated vs. naive patients in the Melanoma cohort).
2.  **GSEA Computation**: Analysis is performed using standard packages like **fgsea**, with genes ranked by their differential expression signal (e.g., Wald statistic or Log2FC).
3.  **Pathway Concordance Score (PCS)**: SynOmicBench introduces the PCS to quantify the agreement between real and synthetic GSEA results. The PCS follows a protocol analogous to the Gene Conservation Score (GCS) used in DGE evaluation, where each pathway is assigned a rank score by integrating the sign of the normalized enrichment score (NES), reflecting regulation direction, together with the Q value (Benjamini-Hochberg adjustment for false discovery rate correction) to capture statistical significance. Higher PCS values indicate a greater proportion of pathways in synthetic data that preserve both the directionality and the significance observed in the original dataset.
    *   **Rank Score Calculation**: For each pathway, a rank score is calculated:
        $$RankScore = sign(NES) \times -\log_{10}(Q\text{-value})$$
    *   **Alignment**: Original and synthetic results are matched by pathway names (inner join).
    *   **PCS Formula**: The PCS measures the proportion of concordant pathways, weighted by significance:
        $$PCS = \frac{N_{sign} + w \times N_{non\text{-}sign}}{M}$$
        Where $N_{sign}$ is the number of concordant significant pathways, $N_{non\text{-}sign}$ is the number of concordant non-significant pathways, $w$ is a weight factor (typically 0.5), and $M$ is a normalization constant based on the original significant pathways. Pathways in the Upper Right (UR) and Lower Left (LL) quadrants are concordant signals where the two datasets agree on the direction of regulation and the significance.
4.  **Visualization**: Scatter plots of PCS results are generated, identifying concordant and discordant pathways across different significance zones.

## Benchmark Results

Evaluation across multiple cohorts (ccRCC, Melanoma, NSCLC) demonstrates that preserving pathway biology requires more than just statistical fidelity. According to the PCS scores, different SDG approaches yielded competing best methodologies for different cancer types: TVAE for Melanoma, Avatars K10 for ccRCC, and Gaussian Copula for NSCLC.

![GSEA Benchmark Results](../../assets/figures/narrow-utility-gsea.png)

*Figure 5: Evaluation of Gene Set Enrichment Analysis preservation. The Pathway Concordance Score (PCS) measures the agreement between original and synthetic enrichment results.*

### Directional Agreement Patterns

Beyond global concordance metrics, examination of cancer-relevant pathways reveals method-specific patterns in preserving biological signatures.

**Melanoma immune pathways:** In the original Melanoma cohort, five immune-related pathways (IFN-γ response, Allograft rejection, Complement, Inflammatory response, and IL6-JAK-STAT3 signaling) were enriched in responders, with no pathways enriched in progressors. These biological signatures were largely recovered by Avatars (K5/K10), Gaussian Copula, Synthpop, and TVAE, but not by CTGAN. Importantly, robust recovery across random seed replicates was only observed for Avatars K10, Gaussian Copula, Synthpop, and TVAE.

**NSCLC pathway patterns:** Both responder-associated pathways (IFN-γ response, Allograft rejection, DNA repair) and non-responder associated pathways (EMT, WNT β-catenin, TGF-β signaling) were recapitulated with varying degrees of robustness. TVAE demonstrated directional agreement across all these pathways in at least three out of five replicates. While Gaussian Copula and Synthpop showed consistent alignment with responder-associated pathways, Avatars (K5/K10) exhibited more robust agreement across replicates for non-responder associated pathways.

### Biomarker Recovery: Del9p21.3 Deletion in ccRCC

To assess biomarker recovery, GSEA was performed comparing 9p21.3-deleted and wild-type tumors in the ccRCC cohort. In the original data, 9p21.3 loss was associated with increased EMT, mTORC1 signaling, angiogenesis, hypoxia, and glycolysis, alongside decreased oxidative phosphorylation, fatty acid metabolism, and TGF-β signaling.

Synthetic datasets displayed considerable variability across replicates. Avatars (K5/K10) and the Gaussian Copula reproducibly recapitulated downregulated pathways, in particular fatty acid metabolism and oxidative phosphorylation. However, the retracing of the upregulated pathways was less strong, with EMT being the only signal that was consistently detected in all methods. Gaussian Copula had the best stability for all the random seeds, including one replicate that was almost identical to the original full pathway pattern.

### Treatment-stratified Analysis: IFN Response in Melanoma

In the original study of Melanoma by Liu et al., significant enrichment of IFN-γ and IFN-α response pathways was reported in ipilimumab-treated responders to anti-PD1 therapy (FDR Q < 0.0001 for both), while no such enrichment was observed in the ipilimumab-naive subgroup (FDR Q = 0.13 and Q = 0.996, respectively).

Gaussian Copula successfully reproduced this differential enrichment pattern in both interferon pathways:

- **IFN-γ pathway**: Ipilimumab-treated FDR Q = 0.0012, Ipilimumab-naive FDR Q = 0.997
- **IFN-α pathway**: Ipilimumab-treated FDR Q = 0.0012, Ipilimumab-naive FDR Q = 1.0

Avatars K10 and Synthpop partially captured these signals, each recovering only one pathway. Moreover, Gaussian Copula showed superior robustness across replicates, with three out of five runs reproducing the subgroup effect, whereas Synthpop and Avatars K10 failed to demonstrate consistent recovery.

### Reproducibility Assessment

Although some SDG approaches recovered pathway-level signals in single simulated datasets, the level of reproducibility over random seed replicates varied considerably. Methods like Avatars (K5/K10) and Gaussian Copula were in general more stable when retaining biologically meaningful pathways, while others showed dramatic variability in performance across runs. These results indicate that single run assessments may overestimate the quality of synthetic data and the biological relevance of transcriptomic synthetic data should be evaluated for replicability.

## References

**Analysis notebook:** `Manuscripts/Melanoma/NarrowUtility/GSEA/PCS_analysis.ipynb`

**Source code:** `src/SynOmics/metrics/narrow_utility/GSEA.py`

## Observations

- Different synthesis methods achieved optimal PCS performance for different cancer types: TVAE for Melanoma, Avatars K10 for ccRCC, and Gaussian Copula for NSCLC
- Avatars (K5/K10) and Gaussian Copula demonstrated superior stability in preserving pathway-level biological signals across random seed replicates
- Complex biomarker patterns (Del9p21.3-associated pathways in ccRCC, treatment-stratified IFN responses in Melanoma) were reproducibly recovered by Gaussian Copula with highest cross-replicate stability
- Single-run assessments may overestimate synthetic data quality; replicability evaluation across multiple random seeds is critical for assessing biological relevance
- Methods focusing on univariate distributions may preserve individual gene signals but show variable performance on pathway-level coordination
## Code Example

The `PCSAnalyzer` class in SynOmicBench provides a streamlined interface for computing the Pathway Concordance Score.

```python
import pandas as pd
from SynOmics.metrics.narrow_utility.GSEA import PCSAnalyzer

# Load GSEA results (e.g., output from fgsea)
gsea_real = pd.read_csv("gsea_results_real.csv")
gsea_syn_path = "gsea_results_synthetic.csv"

# Initialize the analyzer
# term_col: pathway names, nes_col: NES, q_col: FDR q-value
analyzer = PCSAnalyzer(
    term_col="Term", 
    nes_col="NES", 
    q_col="FDR q-val", 
    q_thr=0.05, 
    w=0.5
)

# Process the results
x, y, result = analyzer.process_single_gsea_result(gsea_real, gsea_syn_path)

print(f"Pathway Concordance Score (PCS): {result.pcs:.3f}")
print(f"Significant concordant pathways: {result.n_sign}")
print(f"Aligned pathway size: {result.aligned_size}")
```

This analysis ensures that synthetic data remains biologically valid at a systems level, allowing researchers to explore pathway-level hypotheses with the same confidence they would have with the original data.

# Meta-Ranking

This page documents the overall performance ranking of synthetic data generation (SDG) methods evaluated in SynOmicBench. We employ a rank-derived meta-score aggregation approach that integrates results across all evaluation dimensions—broad utility, narrow utility, and privacy—to identify which methods provide the most balanced performance for high-dimensional cancer omics data.

## Methodology

We calculated the rank-derived meta-score for each SDG method following the protocol of Yan et al.[^1] These meta-scores provide a comprehensive ranking that integrates all metrics from three evaluation pillars: **broad utility**, **narrow utility**, and **privacy**. The rank-derived approach transforms raw metric values into ranks within each evaluation dimension, then computes a weighted composite score. Lower meta-scores indicate better overall performance across the evaluation framework.

[^1]: Yan, A., et al. (2022). Benchmarking synthetic data generation methods. *arXiv preprint arXiv:2203.14590*.

The meta-score calculation is implemented in the following Jupyter notebooks:

- **Aggregated analysis**: `Manuscripts/MetaScore/MetaScore_all.ipynb` — computes meta-scores across all three cancer datasets (ccRCC, melanoma, NSCLC)
- **Cancer-specific analyses**:
    - `Manuscripts/MetaScore/MetaScore_ccRCC.ipynb` — clear cell renal cell carcinoma
    - `Manuscripts/MetaScore/MetaScore_Melanoma.ipynb` — skin cutaneous melanoma
    - `Manuscripts/MetaScore/MetaScore_NSCLC.ipynb` — non-small cell lung cancer

Each notebook applies the rank-derived meta-score protocol to evaluate the six SDG methods (Gaussian Copula, CTGAN, TVAE, Synthpop, Avatars K5, Avatars K10) across all evaluation metrics collected during the benchmarking experiments.

## Results

Figure 10 presents a comparison of rank-derived meta-scores for SDG methods, evaluated across individual cancer types (Figure 10a), aggregated across all three datasets (Figure 10b), and a pairwise correlation analysis of evaluation metrics (Figure 10c).

![Meta-Ranking Comparison](../assets/figures/meta-ranking.png)

Rank-derived meta-score comparison and metric correlation analysis of SDG methods. (a) Meta-score comparison within each cancer cohort. Stacked bar plots display the rank-derived meta-scores for each SDG method across ccRCC, melanoma, and NSCLC datasets. For each method, the total bar length represents the aggregated meta-score, computed by integrating three evaluation pillars: broad utility, narrow utility, and privacy. The three colored segments correspond to these pillars and indicate their respective contributions to the overall score. Because the metric is rank-derived, lower meta-scores indicate better overall performance. Gaussian Copula achieved the lowest (best) aggregated meta-score across cancer types, followed by Avatars (K5/K10). (b) Aggregated meta-score across all datasets. Stacked bar plots summarize rank-derived meta-scores across all three cancer datasets. Each bar aggregates the three dimensions (broad utility, narrow utility, and privacy), represented by distinct color segments, into a composite meta-score. Consistent with cancer-specific analyses, Gaussian Copula obtained the lowest (best) overall meta-score, followed by Avatars (K5 and K10). A utility-privacy trade-off is observed: CTGAN exhibited stronger privacy contributions, whereas Gaussian Copula and Avatars demonstrated stronger utility components but comparatively lower privacy contributions. (c) Pairwise correlation of evaluation metrics. Heatmap of Spearman correlation coefficients among all evaluation metrics across SDG methods and cancer datasets. Utility-related metrics demonstrate moderate to strong correlations, whereas privacy metrics show weak or negative correlations with most utility measures, reflecting a utility-privacy trade-off.

### Cancer-Specific Performance

As shown in Figure 10a, **Gaussian Copula** consistently achieved the lowest (best) meta-scores across all three cancer types (ccRCC, melanoma, NSCLC), demonstrating robust performance that is not overly sensitive to specific cancer-type characteristics. The two variations of **Avatars** (K5 and K10) occupied the second and third positions across cancer types, showing stable rankings with minor variation between datasets.

**CTGAN** and **TVAE**, the two deep learning-based methods, exhibited more variability across cancer types. Their performance ranking shifted between datasets, suggesting that GAN-based and VAE-based models may require more extensive hyperparameter tuning to adapt to different omics distributions in the high-dimensional, small-sample-size regime typical of clinical cancer cohorts.

**Synthpop** demonstrated moderate broad utility performance but was penalized heavily in the meta-score due to poor privacy performance, particularly regarding singling-out risk. This placed Synthpop in the penultimate position in the overall ranking.

### Aggregated Performance

Figure 10b summarizes the rank-derived meta-scores aggregated across all three cancer datasets. The overall ranking, from best (lowest meta-score) to worst (highest meta-score), is:

1. **Gaussian Copula** — achieved the lowest (best) overall meta-score
2. **Avatars K5** — second position with strong utility and moderate privacy
3. **Avatars K10** — third position, similar to K5 with slightly different utility-privacy balance
4. **CTGAN** — fourth position, notable for stronger privacy contributions but weaker utility
5. **Synthpop** — penultimate position due to poor privacy despite competitive broad utility
6. **TVAE** — lowest-ranked method with the highest (worst) meta-score

### Utility-Privacy Trade-Off

A clear utility-privacy trade-off emerged from the meta-ranking analysis. **CTGAN** obtained higher privacy scores (lower privacy risk contributions to the meta-score), whereas **Gaussian Copula** and **Avatars** (K5/K10) had comparatively lower privacy contributions but demonstrated substantially stronger performance in both broad and narrow utility dimensions.

This trade-off reflects a fundamental challenge in synthetic data generation: methods that preserve more statistical and biological fidelity to the original data tend to carry higher re-identification risks, while methods that introduce more noise or record-level perturbations achieve better privacy at the cost of utility.

## Metric Correlations

To better understand the relationships between evaluation dimensions, we calculated pairwise Spearman correlations between all metrics used in the benchmarking framework (Figure 10c). Several informative patterns emerged from this correlation analysis.

### Utility-Privacy Dichotomy

The utility-privacy trade-off is evident in the correlation structure: privacy metrics are weakly or negatively correlated with most utility-related measures. This confirms that improving utility and preserving privacy represent competing objectives in synthetic data generation, requiring careful balancing based on the intended use case.

### Pathway-Based Metrics: Population vs. Sample-Level

Interestingly, the two pathway-based scores—**GSEA** (Gene Set Enrichment Analysis) and **ssGSEA** (single-sample GSEA)—show very weak correlation despite both being pathway enrichment methods. This is because they belong to different families of metrics:

- **GSEA** is more correlated with **DGE** (Differential Gene Expression) and **survival analysis**, which represent transcriptional effects at the **population level**. GSEA identifies pathways that are differentially enriched between conditions across the entire cohort.
- **ssGSEA** has higher correlation with **UnivariateScore** and **cell deconvolution** metrics, capturing pathway enrichment at the level of **individual samples**. This makes ssGSEA more sensitive to sample-specific biological signals.

This distinction reinforces the importance of including both population-level and sample-level evaluation metrics in the narrow utility pillar.

### Univariate vs. Bivariate Scores

The **univariate score** (marginal distribution similarity) is moderately correlated with the **bivariate score** (pairwise correlation preservation), suggesting that these metrics provide complementary, though not redundant, information. While the univariate score assesses how well each feature's distribution is preserved in isolation, the bivariate score captures the joint structure between feature pairs.

This moderate correlation implies that bivariate modeling captures additional discriminative structures that cannot be captured by univariate screening alone. Synthetic data that preserves marginal distributions may still fail to preserve complex correlation patterns, which are critical for downstream analyses like pathway enrichment and survival modeling.

### Ranking Consistency vs. Complementarity

Strong correlation between metrics indicates **ranking consistency**—different metrics tend to agree on which SDG methods perform better. Weak correlation highlights the **complementary nature** of metrics, meaning they discriminate model quality along different dimensions.[^1] The correlation heatmap in Figure 10c demonstrates that utility-related metrics show moderate to strong correlations (ranking consistency), while privacy metrics show weak or negative correlations with utility measures (complementarity and trade-off).

These results illustrate that for robust evaluation of synthetic data quality, it is essential to employ a **multi-dimensional evaluation framework** rather than rely on a single performance indicator. No single metric can fully capture the trade-offs and nuances of synthetic omics data generation.

## Observations

- **Gaussian Copula** emerged as the best-performing method overall, achieving the lowest meta-score across both cancer-specific and aggregated analyses. Its success is attributed to its ability to model complex correlation structures through multivariate normal transformations, which proves robust in the high-dimensional, small-sample-size regime typical of clinical cancer cohorts.
- **Avatars** (K5 and K10) occupied the second and third positions, demonstrating strong utility with moderate privacy performance. The record-level perturbation approach of Avatars provides a favorable balance between preserving biological signals and reducing re-identification risk.
- **CTGAN** exhibited a different performance profile: stronger privacy contributions but weaker utility compared to Gaussian Copula and Avatars. This suggests that GAN-based methods may introduce sufficient noise to improve privacy but at the cost of biological fidelity in the omics context.
- **Synthpop**, despite competitive performance in broad utility, was heavily penalized for poor privacy (high singling-out risk), resulting in a penultimate ranking. This highlights the importance of evaluating privacy alongside utility when selecting SDG methods for sensitive clinical data.
- **TVAE** ranked lowest overall, with the highest (worst) meta-score. Like CTGAN, it appears that VAE-based methods struggle in the high-dimensional, small-sample regime of cancer omics data without extensive hyperparameter tuning.
- The **utility-privacy trade-off** is a dominant theme: methods that excel in utility tend to have weaker privacy, and vice versa. Researchers must carefully weigh these competing objectives based on the intended application and regulatory requirements.
- **Metric correlations** reveal that a multi-dimensional evaluation framework is essential. Utility-related metrics show consistency in ranking (moderate to strong correlations), while privacy metrics provide complementary information (weak or negative correlations). Pathway-based metrics split into population-level (GSEA) and sample-level (ssGSEA) families, emphasizing the need for diverse narrow utility assessments.
- The moderate correlation between univariate and bivariate scores indicates that preserving marginal distributions is necessary but insufficient—joint correlation structure must also be maintained for downstream biological analyses to remain valid on synthetic data.

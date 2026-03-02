# Narrow Utility Evaluation

Narrow utility evaluates task-specific biological signal preservation in downstream analyses. While broad utility (statistical fidelity) ensures global data similarity, narrow utility assesses whether synthetic data maintains the biological relationships needed for real-world research applications. This evaluation spans five critical downstream analysis tasks commonly used in cancer omics research.

## Evaluation Tasks

- **[Differential Gene Expression (DGE)](dge.md)** — Preservation of log-fold changes and statistical significance in comparisons between cancer subtypes or phenotypes
- **[Gene Set Enrichment Analysis (GSEA)](gsea.md)** — Pathway-level signal recovery and enrichment agreement across biological functions
- **[Single-sample GSEA (ssGSEA)](ssgsea.md)** — Per-sample pathway activity scores for individual-level personalized analysis
- **[Cell Type Deconvolution](cell-deconvolution.md)** — Immune cell fraction estimation from bulk transcriptomics data consistency
- **[Survival Analysis](survival-analysis.md)** — Kaplan-Meier curves and Hazard Ratio preservation for clinical outcome prediction
# Benchmark Leaderboard

The ranking of the six SDG methods of SynOmicsBench, over the 90 synthetic datasets of the revised manuscript.

---

## Setting

- **Cohorts**: ccRCC, Melanoma and NSCLC; see [Biological Results](biological-results.md).
- **Methods**: [Avatars, CTGAN, Gaussian Copula, Synthpop, TVAE and TabDiff](../synthetic-data/index.md), five seeds each: 3 cohorts × 6 methods × 5 seeds = 90 synthetic datasets.
- **Metrics**: twelve metrics in three pillars.
    - Statistical fidelity: [univariate and bivariate similarity, network preservation](statistical-fidelity.md).
    - Biological utility: [F1-GCS](biological-utility/dge.md), [F1-PCS](biological-utility/gsea.md), [ssGSEA](biological-utility/ssgsea.md), [cell deconvolution](biological-utility/cell-deconvolution.md) and the [survival score](biological-utility/survival-analysis.md).
    - Privacy: the residual risks of univariate singling out, multivariate singling out, linkability and attribute inference ([Privacy](privacy.md)).
- **Meta-score**: on every metric, the 90 datasets are ranked together (rank 1 is the best). The rank-derived score of a method is the mean rank of its 15 datasets, a pillar score is the mean over the pillar's metrics, and the meta-score is the weighted sum of the three pillar scores. Lower is better ([how it is computed](autobenchmark.md#how-the-meta-score-is-computed)).

---

## Data-sharing scenarios

The relative importance of statistical fidelity, biological utility and privacy depends on the data-sharing context. Besides **equal weights** (1/3 each), the ranking is given for three scenarios.

**Controlled sharing within a research consortium** (biological utility: 0.5 > statistical fidelity: 0.3 > privacy: 0.2). Here access is governed by a data transfer agreement, so the legal framework carries most of the privacy burden. Synthetic data are valuable not only as a substitute for real data but as an early enabler: because each partner must first obtain its own institutional authorization, often a months-long process, a synthetic substrate can circulate in the meantime, allowing pipeline development, prototyping, and preliminary analyses to advance in parallel rather than wait. Biological utility is therefore prioritized, as the goal is faithful downstream discovery, followed by statistical fidelity as a prerequisite for that utility, and privacy.

**Public release for open challenges or hackathons** (privacy: 0.5 > biological utility: 0.3 > statistical fidelity: 0.2). When synthetic data are released openly to support community benchmarking of predictive models, such as competitions on treatment-response prediction, no governance layer restricts access, and the burden of protection shifts entirely onto the data themselves. Privacy is therefore weighted most heavily. Biological utility comes second, as the released data must retain enough transferable signal that models trained on them generalize to real patients, whereas statistical fidelity comes last.

**Method development and pipeline testing** (privacy: 0.5 > statistical fidelity: 0.3 > biological utility: 0.2). When synthetic data are used to build or stress-test analytical tools, such as normalization, imputation or batch-correction workflows, they are typically embedded in software packages, tutorials, and public code repositories, with no governance layer restricting access. Privacy is therefore weighted most heavily. Among the remaining pillars, statistical fidelity takes precedence, as the goal is not to recover biology but to reproduce the statistical structure of real transcriptomic data closely enough for the software to behave as it would in production: correct dimensionality, sparsity, value distributions, correlation structure, and missingness patterns. Biological utility is weighted lowest, as no biomarker or clinical signal needs to be preserved.

---

## Ranking and sensitivity to the pillar weights

The report below gives the ranking, the ranking under each scenario, and the weight triangle: move the pointer over the triangle, or use the sliders, to see how the ranking changes with the weights.

<iframe src="../../assets/reports/synomicsbench_leaderboard.html" title="SynOmicsBench leaderboard report" style="width:100%; height:1100px; border:1px solid var(--md-default-fg-color--lightest); border-radius:4px;" loading="lazy"></iframe>

[Open the full report](../assets/reports/synomicsbench_leaderboard.html){ .md-button }

---

## Privacy settings of the benchmark

The privacy metrics of the leaderboard follow the [adversary model](privacy.md#adversary-model) of the privacy page, with these settings:

| | ccRCC | Melanoma | NSCLC |
|---|---|---|---|
| Control cohort | IMmotion151 (n = 823) | Gide et al. (n = 91) | Jung et al. (n = 27) |
| Aligned columns | 6 clinical, 16,022 genes | 6 clinical, 15,556 genes | 4 clinical, 15,190 genes |
| Secrets of attribute inference | Age, Sex, MSKCC, ORR, PFS, PFS_CNSR | gender, BR, OS, dead, PFS, progressed | Patient_Age_at_Diagnosis, Patient_Sex, Harmonized_PFS_Months, Harmonized_PFS_Event |

- Each cohort is reduced to the features it shares with its control cohort, so that the original, synthetic and control records occupy one column space.
- Univariate singling out, linkability and attribute inference are evaluated at six levels of adversary knowledge, the clinical fields being known throughout: the FGES genes and random subsets of 5%, 25%, 50%, 75% and 100% of the genes (`proportions=(0.05, 0.25, 0.5, 0.75, 1.0)`, `gene_sets={"FGES": FGES_GMT}`, seed 42).
- Multivariate singling out combines 2, 3, 5, 7, 10, 20 and 50 attributes per predicate, drawn from all the aligned columns. Both singling-out attacks generate 10,000 predicates per evaluation.
- The risk of an attack is the mean residual risk over its evaluations: 4,590 evaluations in total.

---

To benchmark your own synthetic data, go to [Automatic Benchmark](autobenchmark.md); its example report runs the Melanoma cohort with these settings.

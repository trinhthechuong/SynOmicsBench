# Privacy Assessment

Privacy evaluation quantifies the risk that synthetic data may inadvertently expose information about individuals in the original dataset. Following the European Data Protection Board (EDPB) framework, we assess three independent privacy risks using the [Anonymeter](https://arxiv.org/abs/2211.10459) library: **singling out**, **linkability**, and **inference**.

---

## Residual risk with an external control cohort

An attack success rate alone cannot tell what an adversary learns about the patients of the cohort from what they would learn about *any* comparable patient. Every attack function therefore accepts an optional `control` dataset: patients from the same population that the generator never saw (e.g. an independent cohort treated in the same setting).

| | Reported risks |
|---|---|
| With `control` | **Residual risk** $R_\text{residual} = \dfrac{R_\text{attack} - R_\text{control}}{1 - R_\text{control}}$ (bounded below by 0), with the attack risk $R_\text{attack}$ and the control success rate $R_\text{control}$ |
| Without `control` | Attack risk $R_\text{attack}$ and the risk of a naive attacker guessing at random, $R_\text{naive}$; an attack with $R_\text{attack} \le R_\text{naive}$ has failed |

The control dataset must have the columns of the original data, with the same categories and value scales: reduce the original, synthetic and control datasets to the features they share first (e.g. map clinical fields and gene identifiers of the control cohort to those of the original). The record-level attacks (linkability, inference) attack $\min(n_\text{original}, n_\text{control})$ records, since Anonymeter attacks as many records in both datasets.

`privacy_risk_table` turns the output of any attack function into one row per evaluation: with a control dataset, the residual risk with its confidence interval, the attack risk and the control rate; without one, `R_attack` and `R_naive` with their confidence intervals. The table has the same columns for the four attacks; for inference, a `Secret` column gives the inferred clinical attribute. An example is given under [Singling Out Risk](#singling-out-risk).

---

## Adversary model

All attack scenarios follow the Anonymeter threat model: the synthetic dataset is assumed to have been publicly released, so the adversary has full access to it, whereas the fitted generative model is not released and cannot be accessed or queried. Target patients are drawn at random from the original cohort, so the reported risks reflect the overall privacy of the synthetic data rather than the risk for specific sub-populations or individuals. The three attacks differ in what the adversary is assumed to know beforehand.

- **Singling out** assumes no prior knowledge. The adversary uses only the released synthetic data to construct predicates, and the attack succeeds if a predicate isolates a unique record in the original dataset. A successful attack reveals that a patient with a given combination of attributes exists in the original data, without the adversary knowing anything about that patient in advance. Because it requires the least knowledge, it is the most broadly applicable threat.
- **Linkability** assumes an adversary holding two disjoint records about the same patient from separate sources, namely a clinical record and a molecular profile. The adversary seeks to determine, via the synthetic data, whether these records belong to the same individual. This corresponds to a cross-release scenario, relevant when a clinical registry and a molecular dataset are published independently.
- **Attribute inference** assumes an external adversary who holds a patient's molecular profile, for example from a public repository or a prior publication of the same trial, and attempts to infer sensitive clinical attributes of that patient, such as treatment response or survival.

Adversary knowledge is not a single assumption but a gradient, so the attacks can be run across this gradient rather than at a single arbitrary point. Univariate singling out, linkability and attribute inference take the same settings:

- `clinical_cols`: the clinical fields, assumed known throughout;
- `transcriptomic_cols`: the genes of the molecular profile (by default, every other column);
- `proportions`: random subsets of these genes, one level each. `(1.0,)`, the default, is the worst case in which the adversary holds the complete transcriptome profile; SynOmicsBench used `(0.05, 0.25, 0.5, 0.75, 1.0)`. The subsets are drawn with a fixed `seed`, so that all methods are attacked with the same genes;
- `gene_sets`: named gene panels added as further levels. `{"FGES": FGES_GMT}` is the level of an adversary with domain knowledge: the genes of the tumor microenvironment (TME)-related functional gene expression signatures (FGES) ([Bagaev et al., 2021](https://doi.org/10.1016/j.ccell.2021.04.014)), which belong to pathways and molecular signatures directly relevant to immune checkpoint blockade. The file is bundled with SynOmicsBench.

Each level returns one evaluation, gene sets first, then the fractions (for inference, one per level and secret). Multivariate singling out is analyzed along a separate axis, in which adversary knowledge is the width of the predicate the adversary can construct (`n_cols_list`), drawn from all the columns passed.

---

## Singling Out Risk

Singling out measures the ability to isolate a specific individual in the dataset using unique predicates derived from synthetic data. SynOmicsBench runs Anonymeter's singling-out evaluator in its polars implementation, the one used for the results of the manuscript: the pandas evaluator of Anonymeter is too slow on cohorts with tens of thousands of gene columns. Two attack modes are evaluated:

- **Univariate**: predicates from single features among the known columns;
- **Multivariate**: predicates combining `n_cols` features drawn from all the columns passed.

The example below is the singling-out attack of SynOmicsBench on the Melanoma cohort, with the Gide et al. cohort as control.

```python
import pandas as pd
from synomicsbench.metrics.privacy.knowledge import FGES_GMT
from synomicsbench.metrics.privacy.risk import privacy_risk_table
from synomicsbench.metrics.privacy.singling_out import (
    eval_singling_out_univariate,
    eval_singling_out_multivariate,
)

control = pd.read_csv("gide_control.csv", index_col=0)               # Gide et al., aligned to the cohort
original = pd.read_csv("original_data.csv", index_col=0)[control.columns]
syn = pd.read_csv("gaussiancopula_0.csv", index_col=0)[control.columns]

clinical_features = ["gender", "PFS", "progressed", "OS", "dead", "BR"]   # shared with the control
gene_features = [c for c in control.columns if c not in clinical_features]

uni_results = eval_singling_out_univariate(
    ori=original,
    syns={"Gaussian Copula": syn},
    n_attacks=10_000,
    clinical_cols=clinical_features,             # known at every level
    transcriptomic_cols=gene_features,           # genes of the molecular profile
    proportions=(0.05, 0.25, 0.5, 0.75, 1.0),    # random subsets of these genes, one level each
    gene_sets={"FGES": FGES_GMT},                # adversary with domain knowledge
    seed=42,                                     # random draws: gene subsets and attack
    control=control,
)

multi_results = eval_singling_out_multivariate(
    ori=original,
    syns={"Gaussian Copula": syn},
    n_cols_list=(2, 3, 5, 7, 10, 20, 50),        # predicate widths
    seed=42,
    control=control,
)

print(privacy_risk_table(uni_results, "SO_uni", configs=["FGES", "5%", "25%", "50%", "75%", "100%"]))
print(privacy_risk_table(multi_results, "SO_multi", configs=[2, 3, 5, 7, 10, 20, 50]))
```

The first table (univariate singling out, Melanoma, Gaussian Copula replicate 0):

```text
           Dataset  Attack Config  R_residual  R_residual_ci_low  R_residual_ci_high  R_attack  R_attack_ci_low  R_attack_ci_high  R_control
0  Gaussian Copula  SO_uni   FGES    0.002148           0.001033            0.003263  0.002791         0.001775          0.003807   0.000644
1  Gaussian Copula  SO_uni     5%    0.003924           0.002647            0.005202  0.004190         0.002939          0.005442   0.000267
2  Gaussian Copula  SO_uni    25%    0.002999           0.001793            0.004204  0.003491         0.002351          0.004631   0.000494
3  Gaussian Copula  SO_uni    50%    0.003549           0.002305            0.004793  0.003891         0.002686          0.005096   0.000343
4  Gaussian Copula  SO_uni    75%    0.002449           0.001387            0.003511  0.002791         0.001775          0.003807   0.000343
5  Gaussian Copula  SO_uni   100%    0.002849           0.001718            0.003980  0.003191         0.002102          0.004279   0.000343
```

---

## Linkability Risk

Linkability assesses whether an attacker can use synthetic data to connect disjoint attribute sets (clinical features and gene expression) belonging to the same individual, using Gower-distance nearest neighbors. The two records are the clinical columns and the genes of each level.

```python
from synomicsbench.metrics.privacy.linkability import eval_linkability_genes_clinical

link_results = eval_linkability_genes_clinical(
    ori=original,
    syns={"Gaussian Copula": syn},
    clinical_cols=clinical_features,             # first record
    transcriptomic_cols=gene_features,           # second record, at each level
    proportions=(0.05, 0.25, 0.5, 0.75, 1.0),
    gene_sets={"FGES": FGES_GMT},
    n_neighbors=1,
    seed=42,
    control=control,
)

print(privacy_risk_table(link_results, "Linkability", configs=["FGES", "5%", "25%", "50%", "75%", "100%"]))
```

---

## Inference Risk

Inference quantifies the ability to deduce sensitive clinical attributes from auxiliary gene expression features using k-nearest neighbor prediction. Each clinical feature is in turn the secret; the genes of each level are the auxiliary information:

```python
from synomicsbench.metrics.privacy.inference import eval_inference_genes_clinical

infer_results = eval_inference_genes_clinical(
    ori=original,
    syns={"Gaussian Copula": syn},
    clinical_cols=clinical_features,             # the secrets, inferred one at a time
    transcriptomic_cols=gene_features,           # auxiliary information, at each level
    proportions=(0.05, 0.25, 0.5, 0.75, 1.0),
    gene_sets={"FGES": FGES_GMT},
    seed=42,
    control=control,
)

print(privacy_risk_table(infer_results, "Inference"))   # Config: the level; Secret: the inferred column
```

Failed evaluations are returned as `(level, secret, {"error": ...})` and left out of the risk table.

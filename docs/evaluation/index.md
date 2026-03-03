# Evaluation Framework

SynOmicBench evaluates synthetic cancer omics data through a multidimensional lens, ensuring that generated datasets are not only statistically similar to the original but also biologically meaningful and safe for sharing. Our framework is built upon three fundamental pillars and uses a rigorous Bayesian comparison approach to rank generative methods.

---

## 📐 The Three Pillars of Evaluation

The trade-off between **biological utility** and **patient privacy** is the central challenge in synthetic data generation. SynOmicBench addresses this by categorizing metrics into three distinct pillars.

### 1. Broad Utility (Statistical Fidelity)
Broad utility assesses how well the synthetic data preserves the global statistical properties of the original dataset. This is the first line of evaluation for any synthetic data generation (SDG) method.

*   **Univariate Similarity**: Measures the preservation of marginal distributions for individual features (e.g., gene expression levels, clinical categories). We use metrics like the Kolmogorov-Smirnov test and Chi-squared test to quantify the similarity of shapes and frequencies.
*   **Bivariate Similarity**: Evaluates how well inter-variable relationships and correlation structures are maintained. This ensures that the complex co-expression patterns of genes and their associations with clinical traits remain intact.

Detailed metrics can be found in the [Broad Utility](broad-utility.md) section.

### 2. Narrow Utility (Biological Signal)
Narrow utility focuses on task-specific performance in clinically relevant downstream analyses. Statistical fidelity does not always guarantee that biological signals are preserved enough for scientific discovery.

*   **Differential Gene Expression (DGE)**: Comparison of log-fold changes and p-values between original and synthetic cohorts.
*   **Gene Set Enrichment (GSEA/ssGSEA)**: Validation that biological pathway activities and functional signatures are recoverable.
*   **Cell Deconvolution**: Consistency in estimating immune cell fractions from bulk transcriptomics.
*   **Survival Analysis**: Preservation of Kaplan-Meier survival curves and Hazard Ratios for clinical outcomes.
*   **Predictive Modeling**: Evaluation of how well models trained on synthetic data generalize to real-world test sets (Train Synthetic, Test Real - TSTR).

Explore these in the [Narrow Utility](narrow-utility/index.md) section.

### 3. Privacy Risk
Privacy evaluation quantifies the disclosure vulnerability of the synthetic data, aligned with European Data Protection Board (EDPB) principles.

*   **Singling-Out**: The risk of isolating a unique individual in the dataset based on their attributes.
*   **Linkability**: The risk of connecting records from the synthetic dataset to the original or other external datasets.
*   **Inference**: The risk of deducing sensitive attribute values from other available information.

Read more in the [Privacy Risk](privacy.md) section.

---

## 📊 Bayesian Comparison Framework

Traditional p-values often fail to provide a clear picture of which SDG method is truly "better," especially when dealing with high-dimensional omics data across different cohorts. 

SynOmicBench implements a **Bayesian Comparison Framework** using the `baycomp` library. Instead of binary "significant" vs "non-significant" results, we calculate the **Posterior Probability of Superiority**.

### Key Advantages
*   **ROPE (Region of Practical Equivalence)**: We define a threshold (e.g., 0.01) within which two methods are considered practically equivalent.
*   **Direct Probabilities**: We compute $P(\text{Method A} > \text{Method B})$, providing an intuitive measure of how much better one method is than another.
*   **Stability Assessment**: By running multiple seeds and folds, we visualize the stability of method rankings across different cancer types (ccRCC, Melanoma, NSCLC).

For a deep dive into our ranking methodology, see [Meta-Ranking & Stability](meta-ranking.md).

---

## 💻 Usage Example

All evaluation metrics in SynOmicBench are designed with a consistent API. Here is an example of how to compute **Univariate Similarity** using the framework.

```python
import pandas as pd
from SynOmics.metrics.fidelity import UnivariateSimilarity

# Load your original and synthetic datasets
original_df = pd.read_csv("original_data.csv")
synthetic_df = pd.read_csv("synthetic_data.csv")

# Load metadata (SDV format)
metadata = {
    "columns": {
        "Age": {"sdtype": "numerical"},
        "Gender": {"sdtype": "categorical"},
        "TP53": {"sdtype": "numerical"}
    }
}

# Initialize the metric evaluator
evaluator = UnivariateSimilarity(output_dir="results/fidelity")

# Compute the score (0.0 to 1.0, where 1.0 is perfect similarity)
score = evaluator.get_univariate_score(
    original_data=original_df,
    synthetic_data=synthetic_df,
    metadata=metadata,
    save=True
)

print(f"Overall Univariate Similarity: {score:.4f}")

# Access detailed per-column scores
details = evaluator.get_detail_df()
print(details.head())
```

### Performing Bayesian Comparison

Once you have scores for multiple methods, you can compare them:

```python
from SynOmics.metrics.fidelity import BayesianComparison

# Scores for two methods across 5 different seeds
scores = {
    "GaussianCopula": [0.85, 0.86, 0.84, 0.85, 0.87],
    "CTGAN": [0.78, 0.80, 0.79, 0.77, 0.81]
}

comparator = BayesianComparison(rope=0.01)
comparison_results = comparator.compare_methods(scores)

print(comparison_results)
# Output shows Probability(GaussianCopula > CTGAN)
```

---

## 🔗 Detailed Documentation

*   [**Broad Utility**](broad-utility.md): Statistical tests, correlation structures, and fidelity metrics.
*   [**Narrow Utility**](narrow-utility/index.md): Downstream biological validation tasks.
*   [**Privacy Risk**](privacy.md): Attack-based privacy assessments.
*   [**Meta-Ranking**](meta-ranking.md): Stability analysis and Bayesian superiority matrices.

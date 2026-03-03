# Avatars Synthesizer

The Avatars synthesizer generates synthetic data using a K-nearest neighbors approach to create "avatars" of the original records. It is a distance-based method that preserves the local structure of the data while providing privacy through record-level synthesis.

## Overview

- **Methodology**: Local neighborhood-based synthesis (K-Nearest Neighbors).
- **Key Strength**: Exceptional bivariate fidelity, particularly effective for preserving correlations in high-dimensional omic data.
- **Privacy Mechanism**: Each synthetic record is an "avatar" derived from a neighborhood of $K$ original records, preventing direct record linkage.

## Usage in SynOmicBench

In the SynOmicBench framework, the Avatars method is often evaluated with different values of $K$, commonly $K=5$ and $K=10$.

### Configuration Example

While the Avatars implementation may vary across different libraries, it typically requires specifying the number of neighbors:

```python
# Example conceptual usage
# synthesizer = AvatarsSynthesizer(k=5, ...)
# synthesizer.fit(data)
# synthetic_data = synthesizer.sample(n_samples=len(data))
```

## Performance Characteristics

In evaluation across ccRCC, Melanoma, and NSCLC datasets, the Avatars method (specifically K=5) demonstrated:

- **Top Bivariate Fidelity**: Achieved the highest bivariate fidelity scores (e.g., 0.954 on ccRCC omic data), outperforming both statistical copulas and deep learning models.
- **Local Structure Preservation**: Highly effective at maintaining the covariance structure of transcriptomic features.
- **Utility-Privacy Trade-off**: Lower values of $K$ (e.g., K=5) provide higher utility but may have different privacy profiles than larger $K$ values or noise-adding methods.

## Key Features

- **Non-Parametric**: Does not assume a specific underlying distribution (unlike Gaussian Copula).
- **Local Fidelity**: Focuses on preserving the relationship between a record and its closest neighbors in the feature space.
- **Scalability**: Can be applied to high-dimensional omic data by focusing on local neighborhoods.

## Implementation Considerations

When using Avatars for omic data:

1.  **Distance Metric**: The choice of distance metric (e.g., Euclidean, Manhattan) can impact the quality of the neighborhoods.
2.  **K Selection**: A smaller $K$ results in synthetic data closer to the original records (higher utility, lower privacy), while a larger $K$ increases data diversity and privacy at the potential cost of fidelity.
3.  **Dimensionality**: For extremely high-dimensional data, dimensionality reduction (like PCA) is often performed before neighbor selection to combat the "curse of dimensionality."

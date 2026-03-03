# Synthesizers Overview

SynOmicBench provides a suite of state-of-the-art synthetic data generation methods tailored for multi-omics data. Each synthesizer follows a unified interface, ensuring consistency and ease of use across different generation strategies.

## Available Synthesizers

We support six primary synthesizers, ranging from statistical models to deep learning architectures:

| Synthesizer | Category | Key Characteristic | Best For |
| :--- | :--- | :--- | :--- |
| **Gaussian Copula** | Statistical | Models dependencies using copula functions | Balanced performance, numerical data |
| **CTGAN** | Deep Learning | Conditional GAN for tabular data | Complex distributions, categorical data |
| **TVAE** | Deep Learning | Variational Autoencoder for tabular data | Dense data, efficient training |
| **Synthpop** | Regression-based | Sequential classification and regression trees | High fidelity, large datasets |
| **Avatars K5** | K-Anonymity | Differential privacy inspired via K-anonymity | Privacy-centric generation (K=5) |
| **Avatars K10** | K-Anonymity | Higher privacy threshold K-anonymity | Strict privacy requirements (K=10) |

## Comparison and Selection

Choosing the right synthesizer depends on your data characteristics and privacy requirements:

### Statistical & Regression Methods
*   **Gaussian Copula**: Excellent for capturing linear and non-linear correlations in numerical datasets. It is computationally efficient and provides a solid baseline.
*   **Synthpop**: Highly flexible as it uses a sequence of models to predict each column based on previous ones. It is particularly strong at preserving marginal distributions.

### Deep Learning Methods
*   **CTGAN**: Designed specifically for tabular data with highly imbalanced categorical features. It uses a conditional generator to overcome training challenges in standard GANs.
*   **TVAE**: A VAE-based approach that often converges faster than GANs and provides excellent structural preservation for omics data.

### Privacy-Centric Methods
*   **Avatars (K5/K10)**: These methods focus on providing formal privacy guarantees through K-anonymity. Use K5 for a balance between utility and privacy, and K10 when privacy is the primary concern.

## Unified Workflow

Regardless of the underlying algorithm, all synthesizers in SynOmicBench follow the same lifecycle:

1.  **Initialization**: Providing an output path and optional metadata.
2.  **Preprocessing**: Handling data transformations (e.g., scaling or encoding).
3.  **Fitting**: Training the model on original omics data.
4.  **Sampling**: Generating new synthetic records.
5.  **Postprocessing**: Reverting transformations and enforcing data constraints (rounding, min-max).

For more details on the common interface, see the [BaseSynthesizer API](base.md).

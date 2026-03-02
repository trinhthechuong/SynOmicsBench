# Computational Resources

Evaluating synthetic data generation methods requires a clear understanding of their computational demands. SynOmicBench benchmarks each synthesizer's training time, memory footprint, and scalability across multi-omics datasets of varying dimensions.

## Training Time Comparison

Training times vary significantly based on the underlying algorithm and hardware utilization. Methods like Gaussian Copula and Synthpop rely on statistical and regression-based approaches, while CTGAN and TVAE utilize deep learning architectures that benefit from GPU acceleration.

| Synthesizer | Typical Training Time | Hardware Recommendation | Scalability (Features) |
| :--- | :--- | :--- | :--- |
| **Gaussian Copula** | Very Fast (Seconds to Minutes) | CPU | High |
| **Synthpop** | Moderate (Minutes) | CPU (Multi-core) | Moderate |
| **Avatars (K=5/10)** | Fast (Seconds to Minutes) | CPU | Moderate to High |
| **TVAE** | Slow (Minutes to Hours) | GPU Recommended | Moderate |
| **CTGAN** | Very Slow (Hours) | GPU Highly Recommended | Moderate |

### Key Observations
*   **Gaussian Copula** is the most efficient method, capable of processing high-dimensional omics data in seconds on a standard CPU.
*   **Synthpop**'s sequential modeling approach scales with the number of features, as each column is modeled conditioned on previous ones.
*   **Deep Learning models (CTGAN/TVAE)** require significantly more epochs to converge. While TVAE often trains faster than CTGAN, both are substantially more resource-intensive than statistical methods.
*   **Avatars** efficiency depends on the parameter $K$. Smaller $K$ values typically result in faster generation times.

## Memory Requirements

Memory consumption is primarily driven by the dataset size (number of samples $\times$ number of features) and the internal data structures used by the synthesizers.

*   **Low Memory Footprint**: Gaussian Copula and Avatars. These methods avoid storing large intermediate model weights.
*   **High Memory Footprint**: CTGAN and TVAE. The neural network architectures, especially when dealing with wide omics layers (thousands of genes), require substantial VRAM if using a GPU or RAM if using a CPU.

### Scalability for High-Dimensional Data

Multi-omics datasets often feature a "wide" format with thousands of molecular features (genes, proteins, metabolites) but relatively few samples.

1.  **Feature Selection/Reduction**: For CTGAN and TVAE, it is often necessary to perform feature selection or dimensionality reduction (e.g., PCA) before synthesis to remain within memory limits.
2.  **Parallelization**: Synthpop and Gaussian Copula implementations in SynOmicBench leverage multi-core processing where possible to speed up the independent modeling of features or copula estimations.

## Resource Monitoring in SynOmicBench

The framework includes built-in utilities to track resource usage during the synthesis process. The `monitor_resources` decorator can be applied to any synthesis function to capture:

*   **Execution Time**: Precise measurement of the fitting and sampling phases.
*   **RAM Usage**: Peak memory consumption during execution.
*   **CPU/GPU Utilization**: Monitoring core usage and specialized hardware load.

This allows users to benchmark different configurations and select the synthesizer that best fits their available infrastructure.

## Benchmark Environment

Results reported in the manuscript were obtained using the following standardized environment:

*   **CPU**: Multi-core processor (e.g., Intel Xeon or AMD EPYC)
*   **GPU**: NVIDIA Tesla V100 or A100 (for deep learning methods)
*   **RAM**: 64GB+ for high-dimensional omics integration
*   **OS**: Linux-based environment (Ubuntu 20.04/22.04)

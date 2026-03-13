"""
Fidelity metrics for evaluating statistical similarity between original and synthetic data.

This submodule provides tools for measuring:
- Univariate similarity: Marginal distributions of individual attributes
- Bivariate similarity: Inter-variable relationships and correlations
- Missing value preservation
- Visualization utilities
- Bayesian comparison methods
"""

from SynOmics.metrics.fidelity.UnivariateSimilarity import UnivariateSimilarity
from SynOmics.metrics.fidelity.PairwiseSimilarity import PairwiseSimilarity
from SynOmics.metrics.fidelity.BayesianComparison import BayesianComparison

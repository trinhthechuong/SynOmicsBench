"""
Utility functions for SynOmics.

This module provides:
- Monitoring: Logging utilities
- Correlations: Correlation computation functions
"""

from SynOmics.utils.monitoring import set_logger
from SynOmics.utils.correlations import (
    pearson_correlation,
    spearman_correlation,
    compute_correlation_matrix,
)

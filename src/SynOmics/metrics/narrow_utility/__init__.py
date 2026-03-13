"""
Biological utility metrics for evaluating downstream bioinformatics tasks.

This module provides metrics for assessing whether synthetic data preserves:
- Differential Gene Expression (DGE) patterns
- Gene Set Enrichment (GSEA) results
- Cell type deconvolution estimates
- Survival analysis outcomes
- Predictive model transferability
"""

from SynOmics.metrics.narrow_utility.DGE import GCSAnalyzer
from SynOmics.metrics.narrow_utility.GSEA import PCSAnalyzer
from SynOmics.metrics.narrow_utility.survival_analysis import SurvivalEvaluator

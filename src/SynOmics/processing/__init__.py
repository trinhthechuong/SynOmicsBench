"""
Data processing module for preprocessing and integrating clinical and transcriptomic data.

This module provides:
- DataIntegrationPipeline: End-to-end data processing
- DataProcessor: Core data transformation utilities
- MetaData: Metadata management for SDMetrics
- GeneQuery: Gene ID conversion utilities
- Postprocessing: Additional data transformation functions
"""

from SynOmics.processing.pipeline import DataIntegrationPipeline
from SynOmics.processing.preprocessing import DataProcessor
from SynOmics.processing.metadata import MetaData

# API Reference

This page provides auto-generated API documentation from Python docstrings. All classes and modules are documented using mkdocstrings, which extracts comprehensive information directly from the source code including method signatures, parameters, return types, and detailed descriptions.

## Synthesizers

The synthesizer module provides multiple approaches for generating synthetic omics data, all implementing a unified interface through the `BaseSynthesizer` class.

::: SynOmics.synthesizer.BaseSynthesizer.BaseSynthesizer

::: SynOmics.synthesizer.CTGANsynthesizer.CTGANsynthesizer

::: SynOmics.synthesizer.TVAEsynthesizer.TVAEsynthesizer

::: SynOmics.synthesizer.GaussianCopulasynthesizer.GaussianCopulasynthesizer

::: SynOmics.synthesizer.Synthpopsynthesizer.SynthpopSynthesizer

<!-- MICESynthesizer: Requires optional dependency miceforest -->

## Processing

The processing module handles data integration, preprocessing, metadata management, and gene-level queries for multi-omics datasets.

::: SynOmics.processing.pipeline.DataIntegrationPipeline

::: SynOmics.processing.preprocessing.DataProcessor

::: SynOmics.processing.metadata.MetaData

::: SynOmics.processing.gene_query.GeneQuery

## Metrics

The metrics module provides fidelity assessment tools for evaluating the quality of synthetic data against real data distributions.

::: SynOmics.metrics.fidelity.UnivariateSimilarity.UnivariateSimilarity

::: SynOmics.metrics.fidelity.PairwiseSimilarity.PairwiseSimilarity

## Utilities

Utility modules provide monitoring capabilities and correlation analysis tools used throughout the framework.

::: SynOmics.utils.monitoring

::: SynOmics.utils.correlations

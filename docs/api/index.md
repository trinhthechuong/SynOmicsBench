# API Reference

This page provides auto-generated API documentation from Python docstrings. All classes and modules are documented using mkdocstrings, which extracts comprehensive information directly from the source code including method signatures, parameters, return types, and detailed descriptions.

## Synthesizers

The `synthesizer` module provides multiple approaches for generating synthetic omics data, all implementing a unified interface through the `BaseSynthesizer` class.

::: SynOmics.synthesizer.BaseSynthesizer.BaseSynthesizer

::: SynOmics.synthesizer.CTGANsynthesizer.CTGANsynthesizer

::: SynOmics.synthesizer.TVAEsynthesizer.TVAEsynthesizer

::: SynOmics.synthesizer.GaussianCopulasynthesizer.GaussianCopulasynthesizer

::: SynOmics.synthesizer.Synthpopsynthesizer.SynthpopSynthesizer

<!-- MICESynthesizer: Requires optional dependency miceforest -->

## Processing

The `processing` module handles data integration, preprocessing, metadata management, and gene-level queries for multi-omics datasets.

::: SynOmics.processing.pipeline.DataIntegrationPipeline

::: SynOmics.processing.preprocessing.DataProcessor

::: SynOmics.processing.postprocessing

::: SynOmics.processing.metadata.MetaData

::: SynOmics.processing.gene_query.GeneQuery

## Metrics: Fidelity

The `metrics.fidelity` module provides assessment tools for evaluating the distribution quality of synthetic data against real data.

::: SynOmics.metrics.fidelity.UnivariateSimilarity.UnivariateSimilarity

::: SynOmics.metrics.fidelity.PairwiseSimilarity.PairwiseSimilarity

::: SynOmics.metrics.fidelity.MissingValueSimilarity

::: SynOmics.metrics.fidelity.BayesianComparison

::: SynOmics.metrics.fidelity.NarrowTasks.ClassificationComparator.SyntheticDataClassificationComparator

::: SynOmics.metrics.fidelity.visualization

## Metrics: Narrow Utility

The `metrics.narrow_utility` module evaluates the capability of synthetic data in downstream bioinformatics tasks.

::: SynOmics.metrics.narrow_utility.DGE

::: SynOmics.metrics.narrow_utility.GSEA

::: SynOmics.metrics.narrow_utility.cell_deconvolution

::: SynOmics.metrics.narrow_utility.survival_analysis

::: SynOmics.metrics.narrow_utility.predictive_model_comp

::: SynOmics.metrics.narrow_utility.BayesianComparison

## Metrics: Privacy

The `metrics.privacy` module provides tools to assess the likelihood of privacy attacks using synthetic data.

::: SynOmics.metrics.privacy.singling_out

::: SynOmics.metrics.privacy.linkability

::: SynOmics.metrics.privacy.inference

## Utilities

Utility modules provide monitoring capabilities, evaluation utilities, and correlation analysis tools used throughout the framework.

::: SynOmics.utils.monitoring

::: SynOmics.utils.correlations

::: SynOmics.metrics.fidelity.utils

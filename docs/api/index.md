# API Reference

This page provides auto-generated API documentation from Python docstrings. All classes and modules are documented using mkdocstrings, which extracts comprehensive information directly from the source code including method signatures, parameters, return types, and detailed descriptions.

## Synthesizers

The `synthesizer` module provides multiple approaches for generating synthetic omics data, all implementing a unified interface through the `BaseSynthesizer` class.

::: synomicsbench.synthesizer.BaseSynthesizer.BaseSynthesizer

::: synomicsbench.synthesizer.CTGANsynthesizer.CTGANsynthesizer

::: synomicsbench.synthesizer.TVAEsynthesizer.TVAEsynthesizer

::: synomicsbench.synthesizer.GaussianCopulasynthesizer.GaussianCopulasynthesizer

::: synomicsbench.synthesizer.Synthpopsynthesizer.SynthpopSynthesizer

<!-- MICESynthesizer: Requires optional dependency miceforest -->

## Processing

The `processing` module handles data integration, preprocessing, metadata management, and gene-level queries for multi-omics datasets.

::: synomicsbench.processing.pipeline.DataIntegrationPipeline

::: synomicsbench.processing.preprocessing.DataProcessor

::: synomicsbench.processing.postprocessing

::: synomicsbench.processing.metadata.MetaData

::: synomicsbench.processing.gene_query.GeneQuery

## Metrics: Fidelity

The `metrics.fidelity` module provides assessment tools for evaluating the distribution quality of synthetic data against real data.

::: synomicsbench.metrics.fidelity.UnivariateSimilarity.UnivariateSimilarity

::: synomicsbench.metrics.fidelity.PairwiseSimilarity.PairwiseSimilarity

::: synomicsbench.metrics.fidelity.MissingValueSimilarity

::: synomicsbench.metrics.fidelity.BayesianComparison

<!-- ::: synomicsbench.metrics.fidelity.NarrowTasks.ClassificationComparator.SyntheticDataClassificationComparator -->

::: synomicsbench.metrics.fidelity.visualization

## Metrics: Biological Utility

The `metrics.narrow_utility` module evaluates the capability of synthetic data in downstream bioinformatics tasks.

::: synomicsbench.metrics.narrow_utility.DGE

::: synomicsbench.metrics.narrow_utility.GSEA

::: synomicsbench.metrics.narrow_utility.cell_deconvolution

::: synomicsbench.metrics.narrow_utility.survival_analysis

::: synomicsbench.metrics.narrow_utility.predictive_model_comp

::: synomicsbench.metrics.narrow_utility.BayesianComparison

## Metrics: Privacy

The `metrics.privacy` module provides tools to assess the likelihood of privacy attacks using synthetic data.

::: synomicsbench.metrics.privacy.singling_out

::: synomicsbench.metrics.privacy.linkability

::: synomicsbench.metrics.privacy.inference

## Metrics: Automatic Benchmark

The `metrics.autobenchmark` module orchestrates every metric dimension into a single run, producing a rank-derived meta-score and a comprehensive report.

::: synomicsbench.metrics.autobenchmark.config.BenchmarkConfig

::: synomicsbench.metrics.autobenchmark.runner.BenchmarkRunner

::: synomicsbench.metrics.autobenchmark.runners

::: synomicsbench.metrics.autobenchmark.compute

::: synomicsbench.metrics.autobenchmark.metascore

::: synomicsbench.metrics.autobenchmark.report

::: synomicsbench.metrics.autobenchmark.html_report

::: synomicsbench.metrics.autobenchmark.privacy

## Utilities

Utility modules provide monitoring capabilities, evaluation utilities, and correlation analysis tools used throughout the framework.

::: synomicsbench.utils.monitoring

::: synomicsbench.utils.correlations

::: synomicsbench.metrics.fidelity.utils

"""
Attribute inference risk evaluation for synthetic data.
Evaluates whether an adversary can infer sensitive clinical attributes
(secrets) from auxiliary gene expression features using the synthetic
dataset.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Sequence, Tuple

import pandas as pd
from anonymeter.evaluators import InferenceEvaluator

from synomicsbench.metrics.privacy.knowledge import (
    ColumnSpec,
    GeneSetSpec,
    knowledge_levels,
    n_record_attacks,
    numpy_seed,
    resolve_columns,
    subset_frames,
)

logger = logging.getLogger(__name__)


def eval_inference_genes_clinical(
    ori: pd.DataFrame,
    syns: Dict[str, pd.DataFrame],
    clinical_cols: ColumnSpec,
    transcriptomic_cols: ColumnSpec = None,
    proportions: Sequence[float] = (1.0,),
    seed: int = 42,
    control: Optional[pd.DataFrame] = None,
    gene_sets: GeneSetSpec = None,
    evaluator_seed: Optional[int] = None,
) -> Dict[str, List[Tuple[str, str, object]]]:
    """Evaluate attribute inference risk for each clinical variable at several knowledge levels.

    Each knowledge level is a set of genes the attacker knows: a named gene set or a
    fraction of ``transcriptomic_cols`` (see
    :func:`synomicsbench.metrics.privacy.knowledge.knowledge_levels`). At every level and
    for every synthetic dataset, each clinical feature is in turn the *secret*: the
    ``InferenceEvaluator`` from Anonymeter predicts it from the known genes.

    Args:
        ori: Original dataset.
        syns: Mapping from synthetic dataset name to its DataFrame.
        clinical_cols: List of column names or integer indices for clinical
            features (secrets). If indices are provided, they refer to
            ``ori`` column positions.
        transcriptomic_cols: List of column names or integer indices for
            transcriptomic (gene) features (auxiliary). If ``None``, uses
            all remaining columns not in ``clinical_cols``.
        proportions: Fractions of the genes known by the attacker.
        seed: Seed of the gene sampling (reset at every knowledge level).
        control: Optional dataset of patients not used to train the generators, with the
            columns of ``ori``; enables the residual risk. The number of attacks is then
            bounded by its size.
        gene_sets: Optional named gene sets evaluated before the fractions: a path to a
            ``.gmt`` file or a mapping such as ``{"FGES": [...]}``.
        evaluator_seed: Seed of the draw of the target records and of the naive guesses,
            set before every evaluation; ``None`` uses ``seed``.

    Returns:
        Mapping from dataset name to a list of ``(level, secret, results)`` tuples, one
        per knowledge level (gene sets first, then ``proportions``) and secret, where
        ``results`` is an ``EvaluationResults`` object or an error dict if the evaluation
        failed.
    """
    clinical, genes = resolve_columns(ori.columns, clinical_cols, transcriptomic_cols)
    levels = knowledge_levels(clinical, genes, proportions, gene_sets, seed)
    n_attacks = n_record_attacks(ori, control)

    results_all: Dict[str, List[Tuple[str, str, object]]] = {}

    for tool, syn_data in syns.items():
        results: List[Tuple[str, str, object]] = []
        logger.info("Starting inference evaluation for %s", tool)

        for level, cols in levels:
            o, s, c = subset_frames(ori, syn_data, control, cols)
            known_genes = cols[len(clinical):]
            for secret in clinical:
                try:
                    evaluator = InferenceEvaluator(
                        ori=o,
                        syn=s,
                        aux_cols=known_genes,
                        secret=secret,
                        n_attacks=n_attacks,
                        control=c,
                    )
                    with numpy_seed(seed if evaluator_seed is None else evaluator_seed):
                        evaluator.evaluate(n_jobs=-2)
                    res = evaluator.results()
                    results.append((level, secret, res))
                    logger.info("Tool %s: level %s secret %s risk=%s", tool, level, secret,
                                res.risk().value)
                except Exception as ex:
                    logger.exception(
                        "Error evaluating tool=%s level=%s secret=%s: %s", tool, level, secret, ex
                    )
                    results.append((level, secret, {"error": str(ex)}))

        results_all[tool] = results

    return results_all

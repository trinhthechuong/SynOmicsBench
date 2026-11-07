"""
Linkability risk evaluation for synthetic data.

Evaluates whether an attacker can use synthetic data to link
molecular (gene expression) profiles to clinical attributes of the
same individual.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence

import pandas as pd
from anonymeter.evaluators import LinkabilityEvaluator

from synomicsbench.metrics.privacy.knowledge import (
    ColumnSpec,
    GeneSetSpec,
    knowledge_levels,
    n_record_attacks,
    numpy_seed,
    resolve_columns,
    subset_frames,
)


def eval_linkability_genes_clinical(
    ori: pd.DataFrame,
    syns: Dict[str, pd.DataFrame],
    clinical_cols: ColumnSpec,
    transcriptomic_cols: ColumnSpec = None,
    n_neighbors: int = 1,
    proportions: Sequence[float] = (1.0,),
    seed: int = 42,
    control: Optional[pd.DataFrame] = None,
    gene_sets: GeneSetSpec = None,
    evaluator_seed: Optional[int] = None,
) -> Dict[str, List[LinkabilityEvaluator]]:
    """Evaluate linkability risk between gene expression and clinical features.

    The attack attempts to link two disjoint attribute sets of the same
    patient (the clinical variables, and the genes of one knowledge level) using the
    synthetic dataset as a bridge.

    Args:
        ori: Original dataset.
        syns: Mapping from synthetic dataset name to its DataFrame.
        clinical_cols: List of column names or integer indices for clinical
            features. If indices are provided, they refer to ``ori`` column
            positions.
        transcriptomic_cols: List of column names or integer indices for
            transcriptomic (gene) features. If ``None``, uses all remaining
            columns not in ``clinical_cols``.
        n_neighbors: Number of nearest neighbors for the linkability attack.
        proportions: Fractions of gene columns known by the attacker.
        seed: Seed of the gene sampling (reset at every knowledge level).
        control: Optional dataset of patients not used to train the generators, with the
            columns of ``ori``; enables the residual risk. The number of attacks is then
            bounded by its size.
        gene_sets: Optional named gene sets evaluated before the fractions: a path to a
            ``.gmt`` file or a mapping such as ``{"FGES": [...]}``.
        evaluator_seed: Seed of the draw of the target records, set before every
            evaluation; ``None`` uses ``seed``. It matters when ``control`` has fewer
            records than ``ori``, so that only part of the original records are attacked.

    Returns:
        Mapping from dataset name to a list of evaluated
        ``LinkabilityEvaluator`` instances, one per knowledge level (gene sets first,
        then ``proportions``).
    """
    clinical, genes = resolve_columns(ori.columns, clinical_cols, transcriptomic_cols)
    levels = knowledge_levels(clinical, genes, proportions, gene_sets, seed)
    n_attacks = n_record_attacks(ori, control)

    results: Dict[str, List[LinkabilityEvaluator]] = {}
    for syn_name, syn_df in syns.items():
        risks: List[LinkabilityEvaluator] = []
        for _, cols in levels:
            o, s, c = subset_frames(ori, syn_df, control, cols)
            evaluator = LinkabilityEvaluator(
                ori=o,
                syn=s,
                n_attacks=n_attacks,
                aux_cols=(clinical, cols[len(clinical):]),
                n_neighbors=n_neighbors,
                control=c,
            )
            with numpy_seed(seed if evaluator_seed is None else evaluator_seed):
                evaluator.evaluate(n_jobs=-2)
            risks.append(evaluator)
        results[syn_name] = risks

    return results

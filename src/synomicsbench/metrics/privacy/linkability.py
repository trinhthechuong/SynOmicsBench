"""
Linkability risk evaluation for synthetic data.

Evaluates whether an attacker can use synthetic data to link
molecular (gene expression) profiles to clinical attributes of the
same individual.
"""

from __future__ import annotations

import random
from typing import Dict, List, Tuple, Optional, Sequence, Union

import pandas as pd
# from linkability_evaluator import LinkabilityEvaluator # if it's slow, import directly the script from Anonymeter repo
from anonymeter.evaluators import LinkabilityEvaluator

def eval_linkability_genes_clinical(
    ori: pd.DataFrame,
    syns: Dict[str, pd.DataFrame],
    clinical_cols: Union[List[int], List[str]],
    transcriptomic_cols: Union[List[int], List[str]] = None,
    n_neighbors: int = 1,
    proportions: Sequence[float] = (0.25, 0.50, 0.75, 1.0),
    seed: int = 42,
) -> Dict[str, List[LinkabilityEvaluator]]:
    """Evaluate linkability risk between gene expression and clinical features.

    The attack attempts to link two disjoint attribute sets of the same
    patient — clinical variables and a randomly sampled subset of gene
    expression features — using the synthetic dataset as a bridge.

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
        proportions: Fractions of gene columns to sample for the attack.
        seed: Random seed for gene column sampling.

    Returns:
        Mapping from dataset name to a list of evaluated
        ``LinkabilityEvaluator`` instances (one per proportion).
    """
    results: Dict[str, List[LinkabilityEvaluator]] = {}

    all_columns = ori.columns.tolist()

    # Resolve clinical columns (convert indices to names if needed)
    if clinical_cols and isinstance(clinical_cols[0], int):
        clinical_col_names = [all_columns[i] for i in clinical_cols]
    else:
        clinical_col_names = list(clinical_cols)

    # Resolve transcriptomic columns
    if transcriptomic_cols is not None:
        if isinstance(transcriptomic_cols[0], int):
            genes_cols = [all_columns[i] for i in transcriptomic_cols]
        else:
            genes_cols = list(transcriptomic_cols)
    else:
        genes_cols = [col for col in all_columns if col not in clinical_col_names]

    for syn_name, syn_df in syns.items():
        random.seed(seed)
        risks: List[LinkabilityEvaluator] = []

        for p in proportions:
            n = int(len(genes_cols) * p)
            sampled_genes = random.sample(genes_cols, n)
            aux_cols = (clinical_col_names, sampled_genes)

            evaluator = LinkabilityEvaluator(
                ori=ori,
                syn=syn_df,
                n_attacks=ori.shape[0],
                aux_cols=aux_cols,
                n_neighbors=n_neighbors,
            )
            evaluator.evaluate(n_jobs=-2)
            risks.append(evaluator)

        results[syn_name] = risks

    return results

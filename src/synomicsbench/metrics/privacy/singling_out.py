"""
Singling-out risk evaluation for synthetic data.

Provides helper functions that wrap the singling-out evaluator of Anonymeter, in the polars
implementation used for the SynOmicsBench results (vendored under
``synomicsbench.third_party.anonymeter_polars``; the pandas evaluator of Anonymeter is too slow
on cohorts with tens of thousands of columns), to run univariate and multivariate
singling-out attacks.

With a ``control`` dataset (patients from the same population that the generator never
saw), the evaluators report the residual risk
``(R_attack - R_control) / (1 - R_control)``; without it, the attack risk is compared
with the naive (random-guess) baseline. See :func:`synomicsbench.metrics.privacy.risk.privacy_risk_table`.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence

import pandas as pd

from synomicsbench.metrics.privacy.knowledge import (
    ColumnSpec,
    GeneSetSpec,
    knowledge_levels,
    resolve_columns,
    subset_frames,
)
from synomicsbench.third_party.anonymeter_polars.singling_out_evaluator import SinglingOutEvaluator


def eval_singling_out_univariate(
    ori: pd.DataFrame,
    syns: Dict[str, pd.DataFrame],
    n_attacks: int = 10_000,
    max_attempts: int = 1_000_000,
    proportions: Sequence[float] = (1.0,),
    seed: int = 42,
    control: Optional[pd.DataFrame] = None,
    clinical_cols: ColumnSpec = None,
    transcriptomic_cols: ColumnSpec = None,
    gene_sets: GeneSetSpec = None,
    evaluator_seed: Optional[int] = None,
) -> Dict[str, List[SinglingOutEvaluator]]:
    """Run univariate singling-out attacks at several attacker knowledge levels.

    Each knowledge level is a set of columns the attacker knows: all ``clinical_cols``
    plus a named gene set or a fraction of the genes (see
    :func:`synomicsbench.metrics.privacy.knowledge.knowledge_levels`). Without
    ``clinical_cols``, the fractions are taken over all columns.

    Args:
        ori: Original (real) dataset after post-processing.
        syns: Mapping from synthetic dataset name to its DataFrame.
        n_attacks: Number of attack predicates to generate per evaluation.
        max_attempts: Maximum predicate generation attempts.
        proportions: Fractions of the genes (of all columns without ``clinical_cols``)
            known by the attacker.
        seed: Seed of the gene sampling (reset at every knowledge level).
        control: Optional dataset of patients not used to train the generators, with the
            columns of ``ori``; enables the residual risk.
        clinical_cols: Clinical columns (names or positions), known at every level.
        transcriptomic_cols: Gene columns; ``None`` uses every non-clinical column.
        gene_sets: Optional named gene sets evaluated before the fractions: a path to a
            ``.gmt`` file or a mapping such as ``{"FGES": [...]}``.
        evaluator_seed: Seed of the predicate generation; ``None`` uses ``seed``.
            SynOmicsBench used the seed of each synthetic dataset.

    Returns:
        Mapping from synthetic dataset name to a list of evaluated
        ``SinglingOutEvaluator`` instances, one per knowledge level (gene sets first,
        then ``proportions``).
    """
    clinical, genes = resolve_columns(ori.columns, clinical_cols, transcriptomic_cols)
    levels = knowledge_levels(clinical, genes, proportions, gene_sets, seed)

    results: Dict[str, List[SinglingOutEvaluator]] = {}
    for syn_name, syn_df in syns.items():
        risks: List[SinglingOutEvaluator] = []
        for _, cols in levels:
            o, s, c = subset_frames(ori, syn_df, control, cols)
            evaluator = SinglingOutEvaluator(
                ori=o,
                syn=s,
                n_attacks=n_attacks,
                n_cols=1,
                max_attempts=max_attempts,
                seed=seed if evaluator_seed is None else evaluator_seed,
                control=c,
            )
            evaluator.evaluate(mode="univariate")
            risks.append(evaluator)
        results[syn_name] = risks

    return results


def eval_singling_out_multivariate(
    ori: pd.DataFrame,
    syns: Dict[str, pd.DataFrame],
    n_cols_list: Sequence[int] = (2, 3, 5, 7, 10, 20, 50),
    n_attacks: int = 10_000,
    max_attempts: int = 1_000_000,
    seed: int = 42,
    control: Optional[pd.DataFrame] = None,
    evaluator_seed: Optional[int] = None,
) -> Dict[str, List[SinglingOutEvaluator]]:
    """Run multivariate singling-out attacks at varying attribute-combination sizes.

    The predicates are drawn from all columns of ``ori``.

    Args:
        ori: Original dataset.
        syns: Mapping from synthetic dataset name to its DataFrame.
        n_cols_list: Number of columns the attacker uses per predicate.
        n_attacks: Number of attack predicates per evaluation.
        max_attempts: Maximum predicate generation attempts.
        seed: Seed of the predicate generation.
        control: Optional dataset of patients not used to train the generators, with the
            columns of ``ori``; enables the residual risk.
        evaluator_seed: Seed of the predicate generation in place of ``seed``, as in
            :func:`eval_singling_out_univariate`.

    Returns:
        Mapping from synthetic dataset name to a list of evaluated
        ``SinglingOutEvaluator`` instances (one per ``n_cols`` value).
    """
    results: Dict[str, List[SinglingOutEvaluator]] = {}

    for syn_name, syn_df in syns.items():
        o, s, c = subset_frames(ori, syn_df, control, ori.columns)
        risks: List[SinglingOutEvaluator] = []
        for n_col in n_cols_list:
            evaluator = SinglingOutEvaluator(
                ori=o,
                syn=s,
                n_cols=n_col,
                n_attacks=n_attacks,
                max_attempts=max_attempts,
                seed=seed if evaluator_seed is None else evaluator_seed,
                control=c,
            )
            evaluator.evaluate(mode="multivariate")
            risks.append(evaluator)
        results[syn_name] = risks

    return results

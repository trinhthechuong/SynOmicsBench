"""
Attribute inference risk evaluation for synthetic data.

Refactored from ``ccRCC/Privacy/Inference/inference_experiment.py``.
Evaluates whether an adversary can infer sensitive clinical attributes
(secrets) from auxiliary gene expression features using the synthetic
dataset.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple, Union

import pandas as pd
from anonymeter.evaluators import InferenceEvaluator


logger = logging.getLogger(__name__)


def eval_inference_genes_clinical(
    ori: pd.DataFrame,
    syns: Dict[str, pd.DataFrame],
    clinical_cols: Union[List[int], List[str]],
    transcriptomic_cols: Union[List[int], List[str]] = None,
    save_path: Optional[str] = None,
) -> Dict[str, List[Tuple[str, object]]]:
    """Evaluate attribute inference risk for each clinical variable.

    For every synthetic dataset and each clinical feature (treated as a
    *secret*), the ``InferenceEvaluator`` from Anonymeter uses all gene
    expression columns as auxiliary information to predict the secret
    attribute.

    Args:
        ori: Original dataset.
        syns: Mapping from synthetic dataset name to its DataFrame.
        clinical_cols: List of column names or integer indices for clinical
            features (secrets). If indices are provided, they refer to
            ``ori`` column positions.
        transcriptomic_cols: List of column names or integer indices for
            transcriptomic (gene) features (auxiliary). If ``None``, uses
            all remaining columns not in ``clinical_cols``.
        save_path: Optional path to incrementally save results as pickle.

    Returns:
        Mapping from dataset name to a list of ``(secret_name, results)``
        tuples, where ``results`` is an ``EvaluationResults`` object or
        an error dict if the evaluation failed.
    """
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

    results_all: Dict[str, List[Tuple[str, object]]] = {}

    for tool, syn_data in syns.items():
        results: List[Tuple[str, object]] = []
        logger.info("Starting inference evaluation for %s", tool)

        for secret in clinical_col_names:
            try:
                evaluator = InferenceEvaluator(
                    ori=ori,
                    syn=syn_data,
                    aux_cols=genes_cols,
                    secret=secret,
                    n_attacks=ori.shape[0],
                )
                evaluator.evaluate(n_jobs=-2)
                results.append((secret, evaluator.results()))
                logger.info(
                    "Tool %s: secret %s risk=%s",
                    tool,
                    secret,
                    evaluator.results().risk().value,
                )
            except Exception as ex:
                logger.exception(
                    "Error evaluating tool=%s secret=%s: %s", tool, secret, ex
                )
                results.append((secret, {"error": str(ex)}))

        results_all[tool] = results

    return results_all

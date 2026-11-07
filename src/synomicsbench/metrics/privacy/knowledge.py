"""
Attacker knowledge levels shared by the privacy attacks.

An attacker is assumed to know the clinical attributes of a patient and part of the
transcriptome. Each knowledge level is the list of columns the attack may use: all
clinical columns, plus either a named gene set (e.g. a published signature) or a random
fraction of the genes. Every fraction is drawn after resetting the same seed, so all
synthetic datasets are attacked on exactly the same columns. Gene sets are given as a
mapping or read from a ``.gmt`` file.

``FGES_GMT`` is the bundled ``.gmt`` file of the tumor microenvironment (TME)-related
functional gene expression signatures (FGES) used by SynOmicsBench
(Bagaev et al., 2021, https://doi.org/10.1016/j.ccell.2021.04.014):
``gene_sets={"FGES": FGES_GMT}`` is one knowledge level with the genes of all these signatures.
"""

from __future__ import annotations

import os
import random
from contextlib import contextmanager
from typing import Dict, Iterator, List, Mapping, Optional, Sequence, Tuple, Union

import numpy as np
import pandas as pd

ColumnSpec = Union[Sequence[int], Sequence[str], None]
GeneSetSpec = Union[str, "os.PathLike[str]", Mapping[str, Union[Sequence[str], str, "os.PathLike[str]"]], None]

#: Bundled TME-related functional gene expression signatures (FGES), one set per line.
FGES_GMT: str = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                             "data", "fges.gmt")


def read_gmt(path: Union[str, "os.PathLike[str]"]) -> Dict[str, List[str]]:
    """Read gene sets from a ``.gmt`` file.

    Each line holds a set name, a description and the member genes, separated by tabs.

    Args:
        path: Path to the ``.gmt`` file.

    Returns:
        Mapping from set name to member genes, in file order.
    """
    gene_sets: Dict[str, List[str]] = {}
    with open(path) as handle:
        for line in handle:
            fields = [f.strip() for f in line.rstrip("\n").split("\t")]
            if len(fields) < 3 or not fields[0]:
                continue
            gene_sets[fields[0]] = [g for g in fields[2:] if g]
    return gene_sets


def resolve_columns(
    columns: Sequence[str],
    clinical_cols: ColumnSpec,
    transcriptomic_cols: ColumnSpec = None,
) -> Tuple[List[str], List[str]]:
    """Resolve clinical and transcriptomic column names.

    Args:
        columns: Columns of the original dataset.
        clinical_cols: Clinical column names or integer positions in ``columns``.
        transcriptomic_cols: Gene column names or positions; ``None`` uses every column
            that is not clinical.

    Returns:
        ``(clinical column names, gene column names)``, in the order given.
    """
    columns = list(columns)

    def _names(spec: ColumnSpec) -> List[str]:
        spec = list(spec) if spec is not None else []
        if spec and isinstance(spec[0], int):
            return [columns[i] for i in spec]
        return list(spec)

    clinical = _names(clinical_cols)
    if transcriptomic_cols is None:
        clinical_set = set(clinical)
        genes = [c for c in columns if c not in clinical_set]
    else:
        genes = _names(transcriptomic_cols)
    return clinical, genes


def knowledge_levels(
    clinical: Sequence[str],
    genes: Sequence[str],
    proportions: Sequence[float] = (1.0,),
    gene_sets: GeneSetSpec = None,
    feature_seed: int = 42,
) -> List[Tuple[str, List[str]]]:
    """Columns available to the attacker at each knowledge level.

    Named gene sets come first, in the order given, then the gene fractions. A gene set
    keeps the genes of ``genes`` it contains, in the order of ``genes``. A fraction ``p``
    below 1 draws ``int(p * len(genes))`` genes after ``random.seed(feature_seed)``.

    Args:
        clinical: Clinical columns, known at every level.
        genes: Gene columns the attacker may know.
        proportions: Fractions of ``genes`` known by the attacker.
        gene_sets: Optional named gene sets: a path to a ``.gmt`` file (one level per set)
            or a mapping such as ``{"panel": [...]}``. A mapping value that is a path to a
            ``.gmt`` file is one level with the genes of all its sets, e.g.
            ``{"FGES": FGES_GMT}``.
        feature_seed: Seed of the gene sampling.

    Returns:
        List of ``(label, columns)``; fractions are labelled like ``"25%"``.

    Raises:
        ValueError: If a gene set shares no gene with ``genes``.
    """
    clinical, genes = list(clinical), list(genes)
    levels: List[Tuple[str, List[str]]] = []

    if isinstance(gene_sets, (str, os.PathLike)):
        gene_sets = read_gmt(gene_sets)
    for name, members in (gene_sets or {}).items():
        if isinstance(members, (str, os.PathLike)):
            members = {g for genes in read_gmt(members).values() for g in genes}
        members = set(members)
        selected = [g for g in genes if g in members]
        if not selected:
            raise ValueError(f"Gene set '{name}' shares no gene with the attacked columns.")
        levels.append((str(name), clinical + selected))

    for p in proportions:
        if p >= 1.0:
            selected = list(genes)
        else:
            random.seed(feature_seed)
            selected = random.sample(genes, int(len(genes) * p))
        levels.append((level_label(p), clinical + selected))

    return levels


def level_label(proportion: float) -> str:
    """Label of a gene fraction, e.g. ``0.25 -> "25%"``."""
    return f"{proportion:.0%}"


def subset_frames(
    ori: pd.DataFrame,
    syn: pd.DataFrame,
    control: Optional[pd.DataFrame],
    cols: Sequence[str],
) -> Tuple[pd.DataFrame, pd.DataFrame, Optional[pd.DataFrame]]:
    """Restrict the original, synthetic and control datasets to the attacked columns.

    Raises:
        ValueError: If the synthetic or control dataset lacks some of the columns.
    """
    cols = list(cols)
    for name, df in (("synthetic", syn), ("control", control)):
        if df is None:
            continue
        missing = [c for c in cols if c not in df.columns]
        if missing:
            raise ValueError(
                f"The {name} dataset lacks {len(missing)} attacked column(s), e.g. {missing[:5]}. "
                "Reduce all datasets to the columns they share first."
            )
    return ori[cols], syn[cols], (None if control is None else control[cols])


def n_record_attacks(ori: pd.DataFrame, control: Optional[pd.DataFrame]) -> int:
    """Number of record-level attacks: every original record, bounded by the control size.

    Anonymeter attacks the same number of records in the original and the control dataset,
    sampling without replacement, so the smaller of the two bounds the attack budget.
    """
    return int(ori.shape[0] if control is None else min(ori.shape[0], control.shape[0]))


@contextmanager
def numpy_seed(seed: Optional[int]) -> Iterator[None]:
    """Seed numpy's global generator for the duration of one evaluation.

    Anonymeter's linkability and inference evaluators draw their target records (and the
    guesses of the naive attacker of inference) with ``DataFrame.sample``, i.e. numpy's global
    generator: seeding it makes the evaluation repeatable. The previous state of the generator
    is restored afterwards. ``None`` leaves the generator as it is.
    """
    if seed is None:
        yield
        return
    state = np.random.get_state()
    np.random.seed(seed)
    try:
        yield
    finally:
        np.random.set_state(state)

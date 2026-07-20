"""
BenchmarkRunner — orchestrate all metric dimensions over a list of synthetic datasets.

Given the original data and a list of candidate synthetic datasets, run every
enabled dimension (using each dimension's configured mode), aggregate the
per-dimension rank-derived meta-score, and return a :class:`BenchmarkResult`.
Use :func:`~synomicsbench.metrics.autobenchmark.report.write_report` to persist
the comprehensive report and composite figure.
"""

from __future__ import annotations

import glob
import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Union

import pandas as pd

from .config import BenchmarkConfig, ALL_DIMS
from . import runners as R
from .runners import Candidate, load_frame
from .metascore import build_metascore


DIMENSION_RUNNERS = {
    "Univariate": R.run_univariate,
    "Bivariate": R.run_bivariate,
    "DGE": R.run_dge,
    "GSEA": R.run_gsea,
    "ssGSEA": R.run_ssgsea,
    "Cell Deconvolution": R.run_cell_deconvolution,
    "Survival Analysis": R.run_survival,
    # Privacy handled separately (needs the optional privacy_csv argument).
}

# Dimensions that cannot be recomputed in-process default to reuse.
DEFAULT_MODES = {
    "Univariate": "compute",
    "Bivariate": "compute",
    "DGE": "compute",
    "GSEA": "compute",
    "ssGSEA": "compute",
    "Cell Deconvolution": "reuse",
    "Survival Analysis": "compute",
    "Privacy": "reuse",
}


@dataclass
class BenchmarkResult:
    """Container for a benchmark run's outputs."""
    per_dim_values: Dict[str, pd.DataFrame]          # dimension -> long df [Model, Seed, Value]
    metascore: Dict[str, Dict[str, float]]           # dimension -> {model: mean rank}
    value_table: pd.DataFrame                        # wide: index=Model, columns=dimension (mean value)
    rank_table: pd.DataFrame                         # wide: index=Model, columns=dimension (mean rank)
    composite: Optional[pd.DataFrame] = None         # composite pillar scores + Total (if all dims present)
    dims_run: List[str] = field(default_factory=list)
    dims_missing: List[str] = field(default_factory=list)


class BenchmarkRunner:
    """Run the automatic benchmark for one cohort."""

    def __init__(self, config: BenchmarkConfig):
        self.config = config

    def _display_name(self, stem: str) -> str:
        """Map a parsed file-stem to a display name via ``name_map`` (case-insensitive)."""
        s = str(stem)
        for disp, st in self.config.name_map.items():
            if st.lower() == s.lower() or disp.lower() == s.lower():
                return disp
        return s

    def _parse_name(self, name) -> Tuple[str, Optional[int]]:
        """Parse (method_display, seed) from a dataset name / filename.

        Strips any directory and ``.csv`` extension, applies ``config.name_pattern``.
        Returns ``seed=None`` when no trailing ``_<int>`` is found (→ single seed).
        """
        base = os.path.basename(str(name))
        if base.lower().endswith(".csv"):
            base = base[:-4]
        m = re.match(self.config.name_pattern, base)
        if m and m.groupdict().get("seed") is not None:
            return self._display_name(m.group("method")), int(m.group("seed"))
        return self._display_name(base), None

    def _candidates(self, datasets) -> List[Candidate]:
        """Normalise the ``datasets`` argument into a list of Candidate objects.

        Accepts, in order of explicitness:
        - a **directory path** or **glob** (str): expands to its ``*.csv`` files (files whose
          name contains "original"/"metadata" are skipped), each parsed for (method, seed);
        - a **mapping** ``{name: data}``: each ``name`` is parsed for (method, seed);
        - a **list** whose items are ``Candidate``, explicit dicts ``{'method','seed','data'}``,
          name-only dicts ``{'name'|'data'|'path': ...}``, or plain path strings (parsed).

        Multi-seed vs single-seed is then simply the number of **distinct parsed seeds**.
        A name with no trailing ``_<int>`` falls back to ``seed=`` from ``run`` (single seed).
        """
        default_seed = self._default_seed

        # Directory or glob string -> list of CSV paths (skip original/metadata files).
        if isinstance(datasets, str):
            if os.path.isdir(datasets):
                datasets = sorted(glob.glob(os.path.join(datasets, "*.csv")))
            else:
                matched = sorted(glob.glob(datasets))
                datasets = matched if matched else [datasets]
            datasets = [p for p in datasets
                        if not any(k in os.path.basename(p).lower() for k in ("original", "metadata"))]

        out: List[Candidate] = []
        if isinstance(datasets, dict):
            for name, data in datasets.items():
                method, seed = self._parse_name(name)
                out.append(Candidate(method=method, seed=seed if seed is not None else default_seed, data=data))
        else:
            for i, item in enumerate(datasets):
                if isinstance(item, Candidate):
                    out.append(item)
                elif isinstance(item, dict):
                    if "method" in item and "seed" in item:
                        out.append(Candidate(item["method"], int(item["seed"]), item["data"]))
                    else:
                        data = item.get("data", item.get("path"))
                        method, seed = self._parse_name(item.get("name", data))
                        out.append(Candidate(method, seed if seed is not None else default_seed, data))
                elif isinstance(item, str):
                    method, seed = self._parse_name(item)
                    out.append(Candidate(method, seed if seed is not None else default_seed, data=item))
                elif isinstance(item, pd.DataFrame):
                    out.append(Candidate(f"dataset_{i}", default_seed, item))
                else:
                    raise TypeError(f"Unsupported dataset item: {type(item)}")
        return out

    def run(
        self,
        original_data: Union[str, pd.DataFrame],
        datasets,
        seed: int = 42,
        privacy_csv: Optional[str] = None,
        dimensions: Optional[List[str]] = None,
    ) -> BenchmarkResult:
        """Evaluate all (enabled) dimensions and build the rank-derived meta-score.

        Args:
            original_data: reference dataset (path or DataFrame).
            datasets: candidates (see :meth:`_candidates`).
            seed: default seed applied when ``datasets`` is a plain name->data mapping.
            privacy_csv: optional precomputed ``overal_privacy_score`` CSV for the Privacy dim.
            dimensions: subset of dimensions to run (default: all eight).
        """
        self._default_seed = seed
        original = load_frame(original_data, self.config.id_column)
        candidates = self._candidates(datasets)
        dims = dimensions or list(ALL_DIMS)

        per_dim_values: Dict[str, pd.DataFrame] = {}
        dims_run, dims_missing = [], []
        for dim in dims:
            mode = self.config.mode_for(dim, default=DEFAULT_MODES.get(dim, "compute"))
            if mode == "skip":
                dims_missing.append(dim)
                continue
            try:
                if dim == "Privacy":
                    df = R.run_privacy(original, candidates, self.config, mode, privacy_csv=privacy_csv)
                else:
                    df = DIMENSION_RUNNERS[dim](original, candidates, self.config, mode)
            except Exception as exc:  # keep going; report what failed
                print(f"[autobenchmark] dimension '{dim}' failed ({mode}): {exc}")
                dims_missing.append(dim)
                continue
            if df is None or df.empty:
                dims_missing.append(dim)
                continue
            per_dim_values[dim] = df
            dims_run.append(dim)

        metascore = build_metascore(per_dim_values, collapse_dims=self.config.collapse_dims)

        # Wide value & rank tables (mean over seeds per method).
        value_table = self._wide(per_dim_values, "Value")
        rank_table = pd.DataFrame(metascore)

        composite = None
        if all(d in metascore for d in ALL_DIMS):
            from .metascore import plot_weighted_composite_scores
            _, composite = plot_weighted_composite_scores(
                metascore,
                broad_weight=self.config.weights[0],
                narrow_weight=self.config.weights[1],
                privacy_weight=self.config.weights[2],
                save_path=None,
            )
            import matplotlib.pyplot as plt
            plt.close("all")

        return BenchmarkResult(
            per_dim_values=per_dim_values,
            metascore=metascore,
            value_table=value_table,
            rank_table=rank_table,
            composite=composite,
            dims_run=dims_run,
            dims_missing=dims_missing,
        )

    @staticmethod
    def _wide(per_dim_values: Dict[str, pd.DataFrame], col: str) -> pd.DataFrame:
        frames = {}
        for dim, df in per_dim_values.items():
            frames[dim] = df.groupby("Model")[col].mean()
        return pd.DataFrame(frames)

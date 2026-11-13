"""
Run the automatic benchmark: compute the selected metrics over a list of synthetic datasets,
rank them into the rank-derived meta-score and write the report.

:func:`run_benchmark` does everything in one call; :class:`BenchmarkRunner` and
:func:`~synomicsbench.metrics.autobenchmark.report.write_report` are the two steps it chains.
"""

from __future__ import annotations

import glob
import hashlib
import json
import os
import re
import traceback
from dataclasses import dataclass, field, fields
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Union

import pandas as pd

from .config import BenchmarkConfig, PILLARS, PRIVACY_DIMS, resolve_metrics
from . import runners as R
from .runners import Candidate, load_frame
from .metascore import build_metascore, composite_scores


DIMENSION_RUNNERS = {
    "Univariate": R.run_univariate,
    "Bivariate": R.run_bivariate,
    "Network Preservation": R.run_network,
    "DGE": R.run_dge,
    "GSEA": R.run_gsea,
    "ssGSEA": R.run_ssgsea,
    "Cell Deconvolution": R.run_cell_deconvolution,
    "Survival Analysis": R.run_survival,
    # The four privacy dimensions are computed by R.run_privacy, one at a time.
}

#: Settings that do not change the metric values, left out of the fingerprint of saved values.
_NOT_IN_FINGERPRINT = {"output_dir", "on_error", "resume", "weights", "scenarios", "collapse_dims",
                       "name_map", "name_pattern"}


def _describe_input(value: Any) -> Any:
    """A JSON-serializable identity of a setting or an input: files by size and modification
    time, DataFrames by a hash of their content."""
    if isinstance(value, pd.DataFrame):
        return {"dataframe": int(pd.util.hash_pandas_object(value, index=True).sum() % (2 ** 61)),
                "shape": list(value.shape)}
    if isinstance(value, (str, os.PathLike)) and os.path.isfile(value):
        st = os.stat(value)
        return {"file": os.path.abspath(value), "size": st.st_size, "mtime": int(st.st_mtime)}
    if isinstance(value, Mapping):
        return {str(k): _describe_input(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_describe_input(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return repr(value)

def phenotype_list(values) -> str:
    return ", ".join(map(str, values))


#: Dimensions that compare the two phenotype groups.
PHENOTYPE_DIMS = ("DGE", "GSEA", "Survival Analysis")


@dataclass
class BenchmarkResult:
    """Outputs of a benchmark run.

    Attributes:
        per_dim_values: dimension -> long table [Model, Seed, Value].
        metascore: dimension -> {method: mean rank} (lower = better).
        value_table: method x dimension, mean value over the seeds.
        rank_table: method x dimension, mean rank.
        composite: weighted pillar scores and ``Total`` (the meta-score), lowest first.
        dims_run: dimensions computed.
        dims_missing: dimensions requested but not computed (see ``errors``).
        errors: dimension -> reason it was not computed.
        report_paths: files written by ``write_report`` (filled by :func:`run_benchmark`).
    """
    per_dim_values: Dict[str, pd.DataFrame]
    metascore: Dict[str, Dict[str, float]]
    value_table: pd.DataFrame
    rank_table: pd.DataFrame
    composite: Optional[pd.DataFrame] = None
    dims_run: List[str] = field(default_factory=list)
    dims_missing: List[str] = field(default_factory=list)
    errors: Dict[str, str] = field(default_factory=dict)
    report_paths: Dict[str, str] = field(default_factory=dict)

    @property
    def ranking(self) -> Optional[pd.Series]:
        """Meta-score of every method, best (lowest) first."""
        return None if self.composite is None else self.composite["Total"].sort_values()

    @property
    def report_html(self) -> Optional[str]:
        """Path of the HTML report, once written."""
        return self.report_paths.get("report_html")


class BenchmarkRunner:
    """Run the automatic benchmark for one cohort."""

    def __init__(self, config: BenchmarkConfig):
        self.config = config
        self._default_seed = 0

    def _display_name(self, stem: str) -> str:
        """Map a parsed file stem to a display name via ``name_map`` (case-insensitive)."""
        s = str(stem)
        for disp, st in self.config.name_map.items():
            if st.lower() == s.lower() or disp.lower() == s.lower():
                return disp
        return s

    def _parse_name(self, name) -> Tuple[str, str, Optional[int]]:
        """Parse (dataset name, method display name, seed) from a dataset name or file name.

        Strips any directory and ``.csv`` extension, then applies ``config.name_pattern``.
        Returns ``seed=None`` without a trailing ``_<int>`` (single seed).
        """
        base = os.path.basename(str(name))
        if base.lower().endswith(".csv"):
            base = base[:-4]
        m = re.match(self.config.name_pattern, base)
        if m and m.groupdict().get("seed") is not None:
            return base, self._display_name(m.group("method")), int(m.group("seed"))
        return base, self._display_name(base), None

    def _candidate(self, name, data) -> Candidate:
        base, method, seed = self._parse_name(name)
        return Candidate(method=method, seed=seed if seed is not None else self._default_seed,
                         data=data, name=base)

    def _candidates(self, datasets) -> List[Candidate]:
        """Normalise ``datasets`` into a list of :class:`Candidate`.

        Accepts:

        - a directory (str): its ``*.csv`` files, except those whose name contains
          "original" or "metadata";
        - a glob pattern (str);
        - a mapping ``{name: path or DataFrame}``;
        - a list of ``Candidate``, ``{"method", "seed", "data"}`` dicts, ``{"name", "data"}``
          dicts or paths.

        Method and seed are parsed from each name with ``config.name_pattern``
        (``gaussiancopula_0`` -> Gaussian Copula, seed 0).
        """
        if isinstance(datasets, str):
            if os.path.isdir(datasets):
                paths = sorted(glob.glob(os.path.join(datasets, "*.csv")))
            else:
                paths = sorted(glob.glob(datasets))
            paths = [p for p in paths
                     if not any(k in os.path.basename(p).lower() for k in ("original", "metadata"))]
            if not paths:
                raise FileNotFoundError(f"No synthetic dataset (CSV) found in '{datasets}'.")
            datasets = paths

        out: List[Candidate] = []
        if isinstance(datasets, dict):
            for name, data in datasets.items():
                out.append(self._candidate(name, data))
        else:
            for i, item in enumerate(datasets):
                if isinstance(item, Candidate):
                    out.append(item)
                elif isinstance(item, dict) and "method" in item and "seed" in item:
                    out.append(Candidate(item["method"], int(item["seed"]), item["data"], item.get("name")))
                elif isinstance(item, dict):
                    data = item.get("data", item.get("path"))
                    out.append(self._candidate(item.get("name", data), data))
                elif isinstance(item, str):
                    out.append(self._candidate(item, item))
                elif isinstance(item, pd.DataFrame):
                    out.append(Candidate(f"dataset_{i}", self._default_seed, item, f"dataset_{i}"))
                else:
                    raise TypeError(f"Unsupported dataset item: {type(item)}")
        keys = [c.stem_key for c in out]
        duplicated = sorted({k for k in keys if keys.count(k) > 1})
        if duplicated:
            raise ValueError(f"Several synthetic datasets are named {duplicated} (method_seed); a name "
                             "without a seed counts as seed 0. Rename them so that each is unique.")
        return out

    def _check_inputs(self, original: pd.DataFrame, dims: List[str]) -> None:
        """Fail early, before any long computation, on a column the selected metrics need."""
        cfg = self.config
        cols = set(original.columns)
        cfg.resolve_columns(original.columns)
        if any(d in PHENOTYPE_DIMS for d in dims):
            if cfg.phenotype_source_col not in cols:
                raise ValueError(
                    f"phenotype_source_col '{cfg.phenotype_source_col}' is not a column of the original "
                    f"data; it is needed by {[d for d in dims if d in PHENOTYPE_DIMS]}.")
            values = original[cfg.phenotype_source_col]
            for group, members in ((cfg.label_values[0], cfg.responder_values),
                                   (cfg.label_values[1], cfg.progressor_values)):
                n = int(values.isin(list(members)).sum())
                if n < 2:
                    raise ValueError(
                        f"Group '{group}' ({phenotype_list(members)}) has {n} patient(s) in column "
                        f"'{cfg.phenotype_source_col}' of the original data; its values are "
                        f"{sorted(map(str, values.dropna().unique()))[:10]}. Set responder_values "
                        "and progressor_values.")
        if "Survival Analysis" in dims:
            absent = [c for ep in cfg.survival_endpoints for c in ep if c not in cols]
            if absent:
                raise ValueError(f"Survival columns {absent} are not columns of the original data; "
                                 "set survival_endpoints.")
        if any(d in ("GSEA", "ssGSEA") for d in dims) and not os.path.isfile(str(cfg.gene_set)):
            raise FileNotFoundError(f"gene_set not found: {cfg.gene_set}")
        weights = dict(zip(PILLARS, cfg.weights))
        evaluated = {p for p, pdims in PILLARS.items() if any(d in pdims for d in dims)}
        if sum(weights[p] for p in evaluated) <= 0:
            raise ValueError(f"The weights of the evaluated pillars ({sorted(evaluated)}) sum to zero.")
        if "Cell Deconvolution" in dims and cfg.cibersortx is None:
            raise ValueError("Cell deconvolution needs the CIBERSORTx results: set cibersortx= "
                             "(a directory or a mapping {'original': path, <dataset name>: path}).")

    def run(
        self,
        original_data: Union[str, pd.DataFrame],
        datasets: Union[str, Mapping[str, Any], Sequence[Any]],
        metrics: Union[None, str, Iterable[str]] = None,
        seed: int = 0,
    ) -> BenchmarkResult:
        """Compute the selected metrics and build the rank-derived meta-score.

        Args:
            original_data: Original dataset (CSV path or DataFrame).
            datasets: Synthetic datasets (see :meth:`_candidates`).
            metrics: Metrics to compute: ``None``/``"all"``, a group (``"fidelity"``,
                ``"utility"``, ``"privacy"``), metric names (``"f1_gcs"``, ``"survival"``, ...,
                see ``config.METRICS``) or a list of these.
            seed: Seed of the datasets whose name carries none.

        Returns:
            BenchmarkResult. With ``config.on_error="warn"``, a metric that fails is reported
            in ``errors`` and left out of the meta-score.
        """
        self._default_seed = seed
        dims = resolve_metrics(metrics)
        original = load_frame(original_data, self.config.id_column)
        if isinstance(original.index, pd.RangeIndex):
            print(f"[autobenchmark] id_column '{self.config.id_column}' is not a column of the original "
                  "data: patients are identified by row. Set id_column if the data has an ID column, "
                  "otherwise it is treated as a clinical feature.", flush=True)
        candidates = self._candidates(datasets)
        self._check_inputs(original, dims)

        per_dim_values: Dict[str, pd.DataFrame] = {}
        errors: Dict[str, str] = {}
        cache: dict = {}

        # every metric is saved as soon as it is computed; with config.resume, a later run with
        # the same inputs and settings reads the saved metrics back instead of computing them
        values_dir = os.path.join(self.config.output_dir, "_work", "values")
        os.makedirs(values_dir, exist_ok=True)
        fingerprint = self._fingerprint(original_data, candidates)
        fp_path = os.path.join(values_dir, "fingerprint.json")
        reuse = False
        if self.config.resume and os.path.exists(fp_path):
            with open(fp_path) as fh:
                reuse = json.load(fh) == fingerprint
            if not reuse:
                print("[autobenchmark] the saved metric values were computed with other inputs or "
                      "settings: every metric is computed again.", flush=True)
        if not reuse:
            for old in glob.glob(os.path.join(values_dir, "*.csv")):
                os.remove(old)
        with open(fp_path, "w") as fh:
            json.dump(fingerprint, fh, indent=1)

        def saved(dim):
            return os.path.join(values_dir, re.sub(r"[^A-Za-z0-9]+", "_", dim).strip("_") + ".csv")

        def load(dim):
            if reuse and os.path.exists(saved(dim)):
                df = pd.read_csv(saved(dim))
                print(f"[autobenchmark] {dim}: loaded from {saved(dim)}", flush=True)
                return df
            return None

        def record(dim, df):
            if df is None or df.empty or df["Value"].isna().all():
                errors[dim] = "no value was computed"
                return
            per_dim_values[dim] = df
            df[["Model", "Seed", "Value"]].to_csv(saved(dim), index=False)
            means = df.groupby("Model", sort=False)["Value"].mean()
            print(f"[autobenchmark] {dim}: " + ", ".join(f"{m} {v:.4f}" for m, v in means.items()), flush=True)

        def fail(names, exc):
            if self.config.on_error == "raise":
                raise exc
            detail = "".join(traceback.format_exception_only(type(exc), exc)).strip()
            for name in names:
                errors[name] = detail
            print(f"[autobenchmark] {', '.join(names)} failed: {detail}", flush=True)

        for dim in dims:
            df = load(dim)
            if df is not None:
                per_dim_values[dim] = df
                continue
            print(f"[autobenchmark] {dim} ...", flush=True)
            try:
                if dim in PRIVACY_DIMS:
                    record(dim, R.run_privacy(original, candidates, self.config, [dim]).get(dim))
                else:
                    record(dim, DIMENSION_RUNNERS[dim](original, candidates, self.config, cache=cache))
            except Exception as exc:
                fail([dim], exc)

        metascore = build_metascore(per_dim_values, collapse_dims=self.config.collapse_dims)
        composite = composite_scores(metascore, self.config.weights) if metascore else None
        return BenchmarkResult(
            per_dim_values=per_dim_values,
            metascore=metascore,
            value_table=self._wide(per_dim_values, "Value"),
            rank_table=pd.DataFrame(metascore),
            composite=composite,
            dims_run=[d for d in dims if d in per_dim_values],
            dims_missing=[d for d in dims if d not in per_dim_values],
            errors=errors,
        )

    def _fingerprint(self, original_data: Any, candidates: List[Candidate]) -> Dict[str, Any]:
        """Identity of the inputs and of the settings that change the metric values."""
        settings = {f.name: _describe_input(getattr(self.config, f.name))
                    for f in fields(self.config) if f.name not in _NOT_IN_FINGERPRINT}
        datasets = {c.stem_key: _describe_input(c.data) for c in candidates}
        text = json.dumps({"original": _describe_input(original_data), "datasets": datasets,
                           "settings": settings}, sort_keys=True, default=repr)
        return {"sha256": hashlib.sha256(text.encode()).hexdigest(),
                "datasets": sorted(datasets)}

    @staticmethod
    def _wide(per_dim_values: Dict[str, pd.DataFrame], col: str) -> pd.DataFrame:
        return pd.DataFrame({dim: df.groupby("Model")[col].mean() for dim, df in per_dim_values.items()})


def run_benchmark(
    original: Union[str, pd.DataFrame],
    synthetic: Union[str, Mapping[str, Any], Sequence[Any]],
    metrics: Union[None, str, Iterable[str]] = "all",
    config: Optional[BenchmarkConfig] = None,
    seed: int = 0,
    **settings: Any,
) -> BenchmarkResult:
    """Benchmark synthetic datasets against the original data in one call.

    Computes the selected metrics, ranks the datasets into the rank-derived meta-score and
    writes the report (``report.html``, ``REPORT.md`` and the tables) to ``output_dir``.

    Args:
        original: Original dataset (CSV path or DataFrame).
        synthetic: Synthetic datasets: a directory of CSV files, a glob pattern, a mapping
            ``{name: path or DataFrame}`` or a list. Names such as ``gaussiancopula_0`` give
            the method and the seed.
        metrics: ``"all"`` (default), a group (``"fidelity"``, ``"utility"``, ``"privacy"``),
            metric names (``"univariate"``, ``"bivariate"``, ``"network"``, ``"f1_gcs"``,
            ``"f1_pcs"``, ``"ssgsea"``, ``"cell_deconvolution"``, ``"survival"``,
            ``"singling_out_uni"``, ``"singling_out_multi"``, ``"linkability"``,
            ``"inference"``) or a list of these.
        config: A :class:`BenchmarkConfig`; ``settings`` override its fields.
        seed: Seed of the datasets whose name carries none.
        **settings: Any field of :class:`BenchmarkConfig`, e.g. ``gene_start_column``,
            ``phenotype_source_col``, ``survival_endpoints``, ``cibersortx``,
            ``privacy_control``, ``output_dir``.

    Returns:
        BenchmarkResult, with ``ranking``, ``errors`` and ``report_html``.

    Example:
        >>> res = run_benchmark("original.csv", "synthetic/", metrics=["f1_gcs", "survival"],
        ...                     output_dir="benchmark")
        >>> res.ranking
    """
    from dataclasses import replace

    from .report import write_report

    config = replace(config, **settings) if config is not None else BenchmarkConfig(**settings)
    dims = resolve_metrics(metrics)
    # Without CIBERSORTx results, a metric group ("all", "utility") runs without Cell
    # Deconvolution; naming cell_deconvolution explicitly requires the results.
    items = [] if metrics is None else ([metrics] if isinstance(metrics, str) else list(metrics))
    explicit = any(str(m).strip().lower() in ("cell_deconvolution", "cell deconvolution") for m in items)
    skipped = not explicit and "Cell Deconvolution" in dims and config.cibersortx is None
    if skipped:
        dims.remove("Cell Deconvolution")
        print("[autobenchmark] Cell Deconvolution left out: no CIBERSORTx results (cibersortx=).", flush=True)
    result = BenchmarkRunner(config).run(original, synthetic, metrics=dims, seed=seed)
    if skipped:
        result.dims_missing.append("Cell Deconvolution")
        result.errors["Cell Deconvolution"] = "no CIBERSORTx results (cibersortx=)"
    result.report_paths = write_report(result, config)
    print(f"[autobenchmark] report: {result.report_html}", flush=True)
    return result

"""
Co-expression network preservation between original and synthetic transcriptomes.

A weighted gene co-expression network (WGCNA) is built on the original data and used as
the reference for every synthetic dataset. Three metrics are reported:

* ``Zsummary_norm``: median Z-summary of module preservation (WGCNA ``modulePreservation``)
  over the reference modules, divided by the median Z-summary of the original data
  compared with itself and truncated to [0, 1]. 1 means the synthetic data preserve the
  modules as well as the original data preserve their own.
* ``ARI``: adjusted Rand index between the reference modules and the modules of a network
  built on the synthetic data with the reference soft-thresholding power.
* ``TPR``: fraction of the reference's strongest edges (top ``edge_fraction`` of gene pairs
  by topological overlap) also among the synthetic network's strongest edges. Both edge
  sets have the same size, so precision, recall and F1 coincide; chance level is
  ``edge_fraction``.

WGCNA runs in R through rpy2 (R with the WGCNA package must be installed).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence, Tuple, Union

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.colors import TwoSlopeNorm
from sklearn.metrics import adjusted_rand_score

from synomicsbench.metrics.fidelity.visualization import DATASET_COLORS
from synomicsbench.utils.monitoring import set_logger

NETWORK_METRICS: Tuple[str, ...] = ("Zsummary_norm", "ARI", "TPR")
R_SCRIPT = Path(__file__).resolve().parent / "r" / "wgcna_network.R"
#: grey holds the unassigned genes, gold is WGCNA's random reference module
NON_MODULES = ("grey", "gold")


# ---------------------------------------------------------------------------
# Expression preparation
# ---------------------------------------------------------------------------

def sanitize_nonfinite(expr: pd.DataFrame) -> pd.DataFrame:
    """Replace +/-inf by the finite extremes of the same gene and NaN by its median.

    Must run before quantile normalisation, which would otherwise spread a single
    infinity to the top-ranked gene of every sample.
    """
    v = expr.to_numpy(dtype=float)
    bad = ~np.isfinite(v)
    if not bad.any():
        return expr
    v = v.copy()
    for j in np.where(bad.any(axis=0))[0]:
        col = v[:, j]
        finite = col[np.isfinite(col)]
        hi = finite.max() if finite.size else 0.0
        lo = finite.min() if finite.size else 0.0
        col[np.isposinf(col)] = hi
        col[np.isneginf(col)] = lo
        col[np.isnan(col)] = np.median(finite) if finite.size else 0.0
        v[:, j] = col
    return pd.DataFrame(v, index=expr.index, columns=expr.columns)


def collapse_identical_columns(expr: pd.DataFrame) -> pd.DataFrame:
    """Keep the first of every group of genes with identical expression vectors.

    Identical columns (e.g. repeat families mapped to distinct symbols) distort the
    scale-free fit used to choose the soft-thresholding power.
    """
    keep = ~expr.T.duplicated(keep="first")
    return expr.loc[:, keep.values]


def quantile_normalize_samples(expr: pd.DataFrame) -> pd.DataFrame:
    """Give every sample the across-sample mean distribution of sorted expression values.

    Rank based (ties averaged), so invariant to a global additive constant.
    """
    if not np.isfinite(expr.to_numpy(dtype=float)).all():
        raise ValueError("quantile_normalize_samples: non-finite input; call sanitize_nonfinite() first")
    ranked = expr.rank(axis=1, method="average")
    mean_sorted = np.sort(expr.values, axis=1).mean(axis=0)
    rank_positions = np.arange(1, expr.shape[1] + 1)
    out = np.empty_like(expr.values, dtype=float)
    for i in range(expr.shape[0]):
        out[i] = np.interp(ranked.values[i], rank_positions, mean_sorted)
    return pd.DataFrame(out, index=expr.index, columns=expr.columns)


class NetworkPreservation:
    """
    Co-expression network preservation of synthetic transcriptomes (WGCNA).

    The reference network is built once on the original data with :meth:`build_reference`;
    :meth:`evaluate` then scores any number of synthetic datasets against it.

    Expression matrices are samples x genes. With ``log_transform=True`` they are taken as
    TPM-like values: clipped at 0, log2(x + 1), and genes expressed (> 0) in fewer than
    ``min_frac_expressed`` of the original samples are dropped. Otherwise they must already
    be on a log scale. The reference keeps the ``n_genes`` genes with the largest median
    absolute deviation, after removing identical and constant genes; every dataset is then
    quantile-normalised across samples.

    Args:
        output_dir (str): Directory for the reference modules, metadata and log.
        n_genes (int): Number of most variable genes in the network.
        n_permutations (int): Permutations of ``modulePreservation``.
        edge_fraction (float): Fraction of gene pairs kept as strongest edges for the TPR.
        log_transform (bool): Apply clip(0) + log2(x + 1) and the detection filter.
        min_frac_expressed (float): Detection filter of the original genes (log_transform only).
        threads (int): WGCNA threads (1 runs single-threaded).
        seed (int): Seed of the module detection and of the preservation permutations.
        max_module_size (int): Largest module size scored by ``modulePreservation``.
        logger_name (str): Logger name.
    """

    def __init__(
        self,
        output_dir: str,
        n_genes: int = 10_000,
        n_permutations: int = 200,
        edge_fraction: float = 0.05,
        log_transform: bool = False,
        min_frac_expressed: float = 0.25,
        threads: int = 8,
        seed: int = 42,
        max_module_size: int = 1000,
        logger_name: str = "NetworkPreservation",
    ) -> None:
        if not 0.0 < edge_fraction < 1.0:
            raise ValueError("edge_fraction must be in (0, 1).")
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        self.logger = set_logger(logger_name=logger_name, output_path=self.output_dir)
        self.n_genes = n_genes
        self.n_permutations = n_permutations
        self.edge_fraction = edge_fraction
        self.log_transform = log_transform
        self.min_frac_expressed = min_frac_expressed
        self.threads = threads
        self.seed = seed
        self.max_module_size = max_module_size

        self._r = None
        self.genes: Optional[List[str]] = None
        self.reference: Optional[pd.DataFrame] = None
        self.beta: Optional[int] = None
        self.modules: Optional[pd.Series] = None
        self.reference_edges: Optional[np.ndarray] = None
        self.self_median_zsummary: Optional[float] = None
        self.module_zsummary: Optional[pd.DataFrame] = None

    # ------------------------------------------------------------------
    # R bridge
    # ------------------------------------------------------------------

    def _wgcna(self):
        """rpy2 handle with the WGCNA routines loaded (started on first use)."""
        if self._r is None:
            try:
                import rpy2.robjects as robjects
            except ImportError as exc:  # pragma: no cover - depends on the environment
                raise ImportError("NetworkPreservation needs rpy2 and R with the WGCNA package.") from exc
            try:
                robjects.r["source"](str(R_SCRIPT))
            except Exception as exc:  # pragma: no cover - depends on the environment
                raise RuntimeError(
                    "Could not load WGCNA in R. Install it with "
                    "BiocManager::install(c('impute', 'preprocessCore', 'GO.db')); install.packages('WGCNA')."
                ) from exc
            if self.threads >= 2:
                robjects.r["enableWGCNAThreads"](nThreads=self.threads)
            else:
                robjects.r["disableWGCNAThreads"]()
            self._r = robjects
        return self._r

    def _r_matrix(self, expr: pd.DataFrame):
        """samples x genes numeric R matrix with dimnames."""
        ro = self._wgcna()
        m = ro.r["matrix"](ro.FloatVector(expr.to_numpy(dtype=float).ravel(order="F")),
                           nrow=expr.shape[0], ncol=expr.shape[1])
        m = ro.r["colnames<-"](m, ro.StrVector([str(g) for g in expr.columns]))
        return ro.r["rownames<-"](m, ro.StrVector([str(s) for s in expr.index]))

    def _modules(self, expr: pd.DataFrame) -> pd.Series:
        ro = self._wgcna()
        colors = ro.r["sb_modules"](self._r_matrix(expr), self.beta, self.seed)
        return pd.Series(list(colors), index=expr.columns, name="moduleColor")

    def _top_edges(self, expr: pd.DataFrame) -> np.ndarray:
        ro = self._wgcna()
        return np.asarray(ro.r["sb_top_edges"](self._r_matrix(expr), self.beta, self.edge_fraction),
                          dtype=np.int64)

    def _module_preservation(self, test: pd.DataFrame) -> pd.DataFrame:
        ro = self._wgcna()
        res = ro.r["sb_module_preservation"](
            self._r_matrix(self.reference), self._r_matrix(test),
            ro.StrVector(list(self.modules.values)), self.n_permutations, self.seed,
            self.max_module_size,
        )
        cols = ["module", "moduleSize", "Zsummary", "Zdensity", "Zconnectivity"]
        return pd.DataFrame({c: list(res.rx2(c)) for c in cols})

    @staticmethod
    def _median_zsummary(stats: pd.DataFrame) -> float:
        keep = ~stats["module"].isin(NON_MODULES)
        return float(np.nanmedian(stats.loc[keep, "Zsummary"].astype(float)))

    # ------------------------------------------------------------------
    # Expression preparation
    # ------------------------------------------------------------------

    def _log(self, expr: pd.DataFrame) -> pd.DataFrame:
        return np.log2(expr.clip(lower=0) + 1.0)

    def prepare_reference(self, original_expr: pd.DataFrame) -> pd.DataFrame:
        """
        Frozen gene space and quantile-normalised matrix of the original data.

        Args:
            original_expr (pd.DataFrame): Original expression, samples x genes.

        Returns:
            pd.DataFrame: Quantile-normalised samples x ``n_genes`` matrix (genes by
            decreasing median absolute deviation).
        """
        expr = sanitize_nonfinite(original_expr.astype(float))
        if self.log_transform:
            expr = self._log(expr)
            keep = (expr > 0).mean(axis=0) >= self.min_frac_expressed
            expr = expr.loc[:, keep]
        expr = collapse_identical_columns(expr)
        expr = expr.loc[:, expr.var(axis=0) > 0]
        if expr.shape[1] > self.n_genes:
            mad = (expr - expr.median(axis=0)).abs().median(axis=0)
            expr = expr.loc[:, mad.sort_values(ascending=False).head(self.n_genes).index]
        self.genes = [str(g) for g in expr.columns]
        return quantile_normalize_samples(expr)

    def prepare_synthetic(self, synthetic_expr: pd.DataFrame) -> pd.DataFrame:
        """
        Put a synthetic dataset on the reference gene space and scale.

        Constant genes get a tiny jitter (N(0, 1e-9), seed 42) so that the gene space stays
        identical to the reference.

        Args:
            synthetic_expr (pd.DataFrame): Synthetic expression, samples x genes.

        Returns:
            pd.DataFrame: Quantile-normalised samples x reference genes matrix.

        Raises:
            RuntimeError: If the reference was not built.
            ValueError: If reference genes are missing.
        """
        if self.genes is None:
            raise RuntimeError("Call build_reference() first.")
        df = sanitize_nonfinite(synthetic_expr.astype(float))
        if self.log_transform:
            df = self._log(df)
        missing = [g for g in self.genes if g not in df.columns]
        if missing:
            raise ValueError(f"{len(missing)} reference genes are absent from the synthetic data, "
                             f"e.g. {missing[:5]}.")
        df = df.loc[:, self.genes].copy()
        constant = df.var(axis=0) <= 0
        if constant.any():
            rng = np.random.default_rng(42)
            for g in df.columns[constant]:
                df[g] = df[g].values + rng.normal(0, 1e-9, size=df.shape[0])
        return quantile_normalize_samples(df)

    # ------------------------------------------------------------------
    # Reference and evaluation
    # ------------------------------------------------------------------

    def build_reference(self, original_expr: pd.DataFrame) -> Dict[str, object]:
        """
        Build the reference network of the original data.

        Chooses the soft-thresholding power, detects the modules, keeps the strongest
        edges and computes the preservation of the original data with itself (the
        normalisation constant of ``Zsummary_norm``). Writes ``reference_modules.csv`` and
        ``reference_meta.json`` in ``output_dir``.

        Args:
            original_expr (pd.DataFrame): Original expression, samples x genes.

        Returns:
            dict: Reference metadata (beta and its selection rule, number of modules, ...).
        """
        self.reference = self.prepare_reference(original_expr)
        ro = self._wgcna()
        pick = ro.r["sb_pick_beta"](self._r_matrix(self.reference))
        self.beta = int(pick.rx2("beta")[0])
        self.modules = self._modules(self.reference)
        self.reference_edges = self._top_edges(self.reference)
        self_stats = self._module_preservation(self.reference)
        self.self_median_zsummary = self._median_zsummary(self_stats)

        sizes = self.modules.value_counts()
        meta = {
            "n_samples": int(self.reference.shape[0]),
            "n_genes": int(self.reference.shape[1]),
            "beta": self.beta,
            "beta_rule": str(pick.rx2("rule")[0]),
            "beta_rsq": float(pick.rx2("rsq")[0]),
            "beta_mean_k": float(pick.rx2("mean_k")[0]),
            "n_modules": int(sum(1 for m in sizes.index if m not in NON_MODULES)),
            "n_grey": int(sizes.get("grey", 0)),
            "self_median_zsummary": self.self_median_zsummary,
        }
        self.modules.rename_axis("gene").reset_index().to_csv(
            os.path.join(self.output_dir, "reference_modules.csv"), index=False)
        with open(os.path.join(self.output_dir, "reference_meta.json"), "w") as fh:
            json.dump(meta, fh, indent=2)
        self.logger.info(f"Reference network: {meta}")
        return meta

    def evaluate(
        self,
        dataset_dict: Mapping[str, pd.DataFrame],
        metrics: Union[str, Sequence[str], None] = None,
    ) -> pd.DataFrame:
        """
        Score synthetic datasets against the reference network.

        Args:
            dataset_dict (Mapping[str, pd.DataFrame]): Dataset name -> synthetic expression
                (samples x genes, same scale as the original given to :meth:`build_reference`).
            metrics (str | Sequence[str] | None): Any of Zsummary_norm, ARI, TPR; None for all.

        Returns:
            pd.DataFrame: One row per dataset (index "Dataset"), one column per metric, plus
            ``median_Zsummary`` when Zsummary_norm is requested. The per-module Z-summary
            of every dataset is kept in ``self.module_zsummary``.

        Raises:
            RuntimeError: If the reference was not built.
            ValueError: If a metric name is unknown.
        """
        if self.reference is None:
            raise RuntimeError("Call build_reference() first.")
        if metrics is None:
            names = list(NETWORK_METRICS)
        elif isinstance(metrics, str):
            names = [metrics]
        else:
            names = list(metrics)
        unknown = [m for m in names if m not in NETWORK_METRICS]
        if unknown:
            raise ValueError(f"Unknown metric(s) {unknown}. Valid metrics: {list(NETWORK_METRICS)}.")

        rows, per_module = {}, []
        for name, data in dataset_dict.items():
            syn = self.prepare_synthetic(data)
            row: Dict[str, float] = {}
            if "Zsummary_norm" in names:
                stats = self._module_preservation(syn)
                med = self._median_zsummary(stats)
                row["Zsummary_norm"] = float(np.clip(med / self.self_median_zsummary, 0, 1))
                row["median_Zsummary"] = med
                per_module.append(stats.assign(Dataset=name))
            if "ARI" in names:
                row["ARI"] = float(adjusted_rand_score(self.modules.values, self._modules(syn).values))
            if "TPR" in names:
                edges = self._top_edges(syn)
                row["TPR"] = len(np.intersect1d(edges, self.reference_edges)) / max(1, len(self.reference_edges))
            rows[name] = row
            self.logger.info(f"{name}: {row}")

        if per_module:
            self.module_zsummary = pd.concat(per_module, ignore_index=True)
        cols = [m for m in names] + (["median_Zsummary"] if "Zsummary_norm" in names else [])
        out = pd.DataFrame.from_dict(rows, orient="index")[cols]
        out.index.name = "Dataset"
        return out

    # ------------------------------------------------------------------
    # Figure
    # ------------------------------------------------------------------

    def plot_module_heatmap(
        self,
        module_zsummary: Optional[pd.DataFrame] = None,
        vmax: Optional[float] = None,
        figsize: Optional[Tuple[float, float]] = None,
    ) -> Tuple[plt.Figure, pd.DataFrame]:
        """
        Heatmap of the Z-summary of every reference module (columns, largest first) in
        every synthetic dataset (rows).

        The colour scale is centred on 10, the conventional threshold of strong
        preservation: warm colours Z > 10, blue colours lower values (Z < 2: no evidence of
        preservation). Grey and gold are not modules and are left out.

        Args:
            module_zsummary (pd.DataFrame | None): Per-module table of :meth:`evaluate`;
                defaults to ``self.module_zsummary``.
            vmax (float | None): Upper end of the colour scale; defaults to the 99th
                percentile of the values (at least 11).
            figsize (tuple[float, float] | None): Figure size.

        Returns:
            tuple[matplotlib.figure.Figure, pd.DataFrame]: (figure, dataset x module matrix).
        """
        d = self.module_zsummary if module_zsummary is None else module_zsummary
        if d is None or d.empty:
            raise RuntimeError("No per-module Z-summary: run evaluate() with Zsummary_norm first.")
        d = d[~d["module"].isin(NON_MODULES)]
        order = d.groupby("module")["moduleSize"].first().sort_values(ascending=False).index.tolist()
        datasets = list(dict.fromkeys(d["Dataset"]))
        mat = d.pivot_table(index="Dataset", columns="module", values="Zsummary").reindex(
            index=datasets, columns=order)
        if vmax is None:
            vmax = max(11.0, float(np.nanpercentile(mat.values, 99)))
        if figsize is None:
            figsize = (max(6.0, 0.35 * len(order) + 2.5), max(2.5, 0.45 * len(datasets) + 1.5))

        fig, ax = plt.subplots(figsize=figsize)
        sns.heatmap(mat, ax=ax, cmap="RdYlBu_r", norm=TwoSlopeNorm(vcenter=10, vmin=0, vmax=vmax),
                    linewidths=0.3, linecolor="white",
                    cbar_kws={"label": "$Z_{summary}$", "ticks": [0, 2, 10, round(vmax)]})
        sizes = d.groupby("module")["moduleSize"].first()
        ax.set_xticks(np.arange(len(order)) + 0.5)
        ax.set_xticklabels([f"{m} ({int(sizes[m])})" for m in order], rotation=90, fontsize=7)
        ax.set_xlabel("Reference module (gene count), largest first")
        ax.set_ylabel("")
        for t in ax.get_yticklabels():
            t.set_color(DATASET_COLORS.get(t.get_text(), "black"))
            t.set_fontweight("bold")
        fig.tight_layout()
        return fig, mat

"""
Reusable ``DataTransformer`` cache for the ctgan-based synthesizers.

``CTGAN.fit()`` and ``TVAE.fit()`` both build their preprocessing transformer from
scratch on every call::

    self._transformer = DataTransformer()      # ctgan/synthesizers/ctgan.py
    self._transformer.fit(train_data, discrete_columns)
    train_data = self._transformer.transform(train_data)

``DataTransformer.fit`` walks the columns sequentially, fitting one
``BayesianGaussianMixture`` per continuous column (via ``rdt.ClusterBasedNormalizer``).
Measured at roughly 0.09 s/column, which is ~28 minutes for an 18.8k-column cohort and
longer for wider ones -- repeated identically for every seed, every hyper-parameter
configuration and both synthesizers.

The fit is deterministic given the data: ``rdt`` seeds the mixture from a fixed
``INITIAL_FIT_STATE`` rather than the global NumPy RNG, so the CTGAN seed does not
influence it. Since the benchmark feeds one integrated dataset per cohort to every
method, a cohort needs exactly one transformer. Caching it is a pure speed-up: it does
not change the generated data, nor the meaning of the independent replicates.

The fit is also CPU-only, so building the cache in a CPU job moves that work off the
GPU queue entirely.

Typical use::

    # once per cohort, on CPU
    build_cache(data, discrete_columns, "cache/melanoma_transformer.pkl")

    # in every training run
    transformer, meta = load_cache(path, data, discrete_columns)
    with use_cached_transformer(wrap(transformer)):
        model.fit(data, discrete_columns=discrete_columns)
"""

from __future__ import annotations

import hashlib
import logging
import os
import pickle
import time
from contextlib import contextmanager, nullcontext
from typing import Any, Dict, Iterator, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

# Bump when the payload layout changes so stale caches are rejected rather than
# silently misread.
CACHE_VERSION = 1


class TransformerCacheMismatch(ValueError):
    """Raised when a cache does not match the data it is being loaded for.

    Never downgrade this to a warning-and-refit: a transformer fitted on different
    columns produces an ``output_info_list`` that disagrees with the data, which
    corrupts the synthetic output without raising anywhere.
    """


def _library_versions() -> Dict[str, str]:
    """Versions the fitted transformer's internals depend on."""
    import ctgan
    import rdt

    return {"ctgan": ctgan.__version__, "rdt": rdt.__version__}


def compute_fingerprint(data: pd.DataFrame, discrete_columns: Sequence[str]) -> str:
    """Fingerprint the exact inputs a fitted transformer is valid for.

    Covers column names *in order*, dtypes, the discrete-column set, the full data
    content and the ctgan/rdt versions. Content is included because the transformer
    depends on the values themselves -- ``rdt`` derives per-column random seeds from a
    hash of the column name plus its first rows.

    Args:
        data: The frame the transformer is (or was) fitted on.
        discrete_columns: Columns treated as discrete by the synthesizer.

    Returns:
        Hex sha256 digest.
    """
    h = hashlib.sha256()

    h.update(b"columns\0")
    for column in data.columns:
        h.update(str(column).encode("utf-8"))
        h.update(b"\0")

    h.update(b"dtypes\0")
    for dtype in data.dtypes:
        h.update(str(dtype).encode("utf-8"))
        h.update(b"\0")

    h.update(b"discrete\0")
    for column in sorted(str(c) for c in discrete_columns):
        h.update(column.encode("utf-8"))
        h.update(b"\0")

    h.update(b"content\0")
    h.update(np.ascontiguousarray(pd.util.hash_pandas_object(data, index=True).to_numpy()).tobytes())

    h.update(b"versions\0")
    for name, version in sorted(_library_versions().items()):
        h.update(f"{name}={version}\0".encode("utf-8"))

    return h.hexdigest()


class CachedDataTransformer:
    """Proxy around an already-fitted ``DataTransformer`` whose ``fit`` is a no-op.

    Every other attribute is delegated to the wrapped instance, so the synthesizers see
    the interface they expect (``output_dimensions``, ``output_info_list``,
    ``transform``, ``inverse_transform``, ...).

    Args:
        fitted: A fitted ``ctgan.data_transformer.DataTransformer``.
        transformed: Optional precomputed output of ``transform(data)``. When given,
            ``transform`` returns it directly and skips the recomputation too. Only
            valid for the same data the cache was fingerprinted against.
    """

    def __init__(self, fitted: Any, transformed: Optional[np.ndarray] = None) -> None:
        self._fitted = fitted
        self._transformed = transformed

    def fit(self, raw_data: Any = None, discrete_columns: Sequence[str] = ()) -> None:
        """No-op: the wrapped transformer is already fitted."""
        return None

    def transform(self, raw_data: Any) -> np.ndarray:
        if self._transformed is not None:
            return self._transformed
        return self._fitted.transform(raw_data)

    @property
    def wrapped(self) -> Any:
        """The underlying real ``DataTransformer``."""
        return self._fitted

    def __getattr__(self, name: str) -> Any:
        # Only reached for attributes not found on the proxy itself. Guard the lookup so
        # a half-initialised instance raises AttributeError rather than KeyError, which
        # is what copy/pickle protocols expect.
        try:
            fitted = object.__getattribute__(self, "_fitted")
        except AttributeError:
            raise AttributeError(name) from None
        return getattr(fitted, name)


def build_cache(
    data: pd.DataFrame,
    discrete_columns: Sequence[str],
    path: str,
    *,
    include_transformed: bool = False,
    logger: Optional[logging.Logger] = None,
) -> Tuple[Any, Dict[str, Any]]:
    """Fit a ``DataTransformer`` once and persist it with its fingerprint.

    Args:
        data: Integrated cohort data, exactly as passed to the synthesizer.
        discrete_columns: Discrete columns, from ``BaseSynthesizer.detect_discrete_columns``.
        path: Destination file.
        include_transformed: Also store ``transform(data)`` so training runs skip that
            step as well. Costs disk (order of hundreds of MB for a wide cohort).
        logger: Optional logger for progress.

    Returns:
        ``(fitted_transformer, meta)``.
    """
    from ctgan.data_transformer import DataTransformer

    log = logger or logging.getLogger(__name__)
    log.info("Fitting DataTransformer on %d rows x %d columns", data.shape[0], data.shape[1])

    started = time.time()
    transformer = DataTransformer()
    transformer.fit(data, discrete_columns)
    fit_seconds = time.time() - started
    log.info("DataTransformer fitted in %.1fs (output_dimensions=%d)", fit_seconds, transformer.output_dimensions)

    transformed = None
    transform_seconds = None
    if include_transformed:
        started = time.time()
        transformed = transformer.transform(data)
        transform_seconds = time.time() - started
        log.info("transform() computed in %.1fs (shape=%s)", transform_seconds, transformed.shape)

    meta: Dict[str, Any] = {
        "n_rows": int(data.shape[0]),
        "n_columns": int(data.shape[1]),
        "n_discrete_columns": len(list(discrete_columns)),
        "output_dimensions": int(transformer.output_dimensions),
        "fit_seconds": fit_seconds,
        "transform_seconds": transform_seconds,
        "includes_transformed": transformed is not None,
        "versions": _library_versions(),
    }

    payload = {
        "cache_version": CACHE_VERSION,
        "fingerprint": compute_fingerprint(data, discrete_columns),
        "transformer": transformer,
        "transformed": transformed,
        "meta": meta,
    }

    parent = os.path.dirname(os.path.abspath(path))
    os.makedirs(parent, exist_ok=True)
    with open(path, "wb") as handle:
        pickle.dump(payload, handle, protocol=pickle.HIGHEST_PROTOCOL)
    log.info("Wrote transformer cache to %s (%.1f MiB)", path, os.path.getsize(path) / 1048576)

    return transformer, meta


def load_cache(
    path: str,
    data: pd.DataFrame,
    discrete_columns: Sequence[str],
) -> Tuple[Any, Optional[np.ndarray], Dict[str, Any]]:
    """Load a cache and verify it matches the data it will be used for.

    Args:
        path: Cache file written by :func:`build_cache`.
        data: The data about to be fitted.
        discrete_columns: The discrete columns about to be used.

    Returns:
        ``(fitted_transformer, transformed_or_None, meta)``.

    Raises:
        FileNotFoundError: If the cache does not exist.
        TransformerCacheMismatch: If the cache was produced for different data,
            different columns, or different ctgan/rdt versions.
    """
    with open(path, "rb") as handle:
        payload = pickle.load(handle)

    found_version = payload.get("cache_version")
    if found_version != CACHE_VERSION:
        raise TransformerCacheMismatch(
            f"Transformer cache {path!r} has layout version {found_version!r}, "
            f"expected {CACHE_VERSION!r}. Rebuild it with build_cache()."
        )

    expected = compute_fingerprint(data, discrete_columns)
    if payload.get("fingerprint") != expected:
        meta = payload.get("meta", {})
        raise TransformerCacheMismatch(
            f"Transformer cache {path!r} does not match the data it is being loaded for.\n"
            f"  cache was built for : {meta.get('n_rows')} rows x {meta.get('n_columns')} columns, "
            f"{meta.get('n_discrete_columns')} discrete, versions={meta.get('versions')}\n"
            f"  data passed in      : {data.shape[0]} rows x {data.shape[1]} columns, "
            f"{len(list(discrete_columns))} discrete, versions={_library_versions()}\n"
            "Column order and cell values are both part of the fingerprint. "
            "Rebuild the cache for this cohort rather than reusing another one."
        )

    return payload["transformer"], payload.get("transformed"), payload["meta"]


@contextmanager
def use_cached_transformer(cached: CachedDataTransformer) -> Iterator[None]:
    """Make ctgan's synthesizers pick up ``cached`` instead of fitting a new transformer.

    ``ctgan.synthesizers.ctgan`` and ``ctgan.synthesizers.tvae`` both import
    ``DataTransformer`` by name at module level and instantiate it inside ``fit``, so
    rebinding the module-level name is enough to intercept it. The original bindings are
    always restored, including when the body raises.
    """
    import ctgan.synthesizers.ctgan as ctgan_module
    import ctgan.synthesizers.tvae as tvae_module

    modules = (ctgan_module, tvae_module)
    originals = {module: module.DataTransformer for module in modules}

    def factory(*args: Any, **kwargs: Any) -> CachedDataTransformer:
        return cached

    try:
        for module in modules:
            module.DataTransformer = factory
        yield
    finally:
        for module, original in originals.items():
            module.DataTransformer = original


def cache_context(
    path: Optional[str],
    data: pd.DataFrame,
    discrete_columns: Sequence[str],
    logger: Optional[logging.Logger] = None,
):
    """Context manager installing the cached transformer, or a no-op when ``path`` is None.

    Lets a synthesizer wrap its ``model.fit(...)`` call unconditionally.

    Args:
        path: Cache file, or None/empty to disable caching.
        data: Data about to be fitted.
        discrete_columns: Discrete columns about to be used.
        logger: Optional logger.

    Raises:
        TransformerCacheMismatch: If the cache does not match the data.
    """
    if not path:
        return nullcontext()

    log = logger or logging.getLogger(__name__)
    transformer, transformed, meta = load_cache(path, data, discrete_columns)
    log.info(
        "Reusing DataTransformer cache %s (output_dimensions=%d, saves ~%.1fs of fitting%s)",
        path,
        meta.get("output_dimensions", -1),
        meta.get("fit_seconds") or 0.0,
        ", transform() precomputed" if transformed is not None else "",
    )
    return use_cached_transformer(CachedDataTransformer(transformer, transformed))


def unwrap_transformer(model: Any) -> None:
    """Swap the proxy back out for the real transformer on a fitted model.

    Keeps saved ``CTGAN_model.pkl`` / ``TVAE_model.pkl`` files structurally identical to
    ones produced without the cache, so they stay loadable without synomicsbench on the
    path. CTGAN stores it as ``_transformer``, TVAE as ``transformer``.
    """
    for attribute in ("_transformer", "transformer"):
        current = getattr(model, attribute, None)
        if isinstance(current, CachedDataTransformer):
            setattr(model, attribute, current.wrapped)

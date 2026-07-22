"""
Tests for synomicsbench synthesizer modules.

Note: Some tests require optional dependencies and will be skipped if not available.
"""

import os
import numpy as np
import pandas as pd
import pytest


TEST_DATA_DIR = os.path.join(os.path.dirname(__file__), "test_data")


@pytest.fixture
def sample_data():
    np.random.seed(42)
    n = 50
    return pd.DataFrame({
        "id": [f"P{i:03d}" for i in range(n)],
        "age": np.random.randint(40, 80, n),
        "score": np.random.randn(n),
        "category": np.random.choice(["A", "B", "C"], n),
    })


@pytest.fixture
def sample_metadata():
    return {
        "columns": {
            "id": {"sdtype": "id"},
            "age": {"sdtype": "numerical"},
            "score": {"sdtype": "numerical"},
            "category": {"sdtype": "categorical"},
        }
    }


class TestBaseSynthesizer:
    """Tests for BaseSynthesizer class."""

    def test_import_base_synthesizer(self):
        from synomicsbench.synthesizer.BaseSynthesizer import BaseSynthesizer
        assert BaseSynthesizer is not None


class TestGaussianCopulaSynthesizer:
    """Tests for GaussianCopulasynthesizer class."""

    def test_import_gc(self):
        from synomicsbench.synthesizer.GaussianCopulasynthesizer import GaussianCopulasynthesizer
        assert GaussianCopulasynthesizer is not None


class TestCTGANSynthesizer:
    """Tests for CTGANSynthesizer class."""

    def test_import_ctgan(self):
        from synomicsbench.synthesizer.CTGANsynthesizer import CTGANsynthesizer
        assert CTGANsynthesizer is not None


class TestTVAESynthesizer:
    """Tests for TVAESynthesizer class."""

    def test_import_tvae(self):
        from synomicsbench.synthesizer.TVAEsynthesizer import TVAEsynthesizer
        assert TVAEsynthesizer is not None


class TestSynthpopSynthesizer:
    """Tests for SynthpopSynthesizer class."""

    def test_import_synthpop(self):
        try:
            from synomicsbench.synthesizer.Synthpopsynthesizer import SynthpopSynthesizer
            assert SynthpopSynthesizer is not None
        except (ImportError, RuntimeError, FileNotFoundError, ValueError) as e:
            pytest.skip(f"SynthpopSynthesizer tests skipped because R or rpy2 is not properly configured: {e}")



@pytest.fixture
def cache_data():
    """Small mixed-type frame, no id column (ctgan takes the feature matrix)."""
    rng = np.random.default_rng(0)
    n = 40
    return pd.DataFrame({
        **{f"g{i}": rng.normal(size=n) for i in range(6)},
        "sex": rng.choice(["M", "F"], n),
        "stage": rng.choice(["I", "II", "III"], n),
    })


@pytest.fixture
def cache_metadata(cache_data):
    """Flat {column: type} metadata, the form BaseSynthesizer.detect_discrete_columns reads."""
    return {
        col: ("dummy_categorical" if cache_data[col].dtype == object else "numerical")
        for col in cache_data.columns
    }


@pytest.fixture
def discrete_columns(cache_data):
    return [c for c in cache_data.columns if cache_data[c].dtype == object]


class TestTransformerCache:
    """Tests for the reusable DataTransformer cache."""

    def test_fingerprint_detects_relevant_changes(self, cache_data, discrete_columns):
        from synomicsbench.synthesizer.transformer_cache import compute_fingerprint

        base = compute_fingerprint(cache_data, discrete_columns)
        assert compute_fingerprint(cache_data, discrete_columns) == base

        reordered = cache_data[list(cache_data.columns[::-1])]
        assert compute_fingerprint(reordered, discrete_columns) != base

        edited = cache_data.copy()
        edited.loc[0, "g0"] = edited.loc[0, "g0"] + 1.0
        assert compute_fingerprint(edited, discrete_columns) != base

        assert compute_fingerprint(cache_data, discrete_columns[:1]) != base

    def test_build_load_roundtrip_matches_direct_fit(self, tmp_path, cache_data, discrete_columns):
        from ctgan.data_transformer import DataTransformer
        from synomicsbench.synthesizer.transformer_cache import build_cache, load_cache

        direct = DataTransformer()
        direct.fit(cache_data, discrete_columns)

        path = str(tmp_path / "cache.pkl")
        build_cache(cache_data, discrete_columns, path)
        loaded, transformed, meta = load_cache(path, cache_data, discrete_columns)

        assert loaded.output_dimensions == direct.output_dimensions
        assert loaded.output_info_list == direct.output_info_list
        assert meta["output_dimensions"] == direct.output_dimensions
        assert transformed is None  # not requested

    def test_include_transformed_returns_matrix(self, tmp_path, cache_data, discrete_columns):
        from synomicsbench.synthesizer.transformer_cache import build_cache, load_cache

        path = str(tmp_path / "cache.pkl")
        transformer, _ = build_cache(cache_data, discrete_columns, path, include_transformed=True)
        _, transformed, meta = load_cache(path, cache_data, discrete_columns)

        assert meta["includes_transformed"] is True
        assert transformed is not None
        np.testing.assert_array_equal(transformed, transformer.transform(cache_data))

    def test_load_rejects_mismatched_data(self, tmp_path, cache_data, discrete_columns):
        from synomicsbench.synthesizer.transformer_cache import (
            TransformerCacheMismatch,
            build_cache,
            load_cache,
        )

        path = str(tmp_path / "cache.pkl")
        build_cache(cache_data, discrete_columns, path)

        other = cache_data.copy()
        other.loc[0, "g0"] = other.loc[0, "g0"] + 5.0
        with pytest.raises(TransformerCacheMismatch):
            load_cache(path, other, discrete_columns)

        reordered = cache_data[list(cache_data.columns[::-1])]
        with pytest.raises(TransformerCacheMismatch):
            load_cache(path, reordered, discrete_columns)

    def test_context_manager_restores_even_on_error(self, tmp_path, cache_data, discrete_columns):
        import ctgan.synthesizers.ctgan as ctgan_module
        import ctgan.synthesizers.tvae as tvae_module
        from synomicsbench.synthesizer.transformer_cache import (
            CachedDataTransformer,
            build_cache,
            use_cached_transformer,
        )

        original_ctgan = ctgan_module.DataTransformer
        original_tvae = tvae_module.DataTransformer

        path = str(tmp_path / "cache.pkl")
        transformer, _ = build_cache(cache_data, discrete_columns, path)
        cached = CachedDataTransformer(transformer)

        with use_cached_transformer(cached):
            assert ctgan_module.DataTransformer() is cached
            assert tvae_module.DataTransformer() is cached
        assert ctgan_module.DataTransformer is original_ctgan
        assert tvae_module.DataTransformer is original_tvae

        with pytest.raises(RuntimeError):
            with use_cached_transformer(cached):
                raise RuntimeError("boom")
        assert ctgan_module.DataTransformer is original_ctgan
        assert tvae_module.DataTransformer is original_tvae

    @pytest.mark.parametrize("synth_name", ["ctgan", "tvae"])
    def test_cached_run_matches_uncached_run(
        self, tmp_path, cache_data, cache_metadata, discrete_columns, synth_name
    ):
        """The cache must not change generated data: the transformer fit is deterministic."""
        from synomicsbench.synthesizer.transformer_cache import build_cache

        if synth_name == "ctgan":
            from synomicsbench.synthesizer.CTGANsynthesizer import CTGANsynthesizer as Synth
        else:
            from synomicsbench.synthesizer.TVAEsynthesizer import TVAEsynthesizer as Synth

        path = str(tmp_path / "cache.pkl")
        build_cache(cache_data, discrete_columns, path)

        def run(cache_path, tag):
            synth = Synth(output_path=str(tmp_path / tag), metadata=cache_metadata)
            return synth.generate(
                data=cache_data,
                data_ids=list(cache_data.index),
                enforce_rounding=False,
                enforce_min_max=False,
                masking=False,
                n_samples=len(cache_data),
                seed=7,
                fit_params={"epochs": 2, "verbose": False, "cuda": False,
                            "transformer_cache": cache_path},
                output_filename="out.csv",
                save_index=False,
            )

        uncached = run(None, "uncached")
        cached = run(path, "cached")

        # postprocess() appends a Patient_ID column of random UUIDs, which differs on
        # every run independently of the transformer; compare the generated features.
        feature_columns = list(cache_data.columns)
        pd.testing.assert_frame_equal(uncached[feature_columns], cached[feature_columns])

    def test_saved_model_holds_real_transformer(
        self, tmp_path, cache_data, cache_metadata, discrete_columns
    ):
        """unwrap_transformer must swap the proxy back out before the model is saved."""
        from ctgan.data_transformer import DataTransformer
        from synomicsbench.synthesizer.CTGANsynthesizer import CTGANsynthesizer
        from synomicsbench.synthesizer.transformer_cache import CachedDataTransformer, build_cache

        path = str(tmp_path / "cache.pkl")
        build_cache(cache_data, discrete_columns, path)

        synth = CTGANsynthesizer(output_path=str(tmp_path / "run"), metadata=cache_metadata)
        synth.fit(cache_data, seed=7, epochs=2, verbose=False, cuda=False, transformer_cache=path)

        assert isinstance(synth.model._transformer, DataTransformer)
        assert not isinstance(synth.model._transformer, CachedDataTransformer)

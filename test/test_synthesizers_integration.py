import os
import shutil
import numpy as np
import pandas as pd
import pytest

from synomicsbench.processing.preprocessing import DataProcessor
from synomicsbench.processing.metadata import MetaData


N_PATIENTS = 15
N_GENES = 5
ORDINAL_FEATURES = ["Mstage", "Tx_Start_ECOG", "biopsyContext"]
OUTPUT_BASE = os.path.join(os.path.dirname(__file__), "_synth_test_outputs")


# ─── Shared data fixtures ─────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def toy_data():
    np.random.seed(0)
    data = {
        "Patient_ID": [f"P{i+1:02d}" for i in range(N_PATIENTS)],
        "Gender": np.random.choice(["M", "F"], N_PATIENTS),
        "Mstage": np.random.choice(["I", "II", "III", "IV"], N_PATIENTS),
        "Tx_Start_ECOG": np.random.choice([0, 1, 2], N_PATIENTS).astype(float),
        "biopsyContext": np.random.choice(["Primary", "Metastatic"], N_PATIENTS),
        "Age": np.random.randint(45, 80, N_PATIENTS).astype(float),
    }
    for i in range(1, N_GENES + 1):
        data[f"Gene_{i:02d}"] = np.random.normal(loc=5, scale=2, size=N_PATIENTS)

    df = pd.DataFrame(data)
    df.loc[2, "Age"] = np.nan
    df.loc[5, "Mstage"] = np.nan

    df_clean = DataProcessor.remove_unknown_entities(df, id_column="Patient_ID")
    df_clean = DataProcessor.remove_duplications(df_clean, axis=0).reset_index(drop=True)
    df_imputed = DataProcessor.mice_imputation(df_clean, iterations=5, n_estimators=50, add_indicators=True)
    return df_imputed


@pytest.fixture(scope="module")
def toy_metadata(toy_data):
    return MetaData.get_metadata(
        data=toy_data,
        ordinal_features=ORDINAL_FEATURES,
        threshold_unique_values=5,
    )


@pytest.fixture(scope="module")
def categorical_features(toy_data, toy_metadata):
    grouped = MetaData.grouping_features_astype(toy_data, toy_metadata)
    return grouped.get("ordinal_categorical", []) + grouped.get("dummy_categorical", [])


@pytest.fixture(autouse=True, scope="module")
def cleanup_outputs():
    yield
    if os.path.exists(OUTPUT_BASE):
        shutil.rmtree(OUTPUT_BASE)


# ─── GaussianCopula ───────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def gc_result(toy_data, toy_metadata):
    from synomicsbench.synthesizer.GaussianCopulasynthesizer import GaussianCopulasynthesizer

    out_dir = os.path.join(OUTPUT_BASE, "gc")
    synth = GaussianCopulasynthesizer(output_path=out_dir, metadata=toy_metadata)
    result = synth.generate(
        data=toy_data,
        seed=42,
        n_samples=toy_data.shape[0],
        fit_params={"n_jobs": 2, "chunk_size": 100},
        output_filename="gc_synthetic.csv",
    )
    return result, out_dir


class TestGaussianCopulaSynthesizer:

    def test_generate_returns_dataframe(self, gc_result):
        result, _ = gc_result
        assert isinstance(result, pd.DataFrame)

    def test_generate_shape(self, toy_data, gc_result):
        result, _ = gc_result
        assert result.shape == toy_data.shape

    def test_generate_columns(self, toy_data, gc_result):
        result, _ = gc_result
        assert list(result.columns) == list(toy_data.columns)

    def test_output_file_saved(self, gc_result):
        _, out_dir = gc_result
        assert os.path.exists(os.path.join(out_dir, "gc_synthetic.csv"))


# ─── CTGAN ────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def ctgan_result(toy_data, toy_metadata):
    from synomicsbench.synthesizer.CTGANsynthesizer import CTGANsynthesizer

    out_dir = os.path.join(OUTPUT_BASE, "ctgan")
    synth = CTGANsynthesizer(output_path=out_dir, metadata=toy_metadata)
    result = synth.generate(
        data=toy_data,
        seed=42,
        n_samples=toy_data.shape[0],
        fit_params={"epochs": 5, "verbose": False, "cuda": False},
        output_filename="ctgan_synthetic.csv",
    )
    return result, out_dir


class TestCTGANSynthesizer:

    def test_generate_returns_dataframe(self, ctgan_result):
        result, _ = ctgan_result
        assert isinstance(result, pd.DataFrame)

    def test_generate_shape(self, toy_data, ctgan_result):
        result, _ = ctgan_result
        assert result.shape == toy_data.shape

    def test_generate_columns(self, toy_data, ctgan_result):
        result, _ = ctgan_result
        assert list(result.columns) == list(toy_data.columns)

    def test_output_file_saved(self, ctgan_result):
        _, out_dir = ctgan_result
        assert os.path.exists(os.path.join(out_dir, "ctgan_synthetic.csv"))


# ─── TVAE ─────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def tvae_result(toy_data, toy_metadata):
    from synomicsbench.synthesizer.TVAEsynthesizer import TVAEsynthesizer

    out_dir = os.path.join(OUTPUT_BASE, "tvae")
    synth = TVAEsynthesizer(output_path=out_dir, metadata=toy_metadata)
    result = synth.generate(
        data=toy_data,
        seed=42,
        n_samples=toy_data.shape[0],
        fit_params={"epochs": 5, "verbose": False, "cuda": False},
        output_filename="tvae_synthetic.csv",
    )
    return result, out_dir


class TestTVAESynthesizer:

    def test_generate_returns_dataframe(self, tvae_result):
        result, _ = tvae_result
        assert isinstance(result, pd.DataFrame)

    def test_generate_shape(self, toy_data, tvae_result):
        result, _ = tvae_result
        assert result.shape == toy_data.shape

    def test_generate_columns(self, toy_data, tvae_result):
        result, _ = tvae_result
        assert list(result.columns) == list(toy_data.columns)

    def test_output_file_saved(self, tvae_result):
        _, out_dir = tvae_result
        assert os.path.exists(os.path.join(out_dir, "tvae_synthetic.csv"))


# ─── Synthpop ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def synthpop_result(toy_data, toy_metadata, categorical_features):
    pytest.importorskip("rpy2", reason="rpy2 not installed — skipping Synthpop tests")
    from synomicsbench.synthesizer.Synthpopsynthesizer import SynthpopSynthesizer

    out_dir = os.path.join(OUTPUT_BASE, "synthpop")
    synth = SynthpopSynthesizer(output_path=out_dir, metadata=toy_metadata)
    result = synth.generate(
        data=toy_data,
        seed=42,
        n_samples=toy_data.shape[0],
        sample_params={
            "discrete_columns": categorical_features,
            "method": "cart",
            "predictor_matrix": None,
        },
        output_filename="synthpop_synthetic.csv",
    )
    return result, out_dir


class TestSynthpopSynthesizer:

    def test_generate_returns_dataframe(self, synthpop_result):
        result, _ = synthpop_result
        assert isinstance(result, pd.DataFrame)

    def test_generate_shape(self, toy_data, synthpop_result):
        result, _ = synthpop_result
        assert result.shape == toy_data.shape

    def test_generate_columns(self, toy_data, synthpop_result):
        result, _ = synthpop_result
        assert list(result.columns) == list(toy_data.columns)

    def test_output_file_saved(self, synthpop_result):
        _, out_dir = synthpop_result
        assert os.path.exists(os.path.join(out_dir, "synthpop_synthetic.csv"))

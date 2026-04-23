import pytest
import pandas as pd
import numpy as np
import os

# Import Core Modules from synomicsbench
from synomicsbench.processing.preprocessing import DataProcessor
from synomicsbench.processing.metadata import MetaData
from synomicsbench.synthesizer.GaussianCopulasynthesizer import GaussianCopulasynthesizer
from synomicsbench.metrics.fidelity.UnivariateSimilarity import UnivariateSimilarity

@pytest.fixture
def mini_real_data():
    """Create a small mock Real Data DataFrame containing both Categorical and Numerical features."""
    np.random.seed(42)
    return pd.DataFrame({
        'PatientID': [f'P{i}' for i in range(20)],
        'Age': np.random.randint(30, 80, size=20).astype(float),
        'Gender': np.random.choice(['M', 'F'], size=20),
        'GeneA_TPM': np.random.uniform(0, 100, size=20),
        'GeneB_TPM': np.random.uniform(0, 50, size=20)
    }).set_index('PatientID')

@pytest.fixture
def mini_syn_data(mini_real_data):
    """Create a small mock Synthetic Data DataFrame by adding noise mapping to the real data."""
    np.random.seed(99)
    syn_df = mini_real_data.copy()
    syn_df['Age'] = syn_df['Age'] + np.random.normal(0, 5, size=20)
    syn_df['GeneA_TPM'] = syn_df['GeneA_TPM'] + np.random.normal(0, 10, size=20)
    syn_df['Gender'] = np.random.choice(['M', 'F'], size=20)
    return syn_df

def test_data_processor_remove_dup(mini_real_data):
    """Test duplicate rows removal feature."""
    # Manually append a duplicate row
    df_with_dup = pd.concat([mini_real_data, mini_real_data.iloc[[0]]])
    assert len(df_with_dup) == 21
    
    # Process duplicate removal
    df_clean = DataProcessor.remove_duplications(df_with_dup, axis=0)
    assert len(df_clean) == 20

def test_metadata_generation(mini_real_data):
    """Test Metadata statically extracting types layout."""
    meta_dict = MetaData.get_metadata(data=mini_real_data, threshold_unique_values=5)
    assert isinstance(meta_dict, dict)
    assert 'Gender' in meta_dict
    assert meta_dict['Gender'] in ['dummy_categorical', 'ordinal_categorical', 'categorical']
    assert meta_dict['Age'] == 'numerical'

def test_gaussian_copula_instantiation(mini_real_data, tmp_path):
    """Test basic instantiation of a Synthesizer component."""
    meta_dict = MetaData.get_metadata(data=mini_real_data, threshold_unique_values=5)
    synth = GaussianCopulasynthesizer(
        output_path=str(tmp_path),
        metadata=meta_dict
    )
    assert synth is not None

def test_univariate_similarity(mini_real_data, mini_syn_data, tmp_path):
    """Test Univariate Similarity evaluation module under fidelity package."""
    meta_dict = MetaData.get_metadata(data=mini_real_data, threshold_unique_values=5)
    
    evaluator = UnivariateSimilarity(
        output_dir=str(tmp_path),
        logger_name="DummyCancer"
    )
    
    try:
        score = evaluator.get_univariate_score(
            original_data=mini_real_data,
            synthetic_data=mini_syn_data,
            metadata=meta_dict,
            save=False
        )
        assert score is not None
        assert isinstance(score, float)
    except Exception as e:
        pytest.fail(f"UnivariateSimilarity evaluation failed with exception: {e}")

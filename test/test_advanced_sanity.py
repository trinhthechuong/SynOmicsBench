import pytest
import pandas as pd
import numpy as np
import os

from synomicsbench.metrics.fidelity.PairwiseSimilarity import PairwiseSimilarity
from synomicsbench.metrics.fidelity.BayesianComparison import BayesianComparison
from synomicsbench.processing.pipeline import DataIntegrationPipeline
from synomicsbench.processing.metadata import MetaData

@pytest.fixture
def mini_real_data():
    """Create a small mock Real Data DataFrame containing both Categorical and Numerical features."""
    np.random.seed(42)
    return pd.DataFrame({
        'PatientID': [f'P{i}' for i in range(30)],
        'Age': np.random.randint(30, 80, size=30).astype(float),
        'Gender': np.random.choice(['M', 'F'], size=30),
        'GeneA_TPM': np.random.uniform(0, 100, size=30),
        'GeneB_TPM': np.random.uniform(0, 50, size=30)
    }).set_index('PatientID')

@pytest.fixture
def mini_syn_data(mini_real_data):
    """Create a small mock Synthetic Data DataFrame."""
    np.random.seed(99)
    syn_df = mini_real_data.copy()
    syn_df['Age'] = syn_df['Age'] + np.random.normal(0, 5, size=30)
    syn_df['GeneA_TPM'] = syn_df['GeneA_TPM'] + np.random.normal(0, 10, size=30)
    syn_df['Gender'] = np.random.choice(['M', 'F'], size=30)
    return syn_df

def test_pairwise_similarity(mini_real_data, mini_syn_data, tmp_path):
    """Test PairwiseSimilarity metric layout."""
    meta_dict = MetaData.get_metadata(data=mini_real_data, threshold_unique_values=5)
    
    evaluator = PairwiseSimilarity(
        original_data=mini_real_data,
        synthetic_data=mini_syn_data,
        metadata=meta_dict,
        output_dir=str(tmp_path),
        save=False
    )
    
    try:
        results = evaluator.get_pairwise_scores(method="pearson")
        # Expect either a tuple, dict or dataframe depending on their return type
        assert results is not None
    except Exception as e:
        pytest.fail(f"PairwiseSimilarity evaluation failed with exception: {e}")

def test_bayesian_comparison():
    """Test Bayesian Comparison numerical computations (baycomp integration)."""
    comp = BayesianComparison(rope=0.01)
    
    # 5 dummy scores per method to simulate CV results
    dummy_scores = {
        "BaseModel": [0.80, 0.82, 0.81, 0.79, 0.83],
        "SynModel": [0.85, 0.86, 0.84, 0.88, 0.85],
    }
    
    try:
        report_df = comp.compare_methods(method_to_scores=dummy_scores)
        assert not report_df.empty
        assert "Better Prob" in report_df.columns
        assert len(report_df) == 2 # 2 comparisons for 2 methods (excluding self)
    except Exception as e:
        pytest.fail(f"BayesianComparison logic failed with exception: {e}")

def test_data_integration_pipeline_init(tmp_path):
    """Test DataIntegrationPipeline module initialization."""
    try:
        pipeline = DataIntegrationPipeline(
            output_dir=str(tmp_path),
            logger="test_pipeline_logger"
        )
        assert pipeline is not None
    except Exception as e:
        pytest.fail(f"DataIntegrationPipeline instantiation failed: {e}")

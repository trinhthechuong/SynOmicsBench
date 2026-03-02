import pandas as pd
import numpy as np
import sys
parent_path = '/mnt/digphat/syntheticDataBenchmark/Chuong_pipeline'
sys.path.append(parent_path)
from SynOmics.metrics.fidelity.utils import extract_metadata
from numba import njit, prange
from SynOmics.utils.monitoring import monitor_resources
from Synthpop import SynthpopSynthesizer


pred_mat_name = "predictor_matrix_networks_07_500.npy"
sorted_features_name = "sorted_features_networkx_07_500.txt"
output_path = "test_predictor_mat_networkx_07_500"

metadata_path = "../../Data/data_processed/Original_data/feature_metadata.json"
data_path = "../../Data/data_processed/Original_data/integrated_data_jobim.csv"

or_df = pd.read_csv("ForSynthpop_processed_df.csv", index_col = 0)
metadata = extract_metadata(or_df, metadata_path)
categorical_features = metadata.get("ordinal_categorical") + metadata.get("dummy_categorical") + metadata.get("missing_categorical")
numerical_features = metadata.get("numerical")

predictor_matrix = np.load(pred_mat_name)
sorted_features_indices = []
with open(sorted_features_name, "r") as f:
    for line in f:
        sorted_features_indices.append(int(line.strip())) 
sorted_features_names = [or_df.columns[int(i)] for i in sorted_features_indices]

predictor_df_from_dict = pd.DataFrame(predictor_matrix, 
                                      index=sorted_features_names, 
                                      columns=sorted_features_names)

ordered_df = or_df[sorted_features_names]



@monitor_resources
def runSynthpop(data, predictor_matrix, metadata_path, output_path, categorical_features, numerical_features):
    synthpop_synth = SynthpopSynthesizer(output_path = output_path)
    
    synthetic_data = synthpop_synth.generate_synthetic_data(
        data = data,
        metadata_path = metadata_path,
        R_terminal = "R441",
        data_ids = data.index.tolist(),
        discrete_columns = categorical_features,
        numerical_columns = numerical_features,
        seed =  42,
        enforce_rounding = False,
        enforce_min_max = False,
        method = 'ctree',
        minimumlevels = 3,
        proper = False,
        n_datasets  = 1, 
        n_samples = 'auto',
        verbose = True,
        predictor_matrix = predictor_matrix
    )
    return synthetic_data

metadata_path = "../../Data/data_processed/Original_data/feature_metadata.json"
output_path = output_path
synthetic_data_networkx = runSynthpop(
    data = ordered_df,
    predictor_matrix = predictor_df_from_dict,
    metadata_path = metadata_path, 
    output_path = output_path,
    categorical_features=categorical_features, 
    numerical_features=numerical_features)

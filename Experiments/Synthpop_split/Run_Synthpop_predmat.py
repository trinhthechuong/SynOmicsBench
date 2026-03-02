import sys
sys.path.append("/mnt/digphat/syntheticDataBenchmark/Chuong_pipeline/")
import pandas as pd
import numpy as np
from SynOmics.metrics.fidelity.utils import extract_metadata
from Synthpop import SynthpopSynthesizer
import time

or_data = pd.read_csv("ForSynthpop_processed_df.csv", index_col = 0)

with open('order_pred_mat.txt') as f:
    order = [int(line.strip()) for line in f]

mat = np.load("predictor_matrix.npy")
features = or_data.columns.tolist()
features_indices = [features.index(feature) for feature in features]
var_index_zip = list(zip(features, features_indices))


# Create a dict: index -> variable name
index_to_var = {idx: name for name, idx in var_index_zip}

# Reorder variable names according to feature_order
ordered_var_names = [index_to_var[idx] for idx in order]

# Convert np.array to DataFrame
pred_mat_df = pd.DataFrame(mat, index=ordered_var_names, columns=ordered_var_names)

ordered_columns = pred_mat_df.columns.tolist()

ordered_or_data = or_data[ordered_columns]

metadata_path = "../../Data/data_processed/Original_data/feature_metadata.json"
ordered_metadata = extract_metadata(ordered_or_data, metadata_path)
categorical_features = ordered_metadata.get("ordinal_categorical") + ordered_metadata.get("dummy_categorical") + ordered_metadata.get("missing_categorical")
numerical_features = ordered_metadata.get("numerical")



start_time = time.time()
metadata_path = "../../Data/data_processed/Original_data/feature_metadata.json"
output_path = "test_predictor_mat"
synthpop_synth = SynthpopSynthesizer(output_path = output_path)

synthetic_pre_mat = synthpop_synth.generate_synthetic_data(
    data = ordered_or_data,
    metadata_path = metadata_path,
    R_terminal = "R441",
    data_ids = or_data.index.tolist(),
    discrete_columns = categorical_features,
    numerical_columns = numerical_features,
    seed =  42,
    enforce_rounding = False,
    enforce_min_max = False,
    method = 'cart',
    minimumlevels = 3,
    proper = False,
    n_datasets  = 1, 
    n_samples = 'auto',
    verbose = True,
    predictor_matrix = pred_mat_df
)
end_time = time.time()
print(f"Execute time for Synthpop {end_time - start_time}")


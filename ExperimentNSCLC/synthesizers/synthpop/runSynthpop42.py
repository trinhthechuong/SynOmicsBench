import pandas as pd
import numpy as np
import sys
from numba import njit, prange
parent_path = '/mnt/digphat/syntheticDataBenchmark/Chuong_pipeline'
sys.path.append(parent_path)
from SynOmics.processing.metadata import MetaData

from SynOmics.synthesizer.Synthpopsynthesizer import SynthpopSynthesizer


metadata_path = "../OriginalData/feature_metadata.json"
data_path = "../OriginalData/integrated_data_nsclc.csv"

or_df = pd.read_csv(data_path, index_col = 0)
metadata = MetaData.load(metadata_path)
grouped_metadata = MetaData.grouping_features_astype(or_df, metadata)
categorical_features = grouped_metadata.get("dummy_categorical") + grouped_metadata.get("missing_categorical")
numerical_features = grouped_metadata.get("numerical")

#Load predictor matrix
predictor_matrix = np.load("synthpop_materials/predictor_matrix.npy")
sorted_features_indices = []
with open("synthpop_materials/sorted_features.txt", "r") as f:
    for line in f:
        sorted_features_indices.append(int(line.strip())) 
sorted_features_names = [or_df.columns[int(i)] for i in sorted_features_indices]

predictor_df_from_dict = pd.DataFrame(predictor_matrix, 
                                      index=sorted_features_names, 
                                      columns=sorted_features_names)

ordered_df = or_df[sorted_features_names]
seed = 42
synth = SynthpopSynthesizer(
    output_path = f"synthpop_{seed}",
    metadata = metadata,
    r_home = "/opt/R/4.4.1/lib/R",
    r_terminal = "R441"
)
synthetic_data = synth.generate(
    data = ordered_df, 
    data_ids = ordered_df.index.tolist(),
    enforce_rounding = False, 
    enforce_min_max = False, 
    masking = False, 
    seed = seed, 
    n_samples = ordered_df.shape[0], 
    fit_params = None,
    sample_params = {
        "discrete_columns": categorical_features,
        "method": "cart",
        "minimumlevels": 10,
        "proper": False,
        "n_datasets": 1,
        "verbose": True,
        "predictor_matrix": predictor_df_from_dict
    }, 
    output_filename = f'synthpop_{seed}.csv', 
    save_index = False
)

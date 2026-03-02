import pandas as pd
import numpy as np
import sys
sys.path.append("/mnt/digphat/syntheticDataBenchmark/Chuong_pipeline/")
from SynOmics.synthesizer.CTGANsynthesizer import CTGANsynthesizer
from SynOmics.processing.metadata import MetaData

original_data = pd.read_csv("../OriginalData/integrated_data_nsclc.csv", index_col = 0)
metadata_path = "../OriginalData/feature_metadata.json"
metadata = MetaData.load(metadata_path)
# seeds = [42,0,1,2,3]
seed = 1
# for seed in seeds:
output_path = f"ctgan_nsclc_{seed}"
synthesizers = CTGANsynthesizer(output_path = output_path, metadata = metadata)
synthetic_data = synthesizers.generate(
    data = original_data,
    data_ids = original_data.index.tolist(),
    enforce_rounding = False,
    enforce_min_max  = False,
    masking = False,
    n_samples = original_data.shape[0],
    seed = seed,
    fit_params = {"epochs": 200, "verbose":True, "cuda": True},
    output_filename = f"ctgan_{seed}.csv",
    save_index = False,
)

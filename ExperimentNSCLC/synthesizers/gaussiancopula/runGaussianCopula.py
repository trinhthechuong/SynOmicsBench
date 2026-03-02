import pandas as pd
import numpy as np
import sys
sys.path.append("/mnt/digphat/syntheticDataBenchmark/Chuong_pipeline/")
from SynOmics.synthesizer.GaussianCopulasynthesizer import GaussianCopulasynthesizer
from SynOmics.processing.metadata import MetaData



original_data = pd.read_csv("../OriginalData/integrated_data_nsclc.csv", index_col = 0)
metadata_path = "../OriginalData/feature_metadata.json"
metadata = MetaData.load(metadata_path)

# metadata = MetaData.load(metadata_path)
seeds = [42,0,1,2,3]
for seed in seeds:
    output_path = f"gaussiancopula_{seed}"
    synth = GaussianCopulasynthesizer(output_path=output_path, metadata=metadata)
    synthetic_data = synth.generate(
    data=original_data,
    data_ids=original_data.index.tolist(),
    enforce_rounding=True,
    enforce_min_max=False,
    masking=False,
    n_samples=original_data.shape[0],
    seed=seed,
    fit_params={"n_jobs": -1, "chunk_size": 1000},
    output_filename=f"gaussiancopula_{seed}.csv",
    save_index=False,
    )

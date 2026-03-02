import pandas as pd
import numpy as np
import sys
sys.path.append("/mnt/digphat/syntheticDataBenchmark/Chuong_pipeline/")
from SynOmics.synthesizer.GaussianCopulasynthesizer_Debug import GaussianCopulasynthesizer
from SynOmics.processing.metadata import MetaData


seed = 42
original_data = pd.read_csv("OriginalData/integrated_data_final.csv", index_col = 0)
metadata_path = "OriginalData/feature_metadata.json"
metadata = MetaData.load(metadata_path)

output_path = f"gaussiancopula_debug_{seed}"
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
    output_filename=f"gaussiancopulaDebug_{seed}.csv",
    save_index=False,
)

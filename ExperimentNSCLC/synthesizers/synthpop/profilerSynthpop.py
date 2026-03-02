import pandas as pd
import numpy as np
import sys
import os
from codecarbon import OfflineEmissionsTracker
from memory_profiler import memory_usage

# Setup Path
parent_path = '/mnt/digphat/syntheticDataBenchmark/Chuong_pipeline'
sys.path.append(parent_path)

from SynOmics.processing.metadata import MetaData
from SynOmics.synthesizer.Synthpopsynthesizer import SynthpopSynthesizer
from SynOmics.utils.monitoring import monitor_resources as _monitor_resources

@_monitor_resources
def run_synthpop_nsclc_benchmark(seed=42, data_path="../OriginalData/integrated_data_nsclc.csv", metadata_path="../OriginalData/feature_metadata.json"):
    
    # --- 1. Setup Output and Data Loading ---
    output_path = f"profiler_synthpop_nsclc_{seed}"
    os.makedirs(output_path, exist_ok=True)
    
    or_df = pd.read_csv(data_path, index_col=0)
    metadata = MetaData.load(metadata_path)
    
    # Feature grouping logic
    grouped_metadata = MetaData.grouping_features_astype(or_df, metadata)
    categorical_features = (grouped_metadata.get("dummy_categorical") + 
                            grouped_metadata.get("missing_categorical"))
    
    # Load predictor matrix and sort features
    predictor_matrix = np.load("synthpop_materials/predictor_matrix.npy")
    sorted_features_indices = []
    with open("synthpop_materials/sorted_features.txt", "r") as f:
        for line in f:
            sorted_features_indices.append(int(line.strip())) 
            
    sorted_features_names = [or_df.columns[int(i)] for i in sorted_features_indices]
    predictor_df_from_dict = pd.DataFrame(
        predictor_matrix, 
        index=sorted_features_names, 
        columns=sorted_features_names
    )
    ordered_df = or_df[sorted_features_names]

    # --- 2. Define the payload for memory tracking ---
    def execution_payload():
        synth = SynthpopSynthesizer(
            output_path=output_path,
            metadata=metadata,
            r_home="/opt/R/4.4.1/lib/R",
            r_terminal="R441"
        )
        return synth.generate(
            data=ordered_df, 
            data_ids=ordered_df.index.tolist(),
            enforce_rounding=False, 
            enforce_min_max=False, 
            masking=False, 
            seed=seed, 
            n_samples=ordered_df.shape[0], 
            fit_params=None,
            sample_params={
                "discrete_columns": categorical_features,
                "method": "cart",
                "minimumlevels": 10,
                "proper": False,
                "n_datasets": 1,
                "verbose": True,
                "predictor_matrix": predictor_df_from_dict
            }, 
            output_filename=f'synthpop_{seed}.csv', 
            save_index=False
        )

    # --- 3. Setup Emissions Tracker ---
    tracker = OfflineEmissionsTracker(
        tracking_mode='process',
        country_iso_code="VNM",
        output_dir=output_path,
        output_file=f"emissions_synthpop_nsclc_{seed}.csv"
    )

    tracker.start()
    try:
        print(f"--- Starting profiling Synthpop NSCLC (Seed: {seed}) ---")
        
        # --- 4. Track Memory Time-Series ---
        # Synthpop involves an R sub-process; 0.5s interval is perfect for capturing this.
        mem_samples, synthetic_data = memory_usage(
            (execution_payload,), 
            interval=0.5, 
            retval=True
        )
        
        # --- 5. Save Memory History CSV ---
        history_df = pd.DataFrame({
            'time_step_sec': [i * 0.5 for i in range(len(mem_samples))],
            'mem_usage_mib': mem_samples
        })
        history_path = os.path.join(output_path, f"memory_history_synthpop_nsclc_{seed}.csv")
        history_df.to_csv(history_path, index=False)
        
        print(f"--- Complete Seed {seed} ---")
        print(f"Peak RAM: {max(mem_samples):.2f} MiB")
        
        return synthetic_data

    finally:
        emissions_kg = tracker.stop()
        if emissions_kg is not None:
            print(f"CO2 emission: {emissions_kg:.6f} kg")

if __name__ == "__main__":
    # Execute the NSCLC benchmark
    data = run_synthpop_nsclc_benchmark(seed=42)
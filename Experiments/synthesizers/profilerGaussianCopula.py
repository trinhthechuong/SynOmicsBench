import pandas as pd
import numpy as np
import sys
import os
from codecarbon import OfflineEmissionsTracker
from memory_profiler import memory_usage

# Setup Path
sys.path.append("/mnt/digphat/syntheticDataBenchmark/Chuong_pipeline/")
from SynOmics.synthesizer.GaussianCopulasynthesizer import GaussianCopulasynthesizer
from SynOmics.utils.monitoring import monitor_resources as _monitor_resources
from SynOmics.processing.metadata import MetaData

@_monitor_resources
def run_gaussian_copula_benchmark(seed=42, data_path="OriginalData/integrated_data_final.csv", metadata_path="OriginalData/feature_metadata.json"):
    
    # --- Setup Output and Data Loading ---
    output_path = f"Benchmark/gauss_copula_{seed}"
    os.makedirs(output_path, exist_ok=True)
    
    original_data = pd.read_csv(data_path, index_col=0)
    metadata = MetaData.load(metadata_path)

    # 1. Define the internal function to be profiled for memory
    def execution_payload():
        synth = GaussianCopulasynthesizer(output_path=output_path, metadata=metadata)
        return synth.generate(
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

    # 2. Setup CodeCarbon Tracker
    tracker = OfflineEmissionsTracker(
        tracking_mode='process',
        country_iso_code="VNM",
        output_dir=output_path,
        output_file=f"emissions_gauss_copula_seed_{seed}.csv"
    )

    tracker.start()
    try:
        print(f"--- Starting profiling Gaussian Copula Benchmark (Seed: {seed}) ---")
        
        # 3. Track memory over time (Option 3 - Time Series)
        # interval=0.5: capture RAM every 0.5s
        mem_samples, synthetic_data = memory_usage(
            (execution_payload,), 
            interval=0.5, 
            retval=True
        )
        
        # 4. Save memory history to CSV
        history_df = pd.DataFrame({
            'time_step_sec': [i * 0.5 for i in range(len(mem_samples))],
            'mem_usage_mib': mem_samples
        })
        history_path = os.path.join(output_path, f"memory_history_gauss_copula_seed_{seed}.csv")
        history_df.to_csv(history_path, index=False)
        
        print(f"--- Complete Gaussian Copula Benchmark Seed {seed} ---")
        print(f"Peak RAM: {max(mem_samples):.2f} MiB")
        
        return synthetic_data

    finally:
        # Stop tracker and catch emissions value
        emissions_kg = tracker.stop()
        if emissions_kg is not None:
            print(f"CO2 emission: {emissions_kg:.6f} kg")

if __name__ == "__main__":
    # Execute the benchmark
    data = run_gaussian_copula_benchmark(seed=42)
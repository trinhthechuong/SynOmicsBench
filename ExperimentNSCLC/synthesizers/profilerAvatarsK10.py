import pandas as pd
import numpy as np
import os
import time
import json
import uuid
import sys
from codecarbon import OfflineEmissionsTracker
from memory_profiler import memory_usage
from avatars.manager import Manager
from avatars.models import JobKind

# Path setup
sys.path.append("/mnt/digphat/syntheticDataBenchmark/Chuong_pipeline/")

def run_avatars_block_benchmark(i, seed, k, manager, output_path):
    """
    Đo lường RAM, Emission, và Time của đúng 1 block duy nhất.
    """
    def block_payload():
        data = pd.read_csv(f"avatars/original_blocks/original_block_{i}.csv", index_col=False)
        data_clean = data.drop(columns=["Patient_ID"])
        n_feats = data_clean.shape[1]
        
        job_name = f"Block_{i}_k{k}_{seed}_" + str(uuid.uuid4())
        runner = manager.create_runner(job_name, seed=seed)
        table_name = f"block_{i}_k{k}_{seed}_" + str(uuid.uuid4())
        
        runner.add_table(table_name, data_clean)
        runner.set_parameters(table_name, k=k)
        runner.run(jobs_to_run=[JobKind.standard])
        
        synthetic_df = runner.sensitive_unshuffled(table_name)
        synthetic_df.to_csv(f"{output_path}/synthetic_block_{i}.csv", index=False)
        return n_feats

    tracker = OfflineEmissionsTracker(
        tracking_mode='process',
        country_iso_code="VNM",
        output_dir=output_path,
        output_file=f"emissions_block_{i}.csv"
    )

    tracker.start()
    block_start = time.perf_counter()
    try:
        mem_samples, n_features = memory_usage((block_payload,), interval=0.2, retval=True)
        block_end = time.perf_counter()
        
        duration = block_end - block_start
        peak_ram = max(mem_samples)
        
        # Lưu history RAM của block
        history_df = pd.DataFrame({
            'time_step_sec': [j * 0.2 for j in range(len(mem_samples))],
            'mem_usage_mib': mem_samples
        })
        history_df.to_csv(os.path.join(output_path, f"memory_history_block_{i}.csv"), index=False)
        
        return {
            'block_id': i,
            'duration_sec': duration,
            'peak_ram_mib': peak_ram,
            'n_features': n_features
        }
    finally:
        tracker.stop()

# --- Main Script ---
if __name__ == "__main__":
    url = os.environ.get("AVATAR_BASE_API_URL", "https://www.octopize.app/api")
    username = "christophe.battail@cea.fr"
    password = "GT5j6ps4n0*!$"
    
    seed = 42
    k = 10
    output_dir = f"avatars/profiler_nsclc_k{k}_{seed}"
    os.makedirs(output_dir, exist_ok=True)

    manager = Manager(base_url=url)
    manager.authenticate(username, password, should_verify_compatibility=False)

    with open("avatars/cluster_final.json", "r") as f:
        cluster_features = json.load(f)

    all_stats = []
    
    # --- BẮT ĐẦU ĐO TỔNG THỜI GIAN ---
    process_start_time = time.perf_counter()
    print(f"=== Starting Avatars NSCLC Benchmark | k={k} | Seed={seed} ===")

    for i in range(len(cluster_features)):
        print(f"--- Profiling Block {i} ---")
        try:
            stats = run_avatars_block_benchmark(i, seed, k, manager, output_dir)
            all_stats.append(stats)
            
            # Sleep logic
            if stats['n_features'] >= 3000:
                print("Large block. Sleeping 30 mins...")
                time.sleep(1800)
            else:
                time.sleep(30)
                
        except Exception as e:
            print(f"Error at block {i}: {e}")
            continue

    # --- KẾT THÚC ĐO TỔNG THỜI GIAN ---
    process_end_time = time.perf_counter()
    total_duration_sec = process_end_time - process_start_time
    total_duration_min = total_duration_sec / 60

    # Xuất báo cáo tổng hợp
    summary_df = pd.DataFrame(all_stats)
    summary_df.to_csv(f"{output_dir}/summary_performance_nsclc_seed_{seed}.csv", index=False)
    
    # Lưu tổng thời gian vào một file text nhỏ
    with open(f"{output_dir}/total_time_seed_{seed}.txt", "w") as f:
        f.write(f"Total Process Duration: {total_duration_sec:.2f} seconds\n")
        f.write(f"Total Process Duration: {total_duration_min:.2f} minutes\n")

    print(f"\n" + "="*50)
    print(f"BENCHMARK COMPLETE")
    print(f"Total Time: {total_duration_min:.2f} minutes")
    print(f"Summary saved to: {output_dir}/summary_performance_nsclc_seed_{seed}.csv")
    print("="*50)
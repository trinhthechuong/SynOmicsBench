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
# sys.path.append("/mnt/digphat/syntheticDataBenchmark/Chuong_pipeline/")
# from SynOmics.utils.monitoring import monitor_resources as _monitor_resources

def run_avatars_block_benchmark(i, seed, k, manager, output_path):
    """
    Thực hiện và đo lường tài nguyên (RAM, Emission, Time) của đúng 1 block.
    """
    
    # 1. Payload thực thi
    def block_payload():
        data = pd.read_csv(f"avatars/original_blocks/original_block_{i}.csv", index_col=False)
        data_clean = data.drop(columns=["Patient"])
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

    # 2. Setup Tracker
    tracker = OfflineEmissionsTracker(
        tracking_mode='process',
        country_iso_code="VNM",
        output_dir=output_path,
        output_file=f"emissions_block_{i}.csv"
    )

    tracker.start()
    start_time = time.perf_counter() # Bắt đầu đo thời gian
    try:
        # 3. Đo Memory history
        mem_samples, n_features = memory_usage(
            (block_payload,), 
            interval=0.2, 
            retval=True
        )
        end_time = time.perf_counter() # Kết thúc đo thời gian
        
        duration = end_time - start_time
        peak_ram = max(mem_samples)
        
        # 4. Lưu lịch sử Memory của block i
        history_df = pd.DataFrame({
            'time_step_sec': [j * 0.2 for j in range(len(mem_samples))],
            'mem_usage_mib': mem_samples
        })
        history_df.to_csv(os.path.join(output_path, f"memory_history_block_{i}.csv"), index=False)
        
        print(f"Block {i} | Time: {duration:.2f}s | Peak RAM: {peak_ram:.2f} MiB")
        
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
    output_dir = f"Benchmark/avatars/synthetic_blocks_k{k}_{seed}"
    os.makedirs(output_dir, exist_ok=True)

    manager = Manager(base_url=url)
    manager.authenticate(username, password, should_verify_compatibility=False)

    with open("avatars/cluster_final.json", "r") as f:
        cluster_features = json.load(f)

    all_stats = [] # Lưu trữ kết quả tổng hợp

    print(f"=== Starting Avatars Anonymization Benchmark (Seed: {seed}) ===")

    for i in range(len(cluster_features)):
        print(f"--- Profiling Block {i} / {len(cluster_features)-1} ---")
        try:
            # Chạy benchmark và nhận kết quả thống kê
            stats = run_avatars_block_benchmark(i, seed, k, manager, output_dir)
            all_stats.append(stats)
            
            # Sleep logic (Ngoài vùng đo)
            if stats['n_features'] >= 3000:
                time.sleep(1800)
            else:
                time.sleep(30)
                
        except Exception as e:
            print(f"Error processing block {i}: {e}")
            continue

    # 5. Xuất file tổng hợp cuối cùng cho seed này
    summary_df = pd.DataFrame(all_stats)
    summary_df.to_csv(f"{output_dir}/summary_stats_seed_{seed}.csv", index=False)
    
    print(f"\n=== Benchmark Complete. Summary saved to {output_dir}/summary_stats_seed_{seed}.csv ===")
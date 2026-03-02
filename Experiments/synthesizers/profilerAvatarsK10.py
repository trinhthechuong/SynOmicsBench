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

def run_avatars_block_benchmark(i, seed, k, manager, output_path):
    """
    Thực hiện và đo lường Time, RAM, Emission của đúng 1 block ccRCC.
    """
    
    def block_payload():
        # Đọc dữ liệu ccRCC từ các block đã chia
        data = pd.read_csv(f"avatars/original_blocks/original_block_{i}.csv", index_col=False)
        # Drop Patient_ID theo yêu cầu của dataset ccRCC/NSCLC
        data_clean = data.drop(columns=["Patient_ID"])
        n_feats = data_clean.shape[1]
        
        # Khởi tạo Job trên Cloud API
        job_name = f"Block_{i}_k{k}_{seed}_" + str(uuid.uuid4())
        runner = manager.create_runner(job_name, seed=seed)
        table_name = f"block_{i}_k{k}_{seed}_" + str(uuid.uuid4())
        
        runner.add_table(table_name, data_clean)
        runner.set_parameters(table_name, k=k)
        
        # Chạy tiến trình tổng hợp
        runner.run(jobs_to_run=[JobKind.standard])
        
        # Tải dữ liệu synthetic về local
        synthetic_df = runner.sensitive_unshuffled(table_name)
        synthetic_df.to_csv(f"{output_path}/synthetic_block_{i}.csv", index=False)
        
        return n_feats

    # Thiết lập tracker phát thải cho block i
    tracker = OfflineEmissionsTracker(
        tracking_mode='process',
        country_iso_code="VNM",
        output_dir=output_path,
        output_file=f"emissions_block_{i}.csv"
    )

    tracker.start()
    block_start = time.perf_counter()
    try:
        # Đo bộ nhớ với độ phân giải cao 0.2s
        mem_samples, n_features = memory_usage(
            (block_payload,), 
            interval=0.2, 
            retval=True
        )
        block_end = time.perf_counter()
        
        duration = block_end - block_start
        peak_ram = max(mem_samples)
        
        # Lưu lịch sử RAM chi tiết cho block i
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

# --- Chương trình chính ---
if __name__ == "__main__":
    # Cấu hình API và Thông tin ccRCC
    url = os.environ.get("AVATAR_BASE_API_URL", "https://www.octopize.app/api")
    username = "the-chuong.trinh@cea.fr"
    password = "ttcAVATARS#123"
    
    seed = 42
    k = 10
    output_dir = f"Benchmark/avatars/synthetic_blocks_ccRCC_k{k}_{seed}"
    os.makedirs(output_dir, exist_ok=True)

    # Xác thực Manager
    manager = Manager(base_url=url)
    manager.authenticate(username, password, should_verify_compatibility=False)

    # Load danh sách đặc trưng từ file cluster
    with open("avatars/cluster_final.json", "r") as f:
        cluster_features = json.load(f)

    all_stats = []
    
    # Bắt đầu đo TỔNG thời gian cho toàn bộ project
    overall_process_start = time.perf_counter()
    
    print(f"=== Starting Avatars ccRCC Anonymization | k={k} | Seed={seed} ===")

    for i in range(len(cluster_features)):
        print(f"--- Profiling Block {i} / {len(cluster_features)-1} ---")
        try:
            # Thực thi và đo lường block i
            stats = run_avatars_block_benchmark(i, seed, k, manager, output_dir)
            all_stats.append(stats)
            
            # Sleep logic để giãn cách API calls (Nằm ngoài vùng đo tài nguyên)
            if stats['n_features'] >= 3000:
                print(f"Large block ({stats['n_features']} features). Waiting 5 mins...")
                time.sleep(1800)
            else:
                time.sleep(30)
                
        except Exception as e:
            print(f"Error processing block {i}: {e}")
            continue

    # Kết thúc đo tổng thời gian
    overall_process_end = time.perf_counter()
    total_duration_min = (overall_process_end - overall_process_start) / 60

    # 1. Lưu file CSV tổng hợp tất cả các block
    summary_df = pd.DataFrame(all_stats)
    summary_df.to_csv(f"{output_dir}/summary_performance_ccRCC_seed_{seed}.csv", index=False)
    
    # 2. Lưu tổng thời gian chạy thực tế vào file text
    with open(f"{output_dir}/total_execution_time.txt", "w") as f:
        f.write(f"Seed: {seed}, k: {k}\n")
        f.write(f"Total Workflow Duration: {total_duration_min:.2f} minutes\n")

    print(f"\n" + "="*60)
    print(f"BENCHMARK CC-RCC COMPLETE")
    print(f"Total Workflow Time: {total_duration_min:.2f} minutes")
    print(f"Summary Report: {output_dir}/summary_performance_ccRCC_seed_{seed}.csv")
    print("="*60)
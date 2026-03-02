import pandas as pd
import numpy as np
import os
import torch
import time
from memory_profiler import memory_usage
from codecarbon import OfflineEmissionsTracker
import sys
sys.path.append("/mnt/digphat/syntheticDataBenchmark/Chuong_pipeline/")
from SynOmics.synthesizer.CTGANsynthesizer import CTGANsynthesizer
from SynOmics.utils.monitoring import monitor_resources as _monitor_resources

@_monitor_resources
def matrix_stress_test_with_history(size=5000, cuda=False, base_path="Benchmark"):
    # Thiết lập đường dẫn
    output_dir = base_path
    os.makedirs(output_dir, exist_ok=True)
    
    # 1. Hàm chứa logic tính toán
    def computation_logic():
        data = np.random.rand(size, size).astype(np.float32)
        if cuda and torch.cuda.is_available():
            data_tensor = torch.from_numpy(data).cuda()
            u, s, v = torch.linalg.svd(data_tensor)
            torch.cuda.synchronize()
            return s.cpu().numpy()
        else:
            u, s, v = np.linalg.svd(data)
            return s

    # 2. Khởi tạo Tracker cho Carbon
    tracker = OfflineEmissionsTracker(
        tracking_mode="process",
        # country_iso_code="VNM", 
        output_dir=output_dir,
        output_file="emission.csv"
    )

    tracker.start()
    print(f"--- Đang chạy và theo dõi tài nguyên (Size: {size}) ---")
    
    # Khoảng thời gian lấy mẫu (giây)
    sampling_interval = 0.1 
    
    try:
        # 3. Đo lịch sử RAM
        mem_samples, result = memory_usage(
            (computation_logic,), 
            interval=sampling_interval, 
            retval=True
        )
    finally:
        tracker.stop()

    # 4. Lưu toàn bộ lịch sử RAM vào file CSV riêng
    # Tạo danh sách thời gian tương ứng với mỗi điểm dữ liệu
    time_points = [i * sampling_interval for i in range(len(mem_samples))]
    
    history_df = pd.DataFrame({
        'relative_time_sec': time_points,
        'mem_usage_mib': mem_samples
    })
    
    history_path = os.path.join(output_dir, "memory_history.csv")
    history_df.to_csv(history_path, index=False)
    
    print(f"--- Đã lưu lịch sử RAM ({len(mem_samples)} điểm) vào: {history_path}")
    print(f"RAM thấp nhất: {min(mem_samples):.2f} MiB | RAM cao nhất: {max(mem_samples):.2f} MiB")

    return result

if __name__ == "__main__":
    matrix_stress_test_with_history(size=4000, cuda=False)
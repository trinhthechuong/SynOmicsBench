import time
import platform
import psutil
import datetime
import getpass
import pynvml

def monitor_resources(function):
    """Decorator to monitor CPU, RAM, and GPU resources during function execution."""
    def wrapper(*args, **kwargs):
        print("--- System & Process Info ---")
        # Get current time
        current_time = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        print(f"Current Date and Time (UTC): {current_time}")
        
        # Get user info
        try:
            print(f"Current User's Login: {getpass.getuser()}")
        except Exception:
            print("Could not determine user login")
        
        # Get CPU info
        print(f"CPU Model: {platform.processor()}")
        print(f"Physical Cores: {psutil.cpu_count(logical=False)}")
        print(f"Logical Processors: {psutil.cpu_count(logical=True)}")
        
        # Memory before execution
        process = psutil.Process()
        memory_before = process.memory_info().rss / (1024 * 1024)
        print(f"Process RAM before execution: {memory_before:.2f} MB")
        
        # --- GPU Monitoring Start ---
        gpu_handles = []
        gpu_info_available = False
        try:
            # Dynamically import to avoid error if not installed
            import pynvml
            pynvml.nvmlInit()
            gpu_info_available = True
            device_count = pynvml.nvmlDeviceGetCount()
            driver_version = pynvml.nvmlSystemGetDriverVersion()
            
            print("\n--- GPU Info ---")
            print(f"NVIDIA Driver Version: {driver_version}")
            
            if device_count == 0:
                print("No NVIDIA GPUs found.")
                gpu_info_available = False
            else:
                print(f"Detected GPUs: {device_count}")
                mem_info_before = []
                for i in range(device_count):
                    handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                    gpu_handles.append(handle)
                    gpu_name = pynvml.nvmlDeviceGetName(handle)
                    mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                    
                    mem_info_before.append(mem_info.used / (1024 * 1024))
                    
                    print(f"\n[GPU {i}]")
                    print(f"  Model: {gpu_name}")
                    print(f"  Memory Before: {mem_info_before[-1]:.2f} MB / {mem_info.total / (1024 * 1024):.2f} MB")

        except Exception as e:
            print(f"\n--- GPU Info ---")
            print(f"GPU monitoring failed. Ensure 'pynvml' is installed and NVIDIA drivers are accessible.")
            print(f"Error: {e}")
        # --- GPU Monitoring End of Setup ---

        print("\n--- Function Execution ---")
        
        # Track CPU utilization and execution time
        cpu_percent_before = psutil.cpu_percent(percpu=True)
        start_time = time.time()
        
        # Execute the decorated function
        result = function(*args, **kwargs)
        
        execution_time = time.time() - start_time
        cpu_percent_after = psutil.cpu_percent(percpu=True)

        print("\n--- Resource Usage Summary ---")
        print(f"Execution time: {execution_time:.4f} seconds")
        
        # Memory after execution
        memory_after = process.memory_info().rss / (1024 * 1024)
        print(f"Process RAM after execution: {memory_after:.2f} MB")
        print(f"Process RAM used by function: {memory_after - memory_before:.2f} MB")

        # CPU utilization during execution
        cpu_utilized = [i for i, (before, after) in enumerate(zip(cpu_percent_before, cpu_percent_after)) 
                        if after > before + 10]  # +10% threshold for considering a core utilized
        print(f"CPU Cores utilized: {len(cpu_utilized)} of {psutil.cpu_count(logical=True)}")

        # --- GPU Usage Summary ---
        if gpu_info_available:
            for i, handle in enumerate(gpu_handles):
                mem_info_after = pynvml.nvmlDeviceGetMemoryInfo(handle).used / (1024 * 1024)
                util_rates = pynvml.nvmlDeviceGetUtilizationRates(handle)
                
                print(f"\n[GPU {i}] Usage")
                print(f"  Memory After: {mem_info_after:.2f} MB")
                print(f"  Memory Used by function: {mem_info_after - mem_info_before[i]:.2f} MB")
                print(f"  GPU Utilization: {util_rates.gpu}%")
                print(f"  Memory Controller Utilization: {util_rates.memory}%")
            
            # It's crucial to shut down NVML
            pynvml.nvmlShutdown()
        
        print("\n" + "="*40 + "\n")
        
        return result
    return wrapper

# --- Example Usage ---
@monitor_resources
def example_task(n):
    """A simple function that performs some calculations."""
    print(f"Running a task with input {n}...")
    total = 0
    for i in range(n):
        total += i**2
    time.sleep(1) # Simulate some work
    print("Task finished.")
    return total

if __name__ == "__main__":
    example_task(20000000)
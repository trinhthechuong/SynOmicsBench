import logging
import os
import sys
import time
import platform
import psutil
import datetime
import getpass
# import nvidia_smi
import functools


def set_logger(logger_name: str, output_path: str, log_file_name: str = "activity.log"):
    """
    Configures a logger with both file and console handlers and returns it.

    Args:
        logger_name (str): The name for the logger (e.g., __name__ or 'myscript').
        output_path (str): The directory where the log file should be created.
        log_file_name (str): The name of the log file.

    Returns:
        logging.Logger: The configured logger instance.
    """
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)
    
    # Prevent re-adding handlers
    if logger.handlers:
        logger.handlers.clear()

    # Define a consistent formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )

    # File Handler Setup (same as before)
    log_path = os.path.join(output_path, log_file_name)
    try:
        os.makedirs(output_path, exist_ok=True)
        file_handler = logging.FileHandler(log_path)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except OSError as e:
        print(f"WARNING: Could not create log file at {log_path}. Error: {e}", file=sys.stderr)

    # Console Handler Setup (same as before)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    logger.debug("Standalone logger initialized successfully.")
    
    return logger




def _decode_bytes(value):
    return value.decode("utf-8", errors="ignore") if isinstance(value, (bytes, bytearray)) else value


def monitor_resources(func):
    """Decorator to monitor CPU, RAM, and GPU (NVIDIA via nvidia-ml-py) resources during function execution.

    Args:
        func (callable): The function to be monitored.

    Returns:
        callable: The wrapped function with resource monitoring.

    Raises:
        Exception: Re-raises any exception from the wrapped function after reporting.
    """
    import functools, datetime, getpass, platform, psutil, time

    def _decode_bytes(s):
        # nvidia-ml-py returns str, so this is a no-op but kept for compatibility
        return s

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        print("--- System & Process Info ---")
        current_time = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        print(f"Current Date and Time (UTC): {current_time}")

        # Get user info
        try:
            print(f"Current User's Login: {getpass.getuser()}")
        except Exception:
            print("Could not determine user login")

        cpu_model = platform.processor() or getattr(platform.uname(), "processor", "") or platform.machine()
        print(f"CPU Model: {cpu_model}")
        print(f"Physical Cores: {psutil.cpu_count(logical=False)}")
        print(f"Logical Processors: {psutil.cpu_count(logical=True)}")

        process = psutil.Process()
        MB = 1024 * 1024
        memory_before = process.memory_info().rss / MB
        print(f"Process RAM before execution: {memory_before:.2f} MB")

        print("\n--- Function Execution ---")

        psutil.cpu_percent(percpu=True)
        start_time = time.perf_counter()

        exc = None
        result = None
        try:
            result = func(*args, **kwargs)
            return result
        except Exception as e:
            exc = e
        finally:
            execution_time = time.perf_counter() - start_time

            print("\n--- Resource Usage Summary ---")
            print(f"Execution time: {execution_time:.6f} seconds")

            memory_after = process.memory_info().rss / MB
            mem_delta = memory_after - memory_before
            print(f"Process RAM after execution: {memory_after:.2f} MB")
            print(f"Process RAM used by function: {mem_delta:.2f} MB")

            cpu_per_core_during = psutil.cpu_percent(percpu=True)
            utilized_cores = sum(1 for v in cpu_per_core_during if v > 10.0)
            print(f"Average per-core CPU during execution: {[round(v, 1) for v in cpu_per_core_during]}")
            print(f"CPU Cores utilized (>10%): {utilized_cores} of {psutil.cpu_count(logical=True)}")
            print("\n" + "=" * 40 + "\n")

            if exc is not None:
                raise exc

    return wrapper

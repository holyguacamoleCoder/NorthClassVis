import time
from mock_data import *
from ParallelViewTest import *
import sys
import os


def measure_performance(func, *args, **kwargs):
    start_time = time.time()
    result = func(*args, **kwargs)
    end_time = time.time()
    duration = end_time - start_time
    print(f"Function {func.__name__} took {duration:.2f} seconds to execute.")
    return result



def main():
    test_parallel_view()

if __name__ == "__main__":
    main()
import time
from mock_data import *
import test_ParallelView.TestParallelView as TestParallelView


def measure_performance(func, *args, **kwargs):
    start_time = time.time()
    result = func(*args, **kwargs)
    end_time = time.time()
    duration = end_time - start_time
    print(f"Function {func.__name__} took {duration:.2f} seconds to execute.")
    return result



def main():
    TestParallelView.test_parallel_view(num_students=1000, num_titles=45, num_knowledges=8)

if __name__ == "__main__":
    main()
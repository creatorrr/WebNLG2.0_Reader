__version__ = "0.1.0"

import os

from pyannotate_runtime import collect_types
import ray
from tqdm import tqdm

from .patterns.constants import DataSetType
from .reader import download, process_data, save_data


num_cpus = os.cpu_count() or 4

# Make sure workers don't start a copy
ray.shutdown()
ray.init(num_cpus=num_cpus, include_dashboard=False)

def main():
    # download()

    for v in DataSetType:
        data_set_type = v.value
        print(f"[INFO] Processing {data_set_type} set")

        processed = process_data(data_set_type, parallel=False)
        save_data(processed, data_set_type)


if __name__ == "__main__":
    # Collect runtime type data for pyannotate
    collect_types.init_types_collection()

    with collect_types.collect():
        main()

    collect_types.dump_stats("./pyannotate_runtime.stats")

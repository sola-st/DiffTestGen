# Only needed if running different versions of prompts non-stop.
import shutil
import subprocess
from os.path import join, isfile, exists
from os import makedirs, rename
import os

iteration = 0 # not in a list, to spped up by parallel running 
config_versions = [
    # [1, 0, 1, False],
    # [5, 5, 5, False],
    # [5, 8, 8, False],
    [5, 8, 8, True]
    ]

results_folder = join("data", "results")
# if exists(results_folder):
#     rename(results_folder, f"{results_folder}_backup")

breakpoints_data_folder = join(results_folder, "breakpoint", f"iter_{iteration}")

for config in config_versions:
    version_id = '_'.join(map(str, config))
    # add tasks about current target project to database
    subprocess.run(["python", "-m", "testora.evaluation.PreparePRChunks"])

    # run RegressionFinder
    subprocess.run(["python", "-m", "testora.RegressionFinder", "--db", f"--paras={config}"])
    
    # store the breakpoint data seperately
    bp_data_cur_version = join(breakpoints_data_folder, f"bp_{version_id}")
    makedirs(bp_data_cur_version, exist_ok=True)
    for f in os.listdir('.'):
        if isfile(f) and f.endswith("_breakpoint_data.json"):
            shutil.move(f, bp_data_cur_version)

# # rename the llm cache, to check the Non-determinism of models
# cache_dir = "data/llm_cache/gpt-4o-mini-2024-07-18/cache.json"
# iter_marked_cache_dir = cache_dir.replace(".json", f"_{iteration}.json")
# os.rename(cache_dir, iter_marked_cache_dir)

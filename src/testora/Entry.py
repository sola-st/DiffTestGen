# Only needed if running different versions of prompts non-stop.
import ast
import shutil
import subprocess
from os.path import join, isfile, exists
from os import makedirs, rename
import os

max_iteration = 2
pr_split_num = 1 # could be 1, 2, or 3
    
config_versions = [
    [1, 0, 1, False],
    [5, 5, 5, False],
    [5, 8, 8, False],
    [5, 8, 8, True]
    ]

results_folder = join("data", "results")
# if exists(results_folder):
#     rename(results_folder, f"{results_folder}_backup")

for iteration in range(max_iteration):
    breakpoints_data_folder = join(results_folder, "breakpoint", f"iter_{iteration}")

    # the default cache file setting form LLMCache
    cache_dir = join("data", "llm_cache", "gpt-4o-mini-2024-07-18", "cache.json") 
    # to resuse the cache
    iter_marked_cache_dir = cache_dir.replace(".json", f"_{iteration}.json")
    if exists(iter_marked_cache_dir):
        os.rename(iter_marked_cache_dir, cache_dir)

    for config in config_versions:
        version_id = '_'.join(map(str, config))
        # add tasks about current target project to database
        result = subprocess.run(["python", "-m", "testora.evaluation.PreparePRChunks", f"--prsplit={pr_split_num}"])
        pr_list = ast.literal_eval(result.stdout.strip())

        # run RegressionFinder
        config.append(iteration) # config_with_iter
        subprocess.run(["python", "-m", "testora.RegressionFinder", "--db", f"--paras={config}", f"--prs={pr_list}"])
        
        # store the breakpoint data seperately
        bp_data_cur_version = join(breakpoints_data_folder, f"bp_{version_id}")
        makedirs(bp_data_cur_version, exist_ok=True)
        for f in os.listdir('.'):
            if isfile(f) and f.endswith("_breakpoint_data.json"):
                shutil.move(f, bp_data_cur_version)

    # rename the llm cache, to check the Non-determinism of models
    # Finally, we get a cache file for each iteration, and the cache file can be reuse if needed
    os.rename(cache_dir, iter_marked_cache_dir)
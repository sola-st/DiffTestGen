# Only needed if running different versions of prompts non-stop.
# import ast
import shutil
import subprocess
from os.path import join, isfile, exists
from os import makedirs, rename
import os

max_iteration = 5
# model_version = "gpt-4o-mini-2024-07-18"
model_version = "gpt-5-mini-2025-08-07"
pr_split_num = 1 # could be None, 1, 2, or 3

with open(".target_project", "r") as f:
    target_project = f.read().strip()
    
# pr_file = join("data", "meta", "pr_nums", f"{target_project}_PRs_subset10.txt")
# 10 + marshmallow 55, keras 150, 
# 0 + pandas 143, scipy 157
pr_file = join("data", "meta", "pr_nums", f"{target_project}_PRs_subset55.txt")
if pr_split_num:
    pr_file = pr_file.replace(".txt", f"_{pr_split_num}.txt")

with open(pr_file, "r") as f:
    prs = f.readlines()
pr_list = [int(pr) for pr in prs]

'''For a single congif: 
[initial_prompt_version, feedback_prompt_version, context_version, use_error_feedabck, fix_static_error, use_existing_tests]
* existing developer-written tests
    "none": do not make any extra effort about developer-written tests,
    "pr-modified": use the PR-modified tests, 
    "all": use PR-modified tests + local tests
'''
config_versions = [
    [1, 0, 1, False, False, None],
    # [5, 5, 5, False, False, None],
    # [5, 8, 8, False, False, None],
    [5, 8, 8, True, True, "pr-modified"]
]

results_folder = join("data", "results")
# if exists(results_folder):
#     rename(results_folder, f"{results_folder}_backup")

for iteration in range(max_iteration):
    breakpoints_data_folder = join(results_folder, "breakpoint", model_version, f"iter_{iteration}")

    # the default cache file setting form LLMCache
    # gpt-5-mini-2025-08-07, gpt-4o-mini-2024-07-18
    cache_dir = join("data", "llm_cache", model_version, "cache.json")
    # to resuse the cache
    iter_marked_cache_dir = cache_dir.replace(".json", f"_{iteration}.json")
    if exists(iter_marked_cache_dir):
        os.rename(iter_marked_cache_dir, cache_dir)

    for config in config_versions:
        version_id = '_'.join(map(str, config))
        # add tasks about current target project to database
        subprocess.run(["python", "-m", "testora.evaluation.PreparePRChunks", f"--prs={pr_list}"])

        # run RegressionFinder
        config_with_iter = config + [iteration, model_version]
        subprocess.run(["python", "-m", "testora.RegressionFinder", "--db", f"--paras={config_with_iter}", f"--prs={pr_list}"])
        
        # store the breakpoint data seperately
        bp_data_cur_version = join(breakpoints_data_folder, f"bp_{version_id}")
        makedirs(bp_data_cur_version, exist_ok=True)
        for f in os.listdir('.'):
            if isfile(f) and f.endswith("_breakpoint_data.json"):
                shutil.move(f, bp_data_cur_version)

    # rename the llm cache, to check the Non-determinism of models
    # Finally, we get a cache file for each iteration, and the cache file can be reuse if needed
    os.rename(cache_dir, iter_marked_cache_dir)
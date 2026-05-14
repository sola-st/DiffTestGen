import shutil
import subprocess
from os.path import exists, join, isfile
from os import makedirs
import os

iteration = 1
# model_version = "gpt-4o-mini-2024-07-18"
model_version = "gpt-5-mini-2025-08-07"
pr_split_num = 1 # could be None, 1, 2, or 3

with open(".target_project", "r") as f:
    target_project = f.read().strip()
    
subset_mode = True
pr_files = None
if subset_mode == True:
    pr_file = join("data", "meta", f"subset_{target_project}.txt")
else:
    pr_split_num = 1 # could be None, 1, 2, or 3
    # marshmallow 53, keras 133, pandas 128, scipy 129
    num = 65
    if target_project == "keras":
        num = 160
    elif target_project == "pandas":
        num = 143
    elif target_project == "scipy":
        num = 157

pr_file = join("data", "meta", "pr_nums", f"{target_project}_PRs_subset{num}.txt")
if pr_split_num:
    pr_file = pr_file.replace(".txt", f"_{pr_split_num}.txt")

with open(pr_file, "r") as f:
    prs = f.readlines()
pr_list = [int(pr) for pr in prs]

# initial_prompt, feedback_prompt, context_version, \
# pr_modified_tests, use_call_graph, fix_static_error, runtime_error_feedback
config_versions = {
    "testora": [1, 0, 1, True, None, False, False, False],
    "difftestgen": [5, 8, 8, True, "pr-modified", True, True, True],
    "only_coverage_feedback": [5, 8, 8, False, None, False, False, False], # testora + coverage feedback (only)
    "only_cg": [5, 0, 8, False, None, True, False, False], # testora + call graph (only)
} 
            
results_folder = join("data", "results")
log_folder = join(results_folder, model_version, f"iter_{iteration}")

# the default cache file setting form LLMCache
cache_dir = join("data", "llm_cache", model_version, "cache.json")

for config_name, config in config_versions.items():
    # to resuse the cache
    marked_cache_dir = cache_dir.replace(".json", f"_{iteration}_{config_name}.json")
    if exists(marked_cache_dir):
        os.rename(marked_cache_dir, cache_dir)

    config = config + [iteration, model_version]
    # run RegressionFinder
    for pr_num in pr_list:
        subprocess.run(["python", "-m", "testora.RegressionFinder", 
                "--project", target_project, "--pr", f"{pr_num}", f"--paras={config}"])
    
    # store the log results
    # no iter info, to separate local and db, but also good to have, becasuse the log file prefix are different.
    log_folder_cur_version = join(log_folder, f"log_{config_name}", target_project) 
    makedirs(log_folder, exist_ok=True)

    for f in os.listdir('.'):
        if isfile(f):
            if f.startswith("logs_"):
                shutil.move(f, log_folder)

    os.rename(cache_dir, marked_cache_dir)
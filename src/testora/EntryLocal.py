# Only needed if running different versions of prompts non-stop.
import shutil
import subprocess
from os.path import join, isfile, exists
from os import makedirs, rename
import os

iteration = 0
# model_version = "gpt-4o-mini-2024-07-18"
model_version = "gpt-5-mini-2025-08-07"

config_versions = [
    # [1, 0, 1, False, False, None],
    # [5, 5, 5, False, False, None],
    # [5, 8, 8, False, False, None],
    [5, 8, 8, True, True, "pr-modified"]
]
results_folder = join("data", "results")
if exists(results_folder):
    rename(results_folder, f"{results_folder}_backup")

breakpoints_data_folder = join(results_folder, "breakpoint", model_version)

with open(".target_project", "r") as f:
    target_project = f.read().strip()

with open(f"data/meta/pr_nums/{target_project}_PRs_subset10.txt", "r") as f:
    prs = f.readlines()
    pr_list = [int(pr) for pr in prs]

for config in config_versions:
    version_id = '_'.join(map(str, config))
    config = config + [iteration, model_version]
    # run RegressionFinder
    for pr_num in pr_list:
        subprocess.run(["python", "-m", "testora.RegressionFinder", 
                "--project", target_project, "--pr", f"{pr_num}", f"--paras={config}"])
    
    # store the breakpoint data seperately
    bp_data_cur_version = join(breakpoints_data_folder, f"bp_{version_id}")
    makedirs(bp_data_cur_version, exist_ok=True)
    # store the log results
    # no iter info, to separate local and db, but also good to have, becasuse the log file prefix are different.
    log_folder = join(results_folder, model_version, f"log_{version_id}", target_project) 
    makedirs(log_folder, exist_ok=True)

    for f in os.listdir('.'):
        if isfile(f):
            if f.endswith("_breakpoint_data.json"):
                shutil.move(f, bp_data_cur_version)
            elif f.startswith("logs_"):
                shutil.move(f, log_folder)
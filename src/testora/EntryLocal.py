# Only needed if running different versions of prompts non-stop.
import shutil
import subprocess
from os.path import join, isfile, exists
from os import makedirs, rename
import os


config_versions = [
    [1, 0, 1],
    [1, 1, 1],
    [2, 2, 2],
    [3, 3, 3],
    [4, 4, 4],
    [5, 5, 5],
    [6, 6, 6],
    [7, 7, 7],
    [1, 8, 8]
    ]

results_folder = join("data", "results")
if exists(results_folder):
    rename(results_folder, f"{results_folder}_backup")

breakpoints_data_folder = join("data", "results", "breakpoint")

with open(".target_project", "r") as f:
    target_project = f.read().strip()

with open(f"data/meta/pr_nums/{target_project}_PRs_subset10.txt", "r") as f:
    prs = f.readlines()
    pr_list = [int(pr) for pr in prs]

for config in config_versions:
    version_id = '_'.join(map(str, config))
    # run RegressionFinder
    for pr_num in pr_list:
        subprocess.run(["python", "-m", "testora.RegressionFinder", 
                "--project", target_project, "--pr", f"{pr_num}", f"--paras={config}"])
    
    # store the breakpoint data seperately
    bp_data_cur_version = join(breakpoints_data_folder, f"bp_{version_id}")
    makedirs(bp_data_cur_version, exist_ok=True)
    # store the log results
    log_folder = join("data", "results", f"log_{version_id}", target_project)
    makedirs(log_folder, exist_ok=True)

    for f in os.listdir('.'):
        if isfile(f):
            if f.endswith("_breakpoint_data.json"):
                shutil.move(f, bp_data_cur_version)
            elif f.startswith("logs_"):
                shutil.move(f, log_folder)
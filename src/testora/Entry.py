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
# log_folder = join(results_folder, "logs")

for config in config_versions:
    version_id = '_'.join(map(str, config))
    # add tasks about current target prohect to database
    subprocess.run(["python", "-m", "testora.evaluation.PreparePRChunks"])

    # run RegressionFinder
    subprocess.run(["python", "-m", "testora.RegressionFinder", "--db", f"--paras={config}"])
    
    # store the breakpoint data seperately
    bp_data_cur_version = join(breakpoints_data_folder, f"bp_{version_id}")
    makedirs(bp_data_cur_version, exist_ok=True)
    for f in os.listdir('.'):
        if isfile(f) and f.endswith("_breakpoint_data.json"):
            shutil.move(f, bp_data_cur_version)

    # # load the results
    # makedirs(join("data", "results", "keras"), exist_ok=True)
    # subprocess.run(["python", "-m", "testora.evaluation.EvalTaskManager", "--fetch"])
    # rename(join("data", "results", "keras"), join(log_folder, f"log_{version_id}"))
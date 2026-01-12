import shutil
import subprocess
from os.path import join, isfile
from os import makedirs, listdir
import os

iteration = 0
mode = "ablation" # could be 'comparison' and 'ablation'
# model_version = "gpt-4o-mini-2024-07-18"
model_version = "gpt-5-mini-2025-08-07"

config_versions = [
    [1, 0, 1, False, False, None],
    [5, 8, 8, True, True, "pr-modified"]
]
        
results_folder = join("data", "results")
breakpoints_data_folder = join(results_folder, "breakpoint", model_version, f"iter_{iteration}")
classification_folder = join(results_folder, "breakpoint", model_version, f"iter_{iteration}")

with open(".target_project", "r") as f:
    target_project = f.read().strip()

for config in config_versions:
    version_id = '_'.join(map(str, config))
    # config = config + [iteration, model_version]
    breakpoint_files = listdir(join(breakpoints_data_folder, f"bp_{version_id}"))
    for b_file in breakpoint_files:
        pr_num = b_file.split("_", 2)[1]
        # print(pr_num)
        subprocess.run(["python", "-m", "testora.RegressionClassifier", 
                "--project", target_project, "--pr", pr_num])
    
    # move the classification data to a desired foler
    classification_cur_version = join(classification_folder, f"classification_{version_id}")
    makedirs(classification_cur_version, exist_ok=True)
    # store the log results
    # no iter info, to separate local and db, but also good to have, becasuse the log file prefix are different.
    log_folder = join(results_folder, model_version, f"log_{version_id}", target_project) 
    makedirs(log_folder, exist_ok=True)

    for f in os.listdir('.'):
        if isfile(f):
            if f.endswith(".json"): # add another condition to distinguish log and calssification if needed
                shutil.move(f, classification_cur_version)
import shutil
import subprocess
from os.path import join, isfile
from os import makedirs, listdir
import os

iteration = 0
mode = "ablation" # could be 'comparison' and 'ablation'
# model_version = "gpt-4o-mini-2024-07-18"
model_version = "gpt-5-mini-2025-08-07"

config_versions = {
    "testora": [1, 0, 1, None, False, False, False],
    "difftestgen": [5, 8, 8, "pr-modified", True, True, True]
}

results_folder = join("data", "results")
log_folder = join(results_folder, model_version, f"iter_{iteration}")
classification_folder = join(results_folder, "classification", model_version, f"iter_{iteration}")

with open(".target_project", "r") as f:
    target_project = f.read().strip()

for config_name, config in config_versions.items():
    version_folder = join(log_folder, f"log_{config_name}", target_project)
    log_files = listdir(version_folder)
    for b_file in log_files:
        pr_num = b_file.split("_", 1)[0]
        # print(pr_num)
        subprocess.run(["python", "-m", "testora.RegressionClassifier", 
                "--project", target_project, "--pr", pr_num, "--breakpoint_file", join(version_folder, b_file)])
        break
    
    # move the classification data to a desired foler
    classification_cur_version = join(classification_folder, f"cf_{config_name}", target_project)
    makedirs(classification_cur_version, exist_ok=True)
    for f in os.listdir('.'):
        if isfile(f):
            if f.endswith(".json"): # add another condition to distinguish log and classification if needed
                shutil.move(f, classification_cur_version)
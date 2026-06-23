import shutil
import subprocess
from os.path import join, isfile
from os import makedirs, listdir
import os

iteration = 0
# model_version = "gpt-4o-mini-2024-07-18"
model_version = "gpt-5-mini-2025-08-07"

config_versions = {
    # "testora": [1, 0, 1, False, None, False, False, False], # all turned off
    "difftestgen": [5, 8, 8, True, "pr-modified", True, True, True], # all turned on
    # "only_coverage_feedback": [5, 8, 8, False, None, False, False, False], # testora + coverage feedback (only)
    # "only_cg": [5, 0, 8, False, None, True, False, False], # testora + call graph (only)
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
                "--project", target_project, "--pr", pr_num, "--log_file", join(version_folder, b_file)])
    
    # move the classification data to a desired folder
    classification_cur_version = join(classification_folder, f"classification_{config_name}", target_project)
    makedirs(classification_cur_version, exist_ok=True)
    for f in os.listdir('.'):
        if isfile(f):
            if f.startswith("logs_"):
                shutil.move(f, classification_cur_version)
import shutil
import subprocess
from os.path import exists, join, isfile
from os import makedirs, listdir
import os

iteration = 0
model_version = "gpt-5-mini-2025-08-07"
top_k = "5"
projects = ["pandas", "keras", "scipy"] # "marshmallow",
config_versions = {
    "difftestgen": [5, 8, 8, True, "pr-modified", True, True, True], # all turned on
}

results_folder = join("data", "results")
log_folder = join(results_folder, model_version, f"iter_{iteration}")
classification_folder = join(results_folder, "classification", model_version, f"iter_{iteration}")

with open(".target_project", "r") as f:
    target_project = f.read().strip()
pr_file = join("data", "meta", "pr_classifier", f"{target_project}.txt")
with open(pr_file, "r") as f:
    prs = f.readlines()
pr_list = [int(pr) for pr in prs]

cache_dir = join("data", "llm_cache", model_version, "cache.json")
for config_name, config in config_versions.items():
    for project in projects:
        # to resuse the cache
        marked_cache_dir = cache_dir.replace(".json", f"_{iteration}_classification_{config_name}_{project}.json")
        if exists(marked_cache_dir):
            os.rename(marked_cache_dir, cache_dir)

        version_folder = join(log_folder, f"log_{config_name}", target_project)
        checked_indices_folder = join(classification_folder, f"checked_indices_{config_name}", target_project)
        makedirs(checked_indices_folder, exist_ok=True)

        log_files = listdir(version_folder)
        sorted(log_files)
        # idx = [idx for idx, file in enumerate(log_files) if file.startswith("2699")][0]
        # log_files = log_files[idx: idx+2]
        # print(log_files)

        for b_file in log_files:
            pr_num = b_file.split("_", 1)[0]
            if int(pr_num) in pr_list:
                # print(pr_num)
                checked_indices_file = join(checked_indices_folder, f"{pr_num}.txt")
                subprocess.run(["python", "-m", "testora.RegressionClassifier", 
                        "--project", target_project, "--pr", pr_num, "--log_file", join(version_folder, b_file),
                        "--checked_indices_file", checked_indices_file, "--top_k", top_k])
        
        os.rename(cache_dir, marked_cache_dir)

        # move the classification data to a desired folder
        classification_cur_version = join(classification_folder, f"classification_{config_name}", target_project)
        makedirs(classification_cur_version, exist_ok=True)
        for f in os.listdir('.'):
            if isfile(f):
                if f.startswith("logs_"):
                    shutil.move(f, classification_cur_version)
import shutil
import subprocess
from os.path import join, isfile
from os import makedirs
import os


# To run our approach on ChaCo-PRs.
iteration = 0
model_versions = ["gpt-4o-mini-2024-07-18", "gpt-5-mini-2025-08-07"]
config_name = "difftestgen"
config = [5, 8, 8, True, "pr-modified", True, True, True]

results_folder = join("data", "results")

with open(".target_project", "r") as f:
        target_project = f.read().strip()

num = 8
if target_project == "scipy":
    num = 16

pr_file = join("data", "meta", "chaco_prs", "chaco", f"{target_project}_common_{num}.txt")
with open(pr_file, "r") as f:
    prs = f.readlines()
    pr_list = [int(pr) for pr in prs]

for model_version in model_versions:
    config = config + [iteration, model_version]
    # run RegressionFinder
    for pr_num in pr_list:
        subprocess.run(["python", "-m", "testora.RegressionFinder", 
                "--project", target_project, "--pr", f"{pr_num}", f"--paras={config}"])
    
    # store the log results
    # no iter info, to separate local and db, but also good to have, becasuse the log file prefix are different.
    log_folder = join(results_folder, model_version, f"iter_{iteration}", f"log_chaco_{config_name}", target_project) 
    makedirs(log_folder, exist_ok=True)

    for f in os.listdir('.'):
        if isfile(f):
            if f.startswith("logs_"):
                shutil.move(f, log_folder)
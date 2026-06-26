import shutil
import subprocess
from os.path import exists, join, isfile
from os import makedirs
import os


# To run our approach on ChaCo-PRs.
iteration = 0
dataset = "unique", # "unique" or "all"
model_versions = ["gpt-4o-mini-2024-07-18", "gpt-5-mini-2025-08-07"]
config_name = "difftestgen"
config = [5, 8, 8, True, "pr-modified", True, True, True]

results_folder = join("data", "results")

with open(".target_project", "r") as f:
        target_project = f.read().strip()

pr_file = None
if dataset == "unique": # only the ones in ChaCo not in testora
    num = 8
    if target_project == "scipy":
        num = 16
    pr_file = join("data", "meta", "chaco_prs", "chaco", f"{target_project}_unique_{num}.txt")
else: # all PRs
    num = 16
    if target_project == "scipy":
        num = 18
    pr_file = join("data", "meta", "chaco_prs", "chaco", f"chaco_{target_project}_{num}.txt")

with open(pr_file, "r") as f:
    prs = f.readlines()
    pr_list = [int(pr) for pr in prs]

for model_version in model_versions:
    cache_dir = join("data", "llm_cache", model_version, "cache.json")
    config = config + [iteration, model_version]

    # to resuse and identify the cache
    marked_cache_dir = cache_dir.replace(".json", f"_{iteration}_chaco.json")
    if exists(marked_cache_dir):
        os.rename(marked_cache_dir, cache_dir)

    # run RegressionFinder
    for pr_num in pr_list:
        subprocess.run(["python", "-m", "testora.RegressionFinder", 
                "--project", target_project, "--pr", f"{pr_num}", f"--paras={config}"])
    
    os.rename(cache_dir, marked_cache_dir)

    # store the log results
    log_folder = join(results_folder, model_version, f"iter_{iteration}", f"log_chaco_{config_name}", target_project) 
    makedirs(log_folder, exist_ok=True)

    for f in os.listdir('.'):
        if isfile(f):
            if f.startswith("logs_"):
                shutil.move(f, log_folder)
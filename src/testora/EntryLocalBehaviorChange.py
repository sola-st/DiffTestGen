import os
import shutil
import subprocess
import sys
from os.path import exists, isfile, join


model_version = "gpt-5-mini-2025-08-07"
with open(".target_project", "r") as f:
    target_project = f.read().strip()

pr_count = {"marshmallow": 53, "keras": 133, "pandas": 127, "scipy": 126}[target_project]
pr_file = join("data", "meta", "pr_nums_checks", f"{target_project}_PRs_subset{pr_count}.txt")

with open(pr_file, "r") as f:
    pr_list = [int(pr.strip()) for pr in f if pr.strip()]

log_folder = join("data", "results", "behavior_change", model_version, target_project)
os.makedirs(log_folder, exist_ok=True)

# the default cache file setting form LLMCache
cache_dir = join("data", "llm_cache", model_version, "cache.json")
marked_cache_dir = cache_dir.replace(".json", f"_PR_classification.json")
if exists(marked_cache_dir):
    os.rename(marked_cache_dir, cache_dir)

for pr_num in pr_list:
    subprocess.run([sys.executable, "-m", "testora.BehaviorChangeClassifier", "--project", target_project, "--pr", str(pr_num)], check=True)

for log_file in os.listdir("."):
    if log_file.startswith("logs_") and isfile(log_file):
        shutil.move(log_file, log_folder)
os.rename(cache_dir, marked_cache_dir)

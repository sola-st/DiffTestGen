import shutil
import subprocess
from os.path import join, isfile
from os import makedirs
import os


iteration = 0 # exactly the iteration number, not the border of a range.
# model_version = "gpt-4o-mini-2024-07-18"
model_version = "gpt-5-mini-2025-08-07"

with open(".target_project", "r") as f:
    target_project = f.read().strip()
    
subset_mode = False
pr_files = None
if subset_mode == True:
    pr_file = join("data", "meta", f"subset_{target_project}.txt")
else:
    pr_split_num = 1 # could be None, 1, 2, or 3
    # marshmallow 53, keras 133, pandas 127, scipy 126 ==> 439
    num = 53
    if target_project == "keras":
        num = 133
    elif target_project == "pandas":
        num = 127
    elif target_project == "scipy":
        num = 126

    pr_file = join("data", "meta", "pr_nums_checks", f"{target_project}_PRs_subset{num}.txt")

with open(pr_file, "r") as f:
    prs = f.readlines()
pr_list = [int(pr) for pr in prs]

# initial_prompt, feedback_prompt, context_version, \
# pr_modified_tests, use_call_graph, fix_static_error, runtime_error_feedback
config_versions = {
    "difftestgen": [5, 8, 8, True, "pr-modified", True, True, True],
} 
            
results_folder = join("data", "results")
log_folder = join(results_folder, model_version, f"iter_{iteration}")


for config_name, config in config_versions.items():
    config = config + [iteration, model_version]
    # run RegressionFinder
    for pr_num in pr_list:
        subprocess.run(["python", "-m", "testora.RegressionFinder", 
                "--project", target_project, "--pr", f"{pr_num}", f"--paras={config}"])
    
    log_folder_cur_version = join(log_folder, f"log_{config_name}_call_paths", target_project) 
    makedirs(log_folder, exist_ok=True)

    for f in os.listdir('.'):
        if isfile(f):
            if f.startswith("logs_"):
                shutil.move(f, log_folder_cur_version)
import json
from os.path import join
from os import listdir


# record early-stopped PRs
iteration = 0
version_id = "1_0_1_False"
model_version = "gpt-5-mini-2025-08-07"
target_projects = ["scipy", "marshmallow", "pandas", "keras"]
results_folder = "data/results"

for project in target_projects:
    log_folder = join(results_folder, model_version, f"iter_{iteration}", f"log_{version_id}", project)
    non_executable = []
    remained_pr_nums = []

    log_files = listdir(log_folder)
    for file in log_files:
        log_file = join(log_folder, file)
        
        with open(log_file, "r") as f:
            info = json.load(f) 

        pr_num = str(info[1]["pr_nb"])
        if "Ignoring because no executable modified code lines/statements." in json.dumps(info):
            non_executable.append(pr_num)
        else:
            remained_pr_nums.append(pr_num)
    
    if non_executable:
        with open(f"{project}_PRs_{len(remained_pr_nums)}.txt", "a") as f:
            f.writelines("\n".join(remained_pr_nums))
        
        with open(f"{project}_non_executable_PRs_{len(non_executable)}.txt", "a") as f:
            f.writelines("\n".join(non_executable))

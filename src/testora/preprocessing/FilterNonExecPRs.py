import json
from os.path import join


iteration = 0
target_projects = ["scipy", "marshmallow", "pandas", "keras"]
base_folder = "data/results/table_and_plots/gpt-5-mini-2025-08-07"
for project in target_projects:
    coverage_file = join(base_folder, f"iter_{iteration}", project, "coverage_comparison_meta_1_0_1_False.json")
    non_executable = []
    remained_pr_nums = []

    with open(coverage_file, "r") as f:
        info = json.load(f) 

    for info_block in info:
        pr_num = list(info_block.keys())[-1]
        if json.dumps(info_block).count("100.00% (0/0)") == 2:
            non_executable.append(pr_num)
        else:
            remained_pr_nums.append(pr_num)
    
    if non_executable:
        with open(f"{project}_PRs_{len(remained_pr_nums)}.txt", "w") as f:
            f.writelines("\n".join(remained_pr_nums))
        
        with open(f"{project}_non_executable_PRs_{len(non_executable)}.txt", "w") as f:
            f.writelines("\n".join(non_executable))

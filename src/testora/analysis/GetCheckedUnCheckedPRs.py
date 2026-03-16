from os.path import join
from os import listdir


iteration = 0
model_version = "gpt-5-mini-2025-08-07"
version_name = "log_no_coverage_feedback"
results_folder = join("data", "results", model_version, f"iter_{iteration}", version_name)
target_projects = ["scipy"] #, "scipy"] #["marshmallow", "pandas", "scipy", "keras"]

for project in target_projects:
    # marshmallow 53, keras 133, pandas 128, scipy 129
    num = 65
    if project == "keras":
        num = 160
    elif project == "pandas":
        num = 143
    elif project == "scipy":
        num = 157
    # pr_file = join("data", "meta", "pr_nums_checks", f"{project}_PRs_subset{num}.txt")
    pr_file = join("data", "meta", "pr_nums", f"{project}_PRs_all.txt")

    with open(pr_file, "r") as f:
        prs = f.readlines()
    all_prs = [int(pr) for pr in prs]

    all_checked_prs = set()

    log_folder = join(results_folder, project)
    log_files = listdir(log_folder)
    for file in log_files:
        all_checked_prs.add(int(file.split("_")[0]))

    with open(f"{project}_checked.txt", "w") as f:
        f.writelines("\n".join(map(str, all_checked_prs)))

    unchecked_prs = [pr for pr in all_prs if pr not in all_checked_prs]
    with open(f"{project}_unchecked_base_{num}.txt", "w") as f:
        f.writelines("\n".join(map(str, unchecked_prs)))
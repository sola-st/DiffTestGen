from os.path import join
from os import listdir


iteration = 0
model_version = "gpt-5-mini-2025-08-07"
version_id = "log_5_8_8_True"
results_folder = join("data", "results", model_version, f"iter_{iteration}", version_id)
target_projects = ["marshmallow", "pandas", "scipy", "keras"]


for project in target_projects:
    all_checked_prs = []

    log_folder = join(results_folder, project)
    log_files = listdir(log_folder)
    for file in log_files:
        all_checked_prs.append(file.split("_")[0])

    with open(f"data/meta/pr_nums/{project}_checked.txt", "w") as f:
        f.writelines("\n".join(all_checked_prs))
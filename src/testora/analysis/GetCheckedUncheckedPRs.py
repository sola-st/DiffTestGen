from os.path import join
from os import listdir


iteration = 0
model_version = "gpt-5-mini-2025-08-07"
subset_mode = False
pr_split_num_max = 3
version_names = ["difftestgen", "testora", "no_coverage_feedback", "no_cg", "no_runtime", "no_bodies"]
for version_name in version_names:
    target_projects = ["marshmallow", "pandas", "scipy", "keras"]
    results_folder = join("data", "results", model_version, f"iter_{iteration}", f"log_{version_name}")
    if subset_mode:
        results_folder = join("data", "results", model_version, f"iter_{iteration}_subset", version_name)

    num = 0
    for project in target_projects:
        if subset_mode:
            pr_file = join("data", "meta",  f"subset_{project}.txt")
        else: # marshmallow 53, keras 133, pandas 128, scipy 129
            num = 53
            if project == "keras":
                num = 133
            elif project == "pandas":
                num = 128
            elif project == "scipy":
                num = 129
            pr_file_base = join("data", "meta", "pr_nums_checks", f"{project}_PRs_subset{num}.txt")
            # pr_file = join("data", "meta", "pr_nums", f"{project}_PRs_all.txt")
            # pr_file_base = join("data", "meta",  f"{project}.txt")

        for i in range(1, pr_split_num_max + 1):
            if subset_mode:
                pr_file = pr_file_base.replace(".txt", f"_{i}.txt")
            with open(pr_file, "r") as f:
                prs = f.readlines()
            all_prs = [int(pr) for pr in prs]

            all_checked_prs = set()

            log_folder = join(results_folder, project)
            log_files = listdir(log_folder)
            for file in log_files:
                pr_num = int(file.split("_", 1)[0])
                if subset_mode == True:
                    if pr_num not in all_prs:
                        continue
                all_checked_prs.add(pr_num)

            with open(f"{project}_{version_name}_{i}_checked.txt", "w") as f:
                f.writelines("\n".join(map(str, all_checked_prs)))

            unchecked_prs = [pr for pr in all_prs if pr not in all_checked_prs]
            print(f"Project: {project},version: {version_name}, split {i}, Unchecked PRs: {len(unchecked_prs)}")
            with open(f"{project}_{version_name}_{i}_unchecked_base_{num}.txt", "w") as f:
                f.writelines("\n".join(map(str, unchecked_prs)))
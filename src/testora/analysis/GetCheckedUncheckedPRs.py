from os.path import join
from os import listdir


iteration = 2
model_version = "gpt-5-mini-2025-08-07"
subset_mode = False
pr_split_num_max = 6
version_names = ["testora", "testora_pp", "difftestgen", "only_coverage_feedback", "only_cg"]
for version_name in version_names:
    target_projects = ["keras"]#, "pandas"]#, "scipy", "keras"]
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
                num = 127
            elif project == "scipy":
                num = 126
            pr_file_base = join("data", "meta", "pr_nums_checks", f"{project}_PRs_subset{num}.txt")
            # pr_file = join("data", "meta", "pr_nums", f"{project}_PRs_all.txt")
            # pr_file_base = join("data", "meta",  f"{project}.txt")

        print(f"Iteration: {iteration}, project: {project}, version_name: {version_name}")
        for i in range(1, pr_split_num_max + 1):
            # if subset_mode:
            pr_file = pr_file_base.replace(".txt", f"_{i}.txt")
            with open(pr_file, "r") as f:
                prs = f.readlines()
            split_prs = [int(pr) for pr in prs]

            unchecked_prs = []
            split_checked_prs = set()

            log_folder = join(results_folder, project)
            log_files = listdir(log_folder)
            for file in log_files:
                pr_num = int(file.split("_", 1)[0])
                if pr_num in split_prs:
                    # print(f"Found log for PR {pr_num} in split {i}")
                    split_checked_prs.add(pr_num)
            
            unchecked_prs = [pr for pr in split_prs if pr not in split_checked_prs]
            if unchecked_prs:
                # if split_checked_prs:
                #     # print(f"Project: {project}, version: {version_name}, split {i}, Checked PRs: {len(all_checked_prs)}")
                #     with open(f"iter{iteration}_{project}_{version_name}_split{i}_checked{len(split_checked_prs)}.txt", "w") as f:
                #         f.writelines("\n".join(map(str, split_checked_prs)))
                
                print(f"Split {i}, Unchecked PRs: {len(unchecked_prs)}")
                with open(f"iter{iteration}_{project}_{version_name}_split{i}_unchecked{len(unchecked_prs)}.txt", "w") as f:
                    f.writelines("\n".join(map(str, unchecked_prs)))
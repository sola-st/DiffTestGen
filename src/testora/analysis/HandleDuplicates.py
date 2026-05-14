from os.path import join
import os
import shutil
        
mode = "deduplication" # "deduplication" or "get_subset"
results_folder = join("data", "results")
iteration = 0
# model_version = "gpt-4o-mini-2024-07-18"
model_version = "gpt-5-mini-2025-08-07"
project_info = {
    "scipy": 129,
    "marshmallow": 53,
    "pandas": 128,
    "keras": 133
}

config_versions = {
    "testora": [1, 0, 1, False, None, False, False, False],
    "difftestgen": [5, 8, 8, True, "pr-modified", True, True, True],
    "no_coverage_feedback": [5, 0, 8, True, 'pr-modified', True, True, True], 
    "no_cg": [5, 8, 8, True, 'pr-modified', False, True, True],
    "no_runtime": [5, 8, 8, True, 'pr-modified', True, True, False],
    "no_bodies": [5, 8, 8, False, None, True, True, True], # turn off both test function body and function body
}

for config_name, config in config_versions.items():
    project_level = []
    single_iteration = []

    for target_project, num in project_info.items():
        pr_file = join("data", "meta", "pr_nums_checks", f"{target_project}_PRs_subset{num}.txt")
        # pr_file = join("data", "meta", "subset_scipy.txt")
        with open(pr_file, "r") as f:
            prs = f.readlines()
        pr_list = [pr.strip() for pr in prs]
        
        log_folder = join(results_folder, model_version, f"iter_{iteration}", f"log_{config_name}", target_project)
        all_log_files = os.listdir(log_folder)

        if mode == "get_subset":
            for dup_file in all_log_files: # keep the first log file, move the duplicates to a separate folder
                pr = dup_file.split("_", 1)[0]
                if pr in pr_list:
                    log_folder_99 = join(results_folder, model_version, f"iter_{iteration}_subset", f"log_{config_name}", target_project)
                    os.makedirs(log_folder_99, exist_ok=True)
                    shutil.copyfile(join(log_folder, dup_file), join(log_folder_99, dup_file))
        elif mode == "deduplication":
            for pr in pr_list:
                relevant_log_files = [file for file in all_log_files if file.startswith(pr + "_")]
                relevant_log_files.sort() # sort by timestamp
                
                if relevant_log_files:
                    log_folder_for_duplicates = join(results_folder, model_version, f"iter_{iteration}_duplicates", f"log_{config_name}", target_project)
                    os.makedirs(log_folder_for_duplicates, exist_ok=True)
                    for dup_file in relevant_log_files[1:]: # keep the first log file, move the duplicates to a separate folder
                        shutil.move(join(log_folder, dup_file), join(log_folder_for_duplicates, dup_file))
            

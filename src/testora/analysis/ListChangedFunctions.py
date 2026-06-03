import json
from os.path import join
import os


results_folder = join("data", "results")
iteration = 0
# model_version = "gpt-4o-mini-2024-07-18"
model_version = "gpt-5-mini-2025-08-07"
project_info = {
    "keras": 133,
    "marshmallow": 53,
    "pandas": 127,
    "scipy": 126,
}

config_versions = {
    "testora": [1, 0, 1, False, None, False, False, False],
    "difftestgen": [5, 8, 8, True, "pr-modified", True, True, True],
    "only_coverage_feedback": [5, 8, 8, False, None, False, False, False], 
    "only_cg": [5, 0, 8, False, None, True, False, False],
}

for config_name, __ in config_versions.items():
    for target_project, __ in project_info.items():
        changed_function_items = []
        log_folder = join(results_folder, model_version, f"iter_{iteration}", f"log_{config_name}", target_project)
        all_log_files = os.listdir(log_folder)
        for dup_file in all_log_files: # keep the first log file, move the duplicates to a separate folder
            with open(join(log_folder, dup_file), "r") as f:
                info = json.load(f)
            for block in info:
                if "message" in block.keys():
                    if block["message"].startswith("Querying") or block["message"].startswith("Cached result for querying"):
                        try:
                            changed_function_line_tmp = block["content"].split("The diff affects the following functions: ")[1]
                            changed_function_line = changed_function_line_tmp.split("\n")[0].strip()
                            changed_function_items.append(f"{dup_file.split('_')[0]}: {changed_function_line}")
                        except:
                            print(dup_file)
                        break

        with open(f"{target_project}_changed_functions_with_pr_num.txt", "w") as f:
            f.writelines("\n".join(changed_function_items))

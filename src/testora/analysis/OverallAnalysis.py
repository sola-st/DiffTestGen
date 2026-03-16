import json
from os.path import exists, join, isfile
from os import makedirs
import os
import shutil

iteration = 0
# model_version = "gpt-4o-mini-2024-07-18"
model_version = "gpt-5-mini-2025-08-07"
projects = ["marshmallow", "pandas", "scipy", "keras"]
    
# marshmallow 53, keras 133, pandas 128, scipy 129
config_versions = {
    # "testora": [1, 0, 1, None, False, False, False],
    "difftestgen": [5, 8, 8, "pr-modified", True, True, True],
    "no_coverage_feedback": [5, 0, 8, 'pr-modified', True, True, True], 
    # "no_cg": [5, 8, 8, 'pr-modified', False, True, True]
}
        
results_folder = join("data", "results")
log_folder = join(results_folder, model_version, f"iter_{iteration}")

meta = {}
for project in projects:
    meta.update({project: {}})
    for config_name, config in config_versions.items():
        all_prs = [] 
        differ_prs = set()
        differ_tests = 0
        # full_config = "_".join(map(str, config + [config_name]))
        full_config = config_name

        log_folder_cur_version = join(log_folder, f"log_{full_config}", project) 
        log_folder_cur_version_duplications = join(log_folder, f"log_{full_config}", f"{project}_dup") 
        if exists(log_folder_cur_version):
            print(f"{project}   {full_config}")
            for file in os.listdir(log_folder_cur_version):
                pr_num = file.split("_")[0]
                log_file_path = join(log_folder_cur_version, file)
                if pr_num not in all_prs:
                    all_prs.append(pr_num)
                    if isfile(log_file_path):
                        with open(log_file_path, "r") as f:
                            info = json.load(f) 
                        for block in info:
                            if block["message"].startswith("Different outputs"):
                                differ_tests += 1
                                differ_prs.add(pr_num)
                else:
                    makedirs(log_folder_cur_version_duplications, exist_ok=True)
                    shutil.move(log_file_path, join(log_folder_cur_version_duplications, file))

            meta[project].update({config_name:
                {"prs" : f"{len(differ_prs)} / {len(all_prs)}", 
                "tests" : f"{differ_tests}"}
            })


result_file = join(results_folder, f"different_pr_tests_overall_{model_version}.json")
with open(result_file, "w") as f:
    json.dump(meta, f, indent=4)
import ast
from collections import Counter
import json
from os.path import exists, join, isfile
from os import makedirs
import os
import shutil

iteration = 0
# model_version = "gpt-4o-mini-2024-07-18"
model_version = "gpt-5-mini-2025-08-07"
projects = ["marshmallow", "pandas", "scipy"]#, "keras"] ["scipy"] # 
    
# marshmallow 53, keras 133, pandas 128, scipy 129
config_versions = {
    # "testora": [1, 0, 1, None, False, False, False],
    "difftestgen": [5, 8, 8, "pr-modified", True, True, True],
    "no_coverage_feedback": [5, 0, 8, 'pr-modified', True, True, True], 
    "no_cg": [5, 8, 8, 'pr-modified', False, True, True],
    "no_runtime": [5, 8, 8, 'pr-modified', True, True, False]
}
        
results_folder = join("data", "results")
log_folder = join(results_folder, model_version, f"iter_{iteration}")
output_folder = join(results_folder, "ablation_delta_check_subset")
makedirs(output_folder, exist_ok=True)

meta = {}
for project in projects:
    project_ablation_delta_check = []
    meta.update({project: {}})
    pr_file = f"data/meta/subset_{project}.txt"
    with open(pr_file, "r") as f:
        prs = f.readlines()
    subset_prs = [int(pr) for pr in prs]

    output_folder_proj = join(output_folder, project)
    makedirs(output_folder_proj, exist_ok=True)

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
                if int(pr_num) in subset_prs:
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

        with open(join(output_folder_proj, f"differ_{config_name}_{len(differ_prs)}.txt"), "w") as f:
            f.writelines("\n".join(differ_prs))
        
        project_ablation_delta_check.extend(list(differ_prs))

    counts = Counter(project_ablation_delta_check)

    with open(join(output_folder_proj, f"ablation_counts_{project}.txt"), "w") as f:
        for item, count in counts.most_common():
            f.write(f"{item}: {count}\n")
    
result_file = join(results_folder, f"different_pr_tests_overall_{model_version}.json")
with open(result_file, "w") as f:
    json.dump(meta, f, indent=4)
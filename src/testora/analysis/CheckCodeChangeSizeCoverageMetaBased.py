import json
from os import makedirs
from os.path import join


iteration = 0
# model_version = "gpt-4o-mini-2024-07-18"
model_version = "gpt-5-mini-2025-08-07"

target_projects = ["keras", "marshmallow", "pandas", "scipy"]
name = "chaco" # difftestgen or chaco
if name == "chaco":
    target_projects = ["pandas", "scipy"]

results_folder = join("data", "results")
output_base_folder = join(results_folder, "table_and_plots", "coverage_meta_info", f"iter_{iteration}")  
across_projects_change_size = []

for project in target_projects:
    project_change_size = []
    log_folder = join(results_folder, model_version, f"iter_{iteration}", f"log_{name}", project)
    meta_file = join(output_base_folder, f"log_{name}", f"{project}_coverage_meta.json")
    if name == "chaco":
        log_folder = join(results_folder, model_version, f"iter_{iteration}", f"log_{name}_difftestgen", project)
        meta_file = join(output_base_folder, name, model_version, f"dtg_{project}_coverage_meta.json")
    
    with open(meta_file, "r") as f:
        all_from_cur_version = json.load(f)

    for pr_rec in all_from_cur_version:
        old_changed_lines_num = 0
        new_changed_lines_num = 0

        pr_num = list(pr_rec.keys())[-1]
        last_round_cov_pair_dict = pr_rec[pr_num]["Initial"]["R-0"]
        if last_round_cov_pair_dict["old"] != "--":
            old_changed_lines_num = int(last_round_cov_pair_dict["old"].split("/")[1].strip(")"))
        if last_round_cov_pair_dict["new"] != "--":
            new_changed_lines_num = int(last_round_cov_pair_dict["new"].split("/")[1].strip(")"))

        project_change_size.append(old_changed_lines_num + new_changed_lines_num)

    print(f"{project} change size: {(sum(project_change_size) / len(project_change_size))}")
    across_projects_change_size.extend(project_change_size)

print(f"Overall change size: {(sum(across_projects_change_size) / len(across_projects_change_size))}")
# print("\n".join(map(str, across_projects_change_size)))

from os.path import join
import json
from os import listdir, makedirs
import shutil
from testora.prompts.RuntimeErrorsFixingPrompt import extract_error_type
from collections import Counter


iteration = 0
target_projects = ["scipy", "marshmallow", "pandas", "keras"]
cov_base_folder = "data/results/table_and_plots/gpt-5-mini-2025-08-07"

base_folder = "data/results/gpt-5-mini-2025-08-07/iter_0/check_5_8_8_True_latest"
target_parent_folder = f"{base_folder}_0differs"
error_to_0differs = join(target_parent_folder, "error")
error_0cov_to_0differs = join(target_parent_folder, "error_0cov")
pass_to_0differs = join(target_parent_folder, "pass")
pass_0cov_to_0differs = join(target_parent_folder, "pass_0cov")
makedirs(error_to_0differs, exist_ok=True)
makedirs(error_0cov_to_0differs, exist_ok=True)
makedirs(pass_to_0differs, exist_ok=True)
makedirs(pass_0cov_to_0differs, exist_ok=True)

for project in target_projects:
    for folder in [error_to_0differs, error_0cov_to_0differs, pass_to_0differs, pass_0cov_to_0differs]:
        makedirs(join(folder, project), exist_ok=True)

    print(project)
    rec = set()
    old_error_type_list = []
    new_error_type_list = []

    coverage_file = join(cov_base_folder, f"iter_{iteration}", project, "coverage_comparison_meta_5_8_8_True_checked_923.json")
    with open(coverage_file, "r") as f:
        cov_info = json.load(f)

    log_folder = join(base_folder, project)
    log_files = listdir(log_folder)
    
    for log_file_name in log_files:
        no_differ = True
        log_file = join(log_folder, log_file_name)
        with open(log_file, "r") as f:
            info = json.load(f)
        for info_block in info:
            if "old_output" in info_block.keys():
                if info_block["message"].startswith("Different outputs"):
                    no_differ = False
                    break

        if no_differ == True:
            pr_num = log_file_name.split("_", 1)[0]
            old_error_type_list_current_pr = []
            new_error_type_list_current_pr = []
            for info_block in info:
                if "old_output" in info_block.keys():
                    # move to a separate folder for conveniently checking the web
                    old_output = info_block["old_output"]
                    new_output = info_block["new_output"]
                    old_error_type = extract_error_type(old_output)
                    new_error_type = extract_error_type(new_output)
                    
                    if old_error_type or new_error_type:
                        rec.add(f"{pr_num}, {old_error_type}, {new_error_type}")
                        if old_error_type:
                            old_error_type_list_current_pr.append("\n".join(old_error_type)) # extract_error_type
                        if new_error_type:
                            new_error_type_list_current_pr.append("\n".join(new_error_type))

            old_error_type_list.extend(old_error_type_list_current_pr)
            new_error_type_list.extend(new_error_type_list_current_pr)

            pr_cov_block = [cov_block for cov_block in cov_info if list(cov_block.keys())[-1] == f"{pr_num}"][0] 
            if old_error_type_list_current_pr or new_error_type_list_current_pr:
                if json.dumps(pr_cov_block).count("\"old\": \"0.00") > 0 and json.dumps(pr_cov_block).count("\"new\": \"0.00") > 0:
                    shutil.copyfile(log_file, join(error_0cov_to_0differs, project, log_file_name))
                else:
                    shutil.copyfile(log_file, join(error_to_0differs, project, log_file_name))
            else:
                if json.dumps(pr_cov_block).count("\"old\": \"0.00") > 0 and json.dumps(pr_cov_block).count("\"new\": \"0.00") > 0:
                    shutil.copyfile(log_file, join(pass_0cov_to_0differs, project, log_file_name))
                else:
                    shutil.copyfile(log_file, join(pass_to_0differs, project, log_file_name))
    
    with open(join(target_parent_folder, f"{project}_rec_common_error_types_{len(rec)}_all_1kind.txt"), "w") as f:
        f.writelines("\n".join(rec))

    old_str = Counter(old_error_type_list)
    new_str = Counter(new_error_type_list)
    old_error_type_list.extend(new_error_type_list)
    overall = Counter(old_error_type_list)
    with open(join(target_parent_folder, f"{project}_error_counter_results.json"), "w") as f:
        json.dump([overall, old_str, new_str], f, indent=4)

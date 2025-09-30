from os.path import join
import json
from os import listdir
from testora.prompts.RuntimeErrorsFixingPrompt import extract_error_type, extract_error_type_2_kinds
from collections import Counter


iteration = 0
target_projects = ["scipy", "marshmallow", "pandas", "keras"]
base_folder = "data/results/table_and_plots/gpt-5-mini-2025-08-07"


for project in target_projects:
    print(project)
    coverage_file = join(base_folder, f"iter_{iteration}", project, "coverage_comparison_meta_5_8_8_True_checked_923.json")
    rec = set()
    old_error_type_list = []
    new_error_type_list = []

    log_folder = join("data/results/gpt-5-mini-2025-08-07/iter_0/check_5_8_8_True_latest", project)
    log_files = listdir(log_folder)

    # with open(coverage_file, "r") as f:
    #     cov_info = json.load(f) 

    # for cov_info_block in cov_info:
    #     pr_num = list(cov_info_block.keys())[-1]
    #     if json.dumps(cov_info_block).count("\"old\": \"0.00") > 0 and json.dumps(cov_info_block).count("\"new\": \"0.00") > 0:
    #         log_file_name = [file for file in log_files if file.startswith(f"{pr_num}")][0] 
    for log_file_name in log_files:
        log_file = join(log_folder, log_file_name)
        with open(log_file, "r") as f:
            info = json.load(f)
        for info_block in info:
            if "old_output" in info_block.keys():
                test_code = info_block["test_code"]
                old_output = info_block["old_output"]
                new_output = info_block["new_output"]
                old_error_type = extract_error_type_2_kinds(test_code, old_output)
                new_error_type = extract_error_type_2_kinds(test_code, new_output)
                if old_error_type or new_error_type:
                    pr_num = log_file_name.split("_", 1)[0]
                    rec.add(f"{pr_num}, {old_error_type}, {new_error_type}")
                    if old_error_type:
                        old_error_type_list.append("\n".join(old_error_type)) # extract_error_type
                    if new_error_type:
                        new_error_type_list.append("\n".join(new_error_type))
    
    if rec:
        with open(f"{project}_rec_common_error_types_{len(rec)}_all_2kinds.txt", "w") as f:
            f.writelines("\n".join(rec))

        old_str = Counter(old_error_type_list)
        new_str = Counter(new_error_type_list)
        old_error_type_list.extend(new_error_type_list)
        overall = Counter(old_error_type_list)
        with open(f"{project}_counter_results.json", "w") as f:
            json.dump([overall, old_str, new_str], f, indent=4)


from os.path import exists, isfile, join
from os import listdir, makedirs


iteration = 0
# model_version = "gpt-4o-mini-2024-07-18"
model_version = "gpt-5-mini-2025-08-07"
# projects = ["marshmallow", "pandas", "scipy", "keras"]
    
# # marshmallow 53, keras 133, pandas 128, scipy 129
# config_versions = {
#     "difftestgen": [5, 8, 8, "pr-modified", True, True, True],
#     "no_coverage_feedback": [5, 0, 8, 'pr-modified', True, True, True], 
#     "no_cg": [5, 8, 8, 'pr-modified', False, True, True]
# }
        
results_folder = join("data", "results")
base_folder = join(results_folder, model_version, f"iter_{iteration}")

with open(".target_project", "r") as f:
    target_project = f.read().strip()

def get_pr_list_from_folder(folder):
    files = listdir(folder)
    pr_list = []
    for file in files:
        pr_list.append(int(file.split("_")[1]))
    return pr_list

def get_delta_prs(list1, list2):
    delta = []
    for pr in list1:
        if not pr in list2:
            delta.append(pr)
    return delta

def write_pr_list_to_file(pr_list, file):
    with open(file, "w") as f:
        f.writelines("\n".join(map(str, set(pr_list))))

def get_prs_with_different_outputs(folder):
    prs = []
    if exists(folder):
        for file in listdir(folder):
            pr_num = file.split("_")[0]
            log_file_path = join(folder, file)
            if isfile(log_file_path):
                with open(log_file_path, "r") as f:
                    info = f.read()
                if "Different outputs" in info:
                    prs.append(pr_num)
    return prs

# ##### mode 1: from the separated breakpoint files
# feedback_folder = "data/results/breakpoint/gpt-5-mini-2025-08-07/iter_0/bp_5_0_8_pr-modified_True_True_True_no_coverage_feedback/marshmallow"
# pr_list_feedback = get_pr_list_from_folder(feedback_folder)
# print(len(pr_list_feedback))

# dtg_folder = "data/results/breakpoint/gpt-5-mini-2025-08-07/iter_0/bp_5_8_8_pr-modified_True_True_True_difftestgen/marshmallow"
# pr_list_dtg = get_pr_list_from_folder(dtg_folder)
# print(len(pr_list_dtg))

# ##### mode 2: from the log files
feedback_folder = join(base_folder, "log_difftestgen", target_project)
pr_list_feedback = get_prs_with_different_outputs(feedback_folder)
print(pr_list_feedback)

dtg_folder = join(base_folder, "log_no_coverage_feedback", target_project)
pr_list_dtg = get_prs_with_different_outputs(dtg_folder)
print(pr_list_dtg)

in_feedback_not_in_dtg = get_delta_prs(pr_list_feedback, pr_list_dtg)
in_dtg_not_in_feddback = get_delta_prs(pr_list_dtg, pr_list_feedback)

ablation_results_folder = join("data", "results", "ablation")
makedirs(ablation_results_folder, exist_ok=True)
write_pr_list_to_file(in_feedback_not_in_dtg, join(ablation_results_folder, 
        f"{target_project}_in_feedback_not_in_dtg_{len(in_feedback_not_in_dtg)}.txt"))
write_pr_list_to_file(in_dtg_not_in_feddback, join(ablation_results_folder, 
        f"{target_project}_in_dtg_not_in_feedback_{len(in_dtg_not_in_feddback)}.txt"))
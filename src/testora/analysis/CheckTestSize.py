import json
from os.path import join
from os import listdir, makedirs


iteration = 0
# model_version = "gpt-4o-mini-2024-07-18"
model_version = "gpt-5-mini-2025-08-07"
project_info = {
    "keras": 133,
    "marshmallow": 53,
    "pandas": 127,
    # "scipy": 126,
}
config_name = "testora" # "testora" or "difftestgen"
test_num = 20 # 20, 60, or ...

base_folder = join("data", "results")
output_folder = join(base_folder, "table_and_plots", "test_size")
makedirs(output_folder, exist_ok=True)

for target_project, num in project_info.items():
    pr_file = join("data", "meta", "pr_nums_checks", f"{target_project}_PRs_subset{num}.txt")
    with open(pr_file, "r") as f:
        prs = f.readlines()
    pr_list = [int(pr) for pr in prs]
    if target_project == "keras":
        pr_list = pr_list[:67]
    elif target_project == "pandas":
        pr_list = pr_list[:65]

    project_level = [{target_project: {"avg_size": 0}}]
    project_level_size_list = []
    
    log_folder = join(base_folder, model_version, f"iter_{iteration}", f"log_{config_name}", target_project)
    log_files = listdir(log_folder)
    for file in log_files:
        pr_num = int(file.split("_", 1)[0])
        if pr_num in pr_list:
            test_size_list= []
            pr_details = {}
            pr_details.update({"avg_size": 0})
            log_file_path = join(log_folder, file)
            with open(log_file_path, "r") as f:
                info = json.load(f) 
                
            for block in info:
                if "message" in block.keys():
                    if block["message"].startswith("Generated test "):
                        test_size = len(block["content"])
                        test_size_list.append(test_size)
                        pr_details.update({block["message"]: test_size})
            if test_size_list:
                pr_details["avg_size"] = round(sum(test_size_list) / len(test_size_list), 2)
                project_level.append({pr_num: pr_details})
                project_level_size_list.extend(test_size_list)

    project_level[0][target_project]["avg_size"] = round(sum(project_level_size_list) / len(project_level_size_list), 2)

    result_file = join(output_folder, f"{config_name}_{target_project}_{test_num}.json")
    with open(result_file, "w") as f:
        json.dump(project_level, f, indent=4)
            



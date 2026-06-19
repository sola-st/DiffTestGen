from datetime import datetime
import json
from os.path import join
from os import listdir
# from collections import Counter


def parse_time_stamp(time_stamp):
    format_strs = ["%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"]
    for format_str in format_strs:
        try:
            return datetime.strptime(time_stamp, format_str)
        except ValueError:
            pass
    raise ValueError(f"Could not parse time stamp: {time_stamp}")

def get_cg_and_time(file):
    cg_str_list = ""
    start_timestamp = ""
    end_timestamp = ""

    with open(file, "r") as f:
        info = json.load(f) 

    for block in info:
        if "message" in block.keys():
            if block["message"] == "Starting to check PR":
                start_timestamp = block["timestamp"]

            elif block["message"].startswith("Call graph ("):
                cg_str_list = block["content"].split("\n")
                end_timestamp = block["timestamp"]
                break

    exec_time = parse_time_stamp(end_timestamp) - parse_time_stamp(start_timestamp)
    sorted(cg_str_list)
    
    return cg_str_list, exec_time

def main():

    iteration = 0
    # model_version = "gpt-4o-mini-2024-07-18"
    model_version = "gpt-5-mini-2025-08-07"
    config_name = "difftestgen" # "difftestgen", chaco_difftestgen
    project_info = {
        "keras": 133,
        "marshmallow": 53,
        "pandas": 127,
        "scipy": 126,
    }

    
    base_folder = join("data", "results")
    for target_project, num in project_info.items():
        project_level_saved_time = []
        # pr_file = join("data", "meta", "pr_nums_checks", f"{target_project}_PRs_subset{num}.txt")
        # with open(pr_file, "r") as f:
        #     prs = f.readlines()
        # pr_list = [int(pr) for pr in prs]
        # pr_list = [21672, 22322]

        log_folder = join(base_folder, model_version, f"iter_{iteration}", f"log_{config_name}", target_project)
        log_files = listdir(log_folder)

        call_path_folder = join(base_folder, model_version, f"iter_{iteration}", f"log_{config_name}_call_path", target_project)
        path_files = listdir(call_path_folder)
        
        for file in path_files:
            pr_num = file.split("_", 1)[0]
            path_file = join(call_path_folder, file)
            log_file = [join(log_folder, file) for file in log_files if file.startswith(pr_num)][0]

            path_cg_str_list, path_exec_time = get_cg_and_time(path_file)
            log_cg_str_list, log_exec_time = get_cg_and_time(log_file)

            print(f"{pr_num}, from call path: {path_exec_time}")
            print(f"from log file: {log_exec_time}")
            recompute = (log_exec_time - path_exec_time).total_seconds()
            project_level_saved_time.append(recompute)
            print(f"Saved {recompute} seconds.")
            
            if path_cg_str_list != log_cg_str_list:
                with open(f"{target_project}_{pr_num}_call_path.txt", "w") as f:
                    f.writelines("\n".join(path_cg_str_list))
                with open(f"{target_project}_{pr_num}_log.txt", "w") as f:
                    f.writelines("\n".join(log_cg_str_list))
                print(f"-- {pr_num}")
            print()

        print(f"*************** Saved {sum(project_level_saved_time)/len(project_level_saved_time)} seconds on average for project {target_project}.\n")


if __name__ == "__main__":
    main()      



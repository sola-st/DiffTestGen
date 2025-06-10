import json
import os
from os.path import join, exists


def main():
    config_versions = [
        # [1, 1, 1],
        # [4, 4, 4],
        # [5, 5, 5],
        [4, 8, 8]
        ]
    target_projects = ["scipy", "marshmallow", "pandas", "keras"]
    results_folder = join("data", "results")
    
    error_outputs = []
    for config in config_versions:
        version_id = '_'.join(map(str, config))

        for project in target_projects:
            log_folder = join(results_folder, f"log_{version_id}", project)
            if exists(log_folder):
                logs = os.listdir(log_folder)
                if logs:
                    for log_file in logs:
                        with open(join(log_folder, log_file), "r") as f:
                            info = json.load(f)
                        
                        # pr_num = info[1]["pr_nb"]
                        for info_block in info:
                            # if info_block["message"].startswith("Query too long,"):
                            #     print(f"{project} PR{pr_num} {info_block['message']}")
                            if "old_output" in info_block.keys():
                                error_str = {}
                                if info_block["message"].startswith("Both tests failed,"):
                                    error_str = {
                                        "project": project,
                                        "block": info_block
                                    }
                                elif "Traceback (most recent call last)" in info_block["old_output"] or \
                                    "Traceback (most recent call last)" in info_block["new_output"]:
                                    error_str = {
                                        "project": project,
                                        "block": info_block
                                    }
                                if error_str:
                                    error_outputs.append(error_str)
                                
    result_file = join(results_folder, f"overall_error_messages.json") 
    with open(result_file, "w") as f:
        json.dump(error_outputs, f, indent=2)


if __name__=="__main__":
    main()
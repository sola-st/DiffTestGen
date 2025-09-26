from os.path import join
from os import makedirs
import json
import os
from testora.prompts.RuntimeErrorsFixingPrompt import extract_error_type


def analyze_single_pr(log_file_path, version_id):
    updated = False
    with open(log_file_path, "r") as f:
        info = json.load(f) 

    for i, info_block in enumerate(info):
        if "old_output" in info_block.keys():
            old_output = info_block["old_output"]
            new_output = info_block["new_output"]
            old_error_type = extract_error_type(old_output)
            new_error_type = extract_error_type(new_output)
            updated_message_prefix = ""

            if old_error_type == new_error_type:
                if old_error_type == None: # both no errors
                    # updated_message_prefix = "Same output" # instead of flaky tests, will leads some inaccuracy
                    pass
                else:
                    # error exists in both version
                    updated_message_prefix = "Both tests failed, considering them the same"
            else:
                # error exists in one or two version(s)
                updated_message_prefix = "Different outputs"

            # assert updated_message_prefix != ""
            ori_msg = info[i]["message"]
            if updated_message_prefix and (ori_msg.split("\n")[0] != updated_message_prefix):
                updated = True
                info[i]["message"] = f"{updated_message_prefix}\n{ori_msg}"

    if updated == True:
        result_file = log_file_path.replace(f"log_{version_id}", f"check_{version_id}_latest")
        with open(result_file, "w") as f:
            json.dump(info, f, indent=4)
    else:
        result_file = log_file_path.replace(f"log_{version_id}", f"check_{version_id}_latest")
        with open(result_file, "w") as f:
            json.dump(info, f, indent=4)
        print(log_file_path)
        
def main():
    '''
    * [Solved] The number of exposed differences dropped. 
    Because of some of the updates are mis-matched, if ran this again with the flaky tests, this part should be corrected.
    
    * The most importand updates here is about the keras, 
    we can refer to the number to check the details of outputs (the errors and same outputs indentification).
    '''

    results_folder = join("data", "results")

    iteration = 0
    # model_version = "gpt-4o-mini-2024-07-18"
    model_version = "gpt-5-mini-2025-08-07"
    # option 1: for all projects
    project_info = {
        "scipy": 129,
        "marshmallow": 53,
        "pandas": 128,
        "keras": 133
    }

    config_versions = [
        [1, 0, 1, False],
        [5, 8, 8, True]
        ]

    for config in config_versions:
        version_id = '_'.join(map(str, config))

        for target_project, num in project_info.items():
            pr_file = join("data", "meta", "pr_nums", f"{target_project}_PRs_subset{num}.txt")
            with open(pr_file, "r") as f:
                prs = f.readlines()
            pr_list = [int(pr) for pr in prs]
            
            for pr in pr_list:
                log_folder = join(results_folder, model_version, f"iter_{iteration}", f"log_{version_id}", target_project)
                updated_log_folder = log_folder.replace(f"log_{version_id}", f"check_{version_id}_latest")
                makedirs(updated_log_folder, exist_ok=True)

                log_file_path = None
                for fname in os.listdir(log_folder):
                    if str(pr) in fname:
                        log_file_path = join(log_folder, fname)
                        break
                if log_file_path is None:
                    print(f"Iteration {iteration}: No log file found for PR {pr} in {log_folder}")
                else:
                    analyze_single_pr(log_file_path, version_id)
            

if __name__=="__main__":
    main()
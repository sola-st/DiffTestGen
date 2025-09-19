from os.path import join
import json
import os
import re

def analyze_single_pr(info):
    nb_test_generated_patterns = [r"^Generated (\d+) tests", r"^Generated (\d+) more tests", r"Static error fixed (\d+)/"]
    tests_num = 0
    both_failed = 0
    old_flaky = 0
    new_flaky = 0
    same = 0
    different = 0
    pr_num = info[1]["pr_nb"]

    for info_block in info:
        if "message" in info_block.keys():
            msg = info_block["message"]

            for nb_test_generated_pattern in nb_test_generated_patterns:
                nb_generated_tests_match = re.search(
                    nb_test_generated_pattern, msg)
                if nb_generated_tests_match:
                    tests_num += int(nb_generated_tests_match.group(1))
                    
            if msg == "Test execution (old_flaky)":
                old_flaky += 1
            elif msg == "Test execution (new_flaky)":
                new_flaky += 1
            elif msg.startswith("Both tests failed"):
                both_failed += 1
            elif msg.startswith("Same output"):
                same += 1
            elif msg.startswith("Different outputs"):
                different += 1

    json_str = {
        "pr_nb": pr_num,
        "both_failed": both_failed,
        "test_num": tests_num,
        "old_flaky": old_flaky,
        "new_flaky": new_flaky,
        "same": same,
        "different": different
    }
    return json_str
            
def main():
    results_folder = join("data", "results")

    iteration = 0
    # model_version = "gpt-4o-mini-2024-07-18"
    model_version = "gpt-5-mini-2025-08-07"
    # option 1: for all projects
    target_projects = ["marshmallow"] # ["scipy", "marshmallow", "pandas", "keras"]

    config_versions = [
        [1, 0, 1, False]
        # [5, 8, 8, True]
        ]

    all_data = []
    for config in config_versions:
        version_id = '_'.join(map(str, config))

        for target_project in target_projects:
            pr_file = join("data", "meta", "pr_nums", f"{target_project}_PRs_subset10.txt")
            with open(pr_file, "r") as f:
                prs = f.readlines()
            pr_list = [int(pr) for pr in prs]
            
            for pr in pr_list:
                log_folder = join(results_folder, model_version, f"iter_{iteration}", f"log_{version_id}", target_project)
                log_file_path = None
                for fname in os.listdir(log_folder):
                    if str(pr) in fname:
                        log_file_path = join(log_folder, fname)
                        break
                if log_file_path is None:
                    print(f"Iteration {iteration}: No log file found for PR {pr} in {log_folder}")
                else:
                    with open(log_file_path, "r") as f:
                        info = json.load(f) 
                    single_pr_json = analyze_single_pr(info)
                    all_data.append(single_pr_json)

            result_file = join(results_folder, "table_and_plots", model_version, f"{target_project}_time_issue_flaky_check_{version_id}.json")
            with open(result_file, "w") as f:
                json.dump(all_data, f, indent=4)


if __name__=="__main__":
    main()
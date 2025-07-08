'''check how many PRs need the error message feedback, and how many are fixed.'''

import json
from os.path import join, isfile
from os import listdir
from testora.prompts.RuntimeErrorsFixingPrompt import check_whether_error_exist

base_folder = join("data", "results")

# option 1: for all projects
target_projects = ["scipy", "marshmallow", "pandas", "keras"]

# option 2: for a single project
# with open(".target_project", "r") as f:
#     target_project = f.read().strip()
# target_projects = [target_project]

# target_projects = ["scipy"]
overall_level_test = 0
overall_need_fix_tests = 0
overall_fixed_tests= 0
overall_fixed_prs = set()


config_versions = [
    [5, 8, 8, "true"]
    ]

for target_project in target_projects:
    project_level_test = 0
    project_level_need_fix = 0
    project_level_fixed = 0
    project_level_need_fix_test_names = {}
    fixed_relevant_pr = set()

    for config in config_versions:
        version_id = '_'.join(map(str, config))
        log_folder = join(base_folder, f"log_{version_id}", target_project)

        log_files = listdir(log_folder)
        for file in log_files:
            log_file_path = join(log_folder, file)
            if isfile(log_file_path):
                with open(log_file_path, "r") as f:
                    info = json.load(f) 
                
                for info_block in info:
                    try:
                        msg = info_block["message"]
                        # e.g., "Generated 4 more tests. (4 tests before deduplication and cleaning)"
                        if 'before deduplication and cleaning' in msg:
                            current_round_test_num = int(msg.split(" ", 2)[1])
                            project_level_test += current_round_test_num
                        elif msg.startswith("Fixed runtime errors"):
                            project_level_need_fix += 1
                            test_name = info_block["content"].split("(", 1)[0]
                            project_level_need_fix_test_names.update({test_name: {"num": 0, "pr": info_block["pr_nb"]}})
                        elif "_error_fix)" in msg:
                            test_name = info_block["code"].split("(", 1)[0]
                            error_exist = check_whether_error_exist(info_block["code"], info_block["output"])
                            if error_exist == True:
                                project_level_need_fix_test_names[test_name]["num"] += 1
                    except:
                        pass
    
    for test_name, pass_info in project_level_need_fix_test_names.items():
        pass_num, pr_nb = pass_info.values()
        if pass_num != 0: # pass 1 or 2 of the code versions
            project_level_fixed += 1 # the number of fixed test
            fixed_relevant_pr.add(pr_nb)
        else:
            print(pr_nb)

    print(f"Project {target_project} has {project_level_test} tests, {project_level_need_fix} of them need fix.")
    print(f"--With {project_level_fixed} tests fixed, relvant to {len(fixed_relevant_pr)} PRs.")
    print(fixed_relevant_pr)
    print()
    overall_level_test += project_level_test
    overall_need_fix_tests += project_level_need_fix
    overall_fixed_tests+= project_level_fixed
    overall_fixed_prs = overall_fixed_prs.union(fixed_relevant_pr)

print(f"Overall: Tests: {overall_level_test}, need fix {overall_need_fix_tests}, fixed {overall_fixed_tests}. PR: fixed {len(overall_fixed_prs)}.")
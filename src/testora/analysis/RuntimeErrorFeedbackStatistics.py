'''check how many PRs need the error message feedback, and how many are fixed.'''

from collections import Counter
import json
from os import listdir, makedirs
from os.path import join
from testora.prompts.RuntimeErrorsFixingPrompt import extract_error_type


class RuntimeErrorFeedbackStatistics():
    def __init__(self):
        self.overall_tests = 0
        self.overall_need_fix_tests = 0
        self.overall_fixed_tests = 0
        self.overall_fixed_related_prs = set()
        self.overall_fix_attempts = [] # will be used to show the average attemps

        # project level
        self.project_tests = 0
        self.project_need_fix_tests = 0
        self.project_fixed_tests= 0
        self.project_fixed_related_prs = set()
        self.project_fix_attempts = []

    def clear_overall(self):
        self.overall_tests = 0
        self.overall_need_fix_tests = 0
        self.overall_fixed_tests= 0
        self.overall_fixed_related_prs = set()
        self.overall_fix_attempts = []

    def clear_project_level(self):
        self.project_tests = 0
        self.project_need_fix_tests = 0
        self.project_fixed_tests= 0
        self.project_fixed_related_prs = set()
        self.project_fix_attempts = []
        
    def get_error_statictics_single_pr(self, info, pr_num):
        # current pr level
        tests = 0
        need_fix_tests = 0
        fixed_tests = 0
        pre_test_name = None
        fix_attempts = 0
        passed_code_versions = 0
        need_fix_details = []
        final_test_name = None
        feedback_loop_ends = False

        for info_block in info:
            if "message" in info_block.keys():
                msg = info_block["message"]
                test_name = None
                # e.g., "Generated 4 more tests. (4 tests before deduplication and cleaning)"
                if 'before deduplication and cleaning' in msg and msg.startswith("Generated"):
                    tests += int(msg.split(" ", 2)[1])
                elif msg.startswith("Fix runtime errors"):
                    fix_attempts += 1
                    test_name = info_block["content"].split(":", 1)[0]
                    if not test_name.startswith("# Round "):
                        test_name = test_name.split("#")[0]
                    # if pre_test_name and pre_test_name != test_name:
                    if pre_test_name and feedback_loop_ends:
                        fix_attempts_current = fix_attempts -1
                        # the first point that we get to an new example
                        need_fix_details.append({
                            "test_name": pre_test_name, 
                            "fix_attempts": fix_attempts_current, 
                            "passed_code_versions": passed_code_versions # the last fix attempt
                        })

                        if passed_code_versions > 0:
                            fixed_tests += 1
                        
                        self.overall_fix_attempts.append(fix_attempts_current)
                        self.project_fix_attempts.append(fix_attempts_current)

                        # clear for current test, go for the next one
                        fix_attempts = 1
                        passed_code_versions = 0
                        feedback_loop_ends = False
                    
                    pre_test_name = test_name
                    final_test_name = test_name
                elif "_error_fix" in msg:
                    error_exist = extract_error_type(info_block["output"])
                    if error_exist == None:
                        passed_code_versions += 1
                elif "Error feedback loop ends after" in msg:
                    feedback_loop_ends = True

        # add the last test
        if fix_attempts > 0:
            need_fix_details.append({
                "test_name": final_test_name, 
                "fix_attempts": fix_attempts, 
                "passed_code_versions": passed_code_versions # the last fix attempt
            })

            if passed_code_versions > 0:
                fixed_tests += 1
            
            self.overall_fix_attempts.append(fix_attempts)
            self.project_fix_attempts.append(fix_attempts)

        # single pr level
        need_fix_tests = len(need_fix_details)
        single_pr_json = {
            "project": None, # will be updated when returned
            "pr_num": pr_num, 
            "tests_num": tests,
            "need_fix_tests": need_fix_tests,
            "fixed_tests": fixed_tests,
            "details": need_fix_details
        }

        if need_fix_tests > 0:
            # update overall 1.1
            self.overall_tests += tests
            self.overall_need_fix_tests += need_fix_tests
            # update project level 2.1
            self.project_tests += tests
            self.project_need_fix_tests += need_fix_tests

            if fixed_tests > 0 :
                # 1.2
                self.overall_fixed_tests += fixed_tests
                self.overall_fixed_related_prs.add(pr_num)
                # 2.2
                self.project_fixed_tests += fixed_tests
                self.project_fixed_related_prs.add(pr_num)
        
        return single_pr_json

    def main(self):
        results_folder = join("data", "results")

        iteration = 0
        # model_version = "gpt-4o-mini-2024-07-18"
        model_version = "gpt-5-mini-2025-08-07"
        # option 1: for all projects
        target_projects = ["scipy", "marshmallow", "pandas", "keras"]

        # option 2: for a single project
        # with open(".target_project", "r") as f:
        #     target_project = f.read().strip()
        # target_projects = [target_project]

        # target_projects = ["scipy"]

        config_names = ["difftestgen", "no_coverage_feedback", "no_cg"]#, "no_runtime"]

        target_projects = {
            "marshmallow": 53,
            "pandas": 128,
            "scipy": 129
        }

        project_level = []
        single_iteration = []

        for version_name in config_names:
            for target_project, num in target_projects.items():
                pr_file = join("data", "meta", "pr_nums_checks", f"{target_project}_PRs_subset{num}.txt")
                with open(pr_file, "r") as f:
                    prs = f.readlines()
                pr_list = [int(pr) for pr in prs]
                
                for pr in pr_list:
                    # use a fixed order of the prs, could help when check across repetitions (iterations).
                    log_folder = join(results_folder, model_version, f"iter_{iteration}", f"log_{version_name}", target_project)
                    log_file_path = None
                    for fname in listdir(log_folder):
                        if str(pr) in fname:
                            log_file_path = join(log_folder, fname)
                            break
                    if log_file_path is None:
                        print(f"Iteration {iteration}: No log file found for PR {pr} in {log_folder}")
                        single_iteration.append({"pr_num": pr})
                    else:
                        with open(log_file_path, "r") as f:
                            info = json.load(f) 
                        single_pr_json = self.get_error_statictics_single_pr(info, pr)
                        single_pr_json["project"] = target_project
                        single_iteration.append(single_pr_json)

                project_str = {
                    "project": target_project,
                    "project_pr_num" : len(pr_list),
                    "project_tests": self.project_tests,
                    "project_need_fix_tests": self.project_need_fix_tests,
                    "project_fixed_tests": self.project_fixed_tests,
                    "project_avg_fix_attempts" : f"{(sum(self.project_fix_attempts) / len(self.project_fix_attempts)):.2f}" if self.project_fix_attempts else 0,
                    "project_fix_attempts_distribution" : f"{Counter(self.project_fix_attempts)}",
                    "project_fixed_related_prs": len(self.project_fixed_related_prs),
                    "details": f"{self.project_fixed_related_prs}",
                }
                project_level.append(project_str)
                self.clear_project_level()
            
            overall_str = {
                "repetition_num" : iteration,
                "overall_pr_num" : len(single_iteration),
                "overall_tests": self.overall_tests,
                "overall_need_fix_tests": self.overall_need_fix_tests,
                "overall_fixed_tests": self.overall_fixed_tests,
                "overall_fix_attempts_distribution" : f"{Counter(self.overall_fix_attempts)}",
                "overall_fixed_related_prs": len(self.overall_fixed_related_prs),
                "overall_fixed_related_prs": len(self.overall_fixed_related_prs),
            }

            to_write = [overall_str] + project_level + single_iteration
            parent_folder = join(results_folder, "table_and_plots", "differ_distribution")
            makedirs(parent_folder, exist_ok=True)
            result_file = join(parent_folder, f"differ_statistics_{version_name}.json")
            with open(result_file, "w") as f:
                json.dump(to_write, f, indent=4)

            self.clear_overall()



if __name__ == "__main__":
    RuntimeErrorFeedbackStatistics().main()
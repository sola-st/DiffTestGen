from os.path import join
import json
import os
import re


class DifferentOutputsStatistics():
    def __init__(self):
        self.overall_generated_tests = 0
        self.overall_from_uncertain_round = 0
        self.overall_from_rounds = [0]

        # project level
        self.project_generated_tests = 0
        self.project_from_uncertain_round = 0
        self.project_from_rounds = [0]

        self.nb_test_generated_patterns = [r"^Generated (\d+) tests", \
                r"^Generated (\d+) more tests", r"Static error fixed (\d+)/"]


    def clear_overall(self):
        self.overall_generated_tests = 0
        self.overall_from_uncertain_round = 0
        self.overall_from_rounds = [0]

    def clear_project_level(self):
        self.project_generated_tests = 0
        self.project_from_uncertain_round = 0
        self.project_from_rounds = [0]

    def analyze_single_pr(self, info):
        # current pr level
        diff_nb = 0
        from_uncertain_round = 0
        from_rounds = [0]

        for info_block in info:
            if "message" in info_block.keys():
                msg = info_block["message"]
                if msg.startswith("Generated") or msg.startswith("Static error fixed"):
                    for nb_test_generated_pattern in self.nb_test_generated_patterns:
                        nb_generated_tests_match = re.search(nb_test_generated_pattern, msg)
                        if nb_generated_tests_match:
                            nb = int(nb_generated_tests_match.group(1))
                            diff_nb += nb

                            if "#Round" in msg:
                                round_num = int(msg.split("#Round ", 1)[1].replace(")", ""))
                                if round_num >= len(from_rounds):
                                    for _ in range(len(from_rounds), round_num+1):
                                        from_rounds.append(0)
                                from_rounds[round_num] += nb
                            else:
                                from_uncertain_round += nb
                            break

        single_pr_json = {
            "project": None, # will be updated when returned
            "pr_num": None, # will be updated when returned
            "generated_tests": diff_nb,
            "details": {
                "from_uncertain_round": from_uncertain_round
            }
        }

        for idx, num in enumerate(from_rounds):
            single_pr_json["details"].update({f"from_round_{idx}": num})

        # update overall 
        self.overall_generated_tests += diff_nb
        self.overall_from_uncertain_round += from_uncertain_round
        if len(self.overall_from_rounds) < len(from_rounds):
            for _ in range(len(self.overall_from_rounds), len(from_rounds)):
                self.overall_from_rounds.append(0)

        for j, num in enumerate(from_rounds):
            self.overall_from_rounds[j] += num
    
        # update project level
        self.project_generated_tests += diff_nb

        self.project_from_uncertain_round += from_uncertain_round
        if len(self.project_from_rounds) < len(from_rounds):
            for _ in range(len(self.project_from_rounds), len(from_rounds)):
                self.project_from_rounds.append(0)

        for j, num in enumerate(from_rounds):
            self.project_from_rounds[j] += num

        return single_pr_json


    def main(self):
        results_folder = join("data", "results")
        output_folder = join(results_folder, "table_and_plots", "different_outputs_statistics")
        os.makedirs(output_folder, exist_ok=True)

        iteration = 0
        # model_version = "gpt-4o-mini-2024-07-18"
        model_version = "gpt-5-mini-2025-08-07"
        config_names = ["difftestgen", "no_coverage_feedback", "no_cg", "no_runtime"]
        subset_mode = True

        # option 1: for all projects
        project_info = {
            "scipy": 129,
            "marshmallow": 53,
            "pandas": 128,
            # "keras": 133
        }

        # option 2: for a single project
        # with open(".target_project", "r") as f:
        #     target_project = f.read().strip()
        # target_projects = [target_project, 0]

        for version_name in config_names:
            project_level = []
            single_iteration = []

            for target_project, proj_num in project_info.items():
                pr_file = join("data", "meta", "pr_nums_checks", f"{target_project}_PRs_subset{proj_num}.txt")
                if subset_mode == True:
                    pr_file = join("data", "meta", f"subset_{target_project}.txt")
                with open(pr_file, "r") as f:
                    prs = f.readlines()
                pr_list = [int(pr) for pr in prs]
                
                for pr in pr_list:
                    log_folder = join(results_folder, model_version, f"iter_{iteration}", f"log_{version_name}", target_project)
                    if subset_mode == True:
                        log_folder = join(results_folder, model_version, f"iter_{iteration}_subset", f"log_{version_name}", target_project)
                    log_file_path = None
                    for fname in os.listdir(log_folder):
                        if str(pr) in fname:
                            log_file_path = join(log_folder, fname)
                            break
                    if log_file_path is None:
                        print(f"Iteration {iteration}, {version_name}: No log file found for PR {pr} in {log_folder}")
                        single_iteration.append({"pr_num": pr}) 
                    else:
                        with open(log_file_path, "r") as f:
                            info = json.load(f) 
                        single_pr_json = self.analyze_single_pr(info)
                        single_pr_json["project"] = target_project
                        single_pr_json["pr_num"] = pr
                        single_iteration.append(single_pr_json)

                # add project level summaries
                project_str = {
                    "project": target_project,
                    "project_pr_num" : len(pr_list),
                    "project_generated_tests": self.project_generated_tests,
                    "details": {
                        "project_from_uncertain_round": self.project_from_uncertain_round
                    }
                }

                for idx, num in enumerate(self.project_from_rounds):
                    project_str["details"].update({f"project_from_round_{idx}": num})

                project_level.append(project_str)
                self.clear_project_level()
            
            # overall summary
            overall_str = {
                "repetition_num" : iteration,
                "overall_pr_num" : len(single_iteration),
                "overall_generated_tests": self.overall_generated_tests,
                "details": {
                    "overall_from_uncertain_round": self.overall_from_uncertain_round
                }
            }

            for idx, num in enumerate(self.overall_from_rounds):
                overall_str["details"].update({f"overall_from_round_{idx}": num})

            to_write = [overall_str] + project_level + single_iteration

            result_file = join(output_folder, f"{version_name}.json")
            with open(result_file, "w") as f:
                json.dump(to_write, f, indent=4)

            self.clear_overall()

if __name__=="__main__":
    DifferentOutputsStatistics().main()
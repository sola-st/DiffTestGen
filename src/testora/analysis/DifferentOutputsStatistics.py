from os.path import join
import json
import os


class DifferentOutputsStatistics():
    def __init__(self):
        self.overall_diff_related_pr = 0
        self.overall_diff_nb = 0

        self.overall_from_full_diff = 0
        self.overall_from_filtered_diff = 0
        self.overall_from_uncertain_diff = 0

        self.overall_from_uncertain_round = 0
        self.overall_max_rounds = 0
        self.overall_from_rounds = [0]

        # project level
        self.project_diff_related_pr = 0
        self.project_diff_nb = 0

        self.project_from_full_diff = 0
        self.project_from_filtered_diff = 0
        self.project_from_uncertain_diff = 0

        self.project_from_uncertain_round = 0
        self.project_max_rounds = 0
        self.project_from_rounds = [0]

    def clear_overall(self):
        self.overall_diff_related_pr = 0
        self.overall_diff_nb = 0
        self.overall_from_full_diff = 0
        self.overall_from_filtered_diff = 0
        self.overall_from_uncertain_diff = 0
        self.overall_from_uncertain_round = 0
        self.overall_max_rounds = 0
        self.overall_from_rounds = [0]

    def clear_project_level(self):
        self.project_diff_related_pr = 0
        self.project_diff_nb = 0
        self.project_from_full_diff = 0
        self.project_from_filtered_diff = 0
        self.project_from_uncertain_diff = 0
        self.project_from_uncertain_round = 0
        self.project_max_rounds = 0
        self.project_from_rounds = [0]

    def analyze_single_pr(self, info):
        # current pr level
        diff_nb = 0

        from_full_diff = 0
        from_filtered_diff = 0
        from_uncertain_diff = 0

        from_uncertain_round = 0
        max_rounds = 0
        from_rounds = [0]

        for info_block in info:
            if "message" in info_block.keys():
                msg = info_block["message"]
                if not max_rounds:
                    if msg.startswith("Refinement ends"):
                        max_rounds = int(msg.split("Refinement ends after round ", 1)[1].split(",", 1)[0])
                        from_rounds = [0 for _ in range(max_rounds+1)]

                if msg.startswith("Different outputs"):
                    diff_nb += 1
                    # more details
                    test_name, remaining = info_block["test_code"].split("(", 1)
                    if remaining.startswith("full_diff"):
                        from_full_diff += 1
                    elif remaining.startswith("filtered_diff"):
                        from_filtered_diff += 1
                    else:
                        from_uncertain_diff += 1

                    if "# Round" in test_name:
                        round_num = int(test_name.split("# Round ", 1)[1].split(" ", 1)[0])
                        from_rounds[round_num] += 1
                    else:
                        from_uncertain_round += 1

        single_pr_json = {
            "project": None, # will be updated when returned
            "pr_num": None, # will be updated when returned
            "different_outputs": diff_nb,
            "details": {
                "from_full_diff": from_full_diff,
                "from_filtered_diff": from_filtered_diff,
                "from_uncertain_diff": from_uncertain_diff,
            }
        }

        for idx, num in enumerate(from_rounds):
            single_pr_json["details"].update({f"from_round_{idx}": num})

        if diff_nb > 0:
            # update overall 
            self.overall_diff_related_pr += 1
            self.overall_diff_nb += diff_nb

            self.overall_from_full_diff += from_full_diff
            self.overall_from_filtered_diff += from_filtered_diff
            self.overall_from_uncertain_diff += from_uncertain_diff

            self.overall_from_uncertain_round += from_uncertain_round
            if self.overall_max_rounds < max_rounds:
                for _ in range(self.overall_max_rounds, max_rounds):
                    self.overall_from_rounds.append(0)
                self.overall_max_rounds = max_rounds

            for j, num in enumerate(from_rounds):
                self.overall_from_rounds[j] += num
        
            # update project level
            self.project_diff_related_pr += 1
            self.project_diff_nb += diff_nb

            self.project_from_full_diff += from_full_diff
            self.project_from_filtered_diff += from_filtered_diff
            self.project_from_uncertain_diff += from_uncertain_diff

            self.project_from_uncertain_round += from_uncertain_round
            if self.project_max_rounds < max_rounds:
                for _ in range(self.project_max_rounds, max_rounds):
                    self.project_from_rounds.append(0)
                self.project_max_rounds = max_rounds

            for j, num in enumerate(from_rounds):
                self.project_from_rounds[j] += num

        return single_pr_json


    def main(self):
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

        # option 2: for a single project
        # with open(".target_project", "r") as f:
        #     target_project = f.read().strip()
        # target_projects = [target_project]

        config_versions = [
            [1, 0, 1, False],
            [5, 8, 8, True]
            ]
        
        for config in config_versions:
            project_level = []
            single_iteration = []
            version_id = '_'.join(map(str, config))

            for target_project, num in project_info.items():
                pr_file = join("data", "meta", "pr_nums", f"{target_project}_PRs_subset{num}.txt")
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
                    "project_diff_related_pr_num": self.project_diff_related_pr,
                    "project_different_outputs": self.project_diff_nb,
                    "details": {
                        "project_from_full_diff": self.project_from_full_diff,
                        "project_from_filtered_diff": self.project_from_filtered_diff,
                        "project_from_uncertain_diff": self.project_from_uncertain_diff,
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
                "overall_diff_related_pr_num": self.overall_diff_related_pr,
                "overall_different_outputs": self.overall_diff_nb,
                "details": {
                    "overall_from_full_diff": self.overall_from_full_diff,
                    "overall_from_filtered_diff": self.overall_from_filtered_diff,
                    "overall_from_uncertain_diff": self.overall_from_uncertain_diff,
                }
            }

            for idx, num in enumerate(self.overall_from_rounds):
                overall_str["details"].update({f"overall_from_round_{idx}": num})

            to_write = [overall_str] + project_level + single_iteration

            result_file = join(results_folder, "table_and_plots", model_version, f"Different_outputs_statistics_{version_id}.json")
            with open(result_file, "w") as f:
                json.dump(to_write, f, indent=4)

            self.clear_overall()


if __name__=="__main__":
    DifferentOutputsStatistics().main()
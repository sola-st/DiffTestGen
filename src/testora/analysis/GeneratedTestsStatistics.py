from os.path import join
import json
import os
import re


class GeneratedTestsStatistics():
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
        iteration = 0
        results_folder = join("data", "results")
        output_folder = join(results_folder, "table_and_plots", "different_outputs_statistics", f"iter_{iteration}", "generated_tests_meta")
        os.makedirs(output_folder, exist_ok=True)

        # model_version = "gpt-4o-mini-2024-07-18"
        model_version = "gpt-5-mini-2025-08-07"
        config_names = ["testora", "only_coverage_feedback", "only_cg", "difftestgen"]
        approach_names = ["Testora", "Only Coverage Feedback", "Only Access Information", "DiffTestGen"]
        subset_mode = False

        project_info = {
            "keras": 133,
            "marshmallow": 53,
            "pandas": 127,
            "scipy": 126,
        }

        # collect rows for a single LaTeX table across all configurations
        latex_rows = []
        projects_order = list(project_info.keys())

        def _escape_latex(s: str) -> str:
            return s.replace("_", "\\_")

        for version_name, approach_name in zip(config_names, approach_names):
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
                "repetition_idx" : iteration,
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

            # prepare LaTeX row for this configuration
            row_vals = []
            for proj in projects_order:
                # find project entry in project_level
                proj_val = None
                for p in project_level:
                    if p.get("project") == proj:
                        proj_val = p.get("project_generated_tests", 0)
                        break
                if proj_val is None:
                    proj_val = 0
                row_vals.append(proj_val)

            total = sum(row_vals)
            latex_rows.append((approach_name, row_vals, total))

            self.clear_overall()

        # After processing all configurations, write a LaTeX table summarizing generated tests
        cols = 1 + len(projects_order) + 1
        col_spec = "l" + "r" * (len(projects_order) + 1)
        header_cells = [""] + [ _escape_latex(p) for p in projects_order ] + ["Total"]

        latex_lines = ["\\begin{table*}[ht]"
                "\\centering"
                "\\caption{The number of generated tests}",
                "\\label{tab:generated_tests}",\
                "\\setlength{\\tabcolsep}{3pt}",]
        latex_lines.append("\\begin{tabular}{%s}" % col_spec)
        latex_lines.append("\\hline")
        latex_lines.append(" & ".join(header_cells) + "\\\\")
        latex_lines.append("\\hline")
        for approach_name, row_vals, total in latex_rows:
            cells = [ _escape_latex(approach_name) ] + [ str(v) for v in row_vals ] + [ str(total) ]
            latex_lines.append(" & ".join(cells) + " \\\\")
        latex_lines.append("\\hline")
        latex_lines.append("\\end{tabular}")

        latex_file = join(output_folder, "generated_tests_summary_table.tex")
        with open(latex_file, "w") as f:
            f.write("\n".join(latex_lines))


if __name__=="__main__":
    GeneratedTestsStatistics().main()
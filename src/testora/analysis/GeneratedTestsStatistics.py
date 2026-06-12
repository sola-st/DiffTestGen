from os.path import join
import json
import os
import re


class GeneratedTestsStatistics():
    def __init__(self):
        self.overall_generated_tests_raw = 0
        self.overall_from_rounds_raw = [0]

        self.overall_generated_tests = 0
        self.overall_from_rounds = [0]

        # project level
        self.project_generated_tests_raw = 0
        self.project_from_rounds_raw = [0]

        self.project_generated_tests = 0
        self.project_from_rounds = [0]

        self.nb_test_generated_patterns = [r"^Generated (\d+) tests"]# , \
                # r"^Generated (\d+) more tests"] #, r"Static error fixed (\d+)/"]


    def clear_overall(self):
        self.overall_generated_tests_raw = 0
        self.overall_from_rounds_raw = [0]
        self.overall_generated_tests = 0
        self.overall_from_rounds = [0]

    def clear_project_level(self):
        self.project_generated_tests_raw = 0
        self.project_from_rounds_raw = [0]
        self.project_generated_tests = 0
        # self.project_from_uncertain_round = 0
        self.project_from_rounds = [0]

    def analyze_single_pr(self, info):
        # current pr level
        # before_clean_test_num = 0
        before_clean_test_num = 0
        before_clean_test_num_from_rounds = [0]

        after_clean_test_num = 0
        after_clean_test_num_from_rounds = [0]

        for info_block in info:
            if "message" in info_block.keys():
                msg = info_block["message"]
                if msg.startswith("Generated") or msg.startswith("Static error fixed"):
                    for nb_test_generated_pattern in self.nb_test_generated_patterns:
                        nb_generated_tests_match = re.search(nb_test_generated_pattern, msg)
                        if nb_generated_tests_match:
                            nb = int(nb_generated_tests_match.group(1))
                            after_clean_test_num += nb

                            if "#Round" in msg:
                                round_num = int(msg.split("#Round ", 1)[1].replace(")", ""))
                                if round_num >= len(after_clean_test_num_from_rounds):
                                    for _ in range(len(after_clean_test_num_from_rounds), round_num+1):
                                        after_clean_test_num_from_rounds.append(0)
                                after_clean_test_num_from_rounds[round_num] += nb

                                before_clean_test_num_tmp = int(msg.split("(", 1)[1].split(" ", 1)[0])
                                before_clean_test_num += before_clean_test_num_tmp
                                for _ in range(len(before_clean_test_num_from_rounds), round_num+1):
                                        before_clean_test_num_from_rounds.append(0)
                                before_clean_test_num_from_rounds[round_num] += before_clean_test_num_tmp

                            # else:
                            #     from_uncertain_round += nb
                            break

        single_pr_json = {
            "project": None, # will be updated when returned
            "pr_num": None, # will be updated when returned
            "generated_tests": after_clean_test_num,
            "generated_tests_raw": before_clean_test_num,
            "details": {},
            "details_raw": {}
        }

        for idx, num in enumerate(after_clean_test_num_from_rounds):
            single_pr_json["details"].update({f"from_round_{idx}": num})

        for idx, num in enumerate(before_clean_test_num_from_rounds):
            single_pr_json["details_raw"].update({f"from_round_{idx}": num})

        # update overall 
        self.overall_generated_tests += after_clean_test_num
        if len(self.overall_from_rounds) < len(after_clean_test_num_from_rounds):
            for _ in range(len(self.overall_from_rounds), len(after_clean_test_num_from_rounds)):
                self.overall_from_rounds.append(0)

        for j, num in enumerate(after_clean_test_num_from_rounds):
            self.overall_from_rounds[j] += num
        
        # raw
        self.overall_generated_tests_raw += before_clean_test_num
        if len(self.overall_from_rounds_raw) < len(before_clean_test_num_from_rounds):
            for _ in range(len(self.overall_from_rounds_raw), len(before_clean_test_num_from_rounds)):
                self.overall_from_rounds_raw.append(0)

        for j, num in enumerate(before_clean_test_num_from_rounds):
            self.overall_from_rounds_raw[j] += num
    
        # update project level
        self.project_generated_tests += after_clean_test_num

        if len(self.project_from_rounds) < len(after_clean_test_num_from_rounds):
            for _ in range(len(self.project_from_rounds), len(after_clean_test_num_from_rounds)):
                self.project_from_rounds.append(0)

        for j, num in enumerate(after_clean_test_num_from_rounds):
            self.project_from_rounds[j] += num

        # raw
        self.project_generated_tests_raw += before_clean_test_num
        if len(self.project_from_rounds_raw) < len(before_clean_test_num_from_rounds):
            for _ in range(len(self.project_from_rounds_raw), len(before_clean_test_num_from_rounds)):
                self.project_from_rounds_raw.append(0)

        for j, num in enumerate(before_clean_test_num_from_rounds):
            self.project_from_rounds_raw[j] += num

        return single_pr_json


    def main(self):
        iteration = 0
        results_folder = join("data", "results")
        output_folder = join(results_folder, "table_and_plots", "different_outputs_statistics", f"iter_{iteration}", "generated_tests_meta_100")
        os.makedirs(output_folder, exist_ok=True)

        # model_version = "gpt-4o-mini-2024-07-18"
        model_version = "gpt-5-mini-2025-08-07"
        config_names = ["testora"]#, "only_coverage_feedback", "only_cg", "difftestgen"]
        approach_names = ["Testora"]#, "Only Coverage Feedback", "Only Access Information", "DiffTestGen"]
        subset_mode = False

        project_info = {
            "keras": 133,
            "marshmallow": 53,
            "pandas": 127,
            "scipy": 126,
        }

        # collect rows for summary tables across all configurations
        latex_rows = []
        raw_latex_rows = []
        round_rows = []
        raw_round_rows = []
        max_rounds = 0
        max_raw_rounds = 0
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
                    log_folder = join(results_folder, model_version, f"iter_{iteration}_100", f"log_{version_name}", target_project)
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
                    "project_generated_tests_raw": self.project_generated_tests_raw,
                    "details": {
                        
                    },
                    "details_raw": {
                        
                    }
                }

                for idx, num in enumerate(self.project_from_rounds):
                    project_str["details"].update({f"project_from_round_{idx}": num})

                for idx, num in enumerate(self.project_from_rounds_raw):
                    project_str["details_raw"].update({f"project_from_round_raw_{idx}": num})

                project_level.append(project_str)
                self.clear_project_level()
            
            # overall summary
            overall_str = {
                "repetition_idx" : iteration,
                "overall_pr_num" : len(single_iteration),
                "overall_generated_tests": self.overall_generated_tests,
                "overall_generated_tests_raw": self.overall_generated_tests_raw,
                "details": {
                    
                },
                "details_raw": {
                    
                }
            }

            for idx, num in enumerate(self.overall_from_rounds):
                overall_str["details"].update({f"overall_from_round_{idx}": num})

            for idx, num in enumerate(self.overall_from_rounds_raw):
                overall_str["details_raw"].update({f"overall_from_round_raw_{idx}": num})

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

            raw_row_vals = []
            for proj in projects_order:
                proj_val = None
                for p in project_level:
                    if p.get("project") == proj:
                        proj_val = p.get("project_generated_tests_raw", 0)
                        break
                if proj_val is None:
                    proj_val = 0
                raw_row_vals.append(proj_val)
            raw_total = sum(raw_row_vals)
            raw_latex_rows.append((approach_name, raw_row_vals, raw_total))

            round_vals = list(self.overall_from_rounds)
            max_rounds = max(max_rounds, len(round_vals))
            round_rows.append((approach_name, round_vals, total))

            raw_round_vals = list(self.overall_from_rounds_raw)
            max_raw_rounds = max(max_raw_rounds, len(raw_round_vals))
            raw_round_rows.append((approach_name, raw_round_vals, raw_total))

            self.clear_overall()

        # After processing all configurations, write a LaTeX table summarizing generated tests
        # cols = 1 + len(projects_order) + 1
        col_spec = "l" + "r" * (len(projects_order) + 1)
        header_cells = [""] + [ _escape_latex(p) for p in projects_order ] + ["Total"]

        latex_lines = [
            "\\setlength{\\tabcolsep}{3pt}",
            "% Total generated tests by approach and project",
        ]
        latex_lines.append("\\begin{tabular}{%s}" % col_spec)
        latex_lines.append("\\hline")
        latex_lines.append(" & ".join(header_cells) + "\\\\")
        latex_lines.append("\\hline")
        for approach_name, row_vals, total in latex_rows:
            cells = [ _escape_latex(approach_name) ] + [ str(v) for v in row_vals ] + [ str(total) ]
            latex_lines.append(" & ".join(cells) + "\\\\")
        latex_lines.append("\\hline")
        latex_lines.append("\\end{tabular}")
        latex_lines.append("\\vspace{2pt}")
        latex_lines.append("")

        round_col_spec = "l" + "r" * (1 + max_rounds)
        round_header_cells = ["Approach"] + [f"R{i}" for i in range(max_rounds)] + ["Total"]
        latex_lines.append("% Overall round breakdown by approach")
        latex_lines.append("\\begin{tabular}{%s}" % round_col_spec)
        latex_lines.append("\\hline")
        latex_lines.append(" & ".join(round_header_cells) + "\\\\")
        latex_lines.append("\\hline")
        for approach_name, round_vals, total in round_rows:
            padded_rounds = round_vals + [0] * (max_rounds - len(round_vals))
            cells = [ _escape_latex(approach_name) ] + [ str(v) for v in padded_rounds ] + [ str(total) ]
            latex_lines.append(" & ".join(cells) + "\\\\")
        latex_lines.append("\\hline")
        latex_lines.append("\\end{tabular}")
        latex_lines.append("\\vspace{4pt}")
        latex_lines.append("")

        raw_col_spec = "l" + "r" * (len(projects_order) + 1)
        raw_header_cells = [""] + [ _escape_latex(p) for p in projects_order ] + ["Total"]
        latex_lines.append("% Total raw generated tests by approach and project")
        latex_lines.append("\\begin{tabular}{%s}" % raw_col_spec)
        latex_lines.append("\\hline")
        latex_lines.append(" & ".join(raw_header_cells) + "\\\\")
        latex_lines.append("\\hline")
        for approach_name, row_vals, total in raw_latex_rows:
            cells = [ _escape_latex(approach_name) ] + [ str(v) for v in row_vals ] + [ str(total) ]
            latex_lines.append(" & ".join(cells) + "\\\\")
        latex_lines.append("\\hline")
        latex_lines.append("\\end{tabular}")
        latex_lines.append("\\vspace{2pt}")
        latex_lines.append("")

        raw_round_col_spec = "l" + "r" * (1 + max_raw_rounds)
        raw_round_header_cells = ["Approach"] + [f"R{i}" for i in range(max_raw_rounds)] + ["Total"]
        latex_lines.append("% Overall raw round breakdown by approach")
        latex_lines.append("\\begin{tabular}{%s}" % raw_round_col_spec)
        latex_lines.append("\\hline")
        latex_lines.append(" & ".join(raw_round_header_cells) + "\\\\")
        latex_lines.append("\\hline")
        for approach_name, round_vals, total in raw_round_rows:
            padded_rounds = round_vals + [0] * (max_raw_rounds - len(round_vals))
            cells = [ _escape_latex(approach_name) ] + [ str(v) for v in padded_rounds ] + [ str(total) ]
            latex_lines.append(" & ".join(cells) + "\\\\")
        latex_lines.append("\\hline")
        latex_lines.append("\\end{tabular}")
        latex_lines.append("\\vspace{2pt}")
        latex_lines.append("")

        latex_file = join(output_folder, "generated_tests_summary_table.tex")
        with open(latex_file, "w") as f:
            f.write("\n".join(latex_lines))


if __name__=="__main__":
    GeneratedTestsStatistics().main()
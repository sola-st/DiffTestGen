from os.path import join
import json
import os
import re

import numpy as np
from matplotlib import pyplot as plt


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

    def _escape_latex(self, s: str) -> str:
        return s.replace("_", "\\_")

    @staticmethod
    def _round_average_no_decimal(value: float) -> int:
        return int(round(value))

    def _build_latex_table_lines(self, header_cells, row_data, col_spec, comment):
        latex_lines = [
            "\\setlength{\\tabcolsep}{3pt}",
            f"% {comment}",
            "\\begin{tabular}{%s}" % col_spec,
            "\\hline",
            " & ".join(header_cells) + "\\\\",
            "\\hline",
        ]
        for approach_name, row_vals, total in row_data:
            cells = [self._escape_latex(approach_name)] + [str(v) for v in row_vals] + [str(total)]
            latex_lines.append(" & ".join(cells) + "\\\\")
        latex_lines.extend([
            "\\hline",
            "\\end{tabular}",
            "\\vspace{2pt}",
            "",
        ])
        return latex_lines

    def _build_latex_round_table_lines(self, approach_names, round_totals, total_by_approach, max_rounds, comment):
        latex_lines = [
            "\\setlength{\\tabcolsep}{3pt}",
            f"% {comment}",
            "\\begin{tabular}{%s}" % ("l" + "r" * (1 + max_rounds)),
            "\\hline",
            " & ".join(["Approach"] + [f"R{i}" for i in range(max_rounds)] + ["Total"]) + "\\\\",
            "\\hline",
        ]
        for approach_name in approach_names:
            round_vals = round_totals[approach_name]
            padded_rounds = round_vals + [0] * (max_rounds - len(round_vals))
            cells = [self._escape_latex(approach_name)] + [str(v) for v in padded_rounds] + [str(total_by_approach[approach_name])]
            latex_lines.append(" & ".join(cells) + "\\\\")
        latex_lines.extend([
            "\\hline",
            "\\end{tabular}",
            "\\vspace{2pt}",
            "",
        ])
        return latex_lines

    def _write_iteration_summary_tables(self, output_folder, projects_order, approach_names, latex_rows, raw_latex_rows, round_rows, raw_round_rows, max_rounds, max_raw_rounds):
        col_spec = "l" + "r" * (len(projects_order) + 1)
        header_cells = [""] + [self._escape_latex(p) for p in projects_order] + ["Total"]
        latex_lines = self._build_latex_table_lines(header_cells, latex_rows, col_spec, "Total generated tests by approach and project")

        round_totals = {approach_name: round_vals for approach_name, round_vals, _ in round_rows}
        round_totals_by_approach = {approach_name: total for approach_name, _, total in round_rows}
        latex_lines.extend(self._build_latex_round_table_lines(approach_names, round_totals, round_totals_by_approach, max_rounds, "Overall round breakdown by approach"))

        raw_header_cells = [""] + [self._escape_latex(p) for p in projects_order] + ["Total"]
        raw_lines = self._build_latex_table_lines(raw_header_cells, raw_latex_rows, col_spec, "Total raw generated tests by approach and project")
        latex_lines.extend(raw_lines)

        raw_round_totals = {approach_name: round_vals for approach_name, round_vals, _ in raw_round_rows}
        raw_round_totals_by_approach = {approach_name: total for approach_name, _, total in raw_round_rows}
        latex_lines.extend(self._build_latex_round_table_lines(approach_names, raw_round_totals, raw_round_totals_by_approach, max_raw_rounds, "Overall raw round breakdown by approach"))

        latex_file = join(output_folder, "generated_tests_summary_table.tex")
        with open(latex_file, "w") as f:
            f.write("\n".join(latex_lines))

    def _average_values(self, totals_by_approach, repetition_count):
        averaged = {}
        for approach_name, value in totals_by_approach.items():
            averaged[approach_name] = self._round_average_no_decimal(value / repetition_count)
        return averaged

    def _average_list_values(self, totals_by_approach, repetition_count):
        averaged = {}
        for approach_name, values in totals_by_approach.items():
            if not values:
                averaged[approach_name] = []
            else:
                averaged[approach_name] = [self._round_average_no_decimal(v / repetition_count) for v in values]
        return averaged

    def _write_final_summary_tables(self, summary_root, projects_order, approach_names, final_project_totals, final_project_raw_totals, final_round_totals, final_raw_round_totals, final_total_by_approach, final_raw_total_by_approach, repetition_count):
        avg_project_totals = self._average_list_values(final_project_totals, repetition_count)
        avg_project_raw_totals = self._average_list_values(final_project_raw_totals, repetition_count)
        avg_round_totals = self._average_list_values(final_round_totals, repetition_count)
        avg_raw_round_totals = self._average_list_values(final_raw_round_totals, repetition_count)
        avg_total_by_approach = self._average_values(final_total_by_approach, repetition_count)
        avg_raw_total_by_approach = self._average_values(final_raw_total_by_approach, repetition_count)

        final_col_spec = "l" + "r" * (len(projects_order) + 1)
        final_header_cells = [""] + [self._escape_latex(p) for p in projects_order] + ["Total"]
        final_latex_lines = self._build_latex_table_lines(final_header_cells, [(approach_name, avg_project_totals[approach_name], avg_total_by_approach[approach_name]) for approach_name in approach_names], final_col_spec, "Average generated tests across repetitions by approach and project")

        final_round_max = max((len(vals) for vals in avg_round_totals.values()), default=0)
        final_latex_lines.extend(self._build_latex_round_table_lines(approach_names, avg_round_totals, avg_total_by_approach, final_round_max, "Average overall round breakdown across repetitions"))

        raw_final_header_cells = [""] + [self._escape_latex(p) for p in projects_order] + ["Total"]
        final_latex_lines.extend(self._build_latex_table_lines(raw_final_header_cells, [(approach_name, avg_project_raw_totals[approach_name], avg_raw_total_by_approach[approach_name]) for approach_name in approach_names], final_col_spec, "Average raw generated tests across repetitions by approach and project"))

        raw_final_round_max = max((len(vals) for vals in avg_raw_round_totals.values()), default=0)
        final_latex_lines.extend(self._build_latex_round_table_lines(approach_names, avg_raw_round_totals, avg_raw_total_by_approach, raw_final_round_max, "Average overall raw round breakdown across repetitions"))

        final_latex_file = join(summary_root, "generated_tests_summary_table_all_repetitions.tex")
        with open(final_latex_file, "w") as f:
            f.write("\n".join(final_latex_lines))

    def main(self):
        max_iterations = 3
        model_version = "gpt-5-mini-2025-08-07"
        config_names = ["testora", "testora_pp", "only_coverage_feedback", "only_cg", "difftestgen"]
        approach_names = ["Testora", "Testora++", "Only Coverage Feedback", "Only Access Information", "DiffTestGen"]
        subset_mode = False

        project_info = {
            "keras": 133,
            "marshmallow": 53,
            "pandas": 127,
            "scipy": 126,
        }

        results_folder = join("data", "results")
        summary_root = join(results_folder, "table_and_plots", "different_outputs_statistics")
        os.makedirs(summary_root, exist_ok=True)

        final_project_totals = {name: [0] * len(project_info) for name in approach_names}
        final_project_raw_totals = {name: [0] * len(project_info) for name in approach_names}
        final_round_totals = {name: [] for name in approach_names}
        final_raw_round_totals = {name: [] for name in approach_names}
        final_total_by_approach = {name: 0 for name in approach_names}
        final_raw_total_by_approach = {name: 0 for name in approach_names}
        per_iteration_project_totals = {name: [] for name in approach_names}
        per_iteration_round_totals = {name: [] for name in approach_names}
        per_iteration_total_by_approach = {name: [] for name in approach_names}
        projects_order = list(project_info.keys())

        for iteration in range(max_iterations):
            output_folder = join(results_folder, "table_and_plots", "different_outputs_statistics", f"iter_{iteration}", "generated_tests_meta")
            os.makedirs(output_folder, exist_ok=True)

            latex_rows = []
            raw_latex_rows = []
            round_rows = []
            raw_round_rows = []
            max_rounds = 0
            max_raw_rounds = 0
            projects_order = list(project_info.keys())

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

                    project_str = {
                        "project": target_project,
                        "project_pr_num": len(pr_list),
                        "project_generated_tests": self.project_generated_tests,
                        "project_generated_tests_raw": self.project_generated_tests_raw,
                        "details": {},
                        "details_raw": {},
                    }

                    for idx, num in enumerate(self.project_from_rounds):
                        project_str["details"].update({f"project_from_round_{idx}": num})

                    for idx, num in enumerate(self.project_from_rounds_raw):
                        project_str["details_raw"].update({f"project_from_round_raw_{idx}": num})

                    project_level.append(project_str)
                    self.clear_project_level()

                overall_str = {
                    "repetition_idx": iteration,
                    "overall_pr_num": len(single_iteration),
                    "overall_generated_tests": self.overall_generated_tests,
                    "overall_generated_tests_raw": self.overall_generated_tests_raw,
                    "details": {},
                    "details_raw": {},
                }

                for idx, num in enumerate(self.overall_from_rounds):
                    overall_str["details"].update({f"overall_from_round_{idx}": num})

                for idx, num in enumerate(self.overall_from_rounds_raw):
                    overall_str["details_raw"].update({f"overall_from_round_raw_{idx}": num})

                to_write = [overall_str] + project_level + single_iteration

                result_file = join(output_folder, f"{version_name}.json")
                with open(result_file, "w") as f:
                    json.dump(to_write, f, indent=4)

                row_vals = []
                for proj in projects_order:
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
                per_iteration_project_totals[approach_name].append(list(row_vals))
                per_iteration_total_by_approach[approach_name].append(total)

                for idx, val in enumerate(row_vals):
                    final_project_totals[approach_name][idx] += val
                final_total_by_approach[approach_name] += total

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

                for idx, val in enumerate(raw_row_vals):
                    final_project_raw_totals[approach_name][idx] += val
                final_raw_total_by_approach[approach_name] += raw_total

                round_vals = list(self.overall_from_rounds)
                per_iteration_round_totals[approach_name].append(list(round_vals))
                max_rounds = max(max_rounds, len(round_vals))
                round_rows.append((approach_name, round_vals, total))

                if len(final_round_totals[approach_name]) < len(round_vals):
                    final_round_totals[approach_name].extend([0] * (len(round_vals) - len(final_round_totals[approach_name])))
                for idx, val in enumerate(round_vals):
                    final_round_totals[approach_name][idx] += val

                raw_round_vals = list(self.overall_from_rounds_raw)
                max_raw_rounds = max(max_raw_rounds, len(raw_round_vals))
                raw_round_rows.append((approach_name, raw_round_vals, raw_total))

                if len(final_raw_round_totals[approach_name]) < len(raw_round_vals):
                    final_raw_round_totals[approach_name].extend([0] * (len(raw_round_vals) - len(final_raw_round_totals[approach_name])))
                for idx, val in enumerate(raw_round_vals):
                    final_raw_round_totals[approach_name][idx] += val

                self.clear_overall()

            self._write_iteration_summary_tables(output_folder, projects_order, approach_names, latex_rows, raw_latex_rows, round_rows, raw_round_rows, max_rounds, max_raw_rounds)

        self._write_final_summary_tables(summary_root, projects_order, approach_names, final_project_totals, final_project_raw_totals, final_round_totals, final_raw_round_totals, final_total_by_approach, final_raw_total_by_approach, max_iterations)


if __name__ == "__main__":
    GeneratedTestsStatistics().main()
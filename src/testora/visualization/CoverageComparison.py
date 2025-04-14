import json
from os import listdir, makedirs
from testora.execution.CoverageAnalyzer import ranges_to_set_in_batch
from os.path import join


class CoverageComparison():
    def __init__(self, testora_log_folder, dtg_log_folder, output_folder):
        '''
        Return a list of coverage inforamtion that contains both the coverage from Testora and Our approach.
        Each element is a json string for a single PR. Format refer to the json string in function get_single_log_file_coverage_dtg.
        '''
        self.testora_log_folder = testora_log_folder
        self.dtg_log_folder = dtg_log_folder
        self.output_folder = output_folder

        self.all_from_testora = []
        self.all_from_dtg = []

        self.all_executable_modified_lines_old_len = 0
        self.all_executable_modified_lines_new_len = 0
        self.union_covered_lines_round0 = {"old": set(), "new": set()}
        self.union_covered_lines_round1 = {"old": set(), "new": set()}
        self.union_covered_lines_round2 = {"old": set(), "new": set()}
        self.union_covered_lines_round3 = {"old": set(), "new": set()}

    def clear(self):
        # clear all the collected info after a PR is done.
        self.all_executable_modified_lines_old_len = 0
        self.all_executable_modified_lines_new_len = 0
        self.union_covered_lines_round0 = {"old": set(), "new": set()}
        self.union_covered_lines_round1 = {"old": set(), "new": set()}
        self.union_covered_lines_round2 = {"old": set(), "new": set()}
        self.union_covered_lines_round3 = {"old": set(), "new": set()}

    def ranges_to_total_num(self, ranges):
        total_num = 0
        for ran in ranges:
            total_num += len(list(ran))
        return total_num

    def get_single_log_file_coverage_dtg(self, log_file):
        with open(log_file, "r") as f:
            info = json.load(f)
        
        pr_num = None
        project_name = None
        for info_block in info:
            if "details" in info_block.keys():
                info_block_details = info_block["details"]
                if "Old: Coverage:" in info_block_details or \
                        "All executable/coverable modified lines:" in info_block_details:
                    if "Diff coverage, all rounds" in info_block["message"]:
                        if not self.all_executable_modified_lines_old_len and (not self.all_executable_modified_lines_new_len):
                            pr_num = info_block["pr_nb"]
                            tmp = info_block_details.split("Old: ")[1]
                            all_executable_modified_lines_old_ranges, all_executable_modified_lines_new_ranges = tmp.spilt(", New: ")
                            self.all_executable_modified_lines_old_len = self.ranges_to_total_num(all_executable_modified_lines_old_ranges) 
                            self.all_executable_modified_lines_new_len = self.ranges_to_total_num(all_executable_modified_lines_new_ranges) 
                    else:
                        coverage_percentage, uncovered_ranges, covered_modified_line_ranges = info_block_details.split("\n")
                        tmp = covered_modified_line_ranges.split("Old: ")[1]
                        covered_lines_old_ranges, covered_lines_new_ranges = tmp.spilt(", New: ")
                        covered_lines_old, covered_lines_new = ranges_to_set_in_batch(
                                [covered_lines_old_ranges, covered_lines_new_ranges])

                        if "Diff coverage, round 0" in info_block["message"]:
                            self.union_covered_lines_round0["old"].union(covered_lines_old)
                            self.union_covered_lines_round0["new"].union(covered_lines_new)
                        elif "Diff coverage, round 1" in info_block["message"]:
                            self.union_covered_lines_round1["old"].union(covered_lines_old)
                            self.union_covered_lines_round1["new"].union(covered_lines_new)
                        elif "Diff coverage, round 2" in info_block["message"]:
                            self.union_covered_lines_round2["old"].union(covered_lines_old)
                            self.union_covered_lines_round2["new"].union(covered_lines_new)
                        elif "Diff coverage, round 3" in info_block["message"]:
                            self.union_covered_lines_round3["old"].union(covered_lines_old)
                            self.union_covered_lines_round3["new"].union(covered_lines_new)
            elif not project_name and "url" in info_block.keys():
                project_name = info_block["url"].split("/")[-3]

        self.format_coverage_info(pr_num, project_name)

    def format_coverage_info(self, pr_num, project_name):
        # union coverages
        round_0_old, round_0_new = self.compute_percentage(self.union_covered_lines_round0)
        round_1_old, round_1_new = self.compute_percentage(self.union_covered_lines_round1)
        round_2_old, round_2_new = self.compute_percentage(self.union_covered_lines_round2)
        round_3_old, round_3_new = self.compute_percentage(self.union_covered_lines_round3)
        
        json_str = {   
            pr_num: {
                "Project": project_name,
                "Initial": {
                    "R-0": {
                        "Testora": {"old": None, "new": None},
                        "Our Approach": {"old": round_0_old, "new": round_0_new}
                    }
                },
                "Feedback": {
                    "R-1": {
                        "Testora": {"old": "--", "new": "--"},
                        "Our Approach": {"old": round_1_old,  "new": round_1_new}
                    },
                    "R-2": {
                        "Testora": {"old": "--", "new": "--"},
                        "Our Approach": {"old": round_2_old,  "new": round_2_new}
                    },
                    "R-3": {
                        "Testora": {"old": "--", "new": "--"},
                        "Our Approach": {"old": round_3_old,  "new": round_3_new}
                    },
                }
            }
        }
        self.all_from_dtg.append(json_str)
        self.clear()


    def compute_percentage(self, union_covered):
        old = len(union_covered["old"])
        new = len(union_covered["new"])
        old_percentage =  old / self.all_executable_modified_lines_old_len if self.all_executable_modified_lines_old_len > 0 else 1
        new_percentage =  new / self.all_executable_modified_lines_new_len if self.all_executable_modified_lines_new_len > 0 else 1
        old_info_str = f"{old_percentage:.2%} ({old}/{self.all_executable_modified_lines_old_len})"
        new_info_str = f"{new_percentage:.2%} ({new}/{self.all_executable_modified_lines_new_len})"
        return old_info_str, new_info_str

    def get_multiple_pr_coverage_info(self):
        log_files = listdir(self.dtg_log_folder)
        for log_file in log_files:
            self.get_single_log_file_coverage_dtg(log_file)

        meta_file = join(output_folder, "coverage_comparison_meta")
        with open(meta_file, "w") as f:
            json.dump(self.all_from_dtg, f, indent=4, ensure_ascii=False)     
        print(f"All the collected coverage information is wriitten to {meta_file}")

    def table_coverages(self, caption, label, tex_file):
        latex_table = "\\begin{table}[t]\n\\centering\n\\footnotesize\n"
        latex_table += "\\caption{" + caption + "}\n"
        latex_table += "\\label{tab:" + label + "}\n"
        latex_table += "\\begin{tabular}{@{}" + "lll" + "".join(["r"] * 6) + "@{}}\n"
        latex_table += "\\toprule\n"
        # latex_table += "PR & \\multicolumn{" + "2}{" + "c}{" + "Rounds} & \\multicolumn{2" + "}{c" + "}{" + "Testora} & \\multicolumn{2" + "}{c" + "}" + "{Our Approach}\\"
        latex_table += "ID & Project & PR & \multicolumn{2}{c}{Rounds} & \multicolumn{2}{c}{Testora} & \multicolumn{2}{c}{Our Approach}\\"
        latex_table += "\\cmidrule{4-7}"
        latex_table += "& & &  & & Old & New & Old & New \\"
        id = 0
        for pr_num, json_str in self.all_from_dtg:
            id += 1
            latex_table += "\\multirow{4}{*}{" + id + "} & \\multirow{4}{*}{" + json_str["Project"] + "} & \\multirow{4}{*}{" + pr_num + "} &" \
                    + "Initial Round & R-0 & x/xx (xx.3\%) & x/xx (xx.3\%) &" \
                    + json_str["Initial"]["R-0"]["Our Approach"]["old"] + "&" + json_str["Initial"]["R-0"]["Our Approach"]["new"] + "\\"
            latex_table += "\\cmidrule{2-7}"
            latex_table += "& & & \multirow{3}{*}{Feedback Round} & R-1 & -- & -- &" \
                    + json_str["Feedback"]["R-1"]["Our Approach"]["old"] + "&" + json_str["Feedback"]["R-1"]["Our Approach"]["new"] + "\\"
            latex_table += "& & & & R-2 & -- & -- &" \
                    + json_str["Feedback"]["R-2"]["Our Approach"]["old"] + "&" + json_str["Feedback"]["R-2"]["Our Approach"]["new"] + "\\"
            latex_table += "& & & & R-3 & -- & -- &" \
                    + json_str["Feedback"]["R-3"]["Our Approach"]["old"] + "&" + json_str["Feedback"]["R-3"]["Our Approach"]["new"] + "\\"
            latex_table += "\\midrule"

        latex_table += "\\end{tabular}\n"
        latex_table += "\\end{table}"

        with open(tex_file, "w") as f:
            f.write(latex_table + "\n")
        print(f"The comparison table is wriitten to {tex_file}")

if __name__=="__main__":
    testora_log_folder = ""
    dtg_log_folder = ""
    output_folder = join("data", "results")
    table_output_folder = join(output_folder, "table_and_plots")
    makedirs(table_output_folder, exist_ok=True)
    init = CoverageComparison(testora_log_folder, dtg_log_folder, output_folder)
   
    init.get_multiple_pr_coverage_info()
    caption = "Coverage Comparison between Testora and Our Approach"
    label="coverage_comparison"
    tex_file = join(table_output_folder, "coverage_comparison.tex")
    # col_names = ["ID", "Project", "PR", "Rounds", "Testora", "Our Approach"]
    init.table_coverages(caption, label, tex_file)


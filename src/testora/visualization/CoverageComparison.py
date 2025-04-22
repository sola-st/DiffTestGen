import json
import copy
from os import listdir, makedirs
from testora.execution.CoverageAnalyzer import range_to_set, ranges_to_set_in_batch
from os.path import join


class CoverageComparison():
    def __init__(self, testora_log_folder, all_version, all_version_id, output_folder):
        '''
        Return a list of coverage inforamtion that contains both the coverage from Testora and Our approach.
        Each element is a json string for a single PR. Format refer to the json string in function get_single_log_file_coverage_dtg.
        '''
        self.testora_log_folder = testora_log_folder
        self.all_version = all_version
        self.all_version_id = all_version_id
        self.output_folder = output_folder

        self.all_from_testora = []
        self.all_from_dtg = []

        self.all_executable_modified_lines_old_len = 0
        self.all_executable_modified_lines_new_len = 0
        self.union_covered_lines_round0 = {"old": {}, "old_len_cross_file": None,  "new": {}, "new_len_cross_file": None,}
        self.union_covered_lines_round1 = {"old": {}, "old_len_cross_file": None,  "new": {}, "new_len_cross_file": None,}
        self.union_covered_lines_round2 = {"old": {}, "old_len_cross_file": None,  "new": {}, "new_len_cross_file": None,}
        self.union_covered_lines_round3 = {"old": {}, "old_len_cross_file": None,  "new": {}, "new_len_cross_file": None,}

    def clear(self):
        # clear all the collected info after a PR is done.
        self.all_executable_modified_lines_old_len = 0
        self.all_executable_modified_lines_new_len = 0
        self.union_covered_lines_round0 = {"old": {}, "old_len_cross_file": None,  "new": {}, "new_len_cross_file": None,}
        self.union_covered_lines_round1 = {"old": {}, "old_len_cross_file": None,  "new": {}, "new_len_cross_file": None,}
        self.union_covered_lines_round2 = {"old": {}, "old_len_cross_file": None,  "new": {}, "new_len_cross_file": None,}
        self.union_covered_lines_round3 = {"old": {}, "old_len_cross_file": None,  "new": {}, "new_len_cross_file": None,}

    def ranges_to_total_num(self, ranges_dict:dict):
        total_num = 0
        for file, range_list_str in ranges_dict.items():
            ranges = eval(range_list_str)
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
                            all_executable_modified_lines_old_ranges, all_executable_modified_lines_new_ranges = tmp.split(", New: ")
                            old = all_executable_modified_lines_old_ranges.replace("\'", "\"").replace("[", "\"[").replace("]", "]\"")
                            new = all_executable_modified_lines_new_ranges.replace("\'", "\"").replace("[", "\"[").replace("]", "]\"")
                            all_executable_old_ranges_dict = json.loads(old) # from files to lines
                            all_executable_new_ranges_dict = json.loads(new)

                            self.all_executable_modified_lines_old_len = self.ranges_to_total_num(all_executable_old_ranges_dict) 
                            self.all_executable_modified_lines_new_len = self.ranges_to_total_num(all_executable_new_ranges_dict) 
                    else:
                        coverage_percentage, uncovered_ranges_dict_str, covered_modified_line_ranges_dict_str = info_block_details.split("\n")
                        tmp = covered_modified_line_ranges_dict_str.split("Old: ")[1]
                        covered_lines_old_ranges_dict_str, covered_lines_new_ranges_dict_str = tmp.split(", New: ")
                        # transfer to valid json format
                        old = covered_lines_old_ranges_dict_str.replace("\'", "\"").replace("[", "\"[").replace("]", "]\"")
                        new = covered_lines_new_ranges_dict_str.replace("\'", "\"").replace("[", "\"[").replace("]", "]\"")
                        covered_lines_old_ranges_dict = json.loads(old) # from files to lines
                        covered_lines_new_ranges_dict = json.loads(new)
                        info_block_msg = info_block["message"]
                        self.get_union_numbers_form_dict(covered_lines_old_ranges_dict, info_block_msg, "old")
                        self.get_union_numbers_form_dict(covered_lines_new_ranges_dict, info_block_msg, "new")

            elif not project_name and "url" in info_block.keys():
                project_name = info_block["url"].split("/")[-3]

        self.format_coverage_info(pr_num, project_name)

    def get_union_numbers_form_dict(self, range_dict:dict, info_block_msg, version):
        for file, range_list_str in range_dict.items():
            stmt_num_ranges:list = eval(range_list_str)
            covered_stmts_tmp = range_to_set(stmt_num_ranges)
            covered_stmts= set(covered_stmts_tmp)

            if "Diff coverage, round 0" in info_block_msg:
                try:
                    self.union_covered_lines_round0[version][file] = set(self.union_covered_lines_round0[version][file]).union(covered_stmts)
                except:
                    self.union_covered_lines_round0[version].update({file: covered_stmts})
            elif "Diff coverage, round 1" in info_block_msg:
                if not self.union_covered_lines_round1["old"]:
                    self.union_covered_lines_round1 = copy.deepcopy(self.union_covered_lines_round0)
                try:
                    self.union_covered_lines_round1[version][file] = set(self.union_covered_lines_round1[version][file]).union(covered_stmts)
                except:
                    self.union_covered_lines_round1[version].update({file: covered_stmts})
            elif "Diff coverage, round 2" in info_block_msg:
                if not self.union_covered_lines_round2["old"]:
                    self.union_covered_lines_round2 = copy.deepcopy(self.union_covered_lines_round1)
                try:
                    self.union_covered_lines_round2[version][file] = set(self.union_covered_lines_round2[version][file]).union(covered_stmts)
                except:
                    self.union_covered_lines_round2[version].update({file: covered_stmts})
            elif "Diff coverage, round 3" in info_block_msg:
                if not self.union_covered_lines_round3["old"]:
                    self.union_covered_lines_round3 = copy.deepcopy(self.union_covered_lines_round2)
                try:
                    self.union_covered_lines_round3[version][file] = set(self.union_covered_lines_round3[version][file]).union(covered_stmts)
                except:
                    self.union_covered_lines_round3["old"].update({file: covered_stmts})

    def format_coverage_info(self, pr_num, project_name):
        # union coverages
        round_0_old, round_0_new = self.compute_percentage(self.union_covered_lines_round0)
        round_1_old, round_1_new = self.compute_percentage(self.union_covered_lines_round1)
        round_2_old, round_2_new = self.compute_percentage(self.union_covered_lines_round2)
        round_3_old, round_3_new = self.compute_percentage(self.union_covered_lines_round3)
        
        json_str = {   
            pr_num: {
                "Project": project_name,
                "Version": self.version_id,
                "Initial": {
                    "R-0": {
                        "Testora": {"old": "", "new": ""},
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
        union_covered["old_len_cross_file"] = sum([len(num_list) for num_list in union_covered["old"].values()])
        union_covered["new_len_cross_file"] = sum([len(num_list) for num_list in union_covered["new"].values()])

        old_info_str = "--"
        new_info_str = "--"
        if union_covered["old"].keys():
            old_percentage = union_covered["old_len_cross_file"] / self.all_executable_modified_lines_old_len if self.all_executable_modified_lines_old_len > 0 else 1
            new_percentage = union_covered["new_len_cross_file"] / self.all_executable_modified_lines_new_len if self.all_executable_modified_lines_new_len > 0 else 1
            old_info_str = f"{old_percentage:.2%} ({union_covered['old_len_cross_file']}/{self.all_executable_modified_lines_old_len})"
            new_info_str = f"{new_percentage:.2%} ({union_covered['new_len_cross_file']}/{self.all_executable_modified_lines_new_len})"
        return old_info_str, new_info_str

    def get_multiple_pr_coverage_info(self):
        for folder, self.version_id in zip(self.all_version, self.all_version_id):
            log_files = listdir(folder)

            for log_file in log_files:
                self.get_single_log_file_coverage_dtg(join(folder, log_file))

        self.all_from_dtg = sorted(self.all_from_dtg, key=lambda d: next(iter(d)))
        meta_file = join(output_folder, "coverage_comparison_meta.json")
        with open(meta_file, "w") as f:
            json.dump(self.all_from_dtg, f, indent=4, ensure_ascii=False)     
        print(f"All the collected coverage information is wriitten to {meta_file}")

    def table_coverages(self, caption, label, tex_file):
        latex_table = "\\begin{table*}[t]\n\\centering\n\\footnotesize\n"
        latex_table += "\\caption{" + caption + "}\n"
        latex_table += "\\label{tab:" + label + "}\n"
        latex_table += "\\begin{tabular}{@{}" + "lll" + "".join(["rr|"] * 5) + "rr@{}}\n"
        latex_table += "\\toprule\n"
        # latex_table += "PR & \\multicolumn{" + "2}{" + "c}{" + "Rounds} & \\multicolumn{2" + "}{c" + "}{" + "Testora} & \\multicolumn{2" + "}{c" + "}" + "{Our Approach}\\"
        latex_table += "ID & Project & PR & \multicolumn{2}{c}{Rounds} & \multicolumn{2}{c}{Testora} & \multicolumn{2}{c}{Our Approach}\\\\" + "\n" 
        latex_table += "\\cmidrule{4-9}" + "\n" 
        latex_table += "& & &  & & Old & New & Old & New \\\\" + "\n" 
        for id, pr_record in enumerate(self.all_from_dtg):
            for pr_num, json_str in pr_record.items():
                # update version info
                latex_table = latex_table.replace("\multicolumn{2}{c}{Our Approach}", "\multicolumn{2}{c}{Our Approach " + json_str["Version"] + "}")
                # latex_table = latex_table.replace("\multicolumn{2}{c}{Our Approach}", "\multicolumn{2}{c}{Testora}")
                latex_table += "\\multirow{4}{*}{" + str(id) + "} & \\multirow{4}{*}{" + json_str["Project"] + "} & \\multirow{4}{*}{" + str(pr_num) + "} &" \
                        + "Initial Round & R-0 & " + json_str["Initial"]["R-0"]["Testora"]["old"] + "&" + json_str["Initial"]["R-0"]["Testora"]["new"] + "&" \
                        + json_str["Initial"]["R-0"]["Our Approach"]["old"] + "&" + json_str["Initial"]["R-0"]["Our Approach"]["new"] + "\\\\" + "\n"
                latex_table += "\\cmidrule{4-9}" + "\n"
                latex_table += "& & & \multirow{3}{*}{Feedback Round} & R-1 & -- & -- &" \
                        + json_str["Feedback"]["R-1"]["Our Approach"]["old"] + "&" + json_str["Feedback"]["R-1"]["Our Approach"]["new"] + "\\\\" + "\n"
                latex_table += "& & & & R-2 & -- & -- &" \
                        + json_str["Feedback"]["R-2"]["Our Approach"]["old"] + "&" + json_str["Feedback"]["R-2"]["Our Approach"]["new"] + "\\\\" + "\n"
                latex_table += "& & & & R-3 & -- & -- &" \
                        + json_str["Feedback"]["R-3"]["Our Approach"]["old"] + "&" + json_str["Feedback"]["R-3"]["Our Approach"]["new"] + "\\\\" + "\n"
                latex_table += "\\midrule" + "\n"

        latex_table += "\\end{tabular}\n"
        latex_table += "\\end{table*}"

        with open(tex_file, "w") as f:
            f.write(latex_table.replace("%", "\%") + "\n")
        print(f"The comparison table is wriitten to {tex_file}")

if __name__=="__main__":
    testora_log_folder = "local/log_1_0" # "local/log_2_2_4" #
    dtg_log_folder = "local/log_2_2_4" # 
    all_versions = [dtg_log_folder]
    all_version_id = ["2\_2\_4"] # maps to all_version, "1\_0"  "2\_2\_4"
    output_folder = join("data", "results")
    table_output_folder = join(output_folder, "table_and_plots")
    makedirs(table_output_folder, exist_ok=True)
    init = CoverageComparison(testora_log_folder, all_versions, all_version_id, output_folder)
   
    init.get_multiple_pr_coverage_info()
    caption = "Coverage Comparison between Testora and Our Approach"
    label="coverage_comparison"
    tex_file = join(table_output_folder, "coverage_comparison_2_2_4_cross_round.tex")
    init.table_coverages(caption, label, tex_file)


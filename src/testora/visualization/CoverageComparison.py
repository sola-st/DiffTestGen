from collections import defaultdict
import json
import copy
from os import listdir, makedirs
from testora.execution.CoverageAnalyzer import range_to_set
from os.path import join, isfile


def nested_dict():
    return defaultdict(nested_dict)

class CoverageComparison():
    def __init__(self, log_folder, version_id):
        '''
        Return a list of coverage inforamtion that contains the coverage from Testora or Our approach.
        Each element is a json string for a single PR. Format refer to the json string in function get_single_log_file_coverage_dtg.
        '''
        self.log_folder = log_folder
        self.version_id = version_id
        self.all_from_cur_version = [] # to return
        self.outlier_pr = None # to return

        self.all_executable_modified_lines_old_len = 0
        self.all_executable_modified_lines_new_len = 0
        self.union_covered_lines_single_round = {"old": {}, "old_len_cross_file": None,  "new": {}, "new_len_cross_file": None}
        self.union_covered_lines_multiple_rounds = [] # a list of union_covered_lines_single_round
        
        self.approach_name = "Testora"
        if version_id != "1_0_1":
            self.approach_name = "Our Approach"

    def clear(self):
        # clear all the collected info after a PR is done.
        self.all_executable_modified_lines_old_len = 0
        self.all_executable_modified_lines_new_len = 0
        self.union_covered_lines_single_round = {"old": {}, "old_len_cross_file": None,  "new": {}, "new_len_cross_file": None}
        self.union_covered_lines_multiple_rounds = []

    def ranges_to_total_num(self, ranges_dict:dict):
        total_num = 0
        for file, range_list_str in ranges_dict.items():
            ranges = eval(range_list_str)
            for ran in ranges:
                total_num += len(list(ran))
        return total_num

    def get_single_log_file_coverage_dtg(self, log_file, project_name):
        with open(log_file, "r") as f:
            info = json.load(f)
        
        pr_num = info[1]["pr_nb"]
        if not project_name:
            project_name = info[1]["url"].split("/")[-3] # for single pr at local mode

        pre_round = -1
        coverage_exists = False
        for info_block in info:
            if "details" in info_block.keys():
                info_block_details = info_block["details"]
                if "Old: Coverage:" in info_block_details or \
                        "All executable/coverable modified lines:" in info_block_details:
                    coverage_exists = True
                    if "Diff coverage, all rounds" in info_block["message"]:
                        if not self.all_executable_modified_lines_old_len and (not self.all_executable_modified_lines_new_len):
                            # pr_num = info_block["pr_nb"]
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
                        if "Diff coverage, # Round " in info_block_msg:
                            round = int(info_block_msg.split("# Round ", 1)[1].split(" ", 1)[0])
                            if pre_round != round: # another round starts, record all the collected info for round {round}
                                if self.union_covered_lines_single_round["old"].keys():
                                    self.union_covered_lines_multiple_rounds.append(copy.deepcopy(self.union_covered_lines_single_round))
                                    pre_round = round
                                elif pre_round == -1:
                                    self.get_union_numbers_form_dict(covered_lines_old_ranges_dict, "old")
                                    self.get_union_numbers_form_dict(covered_lines_new_ranges_dict, "new")
                                    pre_round = round
                            else: # update self.union_covered_lines_single_round
                                self.get_union_numbers_form_dict(covered_lines_old_ranges_dict, "old")
                                self.get_union_numbers_form_dict(covered_lines_new_ranges_dict, "new")
        
        if coverage_exists == False:
            self.outlier_pr = pr_num


        # append the last round, related to get_union_numbers_form_dict
        self.union_covered_lines_multiple_rounds.append(copy.deepcopy(self.union_covered_lines_single_round))
        self.format_coverage_info(pr_num, project_name)

    def get_union_numbers_form_dict(self, range_dict:dict, version):
        for file, range_list_str in range_dict.items():
            stmt_num_ranges:list = eval(range_list_str)
            covered_stmts_tmp = range_to_set(stmt_num_ranges)
            covered_stmts = set(covered_stmts_tmp)

            try:
                self.union_covered_lines_single_round[version][file] = set(self.union_covered_lines_single_round[version][file]).union(covered_stmts)
            except:
                self.union_covered_lines_single_round[version].update({file: covered_stmts})
            
    def format_coverage_info(self, pr_num, project_name):
        json_str = nested_dict()
        json_str["Approach"] = self.approach_name
        json_str["Version"] = self.version_id
        json_str["Project"] = project_name
         
        for i, round_info_dict in enumerate(self.union_covered_lines_multiple_rounds):
            old_cov, new_cov = self.compute_percentage(round_info_dict)
            if i == 0:
                json_str[pr_num]["Initial"]["R-0"].update({"old": old_cov, "new": new_cov})
            else: # feedback rounds
                json_str[pr_num]["Feedback"][f"R-{i}"].update({"old": old_cov, "new": new_cov})
            
        self.all_from_cur_version.append(json_str)
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

    def get_multiple_pr_coverage_info(self, project=""):
        # listdir in a random order
        log_files = listdir(self.log_folder)
        for file in log_files:
            log_file = join(self.log_folder, file)
            if isfile(log_file) and "breakpoint" not in file:
                # exclude archive folder and breakpoint_data files
                self.get_single_log_file_coverage_dtg(log_file, project)

        self.all_from_cur_version = sorted(self.all_from_cur_version, key=lambda d: list(d.keys())[3])
        return self.all_from_cur_version

if __name__=="__main__":
    dtg_log_folder = "local/log_2_2_4"
    version_id = "2_2_4"
    output_folder = join("data", "results")
    table_output_folder = join(output_folder, "table_and_plots")
    makedirs(table_output_folder, exist_ok=True)
    init = CoverageComparison(dtg_log_folder, version_id)
    all_from_cur_version = init.get_multiple_pr_coverage_info()
    meta_file = join(table_output_folder, f"coverage_comparison_meta_{version_id}.json")
    with open(meta_file, "w") as f:
        json.dump(all_from_cur_version, f, indent=4, ensure_ascii=False)   
    print(f"All the collected coverage information is written to {meta_file}")  

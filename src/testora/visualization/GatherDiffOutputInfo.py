import json
from os import listdir, makedirs
from os.path import join


class GatherDiffOutputInfo():
    def __init__(self, log_folder, version_id):
        '''
        Return a list of different or the same information that contains the coverage from Testora or Our approach.
        Each element is a json string for a single PR. Format refer to the json string in function get_single_log_file_diff_output.
        '''
        self.log_folder = log_folder
        self.version_id = version_id
        self.all_from_cur_version = [] # to return

        self.approach_name = "Testora"
        if version_id != "1_0_1":
            self.approach_name = "Our Approach"

    def get_single_log_file_diff_output(self, log_file):
        self.log_file_level_diff_output_info = []
        with open(log_file, "r") as f:
            info = json.load(f)

        pr_num = info[1]["pr_nb"]
        project_name = info[1]["url"].split("/")[-3]
        for info_block in info:
            if "old_output" in info_block.keys():
                info_block_msg = info_block["message"]
                if info_block_msg.startswith("Different outputs\nCovered lines in old"):
                    tmp = info_block_msg.split("Covered lines in old: ")[1]
                    old_covered_info, new_covered_info = tmp.split(", Covered lines in new: ")
                    test_example_name = info_block["test_code"].split(":", 1)[0]
                    if "\n" in test_example_name:
                        test_example_name = test_example_name.rsplit("\n", 1)[1]
                    test_level_block = {
                        "test_example_name": test_example_name,
                        "covered_lines_in_old": old_covered_info,
                        "covered_lines_in_new": new_covered_info,
                    }
                    self.log_file_level_diff_output_info.append(test_level_block)
        
        json_str = {
            "Approach": self.approach_name,
            "Version": self.version_id,
            "Project": project_name,
            pr_num: self.log_file_level_diff_output_info
        }
         
        self.all_from_cur_version.append(json_str)
        
    def get_multiple_pr_output_info(self):
        log_files = listdir(self.log_folder)
        for log_file in log_files:
            self.get_single_log_file_diff_output(join(self.log_folder, log_file))

        self.all_from_cur_version = sorted(self.all_from_cur_version, key=lambda d: list(d.keys())[3])
        return self.all_from_cur_version


if __name__=="__main__":
    version_id = "1_1_1"
    iteration = 2
    output_folder = join("data", "results")
    dtg_log_folder = join(output_folder, f"logs_iter{iteration}", f"log_{version_id}")
    table_output_folder = join(output_folder, "table_and_plots", f"meta_iter{iteration}")
    makedirs(table_output_folder, exist_ok=True)
    init = GatherDiffOutputInfo(dtg_log_folder, version_id)
    all_from_cur_version = init.get_multiple_pr_output_info()
    meta_file = join(table_output_folder, f"diff_output_meta_{version_id}.json")
    with open(meta_file, "w") as f:
        json.dump(all_from_cur_version, f, indent=4, ensure_ascii=False)   
    print(f"All the extracted different output information is written to {meta_file}")  

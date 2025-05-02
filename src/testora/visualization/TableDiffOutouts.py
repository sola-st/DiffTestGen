import json
from os import listdir, makedirs
from os.path import join, isdir
from testora.visualization.GatherDiffOutputInfo import GatherDiffOutputInfo


def from_test_name_to_round_num(test_name: str):
    return int(test_name.split(" Example")[0].rsplit(" ", 1)[1])

def get_max_round_and_detailed_distribution(grouped_data):
    max_round_list = [] # a max num for a pr
    distribution_list = []
    for pr_rec_cross_approaches in grouped_data:
        round_max = 0
        pr_num = None
        distribution_list_row_level = []
        for pr_rec in pr_rec_cross_approaches:
            distribution_str = {}
            if not pr_num:
                pr_num = list(pr_rec.keys())[-1]
                distribution_str.update({pr_num: {}})
            
            if pr_rec[pr_num]:
                # to know which rounds expose the different output in current approach
                test_example_name = pr_rec[pr_num][-1]["test_example_name"] # the test from the highest round number.
                feedback_round_num = from_test_name_to_round_num(test_example_name)
                round_max = max(round_max, feedback_round_num)

                # get detailed distribution
                for example in pr_rec[pr_num]:
                    round_num = from_test_name_to_round_num(example["test_example_name"])
                    if round_num not in distribution_str[pr_num].keys():
                        distribution_str[pr_num].update({round_num: 1})
                    else:
                        distribution_str[pr_num][round_num] += 1
            distribution_list_row_level.append(distribution_str)

        max_round_list.append(round_max)
        distribution_list.append(distribution_list_row_level)

    return max_round_list, distribution_list

def table_differences(all_data, all_version_id, caption, label, tex_file):
    approaches_num = len(all_data)
    latex_table = "\\begin{table*}[t]\n\\centering\n\\footnotesize\n"
    latex_table += "\\caption{" + caption + "}\n"
    latex_table += "\\label{tab:" + label + "}\n"
    latex_table += "\\begin{tabular}{@{}" + "lll" + "".join(["r|"] * approaches_num) + "rr@{}}\n"
    latex_table += "\\toprule\n"

    # prepare the head line of the table
    head_line = "ID & Project & PR & \multicolumn{2}{c}{Rounds} & {Testora}"
    for version_id in all_version_id[1:]:
        # the first is Testora, and the remaining are all our test genration approach
        head_line += " & Our Approach " + version_id.replace("_", "\_")
    
    latex_table += head_line + "\\\\" + "\n" 
    latex_table += "\\cmidrule{4-" + str(3 + (approaches_num+1)) +"}\n" 

    # a template for every start point of a pr, designed for fitting to dynamic number of feedback rounds
    # add only once when a pr block starts
    pr_block_start_line_prefix = (
        "\\multirow[t]{{{round_max_num}}}{{*}}{{{id}}} & "
        "\\multirow[t]{{{round_max_num}}}{{*}}{{{project}}} & "
        "\\multirow[t]{{{round_max_num}}}{{*}}{{{pr_num}}} & "
        "Initial & R-0"
    )

    pr_block_feedback_start_line_prefix = "& & & \multirow[t]{{{round_max}}}{{*}}{{Feedback}} & R-1 "
    
    grouped = list(zip(*all_data))
    max_round_list, distribution_list = get_max_round_and_detailed_distribution(grouped)

    pr_idx = 0
    for pr_rec_cross_approaches, round_max, row_level_distri in zip(grouped, max_round_list, distribution_list):
        if round_max == 0: # no differences exposed
            continue
        
        pr_idx += 1
        # A PR block contains the following three parts 
        pr_block_follow_lines = [""] * (round_max+1)

        for col_idx, (pr_rec, distribution) in enumerate(zip(pr_rec_cross_approaches, row_level_distri)):
            if col_idx == 0:# get these info only once.
                project = pr_rec["Project"]
                pr_num = list(pr_rec.keys())[-1]
                
                formatted_pr_block_start_line_prefix = pr_block_start_line_prefix.format(
                    round_max_num=round_max,
                    id=pr_idx,
                    project=project,
                    pr_num=pr_num
                )
                formatted_pr_block_feedback_start_line_prefix = pr_block_feedback_start_line_prefix.format(round_max=round_max)

            # add the number of test that expose the differences from current approach and version
            for tmp_round in range(0, round_max+1):
                if tmp_round in distribution[pr_num].keys():
                    pr_block_follow_lines[tmp_round] += f" & {distribution[pr_num][tmp_round]}"
                else:
                    pr_block_follow_lines[tmp_round] += " & -- "

            if col_idx + 1 == approaches_num:
                # add an ending for all the lines in the pr block, and add thepr block to the table
                latex_table += formatted_pr_block_start_line_prefix + pr_block_follow_lines[0] + " \\\\" + "\n"
                for line_idx, line in enumerate(pr_block_follow_lines[1:]):
                    if line_idx == 0:
                        latex_table += formatted_pr_block_feedback_start_line_prefix + line + " \\\\" + "\n"
                    else:
                        latex_table += "& & & & R-" + str(line_idx+1) + line + " \\\\" + "\n"
                latex_table += "\\midrule" + "\n"

    latex_table += "\\end{tabular}\n"
    latex_table += "\\end{table*}"

    with open(tex_file, "w") as f:
        f.write(latex_table.replace("%", "\%") + "\n")
    print(f"The occurrences table is wriitten to {tex_file}")

def main():
    iteration = 2
    all_data = []
    all_version_id = []
    results_folder = join("data", "results")
    log_folder_parent = join(results_folder, f"logs_iter{iteration}")
    table_output_folder = join(results_folder, "table_and_plots", f"meta_iter{iteration}")
    makedirs(table_output_folder, exist_ok=True)

    all_log_folder = [join(log_folder_parent, folder) for folder in listdir(log_folder_parent)\
            if isdir(join(log_folder_parent, folder)) and folder.startswith("log_")]
    all_log_folder = sorted(all_log_folder)
    for log_folder in all_log_folder:
        version_id = log_folder.rsplit("log_", 1)[1]
        init = GatherDiffOutputInfo(log_folder, version_id)
        all_from_cur_version = init.get_multiple_pr_output_info()
        # write a meta file for a version
        meta_file = join(table_output_folder, f"diff_output_meta_{version_id}.json")
        with open(meta_file, "w") as f:
            json.dump(all_from_cur_version, f, indent=4, ensure_ascii=False)   
        print(f"All the extracted different output information is written to {meta_file}")  
        all_data.append(all_from_cur_version)
        all_version_id.append(version_id)

    # generate the table
    caption = " The Timing and Occurrences of Different Outputs from Testora and Our Approach"
    label="different_outputs"
    tex_file = join(table_output_folder, "different_ccurrences.tex")
    table_differences(all_data, all_version_id, caption, label, tex_file)


if __name__=="__main__":
    main()


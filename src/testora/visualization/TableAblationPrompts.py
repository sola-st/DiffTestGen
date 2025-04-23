import json
from os import listdir, makedirs
from os.path import join, isdir
from testora.visualization.CoverageComparison import CoverageComparison


def get_feedback_round_max_num(grouped_data):
    feedback_round_max_list = [] # a max num for a pr
    for pr_rec_cross_approaches in grouped_data:
        feedback_round_max = 0
        pr_num = None
        for col_idx, pr_rec in enumerate(pr_rec_cross_approaches):
            if not pr_num:
                pr_num = list(pr_rec.keys())[-1]
            
            if "Feedback" in pr_rec[pr_num].keys(): 
                # to know how many feedback rounds in current approach
                feedback_round_num = len(pr_rec[pr_num]["Feedback"].keys())
                feedback_round_max = max(feedback_round_max, feedback_round_num)

        feedback_round_max_list.append(feedback_round_max)

    return feedback_round_max_list


def table_coverages(all_data, all_version_id, caption, label, tex_file):
    approaches_num = len(all_data)
    latex_table = "\\begin{table*}[t]\n\\centering\n\\footnotesize\n"
    latex_table += "\\caption{" + caption + "}\n"
    latex_table += "\\label{tab:" + label + "}\n"
    latex_table += "\\begin{tabular}{@{}" + "lll" + "".join(["rr|"] * approaches_num) + "rr@{}}\n"
    latex_table += "\\toprule\n"

    # prepare the head line of the table
    head_line = "ID & Project & PR & \multicolumn{2}{c}{Rounds} & \multicolumn{2}{c}{Testora}"
    for version_id in all_version_id[1:]:
        # the first is Testora, and the remaining are all our test genration approach
        head_line += " & \multicolumn{2}{c}{Our Approach " + version_id.replace("_", "\_") + "}"
    
    latex_table += head_line + "\\\\" + "\n" 
    latex_table += "\\cmidrule{4-" + str(3 + (approaches_num+1) * 2) +"}\n" 
    latex_table += "& & & & " + " ".join(["& Old & New"] * approaches_num) + "\\\\" + "\n" 

    # a template for every start point of a pr, designed for fitting to dynamic number of feedback rounds
    # add only once when a pr block starts
    pr_block_start_line_prefix = (
        "\\multirow[t]{{{initial_and_feedback_round_max_num}}}{{*}}{{{id}}} & "
        "\\multirow[t]{{{initial_and_feedback_round_max_num}}}{{*}}{{{project}}} & "
        "\\multirow[t]{{{initial_and_feedback_round_max_num}}}{{*}}{{{pr_num}}} & "
        "Initial Round & R-0"
    )

    pr_block_feedback_start_line_prefix = "& & & \multirow[t]{{{feedback_round_max}}}{{*}}{{Feedback Round}} & R-1 & -- & -- "
    
    grouped = list(zip(*all_data))
    feedback_round_max_list = get_feedback_round_max_num(grouped)

    for pr_idx, (pr_rec_cross_approaches, feedback_round_max) in enumerate(zip(grouped, feedback_round_max_list)):
        # A PR block contains the following three parts 
        formatted_pr_block_start_line_postfix = ""
        pr_block_follow_lines = [""] * (feedback_round_max)

        for col_idx, pr_rec in enumerate(pr_rec_cross_approaches):
            if col_idx == 0:# get these info only once.
                # the order of projects and prs should be the same, because the coverage info are sorted.
                project = pr_rec["Project"]
                pr_num = list(pr_rec.keys())[-1]
                
                formatted_pr_block_start_line_prefix = pr_block_start_line_prefix.format(
                    initial_and_feedback_round_max_num=feedback_round_max+1,
                    id=pr_idx+1,
                    project=project,
                    pr_num=pr_num
                )
                formatted_pr_block_feedback_start_line_prefix = pr_block_feedback_start_line_prefix.format(feedback_round_max=feedback_round_max)
            pr_info = pr_rec[pr_num]

            # Initial: add the coverage info from current approach and version
            formatted_pr_block_start_line_postfix += " & " + str(pr_info["Initial"]["R-0"]["old"]) + " & " + str(pr_info["Initial"]["R-0"]["new"])
            
            # Feedback: add info from feedback rounds
            idx = 0
            if "Feedback" in pr_info.keys(): # all the versions exclude
                for round, info in pr_info["Feedback"].items():
                    # for every round, add covergae info, leave empty (so far marked as "--" for None coverage info)
                    idx = int(round.split("-")[1]) - 1 # -1 to start at 0
                    pr_block_follow_lines[idx] += "&" + info["old"] + "&" + info["new"]

            for empty_round in range(idx + 1, feedback_round_max):
                # add emptpy values if the current approach has < max round
                pr_block_follow_lines[empty_round] += " & -- & -- "

            if col_idx + 1 == approaches_num:
                # add an ending for all the lines in the pr block, and add thepr block to the table
                latex_table += formatted_pr_block_start_line_prefix + formatted_pr_block_start_line_postfix + " \\\\" + "\n"
                for line_idx, line in enumerate(pr_block_follow_lines):
                    if line_idx == 0:
                        latex_table += formatted_pr_block_feedback_start_line_prefix + line + " \\\\" + "\n"
                    else:
                        latex_table += "& & & & R-" + str(line_idx+1) + line + " \\\\" + "\n"
                latex_table += "\\midrule" + "\n"

    latex_table += "\\end{tabular}\n"
    latex_table += "\\end{table*}"

    with open(tex_file, "w") as f:
        f.write(latex_table.replace("%", "\%") + "\n")
    print(f"The comparison table is wriitten to {tex_file}")

def main():
    all_data = []
    all_version_id = []
    log_folder_parent = "local"

    output_folder = join("data", "results")
    table_output_folder = join(output_folder, "table_and_plots")
    makedirs(table_output_folder, exist_ok=True)

    all_log_folder = [join(log_folder_parent, folder) for folder in listdir(log_folder_parent)\
            if isdir(join(log_folder_parent, folder)) and folder.startswith("log_")]
    all_log_folder = sorted(all_log_folder)
    for log_folder in all_log_folder:
        version_id = log_folder.rsplit("log_", 1)[1]
        init = CoverageComparison(log_folder, version_id)
        all_from_cur_version = init.get_multiple_pr_coverage_info()
        # write a meta file for a version
        meta_file = join(table_output_folder, f"coverage_comparison_meta_{version_id}.json")
        with open(meta_file, "w") as f:
            json.dump(all_from_cur_version, f, indent=4, ensure_ascii=False)   
        print(f"Collected coverage information is written to {meta_file}")

        all_data.append(all_from_cur_version)
        all_version_id.append(version_id)

    # generate the table
    caption = "Coverage Comparison between Testora and Our Approach"
    label="coverage_comparison"
    tex_file = join(table_output_folder, "coverage_comparison.tex")
    table_coverages(all_data, all_version_id, caption, label, tex_file)


if __name__=="__main__":
    main()


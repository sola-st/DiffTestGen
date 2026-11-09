from os.path import exists, join
import json
import os
import matplotlib.pyplot as plt
import numpy as np


class DifferentOutputsStatistics():
    def __init__(self):
        self.overall_diff_related_pr = 0
        self.overall_diff_related_pr_nums = {}
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

        self.pr_tracking = {}

    def clear_overall(self):
        self.overall_diff_related_pr = 0
        self.overall_diff_related_pr_nums = {}
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

    def _extract_pr_title(self, info):
        for info_block in info:
            if isinstance(info_block, dict):
                message = info_block.get("message")
                title = info_block.get("title")
                if message and message.startswith("Starting to check PR") and title:
                    return str(title).strip()
        return "unknown title"

    def _format_summary_table_headers(self, project_names, include_version=False):
        group_count = len(project_names) + 1
        col_format = ("l|" if include_version else "") + "|".join(["rrr"] * group_count) 

        header1_cells = [f"\\multicolumn{{3}}{{c|}}{{{project}}}" for project in project_names]
        header1_cells.append("\\multicolumn{3}{c}{Total}")
        header1 = (" & " if include_version else "") + " & ".join(header1_cells) + " \\\\"

        header2_cells = ["\\multirow{2}{*}{\\makecell{Avg.\\\\Uni. cov}}", "\\multicolumn{2}{c|}{Differ. Outputs}"] * (group_count - 1)
        header2_cells.append("\\multirow{2}{*}{\\makecell{Avg.\\\\Uni. cov}}")
        header2_cells.append("\\multicolumn{2}{c}{Differ. Outputs}")
        header2 = ("" if not include_version else "" ) + " & ".join(([""] if include_version else []) + header2_cells) + " \\\\"
        break_line = "\\cmidrule(lr){" + "}\\cmidrule(lr){".join(f"{i*3}-{i*3 + 1}" for i in range(1, group_count + 1)) + "}"

        header3_cells = ["", "PRs", "Tests"] * group_count
        header3 = ("" if not include_version else "" ) + " & ".join(([""] if include_version else []) + header3_cells) + " \\\\"

        return header1, header2, break_line, header3, col_format

    def _format_all_versions_summary_table_latex(self, versions_summary, project_names):
        header1, header2, break_line, header3, col_format = self._format_summary_table_headers(project_names, include_version=True)

        rows = []
        for version_data in versions_summary:
            row = [version_data["version"]]
            for project in project_names:
                proj_data = next((item for item in version_data["project_data"] if item["project"] == project), None)
                row.extend([
                    "",
                    str(proj_data["project_diff_related_pr_num"]),
                    str(proj_data["project_different_outputs"])
                ])
            row.extend([
                "",
                str(version_data["total"]["overall_diff_related_pr_num"]),
                str(version_data["total"]["overall_different_outputs"])
            ])
            rows.append(" & ".join(row) + " \\\\\n")

        table_lines = [
            "\\begin{table*}[ht]",
            "\\centering",
            "\\caption{Different outputs summary for all versions}",
            "\\label{tab:diff_outputs_summary_all_versions}",
            "\\setlength{\\tabcolsep}{3pt}",
            f"\\begin{{tabular}}{{{col_format}}}",
            "\\hline",
            header1,
            "\\hline",
            header2,
            break_line,
            header3,
            "\\hline",
        ]
        table_lines.extend(rows)
        table_lines.extend([
            "\\hline",
            "\\end{tabular}",
            "\\end{table*}",
        ])
        return "\n".join(table_lines)

    def _write_all_versions_summary_table_file(self, output_folder, versions_summary, project_names):
        latex_file = join(output_folder, "all_versions_summary_table.tex")
        with open(latex_file, "w") as f:
            f.write(self._format_all_versions_summary_table_latex(versions_summary, project_names))

    def _generate_bar_plots(self, output_folder, versions_summary, project_names):
        # Define metrics to plot
        metrics = [
            ('project_diff_related_pr_num', 'Number of PRs with\nbehavioral differences'),
            ('project_different_outputs', 'Number of Different\nOutput Related Tests')
        ]
        colors = ["#4F8A8B", "#01A9B4", "#EA907A", "#FFCB74", "#E36387"]
        plt.rcParams.update({'font.size': 11})
        
        for metric_key, metric_label in metrics:
            fig, ax = plt.subplots(figsize=(10, 2.4))
            num_versions = len(versions_summary)
            width = 0.2  # width of each bar
            group_width = width * num_versions
            gap = 0.3 # gap between groups
            step = group_width + gap

            # x positions for each group (projects + overall)
            x = np.arange(len(project_names) + 1) * step

            # offsets for each version within a group, centered around group x
            offsets = (np.arange(num_versions) - (num_versions - 1) / 2.0) * width

            for i, version_data in enumerate(versions_summary):
                values = []
                # Get values for each project
                for project in project_names:
                    proj_data = next((item for item in version_data["project_data"] if item["project"] == project), None)
                    values.append(proj_data[metric_key] if proj_data else 0)
                
                # Add overall value
                overall_key = metric_key.replace("project_", "overall_")
                values.append(version_data["total"][overall_key])
                
                # Plot bars with offset for grouping
                bars = ax.bar(x + offsets[i], values, width, label=version_data["version"], color=colors[i])
                
                # Add value labels on top of bars
                for bar in bars:
                    height = bar.get_height()
                    if height > 0:  # Only show label if value > 0
                        ax.text(bar.get_x() + bar.get_width() / 2., height - 1,
                               f'{int(height)}',
                               ha='center', va='top', fontsize=10)
                    # if height > 0:
                    #     ax.annotate(
                    #         f'{int(height)}',
                    #         xy=(bar.get_x() + bar.get_width() / 2, height),
                    #         xytext=(0, -4),          # 4 points below the top
                    #         textcoords='offset points',
                    #         ha='center',
                    #         va='top',
                    #         fontsize=10
                    #     )
            
            # Customize plot
            ax.set_ylabel(metric_label)
            ax.set_xticks(x)
            ax.set_xticklabels(list(project_names) + ['Overall'])
            ax.legend(fontsize=10)
            ax.grid(axis='y', alpha=0.3)
            
            # Save figure
            plot_file = join(output_folder, f"{metric_key}_comparison.pdf")
            plt.tight_layout()
            plt.savefig(plot_file, dpi=300, bbox_inches='tight')
            plt.close()
            
            print(f"Saved plot: {plot_file}")

    def analyze_single_pr(self, info, target_project, pr, version_name):
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
                    if msg.startswith("Coverage feedback ends") or msg.startswith("Refinement ends"):
                        try:
                            max_rounds = int(msg.split("Coverage feedback ends after round ", 1)[1].split(",", 1)[0])
                        except:
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

                    if "# Round " in test_name:
                        round_num = int(test_name.split("# Round ", 1)[1].split(" ", 1)[0])
                        try:
                            from_rounds[round_num] += 1
                        except IndexError:
                            from_uncertain_round += 1
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
                "from_uncertain_round": from_uncertain_round
            }
        }

        for idx, num in enumerate(from_rounds):
            single_pr_json["details"].update({f"from_round_{idx}": num})

        if diff_nb > 0:
            # update overall 
            self.overall_diff_related_pr += 1
            self.overall_diff_related_pr_nums[target_project].add(pr)
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

            # update pr_tracking
            if version_name in self.pr_tracking:
                self.pr_tracking[version_name][target_project].add(pr)

        return single_pr_json


    def main(self):
        results_folder = join("data", "results")
        iteration_max = 3
        # model_version = "gpt-4o-mini-2024-07-18"
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

        for iteration in range(1, iteration_max):
            output_folder = join(results_folder, "table_and_plots", "different_outputs_statistics", f"iter_{iteration}", "differ_outputs_meta")
            os.makedirs(output_folder, exist_ok=True)

            self.pr_tracking = {
                "testora": {project: set() for project in project_info.keys()},
                "testora_pp": {project: set() for project in project_info.keys()},
                "difftestgen": {project: set() for project in project_info.keys()}
            }
            no_different_outputs_prs = {
                "testora": {},
                "testora_pp": {},
                "difftestgen": {}
            }

            versions_summary = []
            for version_name, approach_name in zip(config_names, approach_names):
                project_level = []
                single_iteration = []

                for target_project, num in project_info.items():
                    self.overall_diff_related_pr_nums.update({target_project: set()})

                    log_folder = join(results_folder, model_version, f"iter_{iteration}", f"log_{version_name}", target_project)
                    if subset_mode == True:
                        log_folder = join(results_folder, model_version, f"iter_{iteration}_subset", f"log_{version_name}", target_project)
                    
                    pr_file = join("data", "meta", "pr_nums_checks", f"{target_project}_PRs_subset{num}.txt")
                    if subset_mode == True:
                        pr_file = join("data", "meta", f"subset_{target_project}.txt")

                    with open(pr_file, "r") as f:
                        prs = f.readlines()
                    pr_list = [int(pr) for pr in prs]
                    
                    for pr in pr_list:
                        log_file_path = None
                        for fname in os.listdir(log_folder):
                            if str(pr) in fname:
                                log_file_path = join(log_folder, fname)
                                break
                        if log_file_path is None:
                            print(f"Iteration {iteration}: No log file found for PR {pr} in {log_folder}")
                            single_iteration.append({"pr_num": pr}) 
                        else:
                            try:
                                with open(log_file_path, "r") as f:
                                    info = json.load(f)
                                single_pr_json = self.analyze_single_pr(info, target_project, pr, version_name)
                                single_pr_json["project"] = target_project
                                single_pr_json["pr_num"] = pr
                                if single_pr_json["different_outputs"] == 0 and version_name in no_different_outputs_prs:
                                    pr_title = self._extract_pr_title(info)
                                    no_different_outputs_prs[version_name][pr] = pr_title
                                single_iteration.append(single_pr_json)
                            except json.JSONDecodeError:
                                print(f"Iteration {iteration}: Error reading log file for PR {pr} in {log_folder}")
                                continue

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
                            "project_from_uncertain_round": self.project_from_uncertain_round
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
                        "overall_from_uncertain_round": self.overall_from_uncertain_round
                    },
                    "related_prs": f"{self.overall_diff_related_pr_nums}"
                }

                # Add keys for unique PRs at overall level
                if version_name == "difftestgen":
                    unique_in_difftestgen = {}
                    for project in project_info.keys():
                        project_prs = self.pr_tracking["difftestgen"][project] - (self.pr_tracking["testora"][project] | self.pr_tracking["testora_pp"][project])
                        if project_prs:
                            unique_in_difftestgen[project] = sorted(list(project_prs))
                    if unique_in_difftestgen:
                        overall_str["only_in_difftestgen"] = f"{unique_in_difftestgen}"
                        total_count = sum(len(v) for v in unique_in_difftestgen.values())
                        print(f"Overall add {total_count} uniques to difftestgen.")
                    else:
                        print("No unique PRs in DiffTestGen.")

                    for v_name in ["testora", "testora_pp"]:
                        unique_in_version = {}
                        for project in project_info.keys():
                            project_prs = self.pr_tracking[v_name][project] - self.pr_tracking["difftestgen"][project]
                            if project_prs:
                                unique_in_version[project] = sorted(list(project_prs))
                        if unique_in_version:
                            key_name = f"in_{v_name}_not_dtg"
                            overall_str[key_name] = f"{unique_in_version}"
                            total_count = sum(len(v) for v in unique_in_version.values())
                            print(f"Overall add {total_count} uniques to {v_name}.")
                        else:
                            print(f"No unique PRs in {v_name}.")

                for idx, num in enumerate(self.overall_from_rounds):
                    overall_str["details"].update({f"overall_from_round_{idx}": num})

                to_write = [overall_str] + project_level + single_iteration
                result_file = join(output_folder, f"{version_name}.json")
                with open(result_file, "w") as f:
                    json.dump(to_write, f, indent=4)

                if version_name in no_different_outputs_prs:
                    no_diff_output_file = join(output_folder, f"{version_name}_no_different_outputs_prs.txt")
                    with open(no_diff_output_file, "w", encoding="utf-8") as f:
                        for pr_num in sorted(no_different_outputs_prs[version_name].keys()):
                            f.write(f"{pr_num}: {no_different_outputs_prs[version_name][pr_num]}\n")

                versions_summary.append({
                    "version": approach_name,
                    "project_data": [
                        {
                            "project": data["project"],
                            "project_diff_related_pr_num": data["project_diff_related_pr_num"],
                            "project_different_outputs": data["project_different_outputs"]
                        }
                        for data in project_level
                    ],
                    "total": {
                        "overall_diff_related_pr_num": overall_str["overall_diff_related_pr_num"],
                        "overall_different_outputs": overall_str["overall_different_outputs"]
                    }
                })

                self.clear_overall()

            common_no_diff_prs = {}
            if all(no_different_outputs_prs[version] for version in ["testora", "testora_pp", "difftestgen"]):
                common_pr_numbers = (
                    set(no_different_outputs_prs["testora"].keys())
                    & set(no_different_outputs_prs["testora_pp"].keys())
                    & set(no_different_outputs_prs["difftestgen"].keys())
                )
                for pr_num in sorted(common_pr_numbers):
                    common_no_diff_prs[pr_num] = (
                        no_different_outputs_prs["testora"].get(pr_num)
                        or no_different_outputs_prs["testora_pp"].get(pr_num)
                        or no_different_outputs_prs["difftestgen"].get(pr_num)
                    )

            combined_no_diff_output_file = join(output_folder, "all_three_approaches_no_different_outputs_prs.txt")
            with open(combined_no_diff_output_file, "w", encoding="utf-8") as f:
                for pr_num in sorted(common_no_diff_prs.keys()):
                    f.write(f"{pr_num}: {common_no_diff_prs[pr_num]}\n")

            self._write_all_versions_summary_table_file(output_folder, versions_summary, list(project_info.keys()))
            self._generate_bar_plots(output_folder, versions_summary, list(project_info.keys()))
            
            # clear before next iteration
            self.pr_tracking = {
                "testora": {},
                "testora_pp": {},
                "difftestgen": {}
            }


if __name__=="__main__":
    DifferentOutputsStatistics().main()
import json
from os import makedirs
from os.path import join, exists
from testora.visualization.CoverageComparison import CoverageComparison
from testora.visualization.PlotCoverageAblation import get_overall_coverage_rates, plot_coverages_violin


def get_average_new_coverage(pr_records):
    """Return the mean new coverage percentage across all PRs."""
    new_rates = []

    for pr_rec in pr_records:
        pr_num = list(pr_rec.keys())[-1]
        if "Feedback" in pr_rec[pr_num].keys() and "--" not in json.dumps(pr_rec[pr_num]["Feedback"]["R-1"]):
            feedback_rec = pr_rec[pr_num]["Feedback"]
            key_idx = -1
            last_round_key = list(feedback_rec.keys())[key_idx]
            last_round_cov_pair_dict = feedback_rec[last_round_key]
            while "--" in json.dumps(last_round_cov_pair_dict):
                key_idx -= 1
                last_round_key = list(feedback_rec.keys())[key_idx]
                last_round_cov_pair_dict = feedback_rec[last_round_key]
        else:
            last_round_cov_pair_dict = pr_rec[pr_num]["Initial"]["R-0"]

        new_cov = last_round_cov_pair_dict.get("new", "--")
        if new_cov != "--":
            new_rates.append(float(new_cov.strip().split("%")[0]))

    return sum(new_rates) / len(new_rates) if new_rates else 0.0


def main():
    iteration = 0
    approach = "chaco" # "dtg" or "chaco" 
    model_versions = []
    if approach == "dtg":
        model_versions = ["gpt-4o-mini-2024-07-18", "gpt-5-mini-2025-08-07"]
    else:
        model_versions = ["gpt-4o-mini-2024-07-18"] 
    
    target_projects = ["scipy", "pandas"]
    name = "difftestgen"
    axis_names = ["DiffTestGen"]
    results_folder = join("data", "results")

    for model_version in model_versions:
        output_folder = join(results_folder, "table_and_plots", "coverage_meta_info", f"iter_{iteration}", "chaco", model_version)
        makedirs(output_folder, exist_ok=True)

        across_projects = []
        for i, project in enumerate(target_projects):
            all_data = []
            if approach == "dtg":
                log_folder = join(results_folder, model_version, f"iter_{iteration}", f"log_chaco_{name}", project)
            else:
                log_folder = join(results_folder, "ori_chaco_execution", project)
            
            meta_file = join(output_folder, f"{approach}_{project}_coverage_meta.json")
            all_from_cur_version = []
            if exists(meta_file):
                print(f"Meta file {meta_file} already exists. Skipping processing for {name} on {project}.")
                with open(meta_file, "r") as f:
                    all_from_cur_version = json.load(f)
            else:
                init = CoverageComparison(log_folder, name)
                all_from_cur_version = init.get_multiple_pr_coverage_info(project)
                # write a meta file for a version
                with open(meta_file, "w") as f:
                    json.dump(all_from_cur_version, f, indent=4, ensure_ascii=False)   
                print(f"Collected coverage information is written to {meta_file}, relevant pr num: {len(all_from_cur_version)}")

            all_data.append(all_from_cur_version)

            # avg_new_cov = get_average_new_coverage(all_from_cur_version)
            # print(f"Average new coverage for project {project} ({approach}): {avg_new_cov:.3f}% over {len(all_from_cur_version)} PRs")

            overall_data = get_overall_coverage_rates(all_data)
            result_pdf = join(output_folder, f"{approach}_coverage_comparison_ablation_{project}.pdf") 
            plot_coverages_violin(overall_data, axis_names, result_pdf)

            if i == 0:
                across_projects.extend(all_data)
            else:
                for j, approach_data in enumerate(all_data):
                    across_projects[j].extend(approach_data)

        # for the plot
        overall_data = get_overall_coverage_rates(across_projects)
        result_pdf = join(output_folder, f"{approach}_coverage_comparison_ablation.pdf") 
        plot_coverages_violin(overall_data, axis_names, result_pdf)


if __name__=="__main__":
    main()

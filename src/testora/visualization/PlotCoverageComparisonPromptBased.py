import json
from os import listdir, makedirs
from os.path import join, isdir
import numpy as np
from scipy.stats import gmean
from matplotlib import pyplot as plt
from matplotlib.lines import Line2D
from testora.visualization.CoverageComparison import CoverageComparison
from testora.visualization.CoverageUtils import get_overall_cov_rate


def get_overall_coverage_rates(all_data):
    overall_data = [] # element is approach level

    for approach_data in all_data: # single approach data
        pr_level_rates = []
        for pr_rec in approach_data:
            # for every PR, get an aggregated coverage rate.
            pr_num = list(pr_rec.keys())[-1]
            last_round_cov_pair_dict = {}

            if "Feedback" in pr_rec[pr_num].keys() and \
                    "--" not in json.dumps(pr_rec[pr_num]["Feedback"]["R-1"]):
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
            
            # the highest coverage for a pr, a pr a rate.
            union_old_new_cov_str = get_overall_cov_rate(last_round_cov_pair_dict)
            pr_level_rates.append(union_old_new_cov_str)

        overall_data.append(pr_level_rates)
    
    return overall_data
            

def plot_coverages_violin(overall_data, all_version_id, title, result_pdf):
    # Convert percentage strings to floats
    cleaned_data = [
        [float(cov.strip('%')) for cov in pr_level_rates]
        for pr_level_rates in overall_data
    ]

    # violin plot
    fig, ax = plt.subplots()
    # ax.violinplot(cleaned_data, showmeans=True) # default: arithmetic mean
    ax.violinplot(cleaned_data, showmeans=False)  # Turn off default mean

    # arithmetic means
    arith_means = [np.mean(group) for group in cleaned_data]
    ax.scatter(
        range(1, len(arith_means) + 1),
        arith_means,
        color='blue',
        marker='x',
        label='Arithmetic Mean',
        zorder=3
    )

    # geometric means
    geom_means = [gmean(group) for group in cleaned_data]
    ax.scatter(
        range(1, len(geom_means) + 1),  # x positions
        geom_means,                     # y values (geometric means)
        color='orange',
        marker='o',
        label='Geometric Mean',
        zorder=3
    )

    # Label the x-axis
    ax.set_xticks(range(1, len(all_version_id) + 1))
    ax.set_xticklabels(all_version_id)

    # Add labels and title
    ax.set_ylabel("Coverage (%)")
    ax.set_title(title)

    # Add legend
    legend_elements = [
        Line2D([0], [0], marker='x', color='blue', label='Arithmetic Mean', linestyle='None'),
        Line2D([0], [0], marker='o', color='orange', label='Geometric Mean', linestyle='None'),
    ]
    ax.legend(handles=legend_elements, loc='upper right')
    
    plt.grid(True)
    plt.savefig(result_pdf)


def main():
    iteration = 1
    target_projects = ["scipy", "marshmallow", "pandas", "keras"]

    results_folder = join("data", "results")
    across_projects = []
    for i, project in enumerate(target_projects):
        all_data = []
        all_version_id = []
        
        log_folder_parent = join(results_folder, project, f"logs_iter{iteration}")
        output_folder = join(results_folder, "table_and_plots", project, f"meta_iter{iteration}")
        makedirs(output_folder, exist_ok=True)

        all_log_folder = [join(log_folder_parent, folder) for folder in listdir(log_folder_parent)\
                if isdir(join(log_folder_parent, folder)) and folder.startswith("log_")]
        all_log_folder = sorted(all_log_folder)
        for log_folder in all_log_folder:
            version_id = log_folder.rsplit('log_', 1)[1]
            all_version_id.append(version_id)

            init = CoverageComparison(log_folder, version_id)
            all_from_cur_version = init.get_multiple_pr_coverage_info(project)
            # write a meta file for a version
            meta_file = join(output_folder, f"coverage_comparison_meta_{version_id}.json")
            with open(meta_file, "w") as f:
                json.dump(all_from_cur_version, f, indent=4, ensure_ascii=False)   
            print(f"Collected coverage information is written to {meta_file}")

            all_data.append(all_from_cur_version)

        if i == 0:
            across_projects.extend(all_data)
        else:
            for j, approach_data in enumerate(all_data):
                across_projects[j].extend(approach_data)

    # for the plot
    overall_data = get_overall_coverage_rates(across_projects)
    refined_ids = []
    for id in all_version_id:
        version_id = f"Prompt_{id.rsplit('_', 1)[1]}"
        if "1_0_1" in id:
            version_id = "Testora"
        refined_ids.append(version_id)
    
    result_pdf = join(results_folder, "table_and_plots", "Comparison_prompt_based.pdf") 
    title = "Coverage Comparison between Testora and Our Approach"
    plot_coverages_violin(overall_data, refined_ids, title, result_pdf)


if __name__=="__main__":
    main()

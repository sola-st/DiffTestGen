import json
from os import makedirs, listdir
from os.path import join
from matplotlib import pyplot as plt
from matplotlib.lines import Line2D
import numpy as np
from testora.visualization.CoverageComparison import CoverageComparison
from testora.visualization.CoverageUtils import get_feedback_round_max_num, get_overall_cov_rate


def reorganize_coverages(all_data_approach_level, feedback_round_max=0, base=False):
    # Both 1 and 2 are for all PRs across all projects
    initial_round_cov = [] # 1
    if (feedback_round_max == 0) and base == False:
        feedback_round_max = get_feedback_round_max_num(all_data_approach_level)
    feedback_rounds_cov = [[] for _ in range(feedback_round_max)] # 2

    for pr_rec in all_data_approach_level:
        pr_num = list(pr_rec.keys())[-1]
        pr_info = pr_rec[pr_num]

        # Initial
        round_cov_pair_dict = pr_info["Initial"]["R-0"]
        if "--" in json.dumps(round_cov_pair_dict):
            union_old_new_cov_str = "0.00%"
            print(f"Init--{pr_num}")
        else:
            union_old_new_cov_str = get_overall_cov_rate(round_cov_pair_dict)
        initial_round_cov.append(union_old_new_cov_str)
        
        # Feedback
        if "Feedback" in pr_info.keys():
            feedback_rounds = pr_info["Feedback"]
            i = 0
            for round_name, round_rec in feedback_rounds.items():
                if "--" in json.dumps(round_rec):
                    feedback_rounds_cov[i].append("0.00%")
                    print(f"Feedback--{pr_num}")
                else:
                    union_old_new_cov_str = get_overall_cov_rate(round_rec)
                    feedback_rounds_cov[i].append(union_old_new_cov_str)
                i += 1

            # add unchanged coverage to further rounds
            for j in range(i, feedback_round_max):
                feedback_rounds_cov[j].append(union_old_new_cov_str)
        else:
            if base == False:
                for j in range(0, feedback_round_max):
                    feedback_rounds_cov[j].append(union_old_new_cov_str)
    
    all_rounds_cov = [initial_round_cov]
    if feedback_rounds_cov: # not extend for Testora
        all_rounds_cov.extend(feedback_rounds_cov)
    return all_rounds_cov, feedback_round_max # max feedback round is 0 for Testora 
    
def plot_coverages_violin_deviation(cov_baseline, cov_our_approach, feedback_round_max, title, result_pdf):
    cleaned_data = [
        [float(cov.strip('%')) for cov in pr_level_rates]
        for pr_level_rates in (cov_baseline + cov_our_approach)
    ]

    violin_parts = plt.violinplot(cleaned_data, showmeans=False)

    # set different colors for baseline
    # plt.axvspan(0.5, 1.5, color='#F4F8D3', alpha=0.8)
    baseline_box = violin_parts["bodies"][0]
    baseline_box.set_facecolor("#8E7DBE")
    # baseline_box.set_edgecolor('black') 
    baseline_box.set_alpha(0.8) # transparency

    # arithmetic means
    arith_means = [np.mean(group) for group in cleaned_data]
    plt.plot(
        range(2, len(arith_means) + 1),
        arith_means[1:],
        color='blue',
        linestyle='--',
        linewidth=2,
        zorder=2
    )

    plt.scatter(
        range(1, len(arith_means) + 1),
        arith_means,
        color='blue',
        marker='x',
        label='Arithmetic Mean',
        zorder=3
    )

    for i, arith in enumerate(arith_means, start=1):
        # Arithmetic Mean label
        plt.text(i + 0.1, arith + 0.5, f"{arith:.3f}%", color='blue', fontsize=8)

    x_loc = range(0, feedback_round_max + 3)
    x_labels = ["", "Testora"] + list(range(0, feedback_round_max + 1))
    plt.xticks(x_loc, x_labels)

    # Modify x-axis labels: color 'Testora' label differently
    ax = plt.gca()  # Get current axis
    xticklabels = ax.get_xticklabels()  # Get the labels
    xticklabels[1].set_color("#7A73D1")  # Change color of the second label ('Testora')

    legend_elements = [
        Line2D([0], [0], marker='x', color='blue', label='Arithmetic Mean', linestyle='--', linewidth=2),
    ]
    plt.legend(handles=legend_elements, loc='lower right')

    plt.title(title)
    plt.xlabel("Test Generation Rounds")
    plt.ylabel("Coverage (%)")
    plt.grid(True)
    plt.savefig(result_pdf)

def main():
    iterations = 1
    # model_version = "gpt-4o-mini-2024-07-18"
    model_version = "gpt-5-mini-2025-08-07"
    config_versions = ["testora", "difftestgen", "only_coverage_feedback", "only_cg"]
    target_projects = ["marshmallow", "pandas", "scipy", "keras"]
    results_folder = join("data", "results")
    output_folder_base = join(results_folder, "table_and_plots", "coverage_meta_info")
    
    baseline_data = []
    our_approach_data = []
    feedback_round_max = 0
    for version_id in config_versions:
        all_data = [[] for _ in range(iterations)]
        for iter in range(iterations):
            for project in target_projects:
                output_folder = join(output_folder_base, f"log_{version_id}")
                log_folder = join(results_folder, model_version, f"iter_{iter}", f"log_{version_id}", project)
                makedirs(output_folder, exist_ok=True)
                
                if listdir(log_folder):
                    init = CoverageComparison(log_folder, version_id)
                
                    all_from_cur_version = init.get_multiple_pr_coverage_info(project)
                    
                    # # write a meta file for a version
                    # meta_file = join(output_folder, f"coverage_comparison_meta_{version_id}.json")
                    # with open(meta_file, "w") as f:
                    #     json.dump(all_from_cur_version, f, indent=4, ensure_ascii=False)   
                    # print(f"Collected coverage information is written to {meta_file}")

                    all_data[iter].extend(all_from_cur_version)
            
            feedback_round_max_single_iter = get_feedback_round_max_num(all_data[iter])
            if feedback_round_max_single_iter > feedback_round_max:
                feedback_round_max = feedback_round_max_single_iter

        for all_data_single_round in all_data:
            if version_id == "testora":
                baseline_data_iter, __ = reorganize_coverages(all_data_single_round, base=True)
                for k, round_cov in enumerate(baseline_data_iter):
                    try: 
                        baseline_data[k].extend(round_cov)
                    except:
                        baseline_data.append(round_cov)
            else:
                our_approach_data_iter, __ = reorganize_coverages(all_data_single_round, feedback_round_max)
                
                for k, round_cov in enumerate(our_approach_data_iter):
                    try: 
                        our_approach_data[k].extend(round_cov)
                    except:
                        our_approach_data.append(round_cov)

    # for the plot
    title = "Coverage Comparison between Testora and Our Approach"
    result_pdf = join(output_folder_base, f"Comparison_round_based_deviation_{version_id}_iter{iterations}.pdf") 
    plot_coverages_violin_deviation([baseline_data[0]], our_approach_data, feedback_round_max, title, result_pdf)


if __name__=="__main__":
    main()


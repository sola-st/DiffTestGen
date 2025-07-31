import json
from os import makedirs, listdir
from os.path import join
from matplotlib import pyplot as plt
from matplotlib.lines import Line2D
import numpy as np
from testora.visualization.CoverageComparison import CoverageComparison
from testora.visualization.CoverageUtils import get_feedback_round_max_num, get_overall_cov_rate


def reorganize_coverages(all_data_approach_level, base=False):
    # Both 1 and 2 are for all PRs across all projects
    initial_round_cov = [] # 1
    feedback_round_max = get_feedback_round_max_num(all_data_approach_level)
    feedback_rounds_cov = [[] for _ in range(feedback_round_max)] # 2

    for pr_rec in all_data_approach_level:
        pr_num = list(pr_rec.keys())[-1]
        pr_info = pr_rec[pr_num]

        # Initial
        round_cov_pair_dict = pr_info["Initial"]["R-0"]
        if "--" in json.dumps(round_cov_pair_dict):
            union_old_new_cov_str = "0.00%"
            print(f"IHUX_{pr_num}")
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
                    print(f"FHUX_{pr_num}")
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
    
def plot_coverages_violin_deviation(cov_baseline, cov_our_approach, feedback_round_max, iterations, title, result_pdf):
    cleaned_data = [
        [float(cov.strip('%')) for cov in pr_level_rates]
        for pr_level_rates in (cov_baseline + cov_our_approach)
    ]

    our_final_cov = cleaned_data[-1]
    sub_len = int(len(our_final_cov) / iterations)
    our_final_cov_with_sub = [our_final_cov[i:i+sub_len] for i in range(0, iterations)]
    groups = list(zip(*our_final_cov_with_sub))

    # Compute standard deviation for each group
    stds = [np.std(group) for group in groups]
    means = [np.mean(group) for group in groups]
    x = np.arange(1, len(stds) + 1)

    # Plot standard deviation as error bars
    plt.figure(figsize=(8, 5))
    plt.errorbar(x, means, yerr=stds, fmt='o', capsize=5, color='orange', label='Std Dev')
    plt.plot(x, means, color='blue', linestyle='--', marker='x', label='Mean')

    plt.title(title + ' (Std Dev)')
    plt.xlabel('Test Generation Rounds')
    plt.ylabel('Coverage (%)')
    plt.grid(True)
    plt.legend()
    labels = [str(i+1) for i in range(len(stds))]
    plt.xticks(x, labels)
    plt.tight_layout()
    plt.savefig(result_pdf.replace('.pdf', '_stddev.pdf'))
    plt.close()

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
    iterations = 5
    config_versions = [
        # [5, 5, 5, False],
        # [5, 8, 8, False],
        [5, 8, 8, True]
    ]
    
    for config in config_versions:
        target_version = '_'.join(map(str, config))
        prompt_versions = ["1_0_1_False", target_version] # 1_0_1 is Testora, and 2nd element indicates the version of our approach
        target_projects = ["marshmallow", "pandas", "scipy", "keras"]

        baseline_data = []
        our_approach_data = []
        feedback_round_max = 0
        
        results_folder = join("data", "results")
        for version_id in prompt_versions:
            for iter in range(iterations):
                all_data = [] # approach level
                for project in target_projects:
                    output_folder = join(results_folder, "table_and_plots", f"iter_{iter}", project)
                    log_folder = join(results_folder, f"iter_{iter}", f"log_{version_id}", project)
                    makedirs(output_folder, exist_ok=True)
                    
                    if listdir(log_folder):
                        init = CoverageComparison(log_folder, version_id)
                    
                        all_from_cur_version = init.get_multiple_pr_coverage_info(project)
                        # write a meta file for a version
                        meta_file = join(output_folder, f"coverage_comparison_meta_{version_id}.json")
                        with open(meta_file, "w") as f:
                            json.dump(all_from_cur_version, f, indent=4, ensure_ascii=False)   
                        print(f"Collected coverage information is written to {meta_file}")

                        all_data.extend(all_from_cur_version)

                if version_id == "1_0_1_False":
                    baseline_data_iter, __ = reorganize_coverages(all_data, base=True)
                    # baseline_data.extend(baseline_data_iter)
                    for k, round_cov in enumerate(baseline_data_iter):
                        try: 
                            baseline_data[k].extend(round_cov)
                        except:
                            baseline_data.append(round_cov)
                else:
                    our_approach_data_iter, feedback_round_max_single_iter = reorganize_coverages(all_data)
                    # print(feedback_round_max_single_iter)
                    for k, round_cov in enumerate(our_approach_data_iter):
                        try: 
                            our_approach_data[k].extend(round_cov)
                        except:
                            our_approach_data.append(round_cov)

                    if feedback_round_max_single_iter > feedback_round_max:
                        feedback_round_max = feedback_round_max_single_iter

        # for the plot
        title = "Coverage Comparison between Testora and Our Approach"
        result_pdf = join(results_folder, "table_and_plots", f"Comparison_round_based_deviation_{prompt_versions[1]}_iter{iterations}.pdf") 
        plot_coverages_violin_deviation([baseline_data[0]], our_approach_data, feedback_round_max, iterations, title, result_pdf)


if __name__=="__main__":
    main()


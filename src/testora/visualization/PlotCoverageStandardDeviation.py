from os.path import join
from matplotlib import pyplot as plt
import numpy as np
from local.PlotCoverageComparisonRoundBased import reorganize_coverages
from testora.visualization.CoverageComparison import CoverageComparison
from matplotlib import gridspec
import os

    
def plot_coverages_violin_deviation(coverages_pr_level, all_prs, title, result_pdf):
    cleaned_data = [
        [float(cov[0].strip('%')) for cov in pr_level_rates]
        for pr_level_rates in coverages_pr_level
    ]

    # Compute standard deviation for each group
    stds = [np.std(group) for group in cleaned_data]
    means = [np.mean(group) for group in cleaned_data]
    x = np.arange(1, len(stds) + 1)

    # Plot standard deviation as error bars
    fig = plt.figure(figsize=(24, 8))
    gs = gridspec.GridSpec(2, 1, height_ratios=[4, 1])

    # Main plot
    ax_plot = fig.add_subplot(gs[0])
    ax_plot.errorbar(x, means, yerr=stds, fmt='o', capsize=5, color='orange', label='Std Dev')
    ax_plot.plot(x, means, color='blue', linestyle='--', marker='x', label='Mean')
    ax_plot.set_title(title + ' (Std Dev)')
    ax_plot.set_xlabel('Test Generation Rounds')
    ax_plot.set_ylabel('Coverage (%)')
    ax_plot.grid(True)
    ax_plot.legend()
    labels = [str(i+1) for i in range(len(stds))]
    ax_plot.set_xticks(x)
    ax_plot.set_xticklabels(labels)

    # Table subplot
    ax_table = fig.add_subplot(gs[1])
    ax_table.axis('off')  # Hide axes

    # Prepare max/min values for table
    max_vals = [f"{np.max(group):.2f}%" for group in cleaned_data]
    min_vals = [f"{np.min(group):.2f}%" for group in cleaned_data]

    # Create table data
    cell_text = [max_vals, min_vals]
    row_labels = ['Max', 'Min']
    # col_labels = [str(i+1) for i in range(len(groups))]

    table = ax_table.table(
        cellText=cell_text,
        rowLabels=row_labels,
        colLabels=all_prs,
        loc='center',
        cellLoc='center'
    )
    table.auto_set_font_size(False)
    table.set_fontsize(10)  # Bigger font size

    plt.tight_layout()
    plt.savefig(result_pdf)
    plt.close()

    
def main():
    iterations = 5
    config_versions = [
        # [1, 0, 1, False]
        [5, 8, 8, True]
    ]
    
    for config in config_versions:
        version_id = '_'.join(map(str, config))
        target_projects = ["marshmallow", "pandas", "scipy", "keras"]

        coverages_pr_level = [[] for _ in range(40)]  # 10 PRs, each will have 5 runs
        all_prs = []

        results_folder = join("data", "results")
        pr_idx = 0
        for project in target_projects:
            pr_file = join("data", "meta", "pr_nums", f"{project}_PRs_subset10.txt")
            with open(pr_file, "r") as f:
                prs = f.readlines()
            pr_list = [int(pr) for pr in prs]
            all_prs.extend(pr_list)

            for pr in pr_list:
                pr_runs = []
                for iter in range(iterations):
                    log_folder = join(results_folder, f"iter_{iter}", f"log_{version_id}", project)
                    log_file = None
                    for fname in os.listdir(log_folder):
                        if str(pr) in fname:
                            log_file = join(log_folder, fname)
                            break
                    if log_file is None:
                        print(f"Iteration {iter}: No log file found for PR {pr} in {log_folder}")
                        pr_runs.append("0.00%")  # If missing, fill with zero
                    else:
                        init = CoverageComparison(log_folder, version_id)
                        init.get_single_log_file_coverage_dtg(log_file, project)
                        data_single_pr = init.all_from_cur_version
                        
                        if not data_single_pr:
                            print(pr)
                            pr_runs.append("0.00%")
                        else:
                            coverages_single_pr, _ = reorganize_coverages(data_single_pr, base=True)
                            # Take initial round coverage for this PR/run
                            if not coverages_single_pr:
                                print(f"Iteration {iter}: PR {pr}")
                            pr_runs.append(coverages_single_pr[0] if coverages_single_pr else "0.00%")
                coverages_pr_level[pr_idx] = pr_runs  # Store 5 runs for this PR
                pr_idx += 1

        # Plot standard deviation for each PR
        title = "Coverage Standard Deviation Across 5 Repetitions per PR"
        result_pdf = join(results_folder, "table_and_plots", f"Coverage_stddev_per_pr_all.pdf")
        plot_coverages_violin_deviation(coverages_pr_level, all_prs, title, result_pdf)

if __name__=="__main__":
    main()

